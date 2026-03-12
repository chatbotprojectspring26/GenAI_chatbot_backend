from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from .db import get_db
from . import schemas, services

router = APIRouter(prefix="/session", tags=["session"])


@router.post("/start", response_model=schemas.SessionStartResponse)
async def start_session(
    payload: schemas.SessionStartRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Creates or retrieves a participant, opens a new ChatSession for the specified A/B condition,
    and returns the chat_session_id.
    """
    print("Received-Session-Info:", payload)

    if not payload.experiment_id:
        raise HTTPException(status_code=400, detail="experiment_id is required")

    participant = await services.get_or_create_participant(
        db=db,
        pid=payload.pid,
        study_id=payload.study_id,
    )

    try:
        chat_session, condition = await services.create_chat_session(
            db=db,
            participant=participant,
            experiment_id=payload.experiment_id,
            condition_name=payload.condition_name,
            qr_pre=payload.qr_pre,
            prolific_session_id=payload.prolific_session_id or payload.session_id,
            client_metadata=payload.client_metadata,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Audit log
    await services.log_event(
        db=db,
        event_type="session_start",
        description=f"Session started for pid={payload.pid}",
        chat_session_id=chat_session["id"],
        participant_id=participant["id"],
    )

    return schemas.SessionStartResponse(
        chat_session_id=chat_session["id"],
        condition_id=condition["id"],
        condition_name=condition["name"],
    )


@router.post("/end", response_model=schemas.SessionEndResponse)
async def end_session(
    payload: schemas.SessionEndRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Marks the session as completed and returns the Qualtrics post-survey redirect URL.
    """
    try:
        session = await services.end_chat_session(
            db=db, chat_session_id=payload.chat_session_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    condition = await services.get_condition(db, session["condition_id"])

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
        description=f"Session ended for pid={pid}",
        chat_session_id=session["id"],
        participant_id=session["participant_id"],
    )

    return schemas.SessionEndResponse(redirect_url=redirect_url)


@router.get("/view/{chat_session_id}")
async def view_session(
    chat_session_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """View raw session document from MongoDB."""
    try:
        session = await services.get_chat_session(db, chat_session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Retrieve messages for this session
    messages = await db.messages.find(
        {"chat_session_id": chat_session_id}
    ).sort("turn_index", 1).to_list(length=200)

    for m in messages:
        m["id"] = str(m.pop("_id"))

    return {
        "status": "success",
        "session": session,
        "messages": messages,
    }


@router.get("/active")
async def view_active_sessions(
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """List all currently active sessions from MongoDB."""
    sessions = await db.chat_sessions.find(
        {"status": "active"}
    ).to_list(length=100)

    for s in sessions:
        s["id"] = str(s.pop("_id"))

    return {
        "status": "success",
        "count": len(sessions),
        "sessions": sessions,
    }


@router.post("/tab-event")
async def log_tab_event(
    payload: schemas.TabEventRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Logs browser visibility and window focus events.
    Frontend sends this when the user switches tabs or focuses away.
    """
    from datetime import datetime, timezone

    event_data = payload.model_dump()
    event_data["received_at"] = datetime.now(timezone.utc)
    
    await db.tab_events.insert_one(event_data)
    
    return {"status": "ok"}

