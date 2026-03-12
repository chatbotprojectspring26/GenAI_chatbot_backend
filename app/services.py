"""
Business logic layer — fully async, talks directly to MongoDB via Motor.

Key design decisions:
  - Condition is assigned ONCE per participant (pid + study_id) and never changed.
  - Memory window: last N turns retrieved each call (stateless backend).
  - All LLM config is snapshotted onto each Message document for reproducibility.
  - IDs: chat_sessions use UUID strings; all other collections use ObjectId strings.
"""
import hashlib
from datetime import datetime
from typing import Optional, Tuple
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from . import models
from .config import get_settings
from .llm_client import generate_completion_async

settings = get_settings()


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _to_str_id(doc: dict) -> dict:
    """Return a copy of the MongoDB document with _id converted to 'id' string."""
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    return d


def _hash_prompt(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


# ─────────────────────────────────────────────────────────────────────────────
# Participant
# ─────────────────────────────────────────────────────────────────────────────

async def get_or_create_participant(
    db: AsyncIOMotorDatabase,
    pid: str,
    study_id: Optional[str],
) -> dict:
    """
    Upsert participant by (pid, study_id). Returns the document dict with 'id'.
    The unique index on (pid, study_id) in db.py guarantees idempotency.
    """
    now = datetime.utcnow()
    result = await db.participants.find_one_and_update(
        {"pid": pid, "study_id": study_id},
        {
            "$setOnInsert": {
                "pid": pid,
                "study_id": study_id,
                "assigned_condition_id": None,
                "created_at": now,
                "updated_at": now,
            }
        },
        upsert=True,
        return_document=True,
    )
    return _to_str_id(result)


# ─────────────────────────────────────────────────────────────────────────────
# Condition assignment  (stable A/B)
# ─────────────────────────────────────────────────────────────────────────────

async def _pick_random_condition(
    db: AsyncIOMotorDatabase,
    experiment_id: str,
) -> dict:
    """Pick one active condition at random using MongoDB $sample."""
    pipeline = [
        {"$match": {"experiment_id": experiment_id, "is_active": True}},
        {"$sample": {"size": 1}},
    ]
    docs = await db.conditions.aggregate(pipeline).to_list(length=1)
    if not docs:
        raise ValueError(f"No active conditions for experiment {experiment_id}")
    return _to_str_id(docs[0])


async def get_condition(db: AsyncIOMotorDatabase, condition_id: str) -> dict:
    doc = await db.conditions.find_one({"_id": ObjectId(condition_id)})
    if not doc:
        raise ValueError(f"Condition {condition_id} not found")
    return _to_str_id(doc)


# ─────────────────────────────────────────────────────────────────────────────
# Chat session
# ─────────────────────────────────────────────────────────────────────────────

async def create_chat_session(
    db: AsyncIOMotorDatabase,
    participant: dict,
    experiment_id: str,
    qr_pre: Optional[str],
    prolific_session_id: Optional[str],
    client_metadata: Optional[dict],
) -> Tuple[dict, dict]:
    """
    Create a new ChatSession.

    STABLE A/B LOGIC:
      If the participant already has an assigned_condition_id we reuse it.
      Only on the very first session do we pick randomly.
    This guarantees the same PID always sees the same condition.
    """
    participant_id = participant["id"]

    if participant.get("assigned_condition_id"):
        condition = await get_condition(db, participant["assigned_condition_id"])
    else:
        condition = await _pick_random_condition(db, experiment_id)
        await db.participants.update_one(
            {"_id": ObjectId(participant_id)},
            {
                "$set": {
                    "assigned_condition_id": condition["id"],
                    "updated_at": datetime.utcnow(),
                }
            },
        )

    session_doc = models.ChatSession(
        participant_id=participant_id,
        experiment_id=experiment_id,
        condition_id=condition["id"],
        qr_pre=qr_pre,
        prolific_session_id=prolific_session_id,
        client_metadata=client_metadata,
    ).model_dump()

    # Store UUID string as _id directly (not ObjectId) so it's URL-safe.
    session_doc["_id"] = session_doc.pop("id")
    await db.chat_sessions.insert_one(session_doc)

    session_doc["id"] = session_doc.pop("_id")
    return session_doc, condition


async def get_chat_session(db: AsyncIOMotorDatabase, chat_session_id: str) -> dict:
    doc = await db.chat_sessions.find_one({"_id": chat_session_id})
    if not doc:
        raise ValueError(f"Chat session {chat_session_id} not found")
    return _to_str_id(doc)


async def end_chat_session(
    db: AsyncIOMotorDatabase, chat_session_id: str
) -> dict:
    now = datetime.utcnow()
    doc = await db.chat_sessions.find_one_and_update(
        {"_id": chat_session_id},
        {"$set": {"status": "completed", "ended_at": now}},
        return_document=True,
    )
    if not doc:
        raise ValueError(f"Chat session {chat_session_id} not found")
    return _to_str_id(doc)


# ─────────────────────────────────────────────────────────────────────────────
# Chat turn  (retrieve history → call LLM → log messages)
# ─────────────────────────────────────────────────────────────────────────────

async def _get_next_turn_index(
    db: AsyncIOMotorDatabase, chat_session_id: str
) -> int:
    """Return the next turn index (0-based) for a session."""
    cursor = (
        db.messages.find({"chat_session_id": chat_session_id})
        .sort("turn_index", -1)
        .limit(1)
    )
    docs = await cursor.to_list(length=1)
    return (docs[0]["turn_index"] + 1) if docs else 0


async def handle_chat_turn(
    db: AsyncIOMotorDatabase,
    chat_session_id: str,
    user_message: str,
) -> Tuple[str, dict, str, dict]:
    """
    Full turn cycle:
      1. Validate session is active.
      2. Load the last N turns for context (memory window).
      3. Build LLM payload (system prompt + history + new user message).
      4. Call LLM (OpenAI GPT-4o-mini).
      5. Persist user message + assistant message.
      6. Return (assistant_text, condition_doc, prompt_hash, usage).
    """
    session = await get_chat_session(db, chat_session_id)
    if session["status"] != "active":
        raise ValueError("Chat session is not active")

    condition = await get_condition(db, session["condition_id"])
    system_prompt = condition["system_prompt"]
    prompt_hash = _hash_prompt(system_prompt)

    # ── Memory: retrieve last N turns ────────────────────────────────────────
    window = settings.memory_window
    history_limit = window * 2  # each pair = 1 user + 1 assistant message
    history_cursor = (
        db.messages.find({"chat_session_id": chat_session_id})
        .sort("turn_index", -1)
        .limit(history_limit)
    )
    history_docs = list(reversed(await history_cursor.to_list(length=history_limit)))

    # Build LLM messages payload
    messages_payload = [{"role": "system", "content": system_prompt}]
    for m in history_docs:
        if m["role"] in ("user", "assistant"):
            messages_payload.append({"role": m["role"], "content": m["text"]})
    messages_payload.append({"role": "user", "content": user_message})

    # ── LLM call ─────────────────────────────────────────────────────────────
    assistant_text, usage = await generate_completion_async(
        messages=messages_payload,
        model=condition.get("llm_model") or settings.openai_model,
        temperature=condition.get("temperature", settings.openai_temperature),
        max_tokens=condition.get("max_tokens", settings.openai_max_tokens),
    )

    # ── Persist messages ──────────────────────────────────────────────────────
    base_turn = await _get_next_turn_index(db, chat_session_id)
    now = datetime.utcnow()

    common = dict(
        chat_session_id=chat_session_id,
        condition_id=condition["id"],
        prompt_hash=prompt_hash,
        model=condition.get("llm_model", settings.openai_model),
        temperature=condition.get("temperature", settings.openai_temperature),
        max_tokens=condition.get("max_tokens", settings.openai_max_tokens),
    )
    user_msg = models.Message(
        turn_index=base_turn,
        role="user",
        text=user_message,
        created_at=now,
        num_input_tokens=usage.get("prompt_tokens"),
        message_metadata={"source": "web"},
        **common,
    ).model_dump()
    user_msg.pop("id")  # let MongoDB assign _id

    assistant_msg = models.Message(
        turn_index=base_turn + 1,
        role="assistant",
        text=assistant_text,
        created_at=now,
        num_output_tokens=usage.get("completion_tokens"),
        total_tokens=usage.get("total_tokens"),
        message_metadata={"llm_response_id": usage.get("id"), "source": "llm"},
        **common,
    ).model_dump()
    assistant_msg.pop("id")

    await db.messages.insert_many([user_msg, assistant_msg])

    # Increment turn_count on session
    await db.chat_sessions.update_one(
        {"_id": chat_session_id},
        {"$inc": {"turn_count": 1}},
    )

    return assistant_text, condition, prompt_hash, usage


# ─────────────────────────────────────────────────────────────────────────────
# Qualtrics redirect URL builder
# ─────────────────────────────────────────────────────────────────────────────

def build_qualtrics_redirect(session: dict, condition: dict, pid: str) -> str:
    """
    Append pid, chat_session_id, and condition_id to the Qualtrics post URL.
    Returns empty string if qualtrics_post_base_url is not configured.
    """
    base = settings.qualtrics_post_base_url
    if not base:
        return ""

    parts = list(urlparse(base))
    query = dict(parse_qsl(parts[4]))
    query.update(
        {
            "pid": pid,
            "chat_session_id": session["id"],
            "condition_id": condition["id"],
        }
    )
    parts[4] = urlencode(query)
    return urlunparse(parts)


# ─────────────────────────────────────────────────────────────────────────────
# Event logging
# ─────────────────────────────────────────────────────────────────────────────

async def log_event(
    db: AsyncIOMotorDatabase,
    event_type: str,
    description: str,
    severity: str = "info",
    chat_session_id: Optional[str] = None,
    participant_id: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """Fire-and-forget audit log into the events collection."""
    event = models.Event(
        chat_session_id=chat_session_id,
        participant_id=participant_id,
        event_type=event_type,
        severity=severity,
        description=description,
        metadata=metadata,
    ).model_dump()
    event.pop("id")
    await db.events.insert_one(event)
