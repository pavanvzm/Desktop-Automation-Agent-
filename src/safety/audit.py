"""Immutable audit trail for all agent actions."""

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from ..core.tool_schema import ToolCall, ToolResult


@dataclass
class AuditEntry:
    """A single audit log entry."""

    id: str
    timestamp: datetime
    action_type: str  # tool_call, tool_result, user_message, agent_response
    action_name: str
    details: dict
    user_id: str | None
    session_id: str | None

    # Integrity
    previous_hash: str | None
    entry_hash: str

    # Optional screenshot
    screenshot_hash: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "action_type": self.action_type,
            "action_name": self.action_name,
            "details": self.details,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "previous_hash": self.previous_hash,
            "entry_hash": self.entry_hash,
            "screenshot_hash": self.screenshot_hash,
        }


class AuditLogger:
    """
    Immutable audit trail logger.

    Logs every action with cryptographic integrity verification.
    Entries are chained with hash links to prevent tampering.
    """

    def __init__(
        self,
        db_path: str | Path | None = None,
        user_id: str | None = None,
    ):
        if db_path is None:
            db_path = Path.home() / ".win11-omniagent" / "audit.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.user_id = user_id
        self._init_db()
        self._last_hash = self._get_last_hash()

    def _init_db(self) -> None:
        """Initialize the audit database."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    action_name TEXT NOT NULL,
                    details TEXT NOT NULL,
                    user_id TEXT,
                    session_id TEXT,
                    previous_hash TEXT,
                    entry_hash TEXT NOT NULL,
                    screenshot_hash TEXT
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_log(timestamp)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_action ON audit_log(action_type, action_name)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_session ON audit_log(session_id)
            """)
            conn.commit()

    def _compute_hash(self, entry_data: dict) -> str:
        """Compute SHA-256 hash of entry data."""
        data_str = json.dumps(entry_data, sort_keys=True, default=str)
        return hashlib.sha256(data_str.encode()).hexdigest()

    def _get_last_hash(self) -> str | None:
        """Get the hash of the last entry."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT entry_hash FROM audit_log ORDER BY timestamp DESC LIMIT 1"
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def log(
        self,
        action_type: str,
        action_name: str,
        details: dict,
        session_id: str | None = None,
        screenshot_hash: str | None = None,
    ) -> AuditEntry:
        """Log an action to the audit trail."""
        import uuid

        entry = AuditEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            action_type=action_type,
            action_name=action_name,
            details=details,
            user_id=self.user_id,
            session_id=session_id,
            previous_hash=self._last_hash,
            entry_hash="",  # Will be computed
            screenshot_hash=screenshot_hash,
        )

        # Compute hash including previous hash (chain)
        entry_data = {
            "id": entry.id,
            "timestamp": entry.timestamp.isoformat(),
            "action_type": entry.action_type,
            "action_name": entry.action_name,
            "details": entry.details,
            "user_id": entry.user_id,
            "session_id": entry.session_id,
            "previous_hash": entry.previous_hash,
            "screenshot_hash": entry.screenshot_hash,
        }
        entry.entry_hash = self._compute_hash(entry_data)

        # Store in database
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO audit_log (
                    id, timestamp, action_type, action_name, details,
                    user_id, session_id, previous_hash, entry_hash, screenshot_hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.timestamp.isoformat(),
                    entry.action_type,
                    entry.action_name,
                    json.dumps(entry.details),
                    entry.user_id,
                    entry.session_id,
                    entry.previous_hash,
                    entry.entry_hash,
                    entry.screenshot_hash,
                )
            )
            conn.commit()

        self._last_hash = entry.entry_hash
        return entry

    def log_tool_call(
        self,
        tool_call: ToolCall,
        session_id: str | None = None,
    ) -> AuditEntry:
        """Log a tool call."""
        return self.log(
            action_type="tool_call",
            action_name=tool_call.tool.name,
            details={
                "tool_id": tool_call.id,
                "arguments": tool_call.arguments,
                "risk_level": tool_call.tool.risk_level.value,
            },
            session_id=session_id,
        )

    def log_tool_result(
        self,
        tool_call_id: str,
        tool_name: str,
        result: ToolResult,
        session_id: str | None = None,
    ) -> AuditEntry:
        """Log a tool execution result."""
        return self.log(
            action_type="tool_result",
            action_name=tool_name,
            details={
                "tool_call_id": tool_call_id,
                "success": result.success,
                "execution_time_ms": result.execution_time_ms,
                "error": result.error,
            },
            session_id=session_id,
            screenshot_hash=result.screenshot_path,
        )

    def log_user_message(
        self,
        message: str,
        session_id: str | None = None,
    ) -> AuditEntry:
        """Log a user message."""
        return self.log(
            action_type="user_message",
            action_name="user_input",
            details={"message_length": len(message)},
            session_id=session_id,
        )

    def log_agent_response(
        self,
        response: str,
        session_id: str | None = None,
    ) -> AuditEntry:
        """Log an agent response."""
        return self.log(
            action_type="agent_response",
            action_name="agent_output",
            details={"response_length": len(response)},
            session_id=session_id,
        )

    def verify_integrity(self) -> tuple[bool, list[str]]:
        """Verify the integrity of the audit log."""
        errors = []
        previous_hash = None

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM audit_log ORDER BY timestamp")

            for row in cursor:
                (
                    entry_id,
                    timestamp,
                    action_type,
                    action_name,
                    details,
                    user_id,
                    session_id,
                    prev_hash,
                    entry_hash,
                    screenshot_hash,
                ) = row

                # Check hash chain
                if prev_hash != previous_hash:
                    errors.append(f"Hash chain broken at entry {entry_id}")

                # Verify entry hash
                entry_data = {
                    "id": entry_id,
                    "timestamp": timestamp,
                    "action_type": action_type,
                    "action_name": action_name,
                    "details": json.loads(details),
                    "user_id": user_id,
                    "session_id": session_id,
                    "previous_hash": prev_hash,
                    "screenshot_hash": screenshot_hash,
                }
                computed_hash = self._compute_hash(entry_data)

                if computed_hash != entry_hash:
                    errors.append(f"Entry hash mismatch at entry {entry_id}")

                previous_hash = entry_hash

        return len(errors) == 0, errors

    def query(
        self,
        action_type: str | None = None,
        action_name: str | None = None,
        session_id: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Query audit log entries."""
        conditions = []
        params = []

        if action_type:
            conditions.append("action_type = ?")
            params.append(action_type)

        if action_name:
            conditions.append("action_name = ?")
            params.append(action_name)

        if session_id:
            conditions.append("session_id = ?")
            params.append(session_id)

        if start_time:
            conditions.append("timestamp >= ?")
            params.append(start_time.isoformat())

        if end_time:
            conditions.append("timestamp <= ?")
            params.append(end_time.isoformat())

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT * FROM audit_log
                WHERE {where_clause}
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                params,
            )

            entries = []
            for row in cursor:
                (
                    entry_id,
                    timestamp,
                    action_type,
                    action_name,
                    details,
                    user_id,
                    session_id,
                    prev_hash,
                    entry_hash,
                    screenshot_hash,
                ) = row

                entries.append(AuditEntry(
                    id=entry_id,
                    timestamp=datetime.fromisoformat(timestamp),
                    action_type=action_type,
                    action_name=action_name,
                    details=json.loads(details),
                    user_id=user_id,
                    session_id=session_id,
                    previous_hash=prev_hash,
                    entry_hash=entry_hash,
                    screenshot_hash=screenshot_hash,
                ))

            return entries

    def get_session_history(self, session_id: str) -> list[AuditEntry]:
        """Get all entries for a session."""
        return self.query(session_id=session_id, limit=1000)

    def export_to_json(self, path: str | Path) -> None:
        """Export audit log to JSON file."""
        entries = self.query(limit=100000)
        data = [e.to_dict() for e in entries]
        Path(path).write_text(json.dumps(data, indent=2))