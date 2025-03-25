from fastapi import FastAPI, HTTPException, Depends, status
from sqlalchemy.orm import Session
from database import SessionLocal, engine # эти названия нужно подстроить
from src.database.models import models # и эти тоже


models.Base.metadata.create_all(bind=engine)
app = FastAPI()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(db: Session = Depends(get_db)) -> models.User:
    user = db.query(models.User).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@app.post("/cart/items", status_code=status.HTTP_201_CREATED)
def add_item_to_cart(
    movie_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
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
        .filter(models.CartItem.cart_id == cart.id, models.CartItem.movie_id == movie_id)
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
    current_user: models.User = Depends(get_current_user)
):
    cart = db.query(models.Cart).filter(models.Cart.user_id == current_user.id).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found.")

    cart_item = db.query(models.CartItem).filter(
        models.CartItem.id == item_id, models.CartItem.cart_id == cart.id
    ).first()
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found.")

    db.delete(cart_item)
    db.commit()
    return {"detail": "Item removed from cart"}


@app.get("/cart", status_code=status.HTTP_200_OK)
def view_cart(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    cart = db.query(models.Cart).filter(models.Cart.user_id == current_user.id).first()
    if not cart:
        return {"items": []}

    items = []
    for item in cart.items:
        movie = item.movie
        items.append({
            "cart_item_id": item.id,
            "movie_id": movie.id,
            "title": movie.title,
            "price": float(movie.price),
        })
    return {"items": items}


@app.delete("/cart", status_code=status.HTTP_200_OK)
def clear_cart(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    cart = db.query(models.Cart).filter(models.Cart.user_id == current_user.id).first()
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found.")

    for item in cart.items:
        db.delete(item)
    db.commit()
    return {"detail": "Cart cleared"}
