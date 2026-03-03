import hashlib
from datetime import datetime
from typing import Optional, Tuple
from uuid import UUID

from sqlmodel import Session, select, func

from . import models
from .config import get_settings
from .llm_client import generate_completion


settings = get_settings()


def _hash_prompt(system_prompt: str) -> str:
    return hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()


def get_or_create_participant(
    session: Session,
    pid: str,
    study_id: Optional[str],
) -> models.Participant:
    participant = session.exec(
        select(models.Participant).where(
            models.Participant.pid == pid,
            models.Participant.study_id == study_id,
        )
    ).first()
    if participant:
        return participant

    participant = models.Participant(pid=pid, study_id=study_id)
    session.add(participant)
    session.commit()
    session.refresh(participant)
    return participant


def assign_condition(
    session: Session,
    experiment_id: int,
) -> models.Condition:
    """
    Simple random assignment among active conditions for an experiment.
    """
    conditions = session.exec(
        select(models.Condition).where(
            models.Condition.experiment_id == experiment_id,
            models.Condition.is_active == True,  # noqa: E712
        )
    ).all()
    if not conditions:
        raise ValueError(f"No active conditions configured for experiment {experiment_id}")

    # Basic random assignment using database random()
    condition = session.exec(
        select(models.Condition)
        .where(
            models.Condition.experiment_id == experiment_id,
            models.Condition.is_active == True,  # noqa: E712
        )
        .order_by(func.random())
    ).first()
    if condition is None:
        condition = conditions[0]
    return condition


def create_chat_session(
    session: Session,
    participant: models.Participant,
    experiment_id: int,
    qr_pre: Optional[str],
    prolific_session_id: Optional[str],
    client_metadata: Optional[dict],
) -> Tuple[models.ChatSession, models.Condition]:
    condition = assign_condition(session=session, experiment_id=experiment_id)
    participant.assigned_condition_id = condition.id
    participant.updated_at = datetime.utcnow()
    session.add(participant)

    chat_session = models.ChatSession(
        participant_id=participant.id,
        experiment_id=experiment_id,
        condition_id=condition.id,
        qr_pre=qr_pre,
        prolific_session_id=prolific_session_id,
        client_metadata=client_metadata,
    )
    session.add(chat_session)
    session.commit()
    session.refresh(chat_session)
    return chat_session, condition


def _get_next_turn_index(session: Session, chat_session_id: UUID) -> int:
    last_message = session.exec(
        select(models.Message)
        .where(models.Message.chat_session_id == chat_session_id)
        .order_by(models.Message.turn_index.desc())
    ).first()
    return (last_message.turn_index + 1) if last_message else 0


def handle_chat_turn(
    session: Session,
    chat_session_id: UUID,
    user_message: str,
) -> Tuple[str, models.Condition, str, dict]:
    chat_session = session.get(models.ChatSession, chat_session_id)
    if chat_session is None or chat_session.status != "active":
        raise ValueError("Chat session not found or not active")

    condition = session.get(models.Condition, chat_session.condition_id)
    if condition is None:
        raise ValueError("Condition not found for session")

    # Build system prompt and hash
    system_prompt = condition.system_prompt
    prompt_hash = _hash_prompt(system_prompt)

    # For now, only include the latest context (can be extended to include full history)
    history_messages = session.exec(
        select(models.Message)
        .where(models.Message.chat_session_id == chat_session_id)
        .order_by(models.Message.turn_index)
    ).all()

    messages_payload = [{"role": "system", "content": system_prompt}]
    for m in history_messages:
        if m.role in ("user", "assistant"):
            messages_payload.append({"role": m.role, "content": m.text})
    messages_payload.append({"role": "user", "content": user_message})

    # Call LLM
    assistant_text, usage = generate_completion(
        messages=messages_payload,
        model=condition.llm_model or settings.openai_model,
        temperature=condition.temperature,
        max_tokens=condition.max_tokens,
    )

    # Persist messages
    base_turn_index = _get_next_turn_index(session, chat_session_id)
    user_msg = models.Message(
        chat_session_id=chat_session_id,
        turn_index=base_turn_index,
        role="user",
        text=user_message,
        condition_id=condition.id,
        prompt_hash=prompt_hash,
        model=condition.llm_model,
        temperature=condition.temperature,
        max_tokens=condition.max_tokens,
        num_input_tokens=usage.get("prompt_tokens"),
        message_metadata={"source": "web"},
    )
    assistant_msg = models.Message(
        chat_session_id=chat_session_id,
        turn_index=base_turn_index + 1,
        role="assistant",
        text=assistant_text,
        condition_id=condition.id,
        prompt_hash=prompt_hash,
        model=condition.llm_model,
        temperature=condition.temperature,
        max_tokens=condition.max_tokens,
        num_output_tokens=usage.get("completion_tokens"),
        message_metadata={"source": "llm"},
    )
    session.add(user_msg)
    session.add(assistant_msg)
    session.commit()

    return assistant_text, condition, prompt_hash, usage


def end_chat_session(
    session: Session,
    chat_session_id: UUID,
) -> models.ChatSession:
    chat_session = session.get(models.ChatSession, chat_session_id)
    if chat_session is None:
        raise ValueError("Chat session not found")
    chat_session.status = "completed"
    chat_session.ended_at = datetime.utcnow()
    session.add(chat_session)
    session.commit()
    session.refresh(chat_session)
    return chat_session

