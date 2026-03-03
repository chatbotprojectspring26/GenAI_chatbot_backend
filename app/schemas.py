from datetime import datetime
from typing import List, Optional
from uuid import UUID
from enum import Enum

from pydantic import BaseModel


class SessionStartRequest(BaseModel):
    pid: str
    study_id: Optional[str] = None
    session_id: Optional[str] = None
    qr_pre: Optional[str] = None
    experiment_id: Optional[str] = None
    client_metadata: Optional[dict] = None


class SessionStartResponse(BaseModel):
    chat_session_id: UUID
    condition_id: int
    condition_name: str


class ChatRequest(BaseModel):
    chat_session_id: UUID
    user_message: str
    client_turn_id: Optional[str] = None


class ChatMessage(BaseModel):
    role: str
    text: str
    created_at: datetime


class ChatResponse(BaseModel):
    assistant_message: str
    condition_id: int
    model: str
    usage: Optional[dict] = None


class SessionEndRequest(BaseModel):
    chat_session_id: UUID


class SessionEndResponse(BaseModel):
    redirect_url: str


class FinalChatRequest(BaseModel):
    """
    Final turn that both chats and returns the Qualtrics redirect.
    """

    chat_session_id: UUID
    user_message: str


class FinalChatResponse(BaseModel):
    assistant_message: str
    redirect_url: str

class ExportFormat(str, Enum):
    CSV = "csv"
    JSON = "json"


class ExportQuery(BaseModel):
    experiment_id: Optional[int] = None
    format: ExportFormat = ExportFormat.CSV
    include_tables: Optional[List[str]] = None

