from fastapi import FastAPI

from routes.users import router as users_router
from routes.orders import router as orders_router
from routes.payments import router as payments_router
from routes.cart import router as cart_router
from config.dependencies import get_settings


app = FastAPI(
    title="Online Cinema",
    description="A digital platform that enables users to choose, watch, "
    "and purchase access to movies and other video content via the internet.",
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


settings = get_settings()


api_version_prefix = settings.API_VERSION

app.include_router(users_router, tags=["users"], prefix=f"{api_version_prefix}/users")
app.include_router(
    orders_router, tags=["orders"], prefix=f"{api_version_prefix}/orders"
)
app.include_router(
    payments_router, tags=["payments"], prefix=f"{api_version_prefix}/payments"
)
app.include_router(cart_router, tags=["carts"], prefix=f"{api_version_prefix}/carts")
