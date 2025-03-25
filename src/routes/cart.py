from fastapi import FastAPI, HTTPException, Depends, status
from sqlalchemy.orm import Session
from src.database import SessionLocal, engine
from src.database.models import models
from src.config.dependencies import is_admin
from src.routes.users import get_current_user, get_db

models.Base.metadata.create_all(bind=engine)
app = FastAPI()


@app.get("/admin/users/{user_id}/cart", status_code=status.HTTP_200_OK)
def admin_view_user_cart(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: models.User = Depends(is_admin),
):

    cart = db.query(models.Cart).filter(models.Cart.user_id == user_id).first()
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
def add_item_to_cart(
    movie_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> models.Item:
    movie = db.query(models.Movie).filter(models.Movie.id == movie_id).first()
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found.")

    cart = db.query(models.Cart).filter(models.Cart.user_id == current_user.id).first()
    if not cart:
        cart = models.Cart(user_id=current_user.id)
        db.add(cart)
        db.commit()
        db.refresh(cart)

    exists = (
        db.query(models.CartItem)
        .filter(
            models.CartItem.cart_id == cart.id, models.CartItem.movie_id == movie_id
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="Movie already in cart.")

    cart_item = models.CartItem(cart_id=cart.id, movie_id=movie_id)
    db.add(cart_item)
    db.commit()
    db.refresh(cart_item)
    return {"detail": "Movie added to cart", "cart_item_id": cart_item.id}


@app.delete("/cart/items/{item_id}", status_code=status.HTTP_200_OK)
def remove_item_from_cart(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> models.Item:
    cart = db.query(models.Cart).filter(models.Cart.user_id == current_user.id).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found.")

    cart_item = (
        db.query(models.CartItem)
        .filter(models.CartItem.id == item_id, models.CartItem.cart_id == cart.id)
        .first()
    )
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found.")

    db.delete(cart_item)
    db.commit()
    return {"detail": "Item removed from cart"}


@app.get("/cart", status_code=status.HTTP_200_OK)
def view_cart(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
) -> models.CartItem:
    cart = db.query(models.Cart).filter(models.Cart.user_id == current_user.id).first()
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
def clear_cart(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
) -> models.CartItem:
    cart = db.query(models.Cart).filter(models.Cart.user_id == current_user.id).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found.")

    for item in cart.items:
        db.delete(item)
    db.commit()
    return {"detail": "Cart cleared"}
