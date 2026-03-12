"""
In-memory session logger for real-time console debugging.

Note: This logger tracks sessions within a single server process lifetime only.
Persistent audit logs are written to the MongoDB 'events' collection via services.log_event().
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional


class SessionLogger:
    """Centralized in-memory logging for all session activities (per process)."""

    def __init__(self):
        self.session_data: Dict[str, Dict[str, Any]] = {}

    def log_session_start(
        self,
        payload: Dict[str, Any],
        chat_session_id: str,
        participant_id: str,
        condition_id: str,
    ):
        """Log session start with all details to console and in-memory store."""
        timestamp = datetime.now().isoformat()

        session_info = {
            "timestamp": timestamp,
            "event": "SESSION_START",
            "chat_session_id": chat_session_id,
            "participant_id": participant_id,
            "condition_id": condition_id,
            "payload": payload,
            "status": "SESSION_CREATED",
        }
        self.session_data[chat_session_id] = session_info

        self._print_header("SESSION STARTED", chat_session_id)
        print(f"📋 PID:          {payload.get('pid', 'N/A')}")
        print(f"📋 Study ID:     {payload.get('study_id', 'N/A')}")
        print(f"📋 Experiment:   {payload.get('experiment_id', 'N/A')}")
        print(f"📋 Condition:    {condition_id}")
        print(f"📋 Metadata:     {payload.get('client_metadata', {})}")
        print("=" * 60)

    def log_chat_message(
        self,
        chat_session_id: str,
        role: str,
        message: str,
        usage: Optional[Dict] = None,
    ):
        """Log individual chat messages to console."""
        timestamp = datetime.now().isoformat()
        entry = {
            "timestamp": timestamp,
            "role": role,
            "message": message,
            "usage": usage or {},
        }
        if chat_session_id in self.session_data:
            self.session_data[chat_session_id].setdefault("messages", []).append(entry)

        icon = "👤" if role == "user" else "🤖"
        print(f"{icon} [{role.upper()}] {message}")
        if usage:
            print(f"📊 Token Usage: {usage}")

    def log_session_end(self, chat_session_id: str, redirect_url: str):
        """Log session completion to console."""
        if chat_session_id in self.session_data:
            self.session_data[chat_session_id]["status"] = "COMPLETED"
            self.session_data[chat_session_id]["ended_at"] = datetime.now().isoformat()

        self._print_header("SESSION ENDED", chat_session_id)
        print(f"🔗 Redirect URL: {redirect_url}")
        print("=" * 60)

    def log_error(self, chat_session_id: str, error_type: str, error_details: str):
        """Log errors to console."""
        self._print_header("ERROR", chat_session_id)
        print(f"❌ {error_type}: {error_details}")
        print("=" * 60)

    def _print_header(self, event: str, chat_session_id: str):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n🔍 [{ts}] {event} — Session: {chat_session_id}")
        print("-" * 40)

    def get_session_summary(self, chat_session_id: str) -> Optional[Dict[str, Any]]:
        return self.session_data.get(chat_session_id)

    def get_all_sessions(self) -> Dict[str, Dict[str, Any]]:
        return self.session_data

    def export_session_data(self, chat_session_id: str, fmt: str = "json") -> str:
        data = self.get_session_summary(chat_session_id)
        if not data:
            return "{}"
        if fmt == "json":
            return json.dumps(data, indent=2, default=str)
        return str(data)


# ── Global singleton ──────────────────────────────────────────────────────────
_session_logger: Optional[SessionLogger] = None


def get_session_logger() -> SessionLogger:
    """Return the process-wide SessionLogger (created on first call)."""
    global _session_logger
    if _session_logger is None:
        _session_logger = SessionLogger()
    return _session_logger
