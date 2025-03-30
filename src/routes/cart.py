import traceback

from fastapi import FastAPI, HTTPException, Depends, status, APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload, joinedload

from database.models.users import UserModel as User
from database.models.shopping_cart import CartModel as Cart, CartItem
from database.models.movies import MovieModel as Movie
from security.permissions import is_admin

# from database.session_sqlite import get_sqlite_db
from database.session_postgresql import get_postgres_db
from routes.users import get_current_user

router = APIRouter()


@router.get("/admin/users/{user_id}/cart", status_code=status.HTTP_200_OK)
async def admin_view_user_cart(
    user_id: int,
    db: AsyncSession = Depends(get_postgres_db),
    current_user_admin=Depends(is_admin),
) -> dict:

    stmt = (
        select(Cart)
        .where(Cart.user_id == user_id)
        .options(selectinload(Cart.items).selectinload(CartItem.movie))
    )
    result = await db.execute(stmt)
    cart = result.scalars().all()

    if not cart:
        return {"items": []}

    items = []
    for item in cart.items:
        movie = item.movie
        items.append(
            {
                "cart_item_id": item.id,
                "movie_id": movie.id,
                "title": movie.title,
                "price": float(movie.price),
            }
        )
    return {"items": items}


@router.post("/cart/items", status_code=status.HTTP_201_CREATED)
async def add_item_to_cart(
    movie_id: int,
    db: AsyncSession = Depends(get_postgres_db),
    current_user=Depends(get_current_user),
):
    result = await db.execute(select(Movie).filter(Movie.id == movie_id))
    movie = result.scalars().first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")

    result = await db.execute(select(Cart).filter(Cart.user_id == current_user.id))
    cart = result.scalars().first()
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.add(cart)
        await db.commit()
        await db.refresh(cart)

    result = await db.execute(
        select(CartItem).filter(
            CartItem.cart_id == cart.id, CartItem.movie_id == movie_id
        )
    )
    exists = result.scalars().first()
    if exists:
        raise HTTPException(status_code=400, detail="Movie already in cart.")

    cart_item = CartItem(cart_id=cart.id, movie_id=movie_id)
    db.add(cart_item)
    await db.commit()
    await db.refresh(cart_item)
    return {"detail": "Movie added to cart", "cart_item_id": cart_item.id}


@router.delete("/cart/items/{item_id}", status_code=status.HTTP_200_OK)
async def remove_item_from_cart(
    item_id: int,
    db: AsyncSession = Depends(get_postgres_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    result = await db.execute(select(Cart).filter(Cart.user_id == current_user.id))
    cart = result.scalars().first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found.")

    result = await db.execute(
        select(CartItem).filter(CartItem.id == item_id, CartItem.cart_id == cart.id)
    )
    cart_item = result.scalars().first()
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found.")

    await db.delete(cart_item)
    await db.commit()
    return {"detail": "Item removed from cart"}


@router.get("/cart", status_code=status.HTTP_200_OK)
async def view_cart(
    db: AsyncSession = Depends(get_postgres_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    stmt = (
        select(Cart)
        .options(selectinload(Cart.items).selectinload(CartItem.movie))
        .where(Cart.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    cart = result.scalars().first()
    if not cart:
        return {"items": []}

    items = []
    for item in cart.items:
        movie = item.movie
        items.append(
            {
                "cart_item_id": item.id,
                "movie_id": movie.id,
                "name": movie.name,
                "price": float(movie.price),
            }
        )
    return {"items": items}


@router.delete("/cart", status_code=status.HTTP_200_OK)
async def clear_cart(
    db: AsyncSession = Depends(get_postgres_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    stmt = (
        select(Cart)
        .options(selectinload(Cart.items).selectinload(CartItem.movie))
        .where(Cart.user_id == current_user.id)
    )
    result = await db.execute(stmt)
    cart = result.scalars().first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found.")

    for item in cart.items:
        await db.delete(item)
    await db.commit()
    return {"detail": "Cart cleared"}
