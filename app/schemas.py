from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class SessionStartRequest(BaseModel):
    pid: str
    study_id: Optional[str] = None
    prolific_session_id: Optional[str] = None   # Prolific session token
    session_id: Optional[str] = None            # legacy alias
    qr_pre: Optional[str] = None
    experiment_id: Optional[str] = None         # MongoDB ObjectId string
    client_metadata: Optional[dict] = None


class SessionStartResponse(BaseModel):
    chat_session_id: str                         # UUID string
    condition_id: str                            # MongoDB ObjectId string
    condition_name: str


class ChatRequest(BaseModel):
    chat_session_id: str                         # UUID string
    user_message: str
    client_turn_id: Optional[str] = None


class ChatMessage(BaseModel):
    role: str
    text: str
    created_at: datetime


class ChatResponse(BaseModel):
    assistant_message: str
    condition_id: str                            # MongoDB ObjectId string
    model: str
    usage: Optional[dict] = None


class SessionEndRequest(BaseModel):
    chat_session_id: str


class SessionEndResponse(BaseModel):
    redirect_url: str


class FinalChatRequest(BaseModel):
    """Final turn: processes message, ends session, returns redirect URL."""
    chat_session_id: str
    user_message: str


class FinalChatResponse(BaseModel):
    assistant_message: str
    redirect_url: str


class ExportFormat(str):
    CSV = "csv"
    JSON = "json"


class ExportQuery(BaseModel):
    experiment_id: Optional[str] = None
    format: str = "csv"
    include_tables: Optional[List[str]] = None
