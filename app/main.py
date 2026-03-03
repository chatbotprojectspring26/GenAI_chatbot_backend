from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import init_db
from .routers_session import router as session_router
from .routers_chat import router as chat_router
from .routers_admin import router as admin_router
from .routers_health import router as health_router


settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    # CORS
    origins = [origin.strip() for origin in settings.cors_origins.split(",")] if settings.cors_origins else ["http://localhost:3000"]
    
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

    @app.on_event("startup")
    def on_startup() -> None:
        init_db()

    return app


app = create_app()

