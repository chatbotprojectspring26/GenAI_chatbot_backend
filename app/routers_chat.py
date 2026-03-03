from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from .db import get_session
from . import schemas, services, models
from .config import get_settings


settings = get_settings()

router = APIRouter(prefix="/chat", tags=["chat"])


import logging
logger = logging.getLogger(__name__)

@router.post("", response_model=schemas.ChatResponse)
def chat(
    payload: schemas.ChatRequest,
    db: Session = Depends(get_session),
):
    logger.info("Received: %s", payload)
    print("Received:", payload)
    import sys
    sys.stdout.flush()
    try:
        assistant_text, condition, _prompt_hash, usage = services.handle_chat_turn(
            session=db,
            chat_session_id=payload.chat_session_id,
            user_message=payload.user_message,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return schemas.ChatResponse(
        assistant_message=assistant_text,
        condition_id=condition.id,
        model=condition.llm_model,
        usage=usage,
    )


@router.post("/final", response_model=schemas.FinalChatResponse)
def final_chat_and_redirect(
    payload: schemas.FinalChatRequest,
    db: Session = Depends(get_session),
):
    """
    Final turn endpoint:
    - logs the user's last message
    - calls the LLM and logs the assistant reply
    - marks the session as completed
    - returns both the assistant_message and Qualtrics redirect_url
    """
    try:
        assistant_text, condition, _prompt_hash, usage = services.handle_chat_turn(
            session=db,
            chat_session_id=payload.chat_session_id,
            user_message=payload.user_message,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Close the chat session so participants can't keep chatting
    try:
        chat_session = services.end_chat_session(
            session=db,
            chat_session_id=payload.chat_session_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if settings.qualtrics_post_base_url is None:
        raise HTTPException(
            status_code=500,
            detail="qualtrics_post_base_url is not configured on the backend",
        )

    # Look up participant for pid
    participant = db.exec(
        select(models.Participant).where(
            models.Participant.id == chat_session.participant_id
        )
    ).first()

    pid = participant.pid if participant else None

    from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

    base_url = str(settings.qualtrics_post_base_url)
    url_parts = list(urlparse(base_url))
    query = dict(parse_qsl(url_parts[4]))
    query.update(
        {
            "pid": pid or "",
            "chat_session_id": str(chat_session.id),
            "condition_id": str(condition.id),
        }
    )
    url_parts[4] = urlencode(query)
    redirect_url = urlunparse(url_parts)

    return schemas.FinalChatResponse(
        assistant_message=assistant_text,
        redirect_url=redirect_url,
    )

