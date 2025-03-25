from datetime import datetime
from typing import List

from sqlalchemy import (
    Integer,
    ForeignKey,
    DateTime,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from src.database.models.base import Base


class CartModel(Base):
    __tablename__ = "carts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"), unique=True, nullable=False
    )

    user: Mapped["UserModel"] = relationship(  # noqa: F821
        "User", back_populates="cart"
    )
    items: Mapped[List["CartItem"]] = relationship(
        "CartItem", back_populates="cart", cascade="all, delete-orphan"
    )


class CartItem(Base):
    __tablename__ = "cart_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    cart_id: Mapped[int] = mapped_column(ForeignKey("carts.id"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    cart: Mapped["CartModel"] = relationship("Cart", back_populates="items")
    movie: Mapped["MovieModel"] = relationship("Movie")  # noqa: F821

    __table_args__ = (UniqueConstraint("cart_id", "movie_id", name="_cart_movie_uc"),)
