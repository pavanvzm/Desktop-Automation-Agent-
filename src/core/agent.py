from __future__ import annotations
"""Main OmniAgent implementation with ReAct loop."""

import asyncio
import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Awaitable

from .exceptions import AgentError, CircuitBreakerOpenError, RateLimitExceededError, SafetyViolationError
from .memory import MemorySystem
from .state import AgentState, Message, MessageRole, Turn, TurnStatus, ScreenContext, ActionRiskLevel
from .tool_schema import Tool, ToolCall, ToolResult, ToolRegistry, get_registry


class AgentMode(str, Enum):
    """Operating mode of the agent."""

    ACTIVE = "active"
    DRY_RUN = "dry_run"  # Preview actions without executing
    CONFIRM = "confirm"  # Require confirmation for actions
    OFFLINE = "offline"  # Fallback mode with keyword matching


@dataclass
class AgentConfig:
    """Configuration for the agent."""

    # LLM settings
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o"
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096

    # Agent behavior
    max_iterations: int = 20
    max_tool_calls_per_turn: int = 10
    action_timeout_seconds: int = 30

    # Safety settings
    rate_limit_per_minute: int = 10
    circuit_breaker_threshold: int = 3
    confirm_by_default: bool = True

    # Memory settings
    memory_persist_dir: str | None = None

    # Mode
    default_mode: AgentMode = AgentMode.CONFIRM


class ReActStep(str, Enum):
    """Steps in the ReAct loop."""

    THINK = "think"
    PLAN = "plan"
    ACT = "act"
    OBSERVE = "observe"
    RESPOND = "respond"


@dataclass
class AgentMetrics:
    """Metrics for agent performance tracking."""

    total_turns: int = 0
    successful_turns: int = 0
    failed_turns: int = 0
    total_tool_calls: int = 0
    successful_tool_calls: int = 0
    failed_tool_calls: int = 0
    total_tokens_used: int = 0
    average_response_time_ms: float = 0.0
    last_reset: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "total_turns": self.total_turns,
            "successful_turns": self.successful_turns,
            "failed_turns": self.failed_turns,
            "success_rate": (
                self.successful_turns / self.total_turns if self.total_turns > 0 else 0
            ),
            "total_tool_calls": self.total_tool_calls,
            "successful_tool_calls": self.successful_tool_calls,
            "failed_tool_calls": self.failed_tool_calls,
            "total_tokens_used": self.total_tokens_used,
            "average_response_time_ms": self.average_response_time_ms,
            "last_reset": self.last_reset.isoformat(),
        }


