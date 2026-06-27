"""Agent state management and data models."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MessageRole(str, Enum):
    """Role of a message sender."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class TurnStatus(str, Enum):
    """Status of an agent turn."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    AWAITING_APPROVAL = "awaiting_approval"


class ActionRiskLevel(str, Enum):
    """Risk level for actions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Message:
    """A single message in the conversation."""

    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class ToolCall:
    """Represents a tool call made by the agent."""

    id: str
    name: str
    arguments: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    result: str | None = None
    error: str | None = None
    execution_time_ms: float | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments,
            "timestamp": self.timestamp.isoformat(),
            "result": self.result,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
        }


@dataclass
class Turn:
    """Represents a single turn in the agent loop."""

    id: str
    user_input: str
    status: TurnStatus = TurnStatus.IN_PROGRESS
    tool_calls: list[ToolCall] = field(default_factory=list)
    response: str | None = None
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "user_input": self.user_input,
            "status": self.status.value,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "response": self.response,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }


@dataclass
class ScreenContext:
    """Represents the current screen state."""

    screenshot_path: str | None = None
    ui_tree: dict | None = None
    active_window: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "screenshot_path": self.screenshot_path,
            "ui_tree": self.ui_tree,
            "active_window": self.active_window,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AgentState:
    """Complete state of the agent at any point in time."""

    # Conversation history
    messages: list[Message] = field(default_factory=list)

    # Current turn information
    current_turn: Turn | None = None

    # Screen context
    screen_context: ScreenContext | None = None

    # Execution tracking
    total_tool_calls: int = 0
    consecutive_failures: int = 0

    # Mode flags
    is_dry_run: bool = False
    is_confirm_mode: bool = True

    # Pending confirmations
    pending_confirmations: list[dict] = field(default_factory=list)

    def add_message(self, role: MessageRole, content: str, metadata: dict | None = None) -> None:
        """Add a message to the conversation history."""
        self.messages.append(Message(role=role, content=content, metadata=metadata or {}))

    def get_recent_messages(self, n: int = 10) -> list[Message]:
        """Get the n most recent messages."""
        return self.messages[-n:]

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "messages": [m.to_dict() for m in self.messages],
            "current_turn": self.current_turn.to_dict() if self.current_turn else None,
            "screen_context": self.screen_context.to_dict() if self.screen_context else None,
            "total_tool_calls": self.total_tool_calls,
            "consecutive_failures": self.consecutive_failures,
            "is_dry_run": self.is_dry_run,
            "is_confirm_mode": self.is_confirm_mode,
        }