from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import init_db, close_db
from .routers_session import router as session_router
from .routers_chat import router as chat_router
from .routers_admin import router as admin_router
from .routers_health import router as health_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: open MongoDB connection and create indexes. Shutdown: close it."""
    await init_db()
    yield
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        description="GenAI Research Chatbot Backend – MongoDB + OpenAI LLM",
        version="2.0.0",
        lifespan=lifespan,
    )

    # CORS
    origins = [
        origin.strip()
        for origin in settings.cors_origins.split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(health_router)
    app.include_router(session_router)
    app.include_router(chat_router)
    app.include_router(admin_router)

    return app


app = create_app()
