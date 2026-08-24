from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from app.api.chat import router as chat_router
from app.database.sqlite import (
    initialize_database,
)


@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    initialize_database()

    yield


app = FastAPI(
    title="Hotel Booking AI Agent",
    version="0.4.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(chat_router)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "hotel-booking-agent",
        "phase": "phase4",
        "database": "sqlite",
    }