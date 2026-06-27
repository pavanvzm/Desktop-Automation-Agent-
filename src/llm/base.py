from __future__ import annotations
"""Base LLM client interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    """Standardized LLM response."""

    content: str
    raw_response: Any
    model: str
    tokens_used: int | None = None
    cost: float | None = None
    finish_reason: str | None = None


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients."""

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs,
    ) -> str:
        """Send a chat completion request."""
        pass

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        max_tokens: int | None = None,
        **kwargs,
    ) -> str:
        """Send a text completion request."""
        pass

    @abstractmethod
    async def embed(
        self,
        texts: list[str],
        **kwargs,
    ) -> list[list[float]]:
        """Get embeddings for texts."""
        pass

    def format_messages(self, messages: list[dict[str, str]]) -> list[dict]:
        """Format messages for the specific LLM provider."""
        return messages

    def parse_tool_calls(self, response: Any) -> list[dict]:
        """Parse tool calls from LLM response."""
        return []
