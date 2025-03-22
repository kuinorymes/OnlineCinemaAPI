import enum
from datetime import datetime
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import ForeignKey, DateTime, func, Numeric, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models.base import Base


class OrderStatusEnum(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    CANCELED = "canceled"


class OrderModel(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[OrderStatusEnum] = mapped_column(
        Enum(OrderStatusEnum), default=OrderStatusEnum.PENDING, nullable=False
    )
    total_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), nullable=False)

    user: Mapped["UserModel"] = relationship(back_populates="orders")  # noqa: F821
    order_items: Mapped[List["OrderItemModel"]] = relationship(
        back_populates="order", cascade="all, delete"
    )
    cart: Mapped["CartModel"] = relationship(  # noqa: F821
        "CartModel", back_populates="orders", cascade="all, delete"
    )
    payments: Mapped[List["PaymentModel"]] = relationship(  # noqa: F821
        "PaymentModel", back_populates="order", cascade="all, delete"
    )


class OrderItemModel(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), nullable=False)
    price_at_order: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped["OrderModel"] = relationship(back_populates="order_items")
    movie: Mapped["MovieModel"] = relationship("MovieModel")  # noqa: F821
