from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal
from typing import List

from database.models.orders import OrderModel, OrderStatusEnum, OrderItemModel
from schemas.payments import PaymentItemCreate


async def validate_order_for_payment(
        db: AsyncSession,
        order_id: int,
        user_id: int,
        payment_items: List[PaymentItemCreate]
) -> int:
    """
    Validate order before payment and return total amount
    """
    order = await db.scalar(
        select(OrderModel)
        .where(OrderModel.id == order_id)
        .where(OrderModel.user_id == user_id)
    )
    if not order:
        raise ValueError("Order not found or doesn't belong to user")

    if order.status != OrderStatusEnum.PENDING:
        raise ValueError(f"Order must be {OrderStatusEnum.PENDING.value}")

    order_item_ids = {item.order_item_id for item in payment_items}
    db_items = await db.scalars(
        select(OrderItemModel)
        .where(OrderItemModel.id.in_(order_item_ids))
        .where(OrderItemModel.order_id == order_id)
    )

    if len(db_items.all()) != len(order_item_ids):
        raise ValueError("Some items don't belong to this order")

    return sum(Decimal(str(item.price_at_payment)) for item in payment_items)
