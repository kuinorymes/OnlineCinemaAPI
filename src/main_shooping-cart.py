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


