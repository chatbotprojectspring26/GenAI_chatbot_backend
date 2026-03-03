"""
Comprehensive Logging System for Chatbot Research Platform
Provides real-time session tracking and debugging information
"""

import json
from datetime import datetime
from typing import Dict, Any, Optional
from sqlmodel import Session, select
from . import models


class SessionLogger:
    """Centralized logging for all session activities"""
    
    def __init__(self, db: Session):
        self.db = db
        self.session_data = {}
    
    def log_session_start(self, payload: Dict[str, Any], chat_session_id: str, participant_id: int, condition_id: int):
        """Log session start with all details"""
        timestamp = datetime.now().isoformat()
        
        session_info = {
            "timestamp": timestamp,
            "event": "SESSION_START",
            "chat_session_id": chat_session_id,
            "participant_id": participant_id,
            "condition_id": condition_id,
            "payload": payload,
            "status": "SESSION_CREATED"
        }
        
        self.session_data[chat_session_id] = session_info
        
        # Pretty print for console
        self._print_session_header("SESSION STARTED", chat_session_id)
        print(f"📋 Participant ID: {payload.get('pid', 'N/A')}")
        print(f"📋 Study ID: {payload.get('study_id', 'N/A')}")
        print(f"📋 Experiment ID: {payload.get('experiment_id', 'N/A')}")
        print(f"📋 Condition ID: {condition_id}")
        print(f"📋 Client Metadata: {payload.get('client_metadata', {})}")
        print(f"📋 Session UUID: {chat_session_id}")
        print("=" * 60)
    
    def log_chat_message(self, chat_session_id: str, role: str, message: str, 
                       message_id: Optional[int] = None, usage: Optional[Dict] = None):
        """Log individual chat messages"""
        timestamp = datetime.now().isoformat()
        
        message_info = {
            "timestamp": timestamp,
            "event": "CHAT_MESSAGE",
            "chat_session_id": chat_session_id,
            "role": role,
            "message": message,
            "message_id": message_id,
            "usage": usage or {}
        }
        
        # Update session data
        if chat_session_id in self.session_data:
            self.session_data[chat_session_id].setdefault("messages", []).append(message_info)
        
        # Pretty print for console
        icon = "👤" if role == "user" else "🤖"
        print(f"{icon} [{role.upper()}] {message}")
        
        if usage:
            print(f"📊 Token Usage: {usage}")
    
    def log_session_end(self, chat_session_id: str, redirect_url: str):
        """Log session completion"""
        timestamp = datetime.now().isoformat()
        
        end_info = {
            "timestamp": timestamp,
            "event": "SESSION_END",
            "chat_session_id": chat_session_id,
            "redirect_url": redirect_url,
            "status": "SESSION_COMPLETED"
        }
        
        # Update session data
        if chat_session_id in self.session_data:
            self.session_data[chat_session_id]["status"] = "COMPLETED"
            self.session_data[chat_session_id]["ended_at"] = timestamp
        
        # Pretty print for console
        self._print_session_header("SESSION ENDED", chat_session_id)
        print(f"🔗 Redirect URL: {redirect_url}")
        print("=" * 60)
    
    def log_error(self, chat_session_id: str, error_type: str, error_details: str):
        """Log errors with context"""
        timestamp = datetime.now().isoformat()
        
        error_info = {
            "timestamp": timestamp,
            "event": "ERROR",
            "chat_session_id": chat_session_id,
            "error_type": error_type,
            "error_details": error_details
        }
        
        # Pretty print for console
        self._print_session_header("ERROR", chat_session_id)
        print(f"❌ {error_type}: {error_details}")
        print("=" * 60)
    
    def _print_session_header(self, event: str, chat_session_id: str):
        """Print formatted session header"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n🔍 [{timestamp}] {event} - Session: {chat_session_id}")
        print("-" * 40)
    
    def get_session_summary(self, chat_session_id: str) -> Optional[Dict[str, Any]]:
        """Get complete summary of a session"""
        return self.session_data.get(chat_session_id)
    
    def get_all_sessions(self) -> Dict[str, Dict[str, Any]]:
        """Get all tracked sessions"""
        return self.session_data
    
    def export_session_data(self, chat_session_id: str, format: str = "json") -> str:
        """Export session data in specified format"""
        session_data = self.get_session_summary(chat_session_id)
        if not session_data:
            return "{}"
        
        if format == "json":
            return json.dumps(session_data, indent=2)
        elif format == "ss":
            return self._format_ss_output(session_data)
        else:
            return str(session_data)
    
    def _format_ss_output(self, session_data: Dict[str, Any]) -> str:
        """Format session data like 'ss' for easy reading"""
        output = []
        
        # Header
        output.append("🔍 CHATBOT SESSION SUMMARY")
        output.append("=" * 50)
        output.append(f"Session ID: {session_data.get('chat_session_id', 'N/A')}")
        output.append(f"Timestamp: {session_data.get('timestamp', 'N/A')}")
        output.append(f"Status: {session_data.get('status', 'ACTIVE')}")
        output.append("")
        
        # Participant Info
        payload = session_data.get('payload', {})
        output.append("👤 PARTICIPANT INFO:")
        output.append(f"  PID: {payload.get('pid', 'N/A')}")
        output.append(f"  Study ID: {payload.get('study_id', 'N/A')}")
        output.append(f"  Client Metadata: {payload.get('client_metadata', {})}")
        output.append("")
        
        # Session Info
        output.append("🔧 SESSION INFO:")
        output.append(f"  Condition ID: {session_data.get('condition_id', 'N/A')}")
        output.append(f"  Experiment ID: {payload.get('experiment_id', 'N/A')}")
        output.append("")
        
        # Messages
        messages = session_data.get('messages', [])
        if messages:
            output.append("💬 MESSAGES:")
            for i, msg in enumerate(messages, 1):
                icon = "👤" if msg.get('role') == 'user' else "🤖"
                output.append(f"  {i}. {icon} [{msg.get('role', 'unknown').upper()}]: {msg.get('message', 'N/A')}")
                
                if msg.get('usage'):
                    output.append(f"     📊 Usage: {msg.get('usage')}")
        
        output.append("=" * 50)
        output.append("")
        
        return "\n".join(output)


# Global session logger instance
_session_logger = None


def get_session_logger(db: Session) -> SessionLogger:
    """Get or create global session logger instance"""
    global _session_logger
    if _session_logger is None:
        _session_logger = SessionLogger(db)
    return _session_logger


def log_all_active_sessions(db: Session):
    """Log all currently active sessions in the database"""
    sessions = db.exec(select(models.ChatSession).where(models.ChatSession.status == "active")).all()
    
    print("\n🔍 ALL ACTIVE SESSIONS")
    print("=" * 50)
    
    for session in sessions:
        print(f"📋 Session {session.id}:")
        print(f"  Participant ID: {session.participant_id}")
        print(f"  Status: {session.status}")
        print(f"  Started: {session.started_at}")
        print(f"  Messages: {len([m for m in session.messages]) if hasattr(session, 'messages') else 0} messages")
    
    print("=" * 50)
    print(f"Total Active Sessions: {len(sessions)}")
    print("")
