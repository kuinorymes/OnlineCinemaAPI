from fastapi import FastAPI, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.database.models import models
from src.config.dependencies import is_admin
from src.database.session_sqlite import get_sqlite_db
from src.routes.users import get_current_user

app = FastAPI()


@app.get("/admin/users/{user_id}/cart", status_code=status.HTTP_200_OK)
async def admin_view_user_cart(
    user_id: int,
    db: AsyncSession = Depends(get_sqlite_db),
    current_admin: models.User = Depends(is_admin),
) -> dict:
    result = await db.execute(
        select(models.Cart).filter(models.Cart.user_id == user_id)
    )
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
                "title": movie.title,
                "price": float(movie.price),
            }
        )
    return {"items": items}


@app.post("/cart/items", status_code=status.HTTP_201_CREATED)
async def add_item_to_cart(
    movie_id: int,
    db: AsyncSession = Depends(get_sqlite_db),
    current_user: models.User = Depends(get_current_user),
):
    result = await db.execute(select(models.Movie).filter(models.Movie.id == movie_id))
    movie = result.scalars().first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")

    result = await db.execute(
        select(models.Cart).filter(models.Cart.user_id == current_user.id)
    )
    cart = result.scalars().first()
    if not cart:
        cart = models.Cart(user_id=current_user.id)
        db.add(cart)
        await db.commit()
        await db.refresh(cart)

    result = await db.execute(
        select(models.CartItem).filter(
            models.CartItem.cart_id == cart.id, models.CartItem.movie_id == movie_id
        )
    )
    exists = result.scalars().first()
    if exists:
        raise HTTPException(status_code=400, detail="Movie already in cart.")

    cart_item = models.CartItem(cart_id=cart.id, movie_id=movie_id)
    db.add(cart_item)
    await db.commit()
    await db.refresh(cart_item)
    return {"detail": "Movie added to cart", "cart_item_id": cart_item.id}


@app.delete("/cart/items/{item_id}", status_code=status.HTTP_200_OK)
async def remove_item_from_cart(
    item_id: int,
    db: AsyncSession = Depends(get_sqlite_db),
    current_user: models.User = Depends(get_current_user),
) -> dict:
    result = await db.execute(
        select(models.Cart).filter(models.Cart.user_id == current_user.id)
    )
    cart = result.scalars().first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found.")

    result = await db.execute(
        select(models.CartItem).filter(
            models.CartItem.id == item_id, models.CartItem.cart_id == cart.id
        )
    )
    cart_item = result.scalars().first()
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found.")

    await db.delete(cart_item)
    await db.commit()
    return {"detail": "Item removed from cart"}


@app.get("/cart", status_code=status.HTTP_200_OK)
async def view_cart(
    db: AsyncSession = Depends(get_sqlite_db),
    current_user: models.User = Depends(get_current_user),
) -> dict:
    result = await db.execute(
        select(models.Cart).filter(models.Cart.user_id == current_user.id)
    )
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
                "title": movie.title,
                "price": float(movie.price),
            }
        )
    return {"items": items}


@app.delete("/cart", status_code=status.HTTP_200_OK)
async def clear_cart(
    db: AsyncSession = Depends(get_sqlite_db),
    current_user: models.User = Depends(get_current_user),
) -> dict:
    result = await db.execute(
        select(models.Cart).filter(models.Cart.user_id == current_user.id)
    )
    cart = result.scalars().first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found.")

    for item in cart.items:
        await db.delete(item)
    await db.commit()
    return {"detail": "Cart cleared"}