class OmniAgent:
    """
    Main agent class implementing the ReAct (Reason + Act) loop.

    This agent translates natural language into deterministic system actions
    using a stateful, multi-step execution model with safety guardrails.
    """

    def __init__(
        self,
        config: AgentConfig | None = None,
        llm_client: Any = None,
        memory_system: MemorySystem | None = None,
        tool_registry: ToolRegistry | None = None,
    ):
        self.config = config or AgentConfig()
        self.state = AgentState()
        self.metrics = AgentMetrics()

        # Initialize components
        self.memory = memory_system or MemorySystem(
            persist_directory=self.config.memory_persist_dir
        )
        self.registry = tool_registry or get_registry()
        self.llm = llm_client or self._create_default_llm_client()

        # Rate limiting
        self._action_timestamps: list[datetime] = []

        # Safety callbacks
        self._safety_checks: list[Callable] = []

        # Mode
        self.mode = self.config.default_mode

    def _create_default_llm_client(self) -> "LLMClient":
        """Create the default LLM client."""
        from ..llm.client import LLMClient

        return LLMClient(
            provider=self.config.llm_provider,
            model=self.config.llm_model,
            api_key=self.config.llm_api_key,
            base_url=self.config.llm_base_url,
            temperature=self.config.llm_temperature,
            max_tokens=self.config.llm_max_tokens,
        )

    async def process(
        self,
        user_input: str,
        stream: bool = False,
        context: dict[str, Any] | None = None,
    ) -> str | Awaitable[str]:
        """
        Process user input and execute the ReAct loop.

        Args:
            user_input: The user's natural language input
            stream: Whether to stream the response
            context: Additional context for this turn

        Returns:
            The agent's response
        """
        # Initialize turn
        turn_id = str(uuid.uuid4())
        self.state.current_turn = Turn(id=turn_id, user_input=user_input)
        self.state.add_message(MessageRole.USER, user_input)
        self.memory.add_user_message(user_input)

        if context:
            self.memory.short_term.set_task_context(context)

        try:
            response = await self._run_react_loop(user_input)
            self.state.current_turn.response = response
            self.state.current_turn.status = TurnStatus.COMPLETED
            self.metrics.successful_turns += 1
        except CircuitBreakerOpenError as e:
            response = f"⚠️ Circuit breaker activated after {e.failure_count} consecutive failures. Please try again later."
            self.state.current_turn.error = str(e)
            self.state.current_turn.status = TurnStatus.FAILED
            self.metrics.failed_turns += 1
        except SafetyViolationError as e:
            response = f"⚠️ Safety check failed: {e.reason}"
            self.state.current_turn.error = str(e)
            self.state.current_turn.status = TurnStatus.FAILED
            self.metrics.failed_turns += 1
        except Exception as e:
            response = f"❌ An error occurred: {str(e)}"
            self.state.current_turn.error = str(e)
            self.state.current_turn.status = TurnStatus.FAILED
            self.metrics.failed_turns += 1
            self.state.consecutive_failures += 1

        self.state.current_turn.completed_at = datetime.now()
        self.state.add_message(MessageRole.ASSISTANT, response)
        self.memory.add_assistant_message(response)
        self.metrics.total_turns += 1

        return response

    async def _run_react_loop(self, user_input: str) -> str:
        """Execute the ReAct loop."""
        iteration = 0
        context = self.memory.get_full_context()

        while iteration < self.config.max_iterations:
            iteration += 1

            # Step 1: THINK - Get LLM reasoning
            thought = await self._think(context, user_input)

            # Check if we're done
            if self._is_final_response(thought):
                return self._extract_response(thought)

            # Step 2: PLAN - Parse tool calls from thought
            tool_calls = self._parse_tool_calls(thought)

            if not tool_calls:
                # No tool calls, return the thought as response
                return thought

            # Step 3: ACT - Execute tool calls
            for tool_call in tool_calls[: self.config.max_tool_calls_per_turn]:
                # Check rate limit
                self._check_rate_limit()

                # Check circuit breaker
                self._check_circuit_breaker()

                # Safety check
                await self._run_safety_checks(tool_call)

                # Execute tool
                result = await self._execute_tool(tool_call)

                # Update context with result
                context += f"\n\n[Tool Result: {tool_call.tool.name}]\n{result.format_for_llm()}"

                # Record in state
                self.state.current_turn.tool_calls.append(tool_call)
                self.metrics.total_tool_calls += 1

                if result.success:
                    self.metrics.successful_tool_calls += 1
                    self.state.consecutive_failures = 0
                else:
                    self.metrics.failed_tool_calls += 1
                    self.state.consecutive_failures += 1

                self.memory.add_tool_result(
                    tool_call.tool.name, result.format_for_llm(), result.success
                )

        # Max iterations reached
        return "I wasn't able to complete this task. Could you provide more details or break it down into smaller steps?"

    async def _think(self, context: str, user_input: str) -> str:
        """Get LLM reasoning for the current state."""
        system_prompt = self._build_system_prompt()
        tools = self.registry.get_all_openai_functions()

        response = await self.llm.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Context:\n{context}\n\nTask: {user_input}"},
            ],
            tools=tools,
        )

        return response

    def _build_system_prompt(self) -> str:
        """Build the system prompt with current context."""
        mode_instruction = ""
        if self.mode == AgentMode.DRY_RUN:
            mode_instruction = "\n\n**MODE: DRY RUN** - Preview all actions but do not execute them."
        elif self.mode == AgentMode.CONFIRM:
            mode_instruction = "\n\n**MODE: CONFIRM** - All HIGH/CRITICAL risk actions require user confirmation."

        return f"""You are OmniAgent, an intelligent desktop automation assistant for Windows 11.

Your role is to help users accomplish tasks by:
1. Understanding their natural language requests
2. Breaking down tasks into executable steps
3. Using available tools to perform actions
4. Providing clear feedback on progress

**Available Actions:**
Use the tools provided to accomplish tasks. Each tool has a specific purpose and risk level.

**Response Format:**
- For simple questions or requests: Provide a direct response
- For complex tasks: Use tools to accomplish the goal step by step
- After using tools, observe results and continue until the task is complete

**Safety Guidelines:**
- Always confirm destructive actions (delete, format, etc.) with the user
- Never execute actions that could harm the system without explicit confirmation
- If uncertain about an action, ask for clarification

{mode_instruction}

**Current Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

    def _is_final_response(self, text: str) -> bool:
        """Check if the text is a final response (not a tool call)."""
        # Check if text contains function call markers
        if '"name":' in text and '"arguments":' in text:
            return False
        if "function_call" in text.lower():
            return False
        if text.strip().startswith("{"):
            return False
        return True

    def _extract_response(self, text: str) -> str:
        """Extract the actual response text."""
        # Try to find content in various formats
        patterns = [
            r'"content"\s*:\s*"([^"]*)"',
            r"'''(.*?)'''",
            r'"""(.*?)"""',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(1).strip()

        return text.strip()

    def _parse_tool_calls(self, text: str) -> list[ToolCall]:
        """Parse tool calls from LLM output."""
        tool_calls = []

        # Try to find JSON function calls
        try:
            # Look for function call blocks
            patterns = [
                r'{\s*"name"\s*:\s*"(\w+)"\s*,\s*"arguments"\s*:\s*({.*?})\s*}',
                r'{\s*"function"\s*:\s*{\s*"name"\s*:\s*"(\w+)"\s*,\s*"arguments"\s*:\s*({.*?})\s*}}',
            ]

            for pattern in patterns:
                matches = re.finditer(pattern, text, re.DOTALL)
                for match in matches:
                    tool_name = match.group(1)
                    args_str = match.group(2)

                    tool = self.registry.get(tool_name)
                    if tool:
                        try:
                            arguments = json.loads(args_str)
                            valid, error = tool.validate_arguments(arguments)
                            if valid:
                                tool_calls.append(ToolCall.from_llm_output(tool, arguments, text))
                        except json.JSONDecodeError:
                            continue

        except Exception:
            pass

        return tool_calls

    async def _execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call."""
        import time

        start_time = time.time()
        handler = self.registry.get_handler(tool_call.tool.name)

        if not handler:
            return ToolResult(
                tool_call_id=tool_call.id,
                tool_name=tool_call.tool.name,
                success=False,
                error="Tool handler not found",
            )

        try:
            # Handle both sync and async handlers
            if asyncio.iscoroutinefunction(handler):
                result = await asyncio.wait_for(
                    handler(**tool_call.arguments),
                    timeout=self.config.action_timeout_seconds,
                )
            else:
                result = await asyncio.wait_for(
                    asyncio.to_thread(handler, **tool_call.arguments),
                    timeout=self.config.action_timeout_seconds,
                )

            return ToolResult(
                tool_call_id=tool_call.id,
                tool_name=tool_call.tool.name,
                success=True,
                result=result,
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        except asyncio.TimeoutError:
            return ToolResult(
                tool_call_id=tool_call.id,
                tool_name=tool_call.tool.name,
                success=False,
                error=f"Tool execution timed out after {self.config.action_timeout_seconds}s",
                execution_time_ms=(time.time() - start_time) * 1000,
            )
        except Exception as e:
            return ToolResult(
                tool_call_id=tool_call.id,
                tool_name=tool_call.tool.name,
                success=False,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

    def _check_rate_limit(self) -> None:
        """Check if rate limit has been exceeded."""
        now = datetime.now()
        cutoff = now.timestamp() - 60  # 1 minute window

        self._action_timestamps = [
            ts for ts in self._action_timestamps if ts.timestamp() > cutoff
        ]

        if len(self._action_timestamps) >= self.config.rate_limit_per_minute:
            raise RateLimitExceededError(
                self.config.rate_limit_per_minute, 60
            )

        self._action_timestamps.append(now)

    def _check_circuit_breaker(self) -> None:
        """Check if circuit breaker should be activated."""
        if self.state.consecutive_failures >= self.config.circuit_breaker_threshold:
            raise CircuitBreakerOpenError(self.state.consecutive_failures)

    async def _run_safety_checks(self, tool_call: ToolCall) -> None:
        """Run safety checks on a tool call."""
        for check in self._safety_checks:
            result = check(tool_call)
            if asyncio.iscoroutine(result):
                result = await result

            if not result:
                raise SafetyViolationError(
                    action=tool_call.tool.name,
                    reason=f"Failed safety check for tool '{tool_call.tool.name}'",
                    risk_level=tool_call.tool.risk_level.value,
                )

    def add_safety_check(self, check: Callable[[ToolCall], bool | Awaitable[bool]]) -> None:
        """Add a safety check function."""
        self._safety_checks.append(check)

    def set_mode(self, mode: AgentMode) -> None:
        """Set the agent's operating mode."""
        self.mode = mode
        self.state.is_dry_run = mode == AgentMode.DRY_RUN
        self.state.is_confirm_mode = mode == AgentMode.CONFIRM

    def get_metrics(self) -> dict:
        """Get agent metrics."""
        return self.metrics.to_dict()


# Type hint for LLM client
LLMClient = Any
