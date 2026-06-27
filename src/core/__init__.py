"""
Win11-OmniAgent Core Package

This package contains the core agentic architecture including:
- ReAct/Plan-and-Solve agent loop
- Tool calling protocol
- Memory system (short-term + long-term RAG)
- State management
"""

from .agent import OmniAgent
from .state import AgentState, Message, Turn
from .memory import MemorySystem, ShortTermMemory, LongTermMemory, ScreenContext
from .tool_schema import Tool, ToolCall, ToolResult, ToolRegistry
from .exceptions import AgentError, ToolExecutionError, SafetyViolationError

__all__ = [
    "OmniAgent",
    "AgentState",
    "Message",
    "Turn",
    "MemorySystem",
    "ShortTermMemory",
    "LongTermMemory",
    "ScreenContext",
    "Tool",
    "ToolCall",
    "ToolResult",
    "ToolRegistry",
    "AgentError",
    "ToolExecutionError",
    "SafetyViolationError",
]

__version__ = "0.1.0"