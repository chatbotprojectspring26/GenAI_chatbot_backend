from sqlmodel import SQLModel, create_engine, Session
from typing import Generator

from .config import get_settings


settings = get_settings()

engine = create_engine(
    settings.database_url,
    echo=settings.app_env == "development",
)


def init_db() -> None:
    """
    Create all tables. In production, you may want to use Alembic instead.
    """
    from . import models  # noqa: F401  # ensure models are imported

    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

