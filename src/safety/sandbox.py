"""Action sandboxing and dry-run execution."""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable

from ..core.tool_schema import Tool, ToolCall, ToolResult, ActionRiskLevel


class SandboxMode(str, Enum):
    """Sandbox execution modes."""

    LIVE = "live"  # Execute for real
    DRY_RUN = "dry_run"  # Preview only
    SIMULATED = "simulated"  # Return mock results


@dataclass
class ActionPreview:
    """Preview of an action to be executed."""

    tool_call: ToolCall
    would_execute: bool
    risk_level: ActionRiskLevel
    summary: str
    requires_confirmation: bool
    warnings: list[str] = field(default_factory=list)
    estimated_impact: str = ""


@dataclass
class SandboxResult:
    """Result of sandboxed execution."""

    success: bool
    executed: bool  # False if dry-run
    result: Any = None
    error: str | None = None
    preview: ActionPreview | None = None
    timestamp: datetime = field(default_factory=datetime.now)


class ActionSandbox:
    """
    Sandbox for executing actions safely.

    Provides:
    - Dry-run mode to preview actions
    - Risk assessment
    - Confirmation workflows
    - Execution tracking
    """

    def __init__(
        self,
        mode: SandboxMode = SandboxMode.DRY_RUN,
        max_risk_level: ActionRiskLevel = ActionRiskLevel.HIGH,
    ):
        self.mode = mode
        self.max_risk_level = max_risk_level
        self._handlers: dict[str, Callable] = {}
        self._execution_log: list[SandboxResult] = []

    def register_handler(self, tool_name: str, handler: Callable) -> None:
        """Register a handler for a tool."""
        self._handlers[tool_name] = handler

    def set_mode(self, mode: SandboxMode) -> None:
        """Change the sandbox mode."""
        self.mode = mode

    async def execute(self, tool_call: ToolCall) -> SandboxResult:
        """Execute or preview a tool call."""
        # Assess risk
        preview = self._assess_risk(tool_call)

        if self.mode == SandboxMode.DRY_RUN:
            return SandboxResult(
                success=True,
                executed=False,
                preview=preview,
            )

        if self.mode == SandboxMode.SIMULATED:
            return SandboxResult(
                success=True,
                executed=False,
                result=self._generate_mock_result(tool_call),
                preview=preview,
            )

        # LIVE mode
        if preview.requires_confirmation:
            # Would need external confirmation
            # For now, proceed if risk is acceptable
            pass

        # Execute
        return await self._execute_live(tool_call)

    def _assess_risk(self, tool_call: ToolCall) -> ActionPreview:
        """Assess the risk of executing a tool call."""
        warnings = []
        tool = tool_call.tool

        # Check risk level
        risk_order = [
            ActionRiskLevel.LOW,
            ActionRiskLevel.MEDIUM,
            ActionRiskLevel.HIGH,
            ActionRiskLevel.CRITICAL,
        ]

        exceeds_limit = (
            risk_order.index(tool.risk_level) > risk_order.index(self.max_risk_level)
        )

        if exceeds_limit:
            warnings.append(f"Risk level {tool.risk_level.value} exceeds limit {self.max_risk_level.value}")

        # Specific warnings based on tool type
        tool_warnings = {
            "delete_file": ["This will permanently delete files", "Cannot be undone"],
            "format_drive": ["This will erase all data on the drive", "EXTREMELY DESTRUCTIVE"],
            "execute_command": ["Arbitrary command execution", "Could modify system state"],
            "kill_process": ["Will terminate running application", "Unsaved data may be lost"],
            "modify_registry": ["Changes to registry are permanent", "Could affect system stability"],
        }

        for warning_type, msgs in tool_warnings.items():
            if warning_type in tool.name:
                warnings.extend(msgs)

        # Generate summary
        summary = f"{tool.name}("
        args_str = ", ".join(f"{k}={repr(v)[:50]}" for k, v in tool_call.arguments.items())
        summary += args_str + ")"

        return ActionPreview(
            tool_call=tool_call,
            would_execute=True,
            risk_level=tool.risk_level,
            summary=summary,
            requires_confirmation=tool.requires_confirmation or exceeds_limit,
            warnings=warnings,
        )

    async def _execute_live(self, tool_call: ToolCall) -> SandboxResult:
        """Execute a tool call for real."""
        import time

        start = time.time()

        try:
            handler = self._handlers.get(tool_call.tool.name)
            if not handler:
                return SandboxResult(
                    success=False,
                    executed=True,
                    error=f"No handler registered for {tool_call.tool.name}",
                )

            # Execute with timeout
            result = await asyncio.wait_for(
                handler(**tool_call.arguments),
                timeout=30.0,
            )

            sandbox_result = SandboxResult(
                success=True,
                executed=True,
                result=result,
            )

            self._execution_log.append(sandbox_result)
            return sandbox_result

        except asyncio.TimeoutError:
            error_result = SandboxResult(
                success=False,
                executed=True,
                error="Execution timed out after 30 seconds",
            )
            self._execution_log.append(error_result)
            return error_result

        except Exception as e:
            error_result = SandboxResult(
                success=False,
                executed=True,
                error=str(e),
            )
            self._execution_log.append(error_result)
            return error_result

    def _generate_mock_result(self, tool_call: ToolCall) -> dict:
        """Generate a mock result for simulated mode."""
        return {
            "simulated": True,
            "tool": tool_call.tool.name,
            "arguments": tool_call.arguments,
            "message": "This is a simulated result - no actual action was taken",
        }

    def get_execution_log(self) -> list[SandboxResult]:
        """Get the execution log."""
        return self._execution_log

    def clear_log(self) -> None:
        """Clear the execution log."""
        self._execution_log.clear()


class DryRunExecutor:
    """
    Execute actions in dry-run mode.

    Shows what would happen without actually executing.
    """

    def __init__(self):
        self._actions: list[ActionPreview] = []

    def add_action(self, preview: ActionPreview) -> None:
        """Add an action to be previewed."""
        self._actions.append(preview)

    def get_dry_run_summary(self) -> str:
        """Get a summary of what would be executed."""
        if not self._actions:
            return "No actions to execute."

        lines = ["## Dry Run Summary\n"]
        lines.append(f"Total actions: {len(self._actions)}\n\n")

        # Group by risk level
        by_risk = {}
        for action in self._actions:
            risk = action.risk_level.value
            if risk not in by_risk:
                by_risk[risk] = []
            by_risk[risk].append(action)

        for risk in ["low", "medium", "high", "critical"]:
            if risk in by_risk:
                lines.append(f"### {risk.upper()} Risk ({len(by_risk[risk])} actions)\n")
                for action in by_risk[risk]:
                    lines.append(f"- `{action.summary}`\n")
                    if action.warnings:
                        for warning in action.warnings:
                            lines.append(f"  - ⚠️ {warning}\n")
                lines.append("\n")

        return "".join(lines)

    def confirm_all(self) -> list[ActionPreview]:
        """Mark all actions as confirmed."""
        confirmed = []
        for action in self._actions:
            action.confirmed = True
            confirmed.append(action)
        return confirmed

    def reject_all(self) -> list[ActionPreview]:
        """Mark all actions as rejected."""
        rejected = []
        for action in self._actions:
            action.rejected = True
            rejected.append(action)
        return rejected

    def clear(self) -> None:
        """Clear all pending actions."""
        self._actions.clear()