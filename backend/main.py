
from fastapi import FastAPI

from routers.auth import router as auth_router

app = FastAPI(
    title="CampusCare API",
    version="1.0.0",
)

app.include_router(auth_router, prefix="/api")


@app.get("/api/health")
def health():
    return {
        "success": True,
        "message": "CampusCare API is running",
    }
