"""
Session storage service for managing chat history persistence.
Uses file-based JSON storage with user segregation.
"""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from app.models.schemas import ChatSession, ChatHistoryItem, ChatMessage, TableData, TableColumn, ChatAttachment


class SessionStorage:
    """File-based session storage manager with user segregation."""

    def __init__(self, data_dir: str = "./data/sessions"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _user_dir(self, user_id: str) -> Path:
        """Get or create user-specific directory."""
        # Sanitize user_id for filesystem safety
        safe_user_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in user_id)
        user_dir = self.data_dir / safe_user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    def _index_file(self, user_id: str) -> Path:
        """Get path to user's index file."""
        return self._user_dir(user_id) / "index.json"

    def _ensure_index(self, user_id: str):
        """Ensure user's index file exists."""
        index_file = self._index_file(user_id)
        if not index_file.exists():
            index_file.write_text(json.dumps([], indent=2))

    def _load_index(self, user_id: str) -> List[dict]:
        """Load user's session index."""
        self._ensure_index(user_id)
        return json.loads(self._index_file(user_id).read_text())

    def _save_index(self, user_id: str, index: List[dict]):
        """Save user's session index."""
        self._index_file(user_id).write_text(json.dumps(index, indent=2))

    def _session_file(self, user_id: str, session_id: str) -> Path:
        """Get path to session file."""
        return self._user_dir(user_id) / f"{session_id}.json"

    def create_session(self, user_id: str, title: str = "New Chat") -> ChatSession:
        """Create a new chat session for a user."""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()

        session = ChatSession(
            session_id=session_id,
            title=title,
            messages=[],
            created_at=now,
            updated_at=now,
            user_id=user_id,
        )

        # Save session file
        self._save_session(user_id, session)

        # Update index
        index = self._load_index(user_id)
        index.append({
            "session_id": session_id,
            "title": title,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "message_count": 0
        })
        self._save_index(user_id, index)

        return session

    def _save_session(self, user_id: str, session: ChatSession):
        """Save session to file."""
        session_file = self._session_file(user_id, session.session_id)
        session_data = {
            "session_id": session.session_id,
            "title": session.title,
            "title_generated": session.title_generated,
            "greeted": session.greeted,
            "user_id": user_id,
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat(),
                    **({"tables": [
                        {
                            "columns": [{"header": col.header, "accessor": col.accessor} for col in table.columns],
                            "rows": table.rows
                        } for table in msg.tables
                    ]} if msg.tables else {}),
                    **({"attachments": [
                        {
                            "id": att.id,
                            "name": att.name,
                            "mime_type": att.mime_type,
                            "size": att.size,
                            "data": att.data
                        } for att in msg.attachments
                    ]} if msg.attachments else {})
                }
                for msg in session.messages
            ],
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat()
        }
        session_file.write_text(json.dumps(session_data, indent=2))

    def get_session(self, user_id: str, session_id: str) -> Optional[ChatSession]:
        """Get a specific session by ID for a user."""
        session_file = self._session_file(user_id, session_id)
        if not session_file.exists():
            return None

        data = json.loads(session_file.read_text())

        # Parse messages
        messages = []
        for msg_data in data["messages"]:
            msg = ChatMessage(
                role=msg_data["role"],
                content=msg_data["content"],
                timestamp=datetime.fromisoformat(msg_data["timestamp"])
            )
            # Add tables if present
            if "tables" in msg_data:
                msg.tables = [
                    TableData(
                        columns=[TableColumn(**col) for col in table["columns"]],
                        rows=table["rows"]
                    )
                    for table in msg_data["tables"]
                ]
            # Add attachments if present
            if "attachments" in msg_data:
                msg.attachments = [
                    ChatAttachment(**att)
                    for att in msg_data["attachments"]
                ]
            messages.append(msg)

        return ChatSession(
            session_id=data["session_id"],
            title=data["title"],
            messages=messages,
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            title_generated=data.get("title_generated", False),
            greeted=data.get("greeted", False),
            user_id=data.get("user_id", user_id),
        )

    def list_sessions(self, user_id: str) -> List[ChatHistoryItem]:
        """List all sessions with metadata for a user."""
        index = self._load_index(user_id)

        # Convert to ChatHistoryItem objects
        items = []
        for entry in index:
            # Get last message from session file if exists
            session = self.get_session(user_id, entry["session_id"])
            last_message = ""
            if session and session.messages:
                last_message = session.messages[-1].content[:100]  # First 100 chars

            items.append(ChatHistoryItem(
                session_id=entry["session_id"],
                title=entry["title"],
                last_message=last_message,
                timestamp=datetime.fromisoformat(entry["updated_at"]),
                message_count=entry.get("message_count", 0)
            ))

        # Sort by timestamp descending (newest first)
        items.sort(key=lambda x: x.timestamp, reverse=True)
        return items

    def update_session(self, user_id: str, session: ChatSession):
        """Update an existing session."""
        session.updated_at = datetime.utcnow()
        self._save_session(user_id, session)

        # Update index
        index = self._load_index(user_id)
        for entry in index:
            if entry["session_id"] == session.session_id:
                entry["title"] = session.title
                entry["updated_at"] = session.updated_at.isoformat()
                entry["message_count"] = len(session.messages)
                break
        self._save_index(user_id, index)

    def delete_session(self, user_id: str, session_id: str) -> bool:
        """Delete a session for a user."""
        session_file = self._session_file(user_id, session_id)
        if not session_file.exists():
            return False

        # Delete session file
        session_file.unlink()

        # Update index
        index = self._load_index(user_id)
        index = [entry for entry in index if entry["session_id"] != session_id]
        self._save_index(user_id, index)

        return True

    def add_message(self, user_id: str, session_id: str, message: ChatMessage) -> bool:
        """Add a message to a session."""
        session = self.get_session(user_id, session_id)
        if not session:
            return False

        session.messages.append(message)
        self.update_session(user_id, session)
        return True


# Global instance
_storage: Optional[SessionStorage] = None


def get_storage() -> SessionStorage:
    """Get or create the global storage instance."""
    global _storage
    if _storage is None:
        _storage = SessionStorage()
    return _storage
