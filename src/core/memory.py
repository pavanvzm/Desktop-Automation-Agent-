from __future__ import annotations
"""Hybrid memory system with short-term and long-term (RAG) components."""

import json
import os
import sqlite3
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# NumPy is optional - used for embeddings if available
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    np = None

from .state import Message, MessageRole, ScreenContext


@dataclass
class MemoryEntry:
    """A single entry in memory."""

    id: str
    content: str
    metadata: dict[str, Any]
    embedding: list[float] | None = None
    created_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "access_count": self.access_count,
            "last_accessed": self.last_accessed.isoformat(),
        }


class ShortTermMemory:
    """
    In-memory conversation buffer for short-term context.

    Maintains a sliding window of recent conversation and current
    task context.
    """

    def __init__(self, max_messages: int = 50, max_turns: int = 10):
        self.max_messages = max_messages
        self.max_turns = max_turns
        self._messages: deque[Message] = deque(maxlen=max_messages)
        self._current_task_context: dict[str, Any] = {}
        self._task_history: list[dict] = deque(maxlen=max_turns)

    def add_message(self, message: Message) -> None:
        """Add a message to the conversation buffer."""
        self._messages.append(message)

    def get_recent_messages(self, n: int | None = None) -> list[Message]:
        """Get the n most recent messages. If n is None, return all."""
        if n is None:
            return list(self._messages)
        return list(self._messages)[-n:]

    def get_context_for_llm(self, include_system: bool = True) -> str:
        """Format context for passing to LLM."""
        context_parts = []

        if include_system:
            context_parts.append("## Recent Conversation\n")

        for msg in self._messages:
            role = msg.role.value.capitalize()
            context_parts.append(f"**{role}**: {msg.content}")

        if self._current_task_context:
            context_parts.append("\n## Current Task Context")
            context_parts.append(json.dumps(self._current_task_context, indent=2))

        return "\n".join(context_parts)

    def set_task_context(self, context: dict[str, Any]) -> None:
        """Set the current task context."""
        self._current_task_context = context

    def add_completed_task(self, task: dict) -> None:
        """Record a completed task for future reference."""
        task["completed_at"] = datetime.now().isoformat()
        self._task_history.append(task)

    def clear(self) -> None:
        """Clear all short-term memory."""
        self._messages.clear()
        self._current_task_context = {}


