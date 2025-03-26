import logging
import os
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

import stripe
from dotenv import load_dotenv
from sqlalchemy import select, update, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from exceptions.payment_exceptions import (
    OrderNotFoundError,
    InvalidOrderStatusError,
    PaymentCreationError,
    OrderAlreadyPaidError,
)
from schemas.payments import PaymentDetailResponse, PaymentItemResponse
from services.stripe_utils import StripeService
from database.models.orders import OrderModel, OrderItemModel, OrderStatusEnum
from database.models.payments import PaymentModel, PaymentItemsModel, PaymentStatusEnum

logger = logging.getLogger(__name__)

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


class PaymentService:
    def __init__(self, db: AsyncSession, stripe_service: StripeService):
        self.db = db
        self.stripe_service = stripe_service

    @staticmethod
    def _normalize_datetime(date_value) -> datetime:
        """Converts any date format to datetime"""
        if isinstance(date_value, datetime):
            return date_value
        if isinstance(date_value, (int, float)):
            if date_value > 1e12:
                return datetime.fromtimestamp(date_value / 1000)
            return datetime.fromtimestamp(date_value)
        if isinstance(date_value, str):
            try:
                return datetime.fromisoformat(date_value.replace("Z", "+00:00"))
            except ValueError:
                for fmt in [
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d %H:%M:%S.%f",
                    "%d.%m.%Y %H:%M:%S",
                    "%m/%d/%Y %H:%M:%S",
                ]:
                    try:
                        return datetime.strptime(date_value, fmt)
                    except ValueError:
                        continue
        logger.warning(f"Could not parse date: {date_value}, using current time")
        return datetime.utcnow()

    async def _validate_order(self, order_id: int, user_id: int) -> OrderModel:
        """Check that the order exists and belongs to the user"""
        stmt = text(
            """
            SELECT id, user_id, status, total_amount, created_at
            FROM orders
            WHERE id = :order_id AND user_id = :user_id
        """
        )

        result = await self.db.execute(stmt, {"order_id": order_id, "user_id": user_id})
        order_data = result.mappings().first()

        if not order_data:
            raise OrderNotFoundError(f"Order {order_id} not found")

        created_at = self._normalize_datetime(order_data["created_at"])

        db_status = order_data["status"].lower() if order_data["status"] else None

        order = OrderModel(
            id=order_data["id"],
            user_id=order_data["user_id"],
            status=db_status,
            total_amount=order_data["total_amount"],
            created_at=created_at,
        )

        if order.status != OrderStatusEnum.PENDING:
            raise InvalidOrderStatusError(
                f"Order {order_id} has invalid status: {order.status}. "
                f"Expected: {OrderStatusEnum.PENDING.value}"
            )

        return order

    async def create_payment_record(
        self, order_id: int, user_id: int, amount: Decimal, external_id: str
    ) -> dict:
        """Creates a payment record with secure date handling"""
        payment = PaymentModel(
            user_id=user_id,
            order_id=order_id,
            status=PaymentStatusEnum.PENDING,
            amount=amount,
            external_payment_id=external_id,
            created_at=datetime.utcnow(),
        )

        self.db.add(payment)
        await self.db.commit()
        await self.db.refresh(payment)

        return {
            "id": payment.id,
            "user_id": payment.user_id,
            "order_id": payment.order_id,
            "created_at": payment.created_at,
            "status": payment.status.value,
            "amount": float(payment.amount),
            "external_payment_id": payment.external_payment_id,
        }

    async def _create_payment_items(self, payment_id: int, order_id: int) -> None:
        """Create payment items from order items"""
        stmt = select(OrderItemModel).where(OrderItemModel.order_id == order_id)
        result = await self.db.execute(stmt)
        order_items = result.scalars().all()

        if not order_items:
            logger.warning(f"No order items found for order {order_id}")
            return

        payment_items = [
            PaymentItemsModel(
                payment_id=payment_id,
                order_item_id=item.id,
                price_at_payment=item.price_at_order,
            )
            for item in order_items
        ]

        self.db.add_all(payment_items)
        await self.db.commit()
        logger.info(f"Created {len(payment_items)} payment items")

    async def create_payment_session(
        self, order_id: int, user_id: int, success_url: str, cancel_url: str
    ) -> dict:
        """Create a Stripe checkout session and payment record"""
        try:
            if await self.check_existing_payment(order_id):
                raise OrderAlreadyPaidError(f"Order {order_id} is already paid")

            order = await self._validate_order(order_id, user_id)

            session = await self.stripe_service.create_checkout_session(
                amount=order.total_amount,
                order_id=order_id,
                user_id=user_id,
                success_url=success_url,
                cancel_url=cancel_url,
                description=f"Payment for order #{order_id}",
            )

            payment_data = await self.create_payment_record(
                order_id=order_id,
                user_id=user_id,
                amount=order.total_amount,
                external_id=session["id"],
            )

            await self._create_payment_items(payment_data["id"], order_id)

            return {**payment_data, "payment_url": session["url"]}

        except OrderAlreadyPaidError as e:
            logger.warning(str(e))
            raise
        except Exception as e:
            logger.error(f"Payment creation failed: {str(e)}", exc_info=True)
            await self.db.rollback()
            raise PaymentCreationError(f"Payment creation failed: {str(e)}")

    async def verify_stripe_payment(self, session_id: str) -> bool:
        """Verify payment status in Stripe."""
        try:
            session = await self.stripe_service.retrieve_session(session_id)
            return session.payment_status == "paid"
        except Exception as e:
            logger.error(f"Stripe verification failed: {str(e)}")
            return False

    async def process_successful_payment(self, session_id: str) -> bool:
        """Update payment and order status after successful payment."""
        async with self.db.begin():
            result = await self.db.execute(
                update(PaymentModel)
                .where(PaymentModel.external_payment_id == session_id)
                .values(status=PaymentStatusEnum.COMPLETED)
                .returning(PaymentModel.id, PaymentModel.order_id)
            )
            payment_data = result.first()

            if not payment_data:
                logger.error(f"Payment not found for session: {session_id}")
                return False

            payment_id, order_id = payment_data

            await self.db.execute(
                update(OrderModel)
                .where(OrderModel.id == order_id)
                .values(status=OrderStatusEnum.PAID)
            )

            logger.info(f"Processed payment {payment_id} for order {order_id}")
            return True

    async def get_user_payments(
        self, user_id: int, limit: int = 10, offset: int = 0
    ) -> List[PaymentModel]:
        """Get paginated list of user payments."""
        result = await self.db.execute(
            select(PaymentModel)
            .where(PaymentModel.user_id == user_id)
            .order_by(PaymentModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def get_total_payments_count(self, user_id: int) -> int:
        """Get total count of user payments."""
        result = await self.db.execute(
            select(func.count(PaymentModel.id)).where(PaymentModel.user_id == user_id)
        )
        return result.scalar_one()

    async def get_payment_details(
        self,
        payment_id: Optional[int] = None,
        user_id: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> Optional[PaymentDetailResponse]:
        """Get payment details with items."""
        stmt = select(PaymentModel).options(selectinload(PaymentModel.payment_items))

        if payment_id:
            stmt = stmt.where(PaymentModel.id == payment_id)
        elif session_id:
            stmt = stmt.where(PaymentModel.external_payment_id == session_id)
        else:
            return None

        result = await self.db.execute(stmt)
        payment = result.scalars().first()

        if not payment:
            return None

        return PaymentDetailResponse(
            id=payment.id,
            user_id=payment.user_id,
            order_id=payment.order_id,
            created_at=payment.created_at,
            status=payment.status,
            amount=float(payment.amount),
            external_payment_id=payment.external_payment_id,
            payment_items=[
                PaymentItemResponse(
                    id=item.id,
                    order_item_id=item.order_item_id,
                    price_at_payment=float(item.price_at_payment),
                )
                for item in payment.payment_items
            ],
        )

    async def check_existing_payment(self, order_id: int) -> bool:
        """
        Check if order already has a completed payment
        Returns True if paid payment exists, False otherwise
        """
        stmt = (
            select(PaymentModel)
            .where(
                PaymentModel.order_id == order_id,
                PaymentModel.status == PaymentStatusEnum.COMPLETED,
            )
            .limit(1)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first() is not None

    async def get_payment_with_lock(self, session_id: str) -> Optional[PaymentModel]:
        """
        Get payment with FOR UPDATE lock to prevent race conditions
        """
        try:
            stmt = (
                select(PaymentModel)
                .where(PaymentModel.external_payment_id == session_id)
                .with_for_update()
            )
            result = await self.db.execute(stmt)
            return result.scalars().first()
        except Exception as e:
            logger.error(f"Error getting payment with lock: {str(e)}")
            raise
