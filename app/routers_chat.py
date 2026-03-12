import logging

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from .db import get_db
from . import schemas, services

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=schemas.ChatResponse)
async def chat(
    payload: schemas.ChatRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Process one conversation turn: log user message, call OpenAI LLM,
    log assistant message, return assistant reply.
    """
    logger.info("Received chat payload: %s", payload)
    print("Received:", payload)

    try:
        assistant_text, condition, _prompt_hash, usage = await services.handle_chat_turn(
            db=db,
            chat_session_id=payload.chat_session_id,
            user_message=payload.user_message,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return schemas.ChatResponse(
        assistant_message=assistant_text,
        condition_id=condition["id"],
        model=condition["llm_model"],
        usage=usage,
    )


@router.post("/final", response_model=schemas.FinalChatResponse)
async def final_chat(
    payload: schemas.FinalChatRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Final conversation turn:
      1. Process the last message and get the assistant reply.
      2. End the session (mark completed).
      3. Return assistant reply + Qualtrics redirect URL.
    """
    try:
        assistant_text, condition, _prompt_hash, usage = await services.handle_chat_turn(
            db=db,
            chat_session_id=payload.chat_session_id,
            user_message=payload.user_message,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        session = await services.end_chat_session(
            db=db, chat_session_id=payload.chat_session_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    from bson import ObjectId
    participant_doc = await db.participants.find_one(
        {"_id": ObjectId(session["participant_id"])}
    )
    pid = participant_doc["pid"] if participant_doc else ""

    redirect_url = services.build_qualtrics_redirect(
        session=session, condition=condition, pid=pid
    )

    await services.log_event(
        db=db,
        event_type="session_end",
        description=f"Final turn + session ended for pid={pid}",
        chat_session_id=session["id"],
        participant_id=session["participant_id"],
    )

    return schemas.FinalChatResponse(
        assistant_message=assistant_text,
        redirect_url=redirect_url,
    )
