from datetime import datetime
import stripe
import os
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
    Request,
    Query,
    BackgroundTasks,
)
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from fastapi.responses import JSONResponse

from database.models.orders import OrderModel, OrderStatusEnum
from database.models.payments import PaymentModel, PaymentStatusEnum
from database.models.users import UserModel
from database.session_sqlite import get_sqlite_db
from exceptions.payment_exceptions import (
    OrderNotFoundError,
    InvalidOrderStatusError,
    PaymentCreationError,
    OrderAlreadyPaidError,
)
from notifications.tasks import send_payment_confirmation
from routes.users import get_current_user
from schemas.payments import (
    PaymentResponse,
    PaymentCreateRequest,
    PaymentDetailResponse,
    PaymentListResponse,
    PaymentSuccessResponse,
    PaymentCancelResponse,
)

from services.payment_service import PaymentService
from services.perms_utils import user_moderator_or_admin
from services.stripe_utils import StripeService

import logging

router = APIRouter()

endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_API_KEY = os.getenv("STRIPE_SECRET_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

front_url = "http://127.0.0.1:8000/api/v1/payments"


@router.post(
    "/create_payment",
    response_model=PaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment_endpoint(
    payment_data: PaymentCreateRequest,
    db: AsyncSession = Depends(get_sqlite_db),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Create a new payment session for the specified order
    """
    stripe_service = StripeService(STRIPE_API_KEY, endpoint_secret)
    payment_service = PaymentService(db, stripe_service)

    try:
        success_url = f"{front_url}/{payment_data.order_id}/success?session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{front_url}/{payment_data.order_id}/cancel?session_id={{CHECKOUT_SESSION_ID}}"

        result = await payment_service.create_payment_session(
            order_id=payment_data.order_id,
            user_id=current_user.id,
            success_url=success_url,
            cancel_url=cancel_url,
        )

        return PaymentResponse(
            id=result["id"],
            user_id=result["user_id"],
            order_id=result["order_id"],
            created_at=result["created_at"],
            status=result["status"],
            amount=result["amount"],
            external_payment_id=result["external_payment_id"],
            payment_url=result["payment_url"],
        )
    except OrderAlreadyPaidError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except OrderNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidOrderStatusError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PaymentCreationError as e:
        logger.error(f"Payment creation error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
    except Exception as e:
        logger.error(f"Unexpected error in payment creation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/{order_id}/success", response_model=PaymentSuccessResponse)
async def payment_success(
    background_tasks: BackgroundTasks,
    order_id: int,
    session_id: str = Query(..., alias="session_id"),
    db: AsyncSession = Depends(get_sqlite_db),
):
    """
    Endpoint for successful payment callback (no auth required)
    """
    stripe_service = StripeService(STRIPE_API_KEY, endpoint_secret)
    payment_service = PaymentService(db, stripe_service)

    try:
        stripe_session = await stripe_service.retrieve_session(session_id)
        if not stripe_session or stripe_session.get("payment_status") != "paid":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment verification failed",
            )

        payment_result = await _process_payment_in_transaction(
            db=db,
            payment_service=payment_service,
            session_id=session_id,
            order_id=order_id,
        )

        if not payment_result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment processing failed",
            )

        payment, was_already_processed = payment_result

        if stripe_session.get("customer_email"):
            background_tasks.add_task(
                send_payment_confirmation,
                stripe_session["customer_email"],
                order_id,
                float(payment.amount),
            )

        return {
            "status": "success",
            "message": (
                "Payment already processed"
                if was_already_processed
                else "Payment completed successfully"
            ),
            "order_id": order_id,
            "payment_id": payment.id,
            "amount": float(payment.amount),
            "paid_at": (
                payment.created_at.isoformat()
                if was_already_processed
                else datetime.utcnow().isoformat()
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing payment: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Payment processing error"
        )


async def _process_payment_in_transaction(
    db: AsyncSession, payment_service: PaymentService, session_id: str, order_id: int
) -> Optional[tuple[PaymentModel, bool]]:
    """Helper function to handle payment processing in transaction"""
    try:
        async with db.begin_nested():
            payment = await payment_service.get_payment_with_lock(session_id=session_id)
            if not payment:
                logger.error(f"Payment not found for session: {session_id}")
                return None

            if payment.order_id != order_id:
                logger.error(f"Order ID mismatch: {payment.order_id} != {order_id}")
                return None

            if payment.status == PaymentStatusEnum.COMPLETED:
                logger.info(f"Payment {payment.id} already processed")
                return (payment, True)

            payment.status = PaymentStatusEnum.COMPLETED
            payment.updated_at = datetime.utcnow()

            await db.execute(
                update(OrderModel)
                .where(OrderModel.id == order_id)
                .values(status=OrderStatusEnum.PAID)
            )

            await db.commit()
            return (payment, False)

    except Exception as e:
        logger.error(f"Transaction error: {str(e)}", exc_info=True)
        await db.rollback()
        raise


@router.get("/{order_id}/cancel", response_model=PaymentCancelResponse)
async def payment_cancel(
    order_id: int,
    session_id: str = Query(..., alias="session_id"),
    db: AsyncSession = Depends(get_sqlite_db),
):
    """
    Endpoint for canceled payment callback (no auth required)
    """
    stripe_service = StripeService(STRIPE_API_KEY, endpoint_secret)
    payment_service = PaymentService(db, stripe_service)  # noqa: F841

    try:
        stripe_session = await stripe_service.retrieve_session(session_id)
        if not stripe_session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payment session",
            )

        async with db.begin():
            result = await db.execute(
                update(PaymentModel)
                .where(PaymentModel.external_payment_id == session_id)
                .values(status=PaymentStatusEnum.CANCELLED)
                .returning(PaymentModel.id, PaymentModel.order_id)
            )
            payment_data = result.first()

            if not payment_data or payment_data[1] != order_id:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Payment not found or order mismatch",
                )

            return {
                "status": "canceled",
                "message": "Payment was canceled",
                "order_id": order_id,
                "payment_id": payment_data[0],
                "canceled_at": datetime.utcnow().isoformat(),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing canceled payment: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Error canceling payment"
        )


@router.get("/", response_model=PaymentListResponse)
async def get_payments(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_sqlite_db),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Get paginated list of user payments
    """
    try:
        payment_service = PaymentService(
            db, StripeService(STRIPE_API_KEY, endpoint_secret)
        )

        payments = await payment_service.get_user_payments(
            user_id=current_user.id, limit=per_page, offset=(page - 1) * per_page
        )

        total = await payment_service.get_total_payments_count(current_user.id)
        total_pages = (total + per_page - 1) // per_page

        payments_data = [
            PaymentResponse(
                id=payment.id,
                user_id=payment.user_id,
                order_id=payment.order_id,
                created_at=payment.created_at,
                status=payment.status,
                amount=payment.amount,
                external_payment_id=payment.external_payment_id,
                payment_url=getattr(payment, "payment_url", None),
            )
            for payment in payments
        ]

        return PaymentListResponse(
            payments=payments_data,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
        )

    except Exception as e:
        logger.error(f"Error fetching payments: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching payments",
        )


@router.get("/{payment_id}", response_model=PaymentDetailResponse)
async def get_payment_details(
    payment_id: int,
    db: AsyncSession = Depends(get_sqlite_db),
    current_user: UserModel = Depends(get_current_user),
    staff_user: Optional[UserModel] = Depends(user_moderator_or_admin),
):
    """
    Get details of a specific payment
    """
    try:
        payment_service = PaymentService(
            db, StripeService(STRIPE_API_KEY, endpoint_secret)
        )

        user_id = None if staff_user else current_user.id

        payment_data = await payment_service.get_payment_details(
            payment_id=payment_id, user_id=user_id
        )

        if not payment_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found or access denied",
            )

        return payment_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching payment details: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error fetching payment details",
        )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_sqlite_db),
):
    """
    Stripe webhook handler for payment events
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    stripe_service = StripeService(STRIPE_API_KEY, endpoint_secret)
    payment_service = PaymentService(db, stripe_service)

    try:
        event = await stripe_service.construct_webhook_event(payload, sig_header)

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            if session.payment_status == "paid":
                if not await payment_service.process_successful_payment(session.id):
                    return JSONResponse(content={"status": "failed"}, status_code=400)

        return {"status": "success"}

    except Exception as e:
        logger.error(f"Webhook error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
