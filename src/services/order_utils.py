from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal
from fastapi import HTTPException, status
from typing import List

from database.models.orders import OrderModel, OrderStatusEnum, OrderItemModel
from schemas.payments import PaymentItemCreate


async def validate_order(
        db: AsyncSession,
        order_id: int,
        user_id: int,
        payment_amount: Decimal,
        payment_items: List[PaymentItemCreate]
) -> bool:
    """
    Validate an order before payment processing.

    Checks:
    1. If the order exists
    2. If the order belongs to the user
    3. If the order is in a payable state (PENDING)
    4. If all payment items belong to the order
    5. If the payment amount matches the sum of payment items
    """
    order_result = await db.execute(
        select(OrderModel)
        .where(OrderModel.id == order_id)
    )
    order = order_result.scalar_one_or_none()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )

    if order.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This order does not belong to you"
        )

    if order.status != OrderStatusEnum.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Order status must be PENDING for payment, current status: {order.status}"
        )

    total_amount = Decimal('0.00')
    order_item_ids = {item.order_item_id for item in payment_items}

    items_result = await db.execute(
        select(OrderItemModel)
        .where(OrderItemModel.id.in_(order_item_ids))
        .where(OrderItemModel.order_id == order_id)
    )
    order_items = items_result.scalars().all()

    if len(order_items) != len(payment_items):
        found_ids = {item.id for item in order_items}
        missing_ids = order_item_ids - found_ids
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Some items don't belong to this order. Missing item IDs: {missing_ids}"
        )

    order_item_map = {item.id: item for item in order_items}

    for payment_item in payment_items:
        order_item = order_item_map[payment_item.order_item_id]

        if Decimal(str(payment_item.price_at_payment)) != order_item.price_at_order:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Price mismatch for item {order_item.id}. "
                       f"Expected {order_item.price_at_order}, got {payment_item.price_at_payment}"
            )

        total_amount += Decimal(str(payment_item.price_at_payment))

    payment_amount_dec = Decimal(str(payment_amount))
    if payment_amount_dec != total_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment amount {payment_amount_dec} doesn't match items total {total_amount}"
        )

    return True
