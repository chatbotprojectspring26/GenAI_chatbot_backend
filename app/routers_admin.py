import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlmodel import Session, select

from .db import get_session
from . import models


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/sessions")
def list_sessions(
    experiment_id: Optional[int] = None,
    condition_id: Optional[int] = None,
    db: Session = Depends(get_session),
):
    query = select(models.ChatSession)
    if experiment_id is not None:
        query = query.where(models.ChatSession.experiment_id == experiment_id)
    if condition_id is not None:
        query = query.where(models.ChatSession.condition_id == condition_id)
    sessions = db.exec(query).all()
    return sessions


@router.get("/export")
def export_data(
    experiment_id: Optional[int] = None,
    table: str = "messages",
    format: str = "csv",
    db: Session = Depends(get_session),
):
    if table not in {"participants", "sessions", "messages"}:
        raise HTTPException(status_code=400, detail="Invalid table")

    if table == "participants":
        rows = db.exec(select(models.Participant)).all()
    elif table == "sessions":
        rows = db.exec(select(models.ChatSession)).all()
    else:
        rows = db.exec(select(models.Message)).all()

    if format == "json":
        return rows

    # CSV export
    output = io.StringIO()
    if not rows:
        return Response(content="", media_type="text/csv")

    fieldnames = rows[0].dict().keys()
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row.dict())

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{table}.csv"'},
    )

