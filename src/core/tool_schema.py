"""Tool calling protocol with strict JSON schemas."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Awaitable
import json
import uuid


class ActionRiskLevel(str, Enum):
    """Risk level for actions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ToolParameter:
    """Schema for a tool parameter."""

    name: str
    type: str  # "string", "number", "boolean", "object", "array"
    description: str
    required: bool = True
    default: Any = None
    enum: list[Any] | None = None
    minimum: float | None = None
    maximum: float | None = None

    def to_openai_schema(self) -> dict:
        """Convert to OpenAI function calling schema format."""
        schema: dict[str, Any] = {
            "type": self.type,
            "description": self.description,
        }

        if self.enum:
            schema["enum"] = self.enum
        if self.minimum is not None:
            schema["minimum"] = self.minimum
        if self.maximum is not None:
            schema["maximum"] = self.maximum

        return schema


@dataclass
class Tool:
    """
    Definition of a tool available to the agent.

    All tools MUST be defined with strict JSON schemas for type safety
    and validation. The agent outputs structured function calls, never
    raw code execution.
    """

    name: str
    description: str
    parameters: list[ToolParameter]
    risk_level: ActionRiskLevel = ActionRiskLevel.MEDIUM
    requires_confirmation: bool | None = None  # None = infer from risk level
    category: str = "general"
    examples: list[str] = field(default_factory=list)
    deprecated: bool = False
    deprecation_message: str | None = None

    def __post_init__(self):
        """Validate tool definition."""
        if not self.name.replace("_", "").isalnum():
            raise ValueError(f"Tool name must be alphanumeric with underscores: {self.name}")

        # Auto-set confirmation based on risk level if not specified
        if self.requires_confirmation is None:
            self.requires_confirmation = self.risk_level in [
                ActionRiskLevel.HIGH,
                ActionRiskLevel.CRITICAL,
            ]

    def to_openai_function(self) -> dict:
        """Convert to OpenAI function calling format."""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = param.to_openai_schema()
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    def validate_arguments(self, arguments: dict) -> tuple[bool, str | None]:
        """Validate arguments against the schema."""
        for param in self.parameters:
            if param.required and param.name not in arguments:
                return False, f"Missing required parameter: {param.name}"

            if param.name in arguments:
                value = arguments[param.name]

                # Type checking
                if param.type == "string" and not isinstance(value, str):
                    return False, f"Parameter '{param.name}' must be a string"
                elif param.type == "number" and not isinstance(value, (int, float)):
                    return False, f"Parameter '{param.name}' must be a number"
                elif param.type == "boolean" and not isinstance(value, bool):
                    return False, f"Parameter '{param.name}' must be a boolean"
                elif param.type == "array" and not isinstance(value, list):
                    return False, f"Parameter '{param.name}' must be an array"
                elif param.type == "object" and not isinstance(value, dict):
                    return False, f"Parameter '{param.name}' must be an object"

                # Enum validation
                if param.enum and value not in param.enum:
                    return False, f"Parameter '{param.name}' must be one of: {param.enum}"

                # Range validation
                if param.type == "number":
                    if param.minimum is not None and value < param.minimum:
                        return False, f"Parameter '{param.name}' must be >= {param.minimum}"
                    if param.maximum is not None and value > param.maximum:
                        return False, f"Parameter '{param.name}' must be <= {param.maximum}"

        return True, None


@dataclass
class ToolCall:
    """Represents a parsed tool call from the agent."""

    id: str
    tool: Tool
    arguments: dict[str, Any]
    raw_output: str | None = None  # Raw LLM output for debugging
    timestamp: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_llm_output(cls, tool: Tool, arguments: dict, raw_output: str | None = None) -> "ToolCall":
        """Create a ToolCall from LLM output."""
        return cls(
            id=str(uuid.uuid4()),
            tool=tool,
            arguments=arguments,
            raw_output=raw_output,
        )


@dataclass
class ToolResult:
    """Result of a tool execution."""

    tool_call_id: str
    tool_name: str
    success: bool
    result: Any = None
    error: str | None = None
    execution_time_ms: float = 0.0
    screenshot_path: str | None = None  # Optional screenshot after execution
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        """Convert to dictionary for logging."""
        return {
            "tool_call_id": self.tool_call_id,
            "tool_name": self.tool_name,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "screenshot_path": self.screenshot_path,
            "timestamp": self.timestamp.isoformat(),
        }

    def format_for_llm(self) -> str:
        """Format result for passing back to LLM."""
        if self.success:
            if isinstance(self.result, (dict, list)):
                return json.dumps(self.result, indent=2)
            return str(self.result)
        return f"Error: {self.error}"


class ToolRegistry:
    """Registry of all available tools."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}
        self._handlers: dict[str, Callable[..., Awaitable[Any]]] = {}

    def register(self, tool: Tool, handler: Callable[..., Awaitable[Any]]) -> None:
        """Register a tool with its handler."""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool
        self._handlers[tool.name] = handler

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def get_handler(self, name: str) -> Callable[..., Awaitable[Any]] | None:
        """Get a handler for a tool."""
        return self._handlers.get(name)

    def list_tools(self, category: str | None = None) -> list[Tool]:
        """List all registered tools, optionally filtered by category."""
        tools = list(self._tools.values())
        if category:
            tools = [t for t in tools if t.category == category]
        return [t for t in tools if not t.deprecated]

    def get_all_openai_functions(self) -> list[dict]:
        """Get all tools in OpenAI function calling format."""
        return [tool.to_openai_function() for tool in self.list_tools()]

    def __len__(self) -> int:
        return len(self._tools)


# Global registry instance
_global_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    """Get the global tool registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


def register_tool(tool: Tool) -> Callable:
    """Decorator to register a tool with its handler."""

    def decorator(func: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        registry = get_registry()
        registry.register(tool, func)
        return func

    return decorator