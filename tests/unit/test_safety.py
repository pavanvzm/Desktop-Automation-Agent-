"""Unit tests for safety modules."""

import pytest
from src.safety.rate_limiter import RateLimiter, CircuitBreaker, CircuitBreakerConfig
from src.safety.redaction import PIIRedactor
from src.safety.sandbox import ActionSandbox, SandboxMode
from src.core.tool_schema import Tool, ToolParameter, ToolCall, ActionRiskLevel


class TestRateLimiter:
    """Tests for RateLimiter."""

    @pytest.mark.asyncio
    async def test_acquire_tokens(self):
        """Test acquiring tokens."""
        limiter = RateLimiter()
        result = await limiter.acquire(1)

        assert result is True

    @pytest.mark.asyncio
    async def test_rate_limit_exceeded(self):
        """Test rate limiting when exceeded."""
        limiter = RateLimiter(config=None)

        # Should be able to acquire some
        for _ in range(5):
            await limiter.acquire(1)

        # Should eventually be limited
        remaining = limiter.get_remaining()
        assert remaining < 10


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    @pytest.mark.asyncio
    async def test_circuit_stays_closed_on_success(self):
        """Test circuit breaker stays closed on success."""
        cb = CircuitBreaker("test")

        async def success_func():
            return "success"

        result = await cb.call(success_func)
        assert result == "success"
        assert cb.state.value == "closed"

    @pytest.mark.asyncio
    async def test_circuit_opens_on_failures(self):
        """Test circuit breaker opens after failures."""
        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker("test", config=config)

        async def fail_func():
            raise Exception("fail")

        # Trigger failures
        for _ in range(3):
            try:
                await cb.call(fail_func)
            except Exception:
                pass

        assert cb.state.value == "open"


class TestPIIRedactor:
    """Tests for PIIRedactor."""

    def test_redact_email(self):
        """Test redacting email addresses."""
        redactor = PIIRedactor()
        text = "Contact me at john.doe@example.com for more info."

        redacted, detected = redactor.redact(text)

        assert "[REDACTED]" in redacted
        assert "john.doe@example.com" not in redacted
        assert len(detected) > 0
        assert detected[0]["type"] == "email"

    def test_redact_phone(self):
        """Test redacting phone numbers."""
        redactor = PIIRedactor()
        text = "Call me at (555) 123-4567."

        redacted, detected = redactor.redact(text)

        assert "[REDACTED]" in redacted
        assert len(detected) > 0

    def test_redact_api_key(self):
        """Test redacting API keys."""
        redactor = PIIRedactor()
        text = 'Set API key: api_key = "sk-1234567890abcdefghijklmnop"'

        redacted, detected = redactor.redact(text)

        assert "sk-1234567890" not in redacted

    def test_no_pii_found(self):
        """Test text with no PII."""
        redactor = PIIRedactor()
        text = "Hello, this is a normal message with no sensitive data."

        redacted, detected = redactor.redact(text)

        assert redacted == text
        assert len(detected) == 0


class TestActionSandbox:
    """Tests for ActionSandbox."""

    @pytest.mark.asyncio
    async def test_dry_run_mode(self):
        """Test dry run mode doesn't execute."""
        sandbox = ActionSandbox(mode=SandboxMode.DRY_RUN)

        tool = Tool(
            name="test_tool",
            description="A test tool",
            parameters=[ToolParameter(name="arg", type="string", description="Test arg")],
        )
        tool_call = ToolCall.from_llm_output(tool, {"arg": "value"})

        result = await sandbox.execute(tool_call)

        assert result.executed is False
        assert result.preview is not None

    @pytest.mark.asyncio
    async def test_risk_assessment(self):
        """Test risk assessment of tools."""
        sandbox = ActionSandbox()

        low_risk_tool = Tool(
            name="low_risk_tool",
            description="Low risk tool",
            parameters=[],
            risk_level=ActionRiskLevel.LOW,
        )
        tool_call = ToolCall.from_llm_output(low_risk_tool, {})

        result = await sandbox.execute(tool_call)

        assert result.preview is not None
        assert result.preview.risk_level == ActionRiskLevel.LOW
