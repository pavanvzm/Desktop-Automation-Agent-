"""Custom exceptions for the Win11-OmniAgent core."""


class AgentError(Exception):
    """Base exception for all agent-related errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ToolExecutionError(AgentError):
    """Raised when a tool execution fails."""

    def __init__(self, tool_name: str, message: str, details: dict | None = None):
        super().__init__(f"Tool '{tool_name}' failed: {message}", details)
        self.tool_name = tool_name


class SafetyViolationError(AgentError):
    """Raised when an action violates safety constraints."""

    def __init__(self, action: str, reason: str, risk_level: str = "UNKNOWN"):
        super().__init__(f"Safety violation for action '{action}': {reason}")
        self.action = action
        self.reason = reason
        self.risk_level = risk_level


class RateLimitExceededError(AgentError):
    """Raised when rate limit is exceeded."""

    def __init__(self, limit: int, window: int):
        super().__init__(f"Rate limit exceeded: {limit} actions per {window} seconds")
        self.limit = limit
        self.window = window


class CircuitBreakerOpenError(AgentError):
    """Raised when circuit breaker is open."""

    def __init__(self, failure_count: int):
        super().__init__(f"Circuit breaker open after {failure_count} consecutive failures")
        self.failure_count = failure_count


class MemoryError(AgentError):
    """Raised when memory operations fail."""

    pass


class LLMError(AgentError):
    """Raised when LLM operations fail."""

    def __init__(self, provider: str, message: str, details: dict | None = None):
        super().__init__(f"LLM error ({provider}): {message}", details)
        self.provider = provider


class SchedulerError(AgentError):
    """Raised when scheduler operations fail."""

    pass


class AuthenticationError(AgentError):
    """Raised when authentication fails."""

    pass


class ConfigurationError(AgentError):
    """Raised when configuration is invalid."""

    pass