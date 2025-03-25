from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from database.models.payments import PaymentModel, PaymentStatusEnum, PaymentItemsModel
from schemas.payments import PaymentItemCreate


async def save_payment_to_db(
        db: AsyncSession,
        order_id: int,
        total_amount: float,
        checkout_session_id: str,
        user_id: int
):
    db_payment = PaymentModel(
        user_id=user_id,
        order_id=order_id,
        status=PaymentStatusEnum.PENDING,
        amount=total_amount,
        external_payment_id=checkout_session_id
    )
    db.add(db_payment)
    await db.commit()
    return db_payment


async def save_payment_items_to_db(
        db: AsyncSession,
        payment_id: int,
        payment_items: List[PaymentItemCreate]
):
    """
    Saves the payment elements to the database.
    """
    for item in payment_items:
        db_payment_item = PaymentItemsModel(
            payment_id=payment_id,
            order_item_id=item.order_item_id,
            price_at_payment=item.price_at_payment
        )
        db.add(db_payment_item)
    await db.commit()
