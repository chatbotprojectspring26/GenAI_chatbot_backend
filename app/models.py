from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field, Column, JSON


class Participant(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    pid: str = Field(index=True)
    study_id: Optional[str] = Field(default=None, index=True)
    assigned_condition_id: Optional[int] = Field(default=None, foreign_key="condition.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Experiment(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = None
    status: str = Field(default="draft", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Condition(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    experiment_id: int = Field(foreign_key="experiment.id", index=True)
    name: str
    description: Optional[str] = None
    llm_model: str
    temperature: float = 0.3
    max_tokens: int = 512
    system_prompt: str
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatSession(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    participant_id: int = Field(foreign_key="participant.id", index=True)
    experiment_id: int = Field(foreign_key="experiment.id", index=True)
    condition_id: int = Field(foreign_key="condition.id", index=True)
    qr_pre: Optional[str] = None
    qr_post: Optional[str] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    status: str = Field(default="active", index=True)
    prolific_session_id: Optional[str] = None
    client_metadata: Optional[dict] = Field(
        sa_column=Column(JSON), default=None
    )


class Message(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    chat_session_id: UUID = Field(foreign_key="chatsession.id", index=True)
    turn_index: int = Field(index=True)
    role: str = Field(index=True)  # "system" | "user" | "assistant"
    text: str
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    condition_id: int = Field(foreign_key="condition.id", index=True)
    prompt_hash: Optional[str] = Field(default=None, index=True)
    model: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    num_input_tokens: Optional[int] = None
    num_output_tokens: Optional[int] = None
    message_metadata: Optional[dict] = Field(sa_column=Column(JSON), default=None)

