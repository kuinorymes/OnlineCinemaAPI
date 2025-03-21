import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Integer, DateTime, String, DECIMAL, ForeignKey, func
from sqlalchemy.orm import mapped_column, Mapped, relationship
from sqlalchemy import Enum as SQLAlchemyEnum

from database.models.base import Base


class PaymentStatusEnum(str, Enum):
    PENDING = "Pending"
    PAID = "Paid"
    SUCCESSFUL = "Successful"
    CANCELED = "Canceled"
    REFUNDED = "Refunded"
    PARTIALLY_REFUNDED = "Partially Refunded"


class PaymentModel(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, auto_increment=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    status: Mapped[PaymentStatusEnum] = mapped_column(SQLAlchemyEnum(PaymentStatusEnum), nullable=False)
    amount: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)
    external_payment_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    user: Mapped["UserModel"] = relationship(back_populates="payments")
    order: Mapped["OrderModel"] = relationship(back_populates="payments")
    payment_items: Mapped["PaymentItemsModel"] = relationship(back_populates="payment")

    def __repr__(self) -> str:
        return (
            f"<PaymentModel(id={self.id}, user_id={self.user_id}, order_id={self.order_id}, "
            f"amount={self.amount}, status='{self.status}', created_at='{self.created_at}')>"
        )


class PaymentItemsModel(Base):
    __tablename__ = "payment_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, auto_increment=True)
    payment_id: Mapped[int] = mapped_column(ForeignKey("payments.id"), nullable=False)
    order_item_id: Mapped[int] = mapped_column(ForeignKey("order_items.id"), nullable=False)
    price_at_payment: Mapped[float] = mapped_column(DECIMAL(10, 2), nullable=False)

    payment: Mapped["PaymentModel"] = relationship(back_populates="payment_items")
    order_item: Mapped["OrderItemModel"] = relationship(back_populates="payment_items")

    def __repr__(self) -> str:
        return (
            f"<PaymentItemsModel(id={self.id}, payment_id={self.payment_id}, "
            f"order_item_id={self.order_item_id}, price_at_payment={self.price_at_payment})>"
        )
