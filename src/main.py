from fastapi import FastAPI

app = FastAPI(
    title="Online Cinema",
    description="A digital platform that enables users to choose, watch, "
    "and purchase access to movies and other video content via the internet.",
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


api_version_prefix = "/api/v1"
