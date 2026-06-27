from __future__ import annotations
"""Rate limiting and circuit breaker patterns."""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Any


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    max_requests: int = 10
    window_seconds: int = 60
    burst_size: int = 3  # Allow short bursts


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 2  # Successes to close
    timeout_seconds: int = 30  # Time before trying again
    half_open_max_calls: int = 3


class RateLimiter:
    """
    Token bucket rate limiter.

    Tracks requests over a sliding window and enforces limits.
    """

    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or RateLimitConfig()
        self._tokens: deque[datetime] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> bool:
        """
        Acquire tokens from the rate limiter.

        Returns True if tokens are acquired, False if rate limited.
        """
        async with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=self.config.window_seconds)

            # Remove expired tokens
            while self._tokens and self._tokens[0] < cutoff:
                self._tokens.popleft()

            # Check if we can acquire
            if len(self._tokens) + tokens <= self.config.max_requests:
                for _ in range(tokens):
                    self._tokens.append(now)
                return True

            return False

    async def wait_and_acquire(self, tokens: int = 1, timeout: float = 30.0) -> bool:
        """
        Wait for tokens to become available.

        Returns True if acquired, False if timeout.
        """
        start = time.time()

        while time.time() - start < timeout:
            if await self.acquire(tokens):
                return True

            # Wait a bit before retrying
            await asyncio.sleep(0.1)

        return False

    def get_remaining(self) -> int:
        """Get number of remaining tokens in current window."""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.config.window_seconds)

        # Clean expired (not in lock, but it's okay for approximation)
        valid_tokens = [t for t in self._tokens if t >= cutoff]
        return max(0, self.config.max_requests - len(valid_tokens))

    def reset(self) -> None:
        """Reset the rate limiter."""
        self._tokens.clear()


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    Prevents cascading failures by tracking failures and
    temporarily blocking requests when a service is failing.
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
        fallback: Callable | None = None,
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.fallback = fallback

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: datetime | None = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute a function through the circuit breaker.

        If circuit is open, calls fallback or raises exception.
        """
        async with self._lock:
            # Check if we should try to close
            if self._state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                else:
                    if self.fallback:
                        return await self._execute_fallback()
                    raise CircuitBreakerOpenError(self.name, self._failure_count)

        # Execute the call
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = await asyncio.to_thread(func, *args, **kwargs)

            await self._on_success()
            return result

        except Exception as e:
            await self._on_failure()
            raise

    async def _on_success(self) -> None:
        """Handle successful call."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0

            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = max(0, self._failure_count - 1)

    async def _on_failure(self) -> None:
        """Handle failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now()

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open opens the circuit
                self._state = CircuitState.OPEN
                self._half_open_calls = 0

            elif self._failure_count >= self.config.failure_threshold:
                self._state = CircuitState.OPEN

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self._last_failure_time is None:
            return True

        elapsed = (datetime.now() - self._last_failure_time).total_seconds()
        return elapsed >= self.config.timeout_seconds

    async def _execute_fallback(self) -> Any:
        """Execute the fallback function."""
        if self.fallback:
            if asyncio.iscoroutinefunction(self.fallback):
                return await self.fallback()
            return self.fallback()
        raise CircuitBreakerOpenError(self.name, self._failure_count)

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0

    def get_stats(self) -> dict:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "last_failure": self._last_failure_time.isoformat() if self._last_failure_time else None,
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""

    def __init__(self, name: str, failure_count: int):
        super().__init__(f"Circuit breaker '{name}' is open after {failure_count} failures")
        self.name = name
        self.failure_count = failure_count


class MultiRateLimiter:
    """
    Rate limiter for multiple resources.

    Manages separate rate limits for different resources.
    """

    def __init__(self):
        self._limiters: dict[str, RateLimiter] = {}
        self._lock = asyncio.Lock()

    async def get_limiter(
        self,
        name: str,
        config: RateLimitConfig | None = None,
    ) -> RateLimiter:
        """Get or create a rate limiter for a resource."""
        async with self._lock:
            if name not in self._limiters:
                self._limiters[name] = RateLimiter(config)
            return self._limiters[name]

    async def acquire(
        self,
        resource: str,
        tokens: int = 1,
        config: RateLimitConfig | None = None,
    ) -> bool:
        """Acquire tokens for a resource."""
        limiter = await self.get_limiter(resource, config)
        return await limiter.acquire(tokens)

    def reset_all(self) -> None:
        """Reset all rate limiters."""
        for limiter in self._limiters.values():
            limiter.reset()

    def get_stats(self) -> dict:
        """Get statistics for all limiters."""
        return {
            name: {"remaining": limiter.get_remaining()}
            for name, limiter in self._limiters.items()
        }
