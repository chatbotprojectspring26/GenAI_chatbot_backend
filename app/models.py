"""
Pydantic document models representing MongoDB collections.

Convention:
  - `id` field maps to MongoDB _id.
  - Session _id is stored as a UUID string (URL-safe).
  - Condition / Participant _id are MongoDB ObjectId hex strings.
  - Timestamps are always UTC datetime objects.
"""
from datetime import datetime
from typing import Any, Dict, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# experiments collection
# ─────────────────────────────────────────────────────────────────────────────
class Experiment(BaseModel):
    id: Optional[str] = None                  # MongoDB ObjectId hex string
    name: str
    description: Optional[str] = None
    status: Literal["draft", "active", "completed"] = "draft"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# conditions collection  (one document per A/B arm)
# ─────────────────────────────────────────────────────────────────────────────
class Condition(BaseModel):
    id: Optional[str] = None
    experiment_id: str                        # ref → experiments._id
    name: str                                 # e.g. "control" | "treatment"
    description: Optional[str] = None
    system_prompt: str
    llm_model: str
    temperature: float = 0.3
    max_tokens: int = 512
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# participants collection  (one document per PID × study_id pair)
# ─────────────────────────────────────────────────────────────────────────────
class Participant(BaseModel):
    id: Optional[str] = None
    pid: str                                  # Prolific participant ID
    study_id: Optional[str] = None            # Prolific study ID
    assigned_condition_id: Optional[str] = None   # set once on first session
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ─────────────────────────────────────────────────────────────────────────────
# chat_sessions collection
# ─────────────────────────────────────────────────────────────────────────────
class ChatSession(BaseModel):
    # UUID string stored as MongoDB _id — URL-safe and unguessable.
    id: str = Field(default_factory=lambda: str(uuid4()))
    participant_id: str                       # ref → participants._id
    experiment_id: str                        # ref → experiments._id
    condition_id: str                         # ref → conditions._id
    qr_pre: Optional[str] = None             # Qualtrics PreSurvey ResponseID
    qr_post: Optional[str] = None            # Qualtrics PostSurvey ResponseID
    prolific_session_id: Optional[str] = None
    status: Literal["active", "completed", "abandoned"] = "active"
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    turn_count: int = 0                       # incremented per user turn
    client_metadata: Optional[Dict[str, Any]] = None


# ─────────────────────────────────────────────────────────────────────────────
# messages collection
# ─────────────────────────────────────────────────────────────────────────────
class Message(BaseModel):
    id: Optional[str] = None
    chat_session_id: str                      # ref → chat_sessions._id (UUID)
    turn_index: int                           # 0-based; even=user, odd=assistant
    role: Literal["user", "assistant", "system"]
    text: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # ── experimental provenance (denormalised for flat CSV export) ────────────
    condition_id: str
    prompt_hash: str                          # SHA-256 of system_prompt
    model: str
    temperature: float
    max_tokens: int
    # ── token accounting ──────────────────────────────────────────────────────
    num_input_tokens: Optional[int] = None
    num_output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    # ── arbitrary extra data ──────────────────────────────────────────────────
    message_metadata: Optional[Dict[str, Any]] = None


# ─────────────────────────────────────────────────────────────────────────────
# events collection  (system / error audit log)
# ─────────────────────────────────────────────────────────────────────────────
class Event(BaseModel):
    id: Optional[str] = None
    chat_session_id: Optional[str] = None     # may be None for pre-session errors
    participant_id: Optional[str] = None
    event_type: str                           # e.g. "session_start" | "error"
    severity: Literal["info", "warning", "error", "fatal"] = "info"
    description: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[Dict[str, Any]] = None
