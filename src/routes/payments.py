import os

import stripe
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

from database.models.payments import PaymentModel, PaymentStatusEnum, PaymentItemsModel
from database.session_sqlite import get_sqlite_db
from routes.users import get_current_user
from schemas.payments import (
    PaymentCreate,
    PaymentResponse,
    PaymentHistoryResponse,
)
from services.order_utils import validate_order

router = APIRouter()


@router.post("/payments/", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
        payment_data: PaymentCreate,
        db: AsyncSession = Depends(get_sqlite_db),
        current_user: dict = Depends(get_current_user)
):
    """
    Create a new payment with Stripe
    """
    if not await validate_order(
            db=db,
            order_id=payment_data.order_id,
            user_id=current_user["id"],
            payment_amount=Decimal(str(payment_data.amount)),
            payment_items=payment_data.payment_items
        ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid order or order does not belong to user"
        )

    try:
        payment_intent = stripe.PaymentIntent.create(
            amount=int(payment_data.amount * 100),
            currency="usd",
            payment_method=payment_data.payment_method_id,
            confirmation_method="manual",
            confirm=True,
            metadata={
                "user_id": str(current_user["id"]),
                "order_id": str(payment_data.order_id)
            }
        )

        if payment_intent.status == "succeeded":
            db_payment = PaymentModel(
                user_id=current_user["id"],
                order_id=payment_data.order_id,
                status=PaymentStatusEnum.SUCCESSFUL,
                amount=payment_data.amount,
                external_payment_id=payment_intent.id
            )
            db.add(db_payment)
            await db.commit()
            await db.refresh(db_payment)

            for item in payment_data.payment_items:
                db_item = PaymentItemsModel(
                    payment_id=db_payment.id,
                    order_item_id=item.order_item_id,
                    price_at_payment=item.price_at_payment
                )
                db.add(db_item)

            await db.commit()

            # TODO: Send confirmation email

            return db_payment

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment failed: "
                   f"{payment_intent.last_payment_error.message
                   if payment_intent.last_payment_error
                   else 'Unknown error'}"
        )

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the payment"
        )


@router.get("/payments/", response_model=List[PaymentHistoryResponse])
async def get_payment_history(
        db: AsyncSession = Depends(get_sqlite_db),
        current_user: dict = Depends(get_current_user),
        status: Optional[PaymentStatusEnum] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
):
    """
    Get payment history for the current user with optional filters
    """
    query = select(PaymentModel).where(PaymentModel.user_id == current_user["id"])

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
            select(PaymentItemsModel)
            .where(PaymentItemsModel.payment_id == payment.id)
        ).all()

        result.append({
            "payment": payment,
            "items": items
        })

    return result


@router.get("/payments/{payment_id}", response_model=PaymentHistoryResponse)
async def get_payment_details(
        payment_id: int,
        db: AsyncSession = Depends(get_sqlite_db),
        current_user: dict = Depends(get_current_user)
):
    """
    Get details of a specific payment
    """
    payment = await db.get(PaymentModel, payment_id)

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )

    if payment.user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this payment"
        )

    items = await db.scalars(
        select(PaymentItemsModel)
        .where(PaymentItemsModel.payment_id == payment_id)
    ).all()

    return {
        "payment": payment,
        "items": items
    }


@router.post("/payments/webhook/")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_sqlite_db)):
    """
    Handle Stripe webhook events
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    endpoint_secret = os.getenv("STRIPE_WEBHOOK_SECRET")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except stripe.error.SignatureVerificationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        payment = await db.scalar(
            select(PaymentModel)
            .where(PaymentModel.external_payment_id == payment_intent["id"])
        )

        if payment:
            payment.status = PaymentStatusEnum.SUCCESSFUL
            await db.commit()

    elif event["type"] == "payment_intent.payment_failed":
        payment_intent = event["data"]["object"]
        payment = await db.scalar(
            select(PaymentModel)
            .where(PaymentModel.external_payment_id == payment_intent["id"])
        )

        if payment:
            payment.status = PaymentStatusEnum.CANCELED
            await db.commit()

    elif event["type"] == "charge.refunded":
        charge = event["data"]["object"]
        payment = await db.scalar(
            select(PaymentModel)
            .where(PaymentModel.external_payment_id == charge["payment_intent"])
        )

        if payment:
            payment.status = PaymentStatusEnum.REFUNDED
            await db.commit()

    return {"status": "success"}


# Admin endpoints
@router.get("/admin/payments/", response_model=List[PaymentHistoryResponse])
async def admin_get_payments(
        db: AsyncSession = Depends(get_sqlite_db),
        user_id: Optional[int] = None,
        status: Optional[PaymentStatusEnum] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
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
            select(PaymentItemsModel)
            .where(PaymentItemsModel.payment_id == payment.id)
        ).all()

        result.append({
            "payment": payment,
            "items": items
        })

    return result
