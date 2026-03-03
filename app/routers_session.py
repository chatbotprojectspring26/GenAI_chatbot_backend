from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from .db import get_session
from . import models, schemas, services
from .config import get_settings
from .logging_system import get_session_logger


router = APIRouter(prefix="/session", tags=["session"])
settings = get_settings()


@router.post("/start", response_model=schemas.SessionStartResponse)
def start_session(
    payload: schemas.SessionStartRequest,
    db: Session = Depends(get_session),
):
    """
    Creates or retrieves a participant, assigns A/B condition, 
    opens a new ChatSession, and returns the chat_session_id.
    """
    print("Received-Session-Info:", payload)
    
    experiment_id = payload.experiment_id
    if experiment_id is None:
        # In a more advanced setup, resolve by name; for now require numeric ID
        raise HTTPException(status_code=400, detail="experiment_id is required")
    
    # Convert string experiment_id to integer
    try:
        experiment_id_int = int(experiment_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="experiment_id must be a valid integer")

    # Initialize session logger
    logger = get_session_logger(db)

    # FIX 1: Ensure participant creation is active
    participant = services.get_or_create_participant(
        session=db,
        pid=payload.pid,
        study_id=payload.study_id,
    )

    try:
        # FIX 2: Ensure client_metadata is passed correctly
        chat_session, condition = services.create_chat_session(
            session=db,
            participant=participant,
            experiment_id=experiment_id_int,
            qr_pre=payload.qr_pre,
            prolific_session_id=payload.session_id,
            client_metadata=payload.client_metadata,  # This was the missing piece
        )
        
        # Log session start with detailed information
        logger.log_session_start(
            payload.dict(),
            str(chat_session.id),
            participant.id,
            condition.id
        )
        
    except ValueError as e:
        logger.log_error(str(chat_session.id) if 'chat_session' in locals() else "unknown", "SESSION_CREATE_ERROR", str(e))
        raise HTTPException(status_code=400, detail=str(e))

    # Log the session start event for debugging
    try:
        # Optional: Add event logging if needed
        pass
    except Exception:
        # Don't fail the session if logging fails
        pass

    return schemas.SessionStartResponse(
        chat_session_id=chat_session.id,
        condition_id=condition.id,
        condition_name=condition.name,
    )


@router.post("/end", response_model=schemas.SessionEndResponse)
def end_session(
    payload: schemas.SessionEndRequest,
    db: Session = Depends(get_session),
):
    """
    Marks a session as completed and returns redirect URL.
    """
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

    return schemas.SessionEndResponse(
        redirect_url=redirect_url,
    )


@router.get("/view/{chat_session_id}")
def view_session(
    chat_session_id: str,
    db: Session = Depends(get_session),
):
    """
    View detailed session information (like 'ss' command)
    """
    logger = get_session_logger(db)
    session_data = logger.get_session_summary(chat_session_id)
    
    if session_data:
        return {
            "status": "success",
            "session_data": session_data,
            "formatted_output": logger.export_session_data(chat_session_id, "ss")
        }
    else:
        return {
            "status": "error",
            "message": f"Session {chat_session_id} not found in active logging"
        }


@router.get("/active")
def view_active_sessions(
    db: Session = Depends(get_session),
):
    """
    View all currently active sessions
    """
    from .logging_system import log_all_active_sessions
    log_all_active_sessions(db)
    
    return {
        "status": "success",
        "message": "Active sessions logged to console"
    }

