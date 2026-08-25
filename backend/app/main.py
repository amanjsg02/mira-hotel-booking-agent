import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from app.api.chat import router as chat_router
from app.database.sqlite import (
    initialize_database,
)


# Load environment variables from .env during local
# development. Render supplies them through its dashboard.
load_dotenv()


def get_allowed_origins() -> list[str]:
    """
    Return frontend origins that are allowed to call the API.

    Local development URLs are always supported.

    Production origins can be configured using either:

    FRONTEND_ORIGIN=https://example.vercel.app

    or multiple origins:

    CORS_ORIGINS=https://one.vercel.app,https://two.vercel.app
    """
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    frontend_origin = os.getenv(
        "FRONTEND_ORIGIN",
        "",
    ).strip()

    if frontend_origin:
        origins.append(
            frontend_origin.rstrip("/")
        )

    additional_origins = os.getenv(
        "CORS_ORIGINS",
        "",
    )

    for origin in additional_origins.split(","):
        normalized_origin = (
            origin.strip().rstrip("/")
        )

        if normalized_origin:
            origins.append(normalized_origin)

    # Remove duplicates while preserving order.
    return list(dict.fromkeys(origins))


@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    """
    Initialize application resources when FastAPI starts.

    The SQLite database and its tables are created before
    the application begins accepting requests.
    """
    initialize_database()

    yield


app = FastAPI(
    title="Mera Hotel Booking AI Agent",
    description=(
        "A conversational hotel-search and booking "
        "assistant with persistent state, grounded hotel "
        "information and deterministic pricing."
    ),
    version="0.5.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(chat_router)


@app.get("/")
def root():
    """
    Provide a simple response when the deployed backend
    root URL is opened in a browser.
    """
    return {
        "status": "running",
        "service": "mera-hotel-booking-agent",
        "documentation": "/docs",
        "health": "/health",
    }


@app.get("/health")
def health_check():
    """
    Health endpoint used by the frontend and hosting
    service to verify that the API is running.
    """
    return {
        "status": "healthy",
        "service": "hotel-booking-agent",
        "phase": "phase5",
        "database": "sqlite",
    }