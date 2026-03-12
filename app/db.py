"""
MongoDB connection via Motor (async driver).

Usage in route handlers:
    db: AsyncIOMotorDatabase = Depends(get_db)
"""
from __future__ import annotations

from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .config import get_settings

settings = get_settings()

# Module-level client — created once on startup, closed on shutdown.
_client: Optional[AsyncIOMotorClient] = None


def get_client() -> AsyncIOMotorClient:
    """Return the shared Motor client (must call init_db first)."""
    if _client is None:
        raise RuntimeError("MongoDB client not initialised. Call init_db() on startup.")
    return _client


def get_database() -> AsyncIOMotorDatabase:
    """Return the configured database handle."""
    return get_client()[settings.mongodb_db_name]


async def get_db() -> AsyncIOMotorDatabase:
    """FastAPI dependency — yields the Motor database for a single request."""
    return get_database()


async def init_db() -> None:
    """
    Open the Motor client and ensure collection indexes exist.
    Called from the FastAPI lifespan startup handler.
    """
    global _client
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    db = _client[settings.mongodb_db_name]

    # ── participants ──────────────────────────────────────────────────────────
    # Unique compound index: same PID across different studies is allowed,
    # but within one study a PID must be unique (idempotent upsert key).
    await db.participants.create_index(
        [("pid", 1), ("study_id", 1)], unique=True, name="uq_pid_study"
    )

    # ── conditions ───────────────────────────────────────────────────────────
    await db.conditions.create_index(
        [("experiment_id", 1), ("is_active", 1)], name="idx_cond_exp_active"
    )

    # ── chat_sessions ─────────────────────────────────────────────────────────
    await db.chat_sessions.create_index("participant_id", name="idx_sess_participant")
    await db.chat_sessions.create_index("status", name="idx_sess_status")
    await db.chat_sessions.create_index("experiment_id", name="idx_sess_experiment")

    # ── messages ──────────────────────────────────────────────────────────────
    # Compound index: retrieve ordered conversation history in one seek.
    await db.messages.create_index(
        [("chat_session_id", 1), ("turn_index", 1)],
        name="idx_msg_session_turn",
    )
    await db.messages.create_index("prompt_hash", name="idx_msg_prompt_hash")

    # ── events ───────────────────────────────────────────────────────────────
    await db.events.create_index("chat_session_id", name="idx_events_session")
    await db.events.create_index("created_at", name="idx_events_time")


async def close_db() -> None:
    """Close the Motor client. Called from FastAPI lifespan shutdown handler."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