class LongTermMemory:
    """
    Vector-based long-term memory using ChromaDB.

    Stores user preferences, past task solutions, and
    application-specific knowledge.
    """

    def __init__(
        self,
        persist_directory: str | Path | None = None,
        collection_name: str = "agent_memory",
    ):
        self.persist_directory = persist_directory or self._get_default_dir()
        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self._initialize()

    def _get_default_dir(self) -> Path:
        """Get the default persistence directory."""
        base = Path(os.environ.get("APPDATA", ".")) / "Win11-OmniAgent" / "vectors"
        base.mkdir(parents=True, exist_ok=True)
        return base

    def _initialize(self) -> None:
        """Initialize the vector database."""
        try:
            import chromadb

            self._client = chromadb.PersistentClient(path=str(self.persist_directory))
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "Win11-OmniAgent long-term memory"},
            )
        except ImportError:
            # ChromaDB not available, use SQLite fallback
            self._use_sqlite_fallback = True
            self._init_sqlite_fallback()

    def _init_sqlite_fallback(self) -> None:
        """Initialize SQLite fallback for when ChromaDB is unavailable."""
        self._sqlite_path = self.persist_directory / "memory.db"
        conn = sqlite3.connect(str(self._sqlite_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_entries (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                metadata TEXT,
                created_at TEXT,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT
            )
            """
        )
        conn.commit()
        conn.close()

    def add(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        embedding: list[float] | None = None,
    ) -> str:
        """Add an entry to long-term memory."""
        entry = MemoryEntry(
            id=f"mem_{datetime.now().timestamp()}",
            content=content,
            metadata=metadata or {},
            embedding=embedding,
        )

        if hasattr(self, "_use_sqlite_fallback"):
            conn = sqlite3.connect(str(self._sqlite_path))
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO memory_entries (id, content, metadata, created_at, access_count, last_accessed) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    entry.id,
                    entry.content,
                    json.dumps(entry.metadata),
                    entry.created_at.isoformat(),
                    entry.access_count,
                    entry.last_accessed.isoformat(),
                ),
            )
            conn.commit()
            conn.close()
        else:
            self._collection.add(
                ids=[entry.id],
                documents=[entry.content],
                metadatas=[entry.metadata],
            )

        return entry.id

    def search(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[dict]:
        """Search long-term memory for relevant entries."""
        if hasattr(self, "_use_sqlite_fallback"):
            # Simple keyword fallback
            conn = sqlite3.connect(str(self._sqlite_path))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, content, metadata, access_count FROM memory_entries WHERE content LIKE ? ORDER BY access_count DESC LIMIT ?",
                (f"%{query}%", n_results),
            )
            results = [
                {
                    "id": row[0],
                    "content": row[1],
                    "metadata": json.loads(row[2]) if row[2] else {},
                    "access_count": row[3],
                }
                for row in cursor.fetchall()
            ]
            conn.close()
            return results

        try:
            import chromadb.utilsembedding_functions as embedding_functions

            results = self._collection.query(
                query_texts=[query],
                n_results=n_results,
                where=filter_metadata,
            )

            return [
                {
                    "id": results["ids"][0][i],
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if "distances" in results else None,
                }
                for i in range(len(results["ids"][0]))
            ]
        except Exception:
            return []

    def update_access(self, entry_id: str) -> None:
        """Update access statistics for an entry."""
        if hasattr(self, "_use_sqlite_fallback"):
            conn = sqlite3.connect(str(self._sqlite_path))
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE memory_entries SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
                (datetime.now().isoformat(), entry_id),
            )
            conn.commit()
            conn.close()

    def delete(self, entry_id: str) -> bool:
        """Delete an entry from memory."""
        if hasattr(self, "_use_sqlite_fallback"):
            conn = sqlite3.connect(str(self._sqlite_path))
            cursor = conn.cursor()
            cursor.execute("DELETE FROM memory_entries WHERE id = ?", (entry_id,))
            deleted = cursor.rowcount > 0
            conn.commit()
            conn.close()
            return deleted

        try:
            self._collection.delete(ids=[entry_id])
            return True
        except Exception:
            return False


class ScreenContextMemory:
    """
    Manages screen context for grounding the LLM in current GUI state.
    """

    def __init__(self, max_screenshots: int = 5, retention_minutes: int = 5):
        self.max_screenshots = max_screenshots
        self.retention_minutes = retention_minutes
        self._screenshots: deque[ScreenContext] = deque(maxlen=max_screenshots)
        self._ui_trees: list[dict] = []
        self._cleanup_old_entries()

    def add_screen_context(self, context: ScreenContext) -> None:
        """Add a new screen context."""
        self._screenshots.append(context)
        if context.ui_tree:
            self._ui_trees.append(context.ui_tree)
            # Keep only recent UI trees
            self._ui_trees = self._ui_trees[-20:]

    def get_latest_context(self) -> ScreenContext | None:
        """Get the most recent screen context."""
        if self._screenshots:
            return self._screenshots[-1]
        return None

    def get_context_for_llm(self, include_screenshot_path: bool = False) -> str:
        """Format screen context for LLM."""
        context = self.get_latest_context()
        if not context:
            return "No screen context available."

        parts = []
        if context.active_window:
            parts.append(f"**Active Window**: {context.active_window}")

        if context.ui_tree:
            parts.append("\n**UI Structure** (top-level elements):")
            parts.append(self._format_ui_tree(context.ui_tree, max_depth=3))

        return "\n".join(parts)

    def _format_ui_tree(self, tree: dict, max_depth: int = 3, current_depth: int = 0) -> str:
        """Format UI tree for display."""
        if current_depth >= max_depth:
            return "..."

        lines = []
        name = tree.get("name", tree.get("ControlType", "Unknown"))
        role = tree.get("role", "")
        value = tree.get("value", "")

        indent = "  " * current_depth
        line = f"{indent}- {name}"
        if role:
            line += f" [{role}]"
        if value:
            line += f": '{value}'"
        lines.append(line)

        children = tree.get("children", [])
        for child in children[:10]:  # Limit children
            lines.append(self._format_ui_tree(child, max_depth, current_depth + 1))

        return "\n".join(lines)

    def _cleanup_old_entries(self) -> None:
        """Remove entries older than retention period."""
        cutoff = datetime.now() - timedelta(minutes=self.retention_minutes)
        while self._screenshots and self._screenshots[0].timestamp < cutoff:
            self._screenshots.popleft()


class MemorySystem:
    """
    Unified memory system combining short-term and long-term memory.

    Provides a seamless interface for the agent to access both
    conversation context and stored knowledge.
    """

    def __init__(
        self,
        persist_directory: str | Path | None = None,
        max_short_term_messages: int = 50,
    ):
        self.short_term = ShortTermMemory(max_messages=max_short_term_messages)
        self.long_term = LongTermMemory(persist_directory=persist_directory)
        self.screen_context = ScreenContextMemory()

    def add_user_message(self, content: str) -> None:
        """Add a user message to short-term memory."""
        self.short_term.add_message(Message(role=MessageRole.USER, content=content))

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message to short-term memory."""
        self.short_term.add_message(Message(role=MessageRole.ASSISTANT, content=content))

    def add_tool_result(self, tool_name: str, result: str, success: bool = True) -> None:
        """Add a tool result to short-term memory."""
        role = MessageRole.TOOL if success else MessageRole.SYSTEM
        self.short_term.add_message(
            Message(
                role=role,
                content=f"[{tool_name}] {result}",
                metadata={"tool_name": tool_name, "success": success},
            )
        )

    def get_full_context(self, include_screen: bool = True, include_memory: bool = True) -> str:
        """Get formatted context for LLM."""
        parts = []

        # Short-term context
        parts.append(self.short_term.get_context_for_llm())

        # Screen context
        if include_screen:
            screen = self.screen_context.get_context_for_llm()
            if screen and screen != "No screen context available.":
                parts.append(f"\n## Current Screen\n{screen}")

        # Long-term memory (if relevant)
        if include_memory:
            # Extract potential search terms from recent conversation
            recent = self.short_term.get_recent_messages(3)
            if recent:
                search_query = " ".join([m.content for m in recent if m.content])[-200:]
                memories = self.long_term.search(search_query, n_results=3)
                if memories:
                    parts.append("\n## Related Past Experiences")
                    for mem in memories:
                        parts.append(f"- {mem['content'][:150]}...")

        return "\n\n".join(parts)

    def store_learning(self, task: str, solution: str, outcome: str) -> None:
        """Store a successful task solution for future reference."""
        self.long_term.add(
            content=f"Task: {task}\nSolution: {solution}\nOutcome: {outcome}",
            metadata={
                "type": "task_solution",
                "task": task,
                "outcome": outcome,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def store_preference(self, preference_type: str, value: str, context: str = "") -> None:
        """Store a user preference."""
        self.long_term.add(
            content=f"{preference_type}: {value}\nContext: {context}",
            metadata={
                "type": "preference",
                "preference_type": preference_type,
                "context": context,
                "timestamp": datetime.now().isoformat(),
            },
        )
