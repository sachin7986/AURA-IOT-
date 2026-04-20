"""
AURA Chat History Manager
---------------------------
Async MongoDB (Motor) backend for persistent chat session storage.
Handles: create, append, list, search, delete, and auto-cleanup.
"""

import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any

import motor.motor_asyncio
from pymongo import DESCENDING

logger = logging.getLogger("aura.core.chat_history")

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = "aura_db"
SESSIONS_COLLECTION = "sessions"


class ChatHistoryManager:
    """
    Async MongoDB manager for AURA chat sessions.
    Each session contains metadata + a list of messages.
    """

    def __init__(self):
        self._client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None
        self._db = None
        self._sessions = None

    async def connect(self):
        """Initialize Motor client connection."""
        try:
            self._client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI, serverSelectionTimeoutMS=5000)
            # Trigger a real connection to confirm it works
            await self._client.admin.command("ping")
            self._db = self._client[DB_NAME]
            self._sessions = self._db[SESSIONS_COLLECTION]
            # Indexes for fast search and cleanup queries
            await self._sessions.create_index("session_id", unique=True)
            await self._sessions.create_index("updated_at")
            await self._sessions.create_index([("title", "text"), ("messages.content", "text")])
            logger.info(f"✅ Connected to MongoDB at: {MONGO_URI}")
        except Exception as e:
            logger.error(f"❌ MongoDB connection failed: {e}")
            self._sessions = None

    async def disconnect(self):
        """Close Motor client."""
        if self._client:
            self._client.close()
            logger.info("MongoDB client closed.")

    def _is_connected(self) -> bool:
        return self._sessions is not None

    # -----------------------------------------------------------------------
    # Session CRUD
    # -----------------------------------------------------------------------

    async def create_session(self, session_id: Optional[str] = None, title: str = "New Chat") -> str:
        """
        Create a new session document. Returns the session_id.
        """
        if not self._is_connected():
            logger.warning("MongoDB not connected — skipping create_session")
            return session_id or str(uuid.uuid4())

        sid = session_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        doc = {
            "session_id": sid,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }
        try:
            await self._sessions.update_one(
                {"session_id": sid},
                {"$setOnInsert": doc},
                upsert=True
            )
        except Exception as e:
            logger.error(f"create_session error: {e}")
        return sid

    async def append_message(self, session_id: str, role: str, content: str):
        """
        Append a message to an existing session. Auto-titles from first user message.
        """
        if not self._is_connected():
            return

        now = datetime.now(timezone.utc)
        message = {
            "role": role,
            "content": content,
            "timestamp": now.isoformat(),
        }
        try:
            # Update the session document
            result = await self._sessions.update_one(
                {"session_id": session_id},
                {
                    "$push": {"messages": message},
                    "$set": {"updated_at": now},
                }
            )
            # If session didn't exist yet, create it first then retry
            if result.matched_count == 0:
                await self.create_session(session_id)
                await self._sessions.update_one(
                    {"session_id": session_id},
                    {
                        "$push": {"messages": message},
                        "$set": {"updated_at": now},
                    }
                )

            # Auto-title: use the first user message as the session title (truncated)
            if role == "user":
                session = await self._sessions.find_one({"session_id": session_id})
                if session:
                    user_messages = [m for m in session.get("messages", []) if m["role"] == "user"]
                    if len(user_messages) == 1:
                        # This is the very first user message — set as title
                        title = content[:60] + ("..." if len(content) > 60 else "")
                        await self._sessions.update_one(
                            {"session_id": session_id},
                            {"$set": {"title": title}}
                        )
        except Exception as e:
            logger.error(f"append_message error: {e}")

    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Return a full session doc (with all messages)."""
        if not self._is_connected():
            return None
        try:
            doc = await self._sessions.find_one({"session_id": session_id})
            if doc:
                doc["_id"] = str(doc["_id"])  # Serialize ObjectId
            return doc
        except Exception as e:
            logger.error(f"get_session error: {e}")
            return None

    async def list_sessions(self, query: str = "") -> List[Dict[str, Any]]:
        """
        List all sessions ordered by most recent first.
        If query is provided, filter by title or message content (text search).
        """
        if not self._is_connected():
            return []
        try:
            filter_q: Dict = {}
            if query.strip():
                # Regex search on title and messages content
                import re
                regex = {"$regex": re.escape(query.strip()), "$options": "i"}
                filter_q = {
                    "$or": [
                        {"title": regex},
                        {"messages.content": regex},
                    ]
                }

            cursor = self._sessions.find(
                filter_q,
                {"session_id": 1, "title": 1, "created_at": 1, "updated_at": 1,
                 "messages": {"$slice": -1}}  # Only return last message as preview
            ).sort("updated_at", DESCENDING)

            sessions = []
            async for doc in cursor:
                doc["_id"] = str(doc["_id"])
                # Serialize datetimes
                if "created_at" in doc and isinstance(doc["created_at"], datetime):
                    doc["created_at"] = doc["created_at"].isoformat()
                if "updated_at" in doc and isinstance(doc["updated_at"], datetime):
                    doc["updated_at"] = doc["updated_at"].isoformat()
                # Extract preview from last message
                msgs = doc.get("messages", [])
                doc["preview"] = msgs[-1]["content"][:80] if msgs else ""
                doc.pop("messages", None)
                sessions.append(doc)
            return sessions
        except Exception as e:
            logger.error(f"list_sessions error: {e}")
            return []

    async def delete_session(self, session_id: str) -> bool:
        """Delete a single session by ID."""
        if not self._is_connected():
            return False
        try:
            result = await self._sessions.delete_one({"session_id": session_id})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"delete_session error: {e}")
            return False

    async def delete_all_sessions(self) -> int:
        """Delete ALL sessions. Returns count deleted."""
        if not self._is_connected():
            return 0
        try:
            result = await self._sessions.delete_many({})
            return result.deleted_count
        except Exception as e:
            logger.error(f"delete_all_sessions error: {e}")
            return 0

    async def cleanup_old_sessions(self, days: int = 30) -> int:
        """Auto-delete sessions older than `days` days. Returns count deleted."""
        if not self._is_connected():
            return 0
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            result = await self._sessions.delete_many({"updated_at": {"$lt": cutoff}})
            deleted = result.deleted_count
            if deleted:
                logger.info(f"Auto-cleanup: deleted {deleted} sessions older than {days} days")
            return deleted
        except Exception as e:
            logger.error(f"cleanup_old_sessions error: {e}")
            return 0


# Global singleton — imported everywhere
chat_history = ChatHistoryManager()
