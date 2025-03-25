from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models.movies import MovieModel as Movie
from database.models.orders import (
    OrderModel as Order,
    OrderItemModel as OrderItem,
    OrderStatusEnum,
)
from database.session_sqlite import get_sqlite_db as get_db
from schemas.orders import (
    OrderResponseSchema,
    OrderCreateSchema,
    OrderListResponseSchema,
)
from routes.users import get_current_user

router = APIRouter()


@router.post(
    "/", response_model=OrderResponseSchema, status_code=status.HTTP_201_CREATED
)
async def create_order(
    order_data: OrderCreateSchema,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    order_items = []
    total_amount = Decimal(0)

    movie_ids = [item.movie_id for item in order_data.items]

    result = await db.execute(select(Movie).where(Movie.id.in_(movie_ids)))
    movies = result.scalars().all()

    if len(movies) != len(movie_ids):
        missing_ids = set(movie_ids) - {movie.id for movie in movies}
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movies with ids: {missing_ids} was not found",
        )

    for item in order_data.items:
        movie = next((movie for movie in movies if movie.id == item.movie_id), None)
        if not movie:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Movie with id: {item.movie_id} was not found",
            )
        order_item = OrderItem(movie_id=movie.id, price_at_order=movie.price)
        order_items.append(order_item)
        total_amount += movie.price

    if not order_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order cannot be created without any items in the cart.",
        )

    new_order = Order(
        user_id=current_user.id,
        total_amount=total_amount,
        status=OrderStatusEnum.PENDING,
        order_items=order_items,
    )

    try:
        db.add(new_order)
        await db.commit()
        await db.refresh(new_order)
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Something went wrong",
        ) from e

    return new_order


@router.get("/", response_model=OrderListResponseSchema)
async def get_user_orders(
    db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)
):
    result = await db.execute(select(Order).where(Order.user_id == current_user.id))
    orders = result.scalars().all()
    return OrderListResponseSchema(orders=orders)


@router.get("/{order_id}", response_model=OrderResponseSchema)
async def get_order_by_id(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.user_id == current_user.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with id: {order_id} was not found",
        )
    return order


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_order(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(
        select(Order).where(Order.id == order_id, Order.user_id == current_user.id)
    )
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order with id: {order_id} was not found",
        )
    if order.status != OrderStatusEnum.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only pending orders can be cancelled",
        )

    order.status = OrderStatusEnum.CANCELED
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel the order",
        ) from e

    return {"detail": "Order canceled successfully"}


@router.get("/admin/", response_model=OrderListResponseSchema)
async def get_all_orders(
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.group.name.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You are not an administrator"
        )

    query = select(Order).options(
        selectinload(Order.user), selectinload(Order.order_items)
    )
    if status_filter:
        query = query.where(Order.status == status_filter)
    result = await db.execute(query)
    orders = result.scalars().all()
    return OrderListResponseSchema(orders=orders)


@router.get("/admin/{order_id}", response_model=OrderResponseSchema)
async def get_order_details_admin(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if current_user.group.name.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You are not an administrator"
        )
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order does not exist"
        )

    return order
