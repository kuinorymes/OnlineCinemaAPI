from fastapi import FastAPI

from routes.users import router as users_router
from routes.orders import router as orders_router


app = FastAPI(
    title="Online Cinema",
    description="A digital platform that enables users to choose, watch, "
    "and purchase access to movies and other video content via the internet.",
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


api_version_prefix = "/api/v1"

app.include_router(users_router, tags=["users"], prefix=f"{api_version_prefix}/users")
app.include_router(
    orders_router, tags=["orders"], prefix=f"{api_version_prefix}/orders"
)
