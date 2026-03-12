import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from .db import get_db

router = APIRouter(prefix="/admin", tags=["admin"])

VALID_TABLES = {"participants", "sessions", "messages"}


@router.get("/sessions")
async def list_sessions(
    experiment_id: Optional[str] = None,
    condition_id: Optional[str] = None,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """List chat sessions, optionally filtered by experiment or condition."""
    query: dict = {}
    if experiment_id:
        query["experiment_id"] = experiment_id
    if condition_id:
        query["condition_id"] = condition_id

    docs = await db.chat_sessions.find(query).to_list(length=500)
    for d in docs:
        d["id"] = str(d.pop("_id"))
    return docs


@router.get("/export")
async def export_data(
    experiment_id: Optional[str] = None,
    table: str = "messages",
    format: str = "csv",
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Export a collection as JSON or CSV.
    Tables: participants | sessions | messages
    """
    if table not in VALID_TABLES:
        raise HTTPException(status_code=400, detail=f"Invalid table. Choose from: {VALID_TABLES}")

    if table == "participants":
        query = {}
        docs = await db.participants.find(query).to_list(length=5000)
    elif table == "sessions":
        query = {}
        if experiment_id:
            query["experiment_id"] = experiment_id
        docs = await db.chat_sessions.find(query).to_list(length=5000)
    else:  # messages
        query = {}
        if experiment_id:
            # Join via sessions to filter by experiment (denormalised: filter by condition's experiment)
            session_ids_cursor = db.chat_sessions.find(
                {"experiment_id": experiment_id} if experiment_id else {},
                {"_id": 1},
            )
            session_ids = [str(s["_id"]) async for s in session_ids_cursor]
            if session_ids:
                query["chat_session_id"] = {"$in": session_ids}
        docs = await db.messages.find(query).sort("turn_index", 1).to_list(length=50000)

    # Convert ObjectId _id fields to strings
    for d in docs:
        if "_id" in d:
            d["id"] = str(d.pop("_id"))

    if format == "json":
        return docs

    # CSV export
    if not docs:
        return Response(content="", media_type="text/csv")

    output = io.StringIO()
    fieldnames = list(docs[0].keys())
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in docs:
        writer.writerow(row)

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{table}.csv"'},
    )
