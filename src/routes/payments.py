import stripe
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import datetime
from fastapi.responses import JSONResponse

from database.models.payments import PaymentModel, PaymentStatusEnum, PaymentItemsModel
from database.models.users import UserModel
from database.session_sqlite import get_sqlite_db
from routes.users import get_current_user
from schemas.payments import (
    PaymentCreate,
    PaymentHistoryResponse,
    PaymentResponse,
    PaymentItemResponse,
)
from services.db_utils import save_payment_to_db, save_payment_items_to_db
from services.stripe_utils import create_checkout_session

router = APIRouter()

stripe.api_key = "sk_test_51QxBPLKX7EO9LjLpMK58n2sEjFFAqE11RuyUCFgTIvLSS7uH4Ho4jLmeNmL224hallbOWXxih3v7XKIbGkp4TMhw00oFPR3ImN"
endpoint_secret = (
    "whsec_f61d76fd5229d4fc777431940843508ab66afec305fb243e17b50ed55cb17f3a"
)

YOUR_DOMAIN = "http://127.0.0.1:8000/api/v1/payments"


@router.get("/success")
async def success_page(session_id: str):
    return {"message": "Payment was successful!", "session_id": session_id}


@router.get("/cancel")
async def cancel_page():
    return {"message": "Payment has been canceled. Try again."}


@router.post("/create_payment", response_model=dict, status_code=201)
async def create_payment(
    background_tasks: BackgroundTasks,
    payment_data: PaymentCreate,
    db: AsyncSession = Depends(get_sqlite_db),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Easily create a Stripe payment session and return a payment link.
    """
    try:
        total_amount = sum(item.price_at_payment for item in payment_data.payment_items)

        payment_url = create_checkout_session(
            payment_data.order_id, total_amount, current_user.id
        )

        db_payment = await save_payment_to_db(
            db, payment_data.order_id, total_amount, payment_url, current_user.id
        )

        await save_payment_items_to_db(db, db_payment.id, payment_data.payment_items)

        return {"payment_link": payment_url}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error when creating a payment: {str(e)}"
        )


@router.get("/", response_model=List[PaymentHistoryResponse])
async def get_payment_history(
    db: AsyncSession = Depends(get_sqlite_db),
    current_user: UserModel = Depends(get_current_user),
    status: Optional[PaymentStatusEnum] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    """
    Get payment history for the current user with optional filters.
    """
    query = select(PaymentModel).where(PaymentModel.user_id == current_user.id)

    if status:
        query = query.where(PaymentModel.status == status)

    if start_date:
        query = query.where(PaymentModel.created_at >= start_date)

    if end_date:
        query = query.where(PaymentModel.created_at <= end_date)

    result = await db.execute(query.order_by(PaymentModel.created_at.desc()))
    payments = result.scalars().all()

    payment_data = []
    for payment in payments:
        items_query = select(PaymentItemsModel).where(
            PaymentItemsModel.payment_id == payment.id
        )
        items_result = await db.execute(items_query)
        payment_items = items_result.scalars().all()

        payment_response = PaymentResponse(
            id=payment.id,
            user_id=payment.user_id,
            order_id=payment.order_id,
            created_at=payment.created_at,
            status=payment.status,
            amount=payment.amount,
            external_payment_id=payment.external_payment_id,
            items=[
                PaymentItemResponse(
                    id=item.id,
                    payment_id=item.payment_id,
                    order_item_id=item.order_item_id,
                    price_at_payment=item.price_at_payment,
                )
                for item in payment_items
            ],
        )

        payment_data.append(
            PaymentHistoryResponse(
                payment=payment_response, items=payment_response.items
            )
        )

    return payment_data


@router.get("/{payment_id}", response_model=PaymentHistoryResponse)
async def get_payment_details(
    payment_id: int,
    db: AsyncSession = Depends(get_sqlite_db),
    current_user: UserModel = Depends(get_current_user),
):
    """
    Get details of a specific payment
    """
    payment = await db.get(PaymentModel, payment_id)

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found"
        )

    if payment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this payment",
        )

    result = await db.execute(
        select(PaymentItemsModel).where(PaymentItemsModel.payment_id == payment_id)
    )
    items = result.scalars().all()

    payment_items = [
        PaymentItemResponse(
            id=item.id,
            payment_id=item.payment_id,
            order_item_id=item.order_item_id,
            price_at_payment=item.price_at_payment,
        )
        for item in items
    ]

    return PaymentHistoryResponse(
        payment=PaymentResponse(
            id=payment.id,
            user_id=payment.user_id,
            order_id=payment.order_id,
            created_at=payment.created_at,
            status=payment.status,
            amount=payment.amount,
            external_payment_id=payment.external_payment_id,
            items=payment_items,
        ),
        items=payment_items,
    )


@router.post("/webhook/")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_sqlite_db)):
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event["type"]
    session = event["data"]["object"]

    if event_type == "checkout.session.completed":
        payment_intent_id = session.get("payment_intent")
        payment_id = session.get("id")
        amount_received = session.get("amount_received") / 100

        order_id = session.get("client_reference_id")
        payment_method_id = session.get("payment_method")

        new_payment = PaymentModel(
            user_id=session["customer"],
            order_id=order_id,
            amount=amount_received,
            external_payment_id=payment_id,
            status=PaymentStatusEnum.SUCCESSFUL,
        )

        db.add(new_payment)
        await db.commit()

        for item in session["line_items"]["data"]:
            order_item_id = item["price"]["product"]
            price_at_payment = item["amount_total"] / 100

            new_payment_item = PaymentItemsModel(
                payment_id=new_payment.id,
                order_item_id=order_item_id,
                price_at_payment=price_at_payment,
            )
            db.add(new_payment_item)

        await db.commit()

        return JSONResponse(
            status_code=200, content={"message": "Webhook received successfully"}
        )
    else:
        return JSONResponse(
            status_code=400, content={"message": "Unhandled event type"}
        )


# Admin endpoints
@router.get("/admin-payments/", response_model=List[PaymentHistoryResponse])
async def admin_get_payments(
    db: AsyncSession = Depends(get_sqlite_db),
    user_id: Optional[int] = None,
    status: Optional[PaymentStatusEnum] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    """
    Admin endpoint to get all payments with filters
    """
    # TODO admin permissions here

    query = select(PaymentModel)

    if user_id:
        query = query.where(PaymentModel.user_id == user_id)

    if status:
        query = query.where(PaymentModel.status == status)

    if start_date:
        query = query.where(PaymentModel.created_at >= start_date)

    if end_date:
        query = query.where(PaymentModel.created_at <= end_date)

    payments = await db.scalars(query.order_by(PaymentModel.created_at.desc())).all()

    result = []
    for payment in payments:
        items = await db.scalars(
            select(PaymentItemsModel).where(PaymentItemsModel.payment_id == payment.id)
        ).all()

        result.append({"payment": payment, "items": items})

    return result
