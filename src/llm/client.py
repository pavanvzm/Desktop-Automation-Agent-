from __future__ import annotations
"""LLM client with support for multiple providers."""

import os
from enum import Enum

from .base import BaseLLMClient, LLMResponse


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    VLLM = "vllm"
    AZURE = "azure"
    GOOGLE = "google"


class LLMClient(BaseLLMClient):
    """
    Unified LLM client supporting multiple providers.

    Automatically selects the appropriate client based on provider.
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ):
        super().__init__(model, api_key, base_url, temperature, max_tokens)
        self.provider = LLMProvider(provider.lower())
        self._client = self._create_client(**kwargs)

    def _create_client(self, **kwargs) -> BaseLLMClient:
        """Create the appropriate client for the provider."""
        if self.provider == LLMProvider.OPENAI:
            return OpenAIClient(
                model=self.model,
                api_key=self.api_key or os.environ.get("OPENAI_API_KEY"),
                base_url=self.base_url,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        elif self.provider == LLMProvider.ANTHROPIC:
            return AnthropicClient(
                model=self.model,
                api_key=self.api_key or os.environ.get("ANTHROPIC_API_KEY"),
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        elif self.provider == LLMProvider.OLLAMA:
            return OllamaClient(
                model=self.model,
                base_url=self.base_url or "http://localhost:11434",
                temperature=self.temperature,
            )
        elif self.provider == LLMProvider.VLLM:
            return VLLMClient(
                model=self.model,
                base_url=self.base_url or "http://localhost:8000",
                api_key=self.api_key or "EMPTY",
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        elif self.provider == LLMProvider.AZURE:
            return AzureOpenAIClient(
                model=self.model,
                api_key=self.api_key or os.environ.get("AZURE_OPENAI_KEY"),
                base_url=self.base_url or os.environ.get("AZURE_OPENAI_ENDPOINT"),
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs,
    ) -> str:
        """Send a chat completion request."""
        return await self._client.chat(messages, tools, tool_choice, **kwargs)

    async def complete(
        self,
        prompt: str,
        max_tokens: int | None = None,
        **kwargs,
    ) -> str:
        """Send a text completion request."""
        return await self._client.complete(prompt, max_tokens, **kwargs)

    async def embed(
        self,
        texts: list[str],
        **kwargs,
    ) -> list[list[float]]:
        """Get embeddings for texts."""
        return await self._client.embed(texts, **kwargs)


class OpenAIClient(BaseLLMClient):
    """OpenAI API client."""

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        super().__init__(model, api_key, base_url, temperature, max_tokens)
        self.base_url = base_url or "https://api.openai.com/v1"

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs,
    ) -> str:
        """Send a chat completion request to OpenAI."""
        import json

        try:
            import httpx
        except ImportError:
            raise ImportError("httpx is required for OpenAI client. Install with: pip install httpx")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        if tools:
            payload["tools"] = tools
            if tool_choice:
                payload["tool_choice"] = tool_choice

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            # Extract content
            if "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                if "message" in choice:
                    msg = choice["message"]
                    # Check for tool calls
                    if "tool_calls" in msg and msg["tool_calls"]:
                        # Return tool call formatted response
                        return json.dumps({
                            "tool_calls": msg["tool_calls"],
                            "content": msg.get("content", ""),
                        })
                    return msg.get("content", "")

        return ""

    async def complete(
        self,
        prompt: str,
        max_tokens: int | None = None,
        **kwargs,
    ) -> str:
        """Send a text completion request."""
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx is required for OpenAI client")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }
        payload.update(kwargs)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0].get("text", "")

        return ""

    async def embed(
        self,
        texts: list[str],
        **kwargs,
    ) -> list[list[float]]:
        """Get embeddings for texts."""
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx is required for OpenAI client")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "text-embedding-3-small",
            "input": texts,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            return [item["embedding"] for item in data.get("data", [])]


class AnthropicClient(BaseLLMClient):
    """Anthropic Claude API client."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-20250514",
        api_key: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        super().__init__(model, api_key, None, temperature, max_tokens)
        self.base_url = "https://api.anthropic.com/v1"

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs,
    ) -> str:
        """Send a chat completion request to Anthropic."""
        import json

        try:
            import httpx
        except ImportError:
            raise ImportError("httpx is required for Anthropic client")

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        # Convert messages to Anthropic format
        anthropic_messages = []
        for msg in messages:
            if msg["role"] == "system":
                continue  # Handle system separately
            anthropic_messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        payload = {
            "model": self.model,
            "messages": anthropic_messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        if tools:
            payload["tools"] = self._convert_tools(tools)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/messages",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            if "content" in data:
                contents = data["content"]
                if isinstance(contents, list):
                    for item in contents:
                        if item.get("type") == "text":
                            return item.get("text", "")
                        elif item.get("type") == "tool_use":
                            return json.dumps({
                                "tool_calls": [{
                                    "id": item.get("id"),
                                    "type": "function",
                                    "function": {
                                        "name": item.get("name"),
                                        "arguments": item.get("input", {}),
                                    }
                                }]
                            })

        return ""

    def _convert_tools(self, tools: list[dict]) -> list[dict]:
        """Convert OpenAI-style tools to Anthropic format."""
        anthropic_tools = []
        for tool in tools:
            if "function" in tool:
                func = tool["function"]
                anthropic_tools.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {}),
                })
        return anthropic_tools

    async def complete(
        self,
        prompt: str,
        max_tokens: int | None = None,
        **kwargs,
    ) -> str:
        """Text completion not supported by Anthropic."""
        raise NotImplementedError("Anthropic does not support text completion API")

    async def embed(
        self,
        texts: list[str],
        **kwargs,
    ) -> list[list[float]]:
        """Embeddings not supported by Anthropic."""
        raise NotImplementedError("Anthropic does not support embeddings API")


class OllamaClient(BaseLLMClient):
    """Ollama local LLM client."""

    def __init__(
        self,
        model: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        super().__init__(model, None, base_url, temperature, max_tokens)

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs,
    ) -> str:
        """Send a chat request to Ollama."""
        import json

        try:
            import httpx
        except ImportError:
            raise ImportError("httpx is required for Ollama client")

        # Convert to Ollama format
        ollama_messages = []
        for msg in messages:
            if msg["role"] == "system":
                continue
            ollama_messages.append({
                "role": msg["role"],
                "content": msg["content"],
            })

        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
            },
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            if "message" in data:
                msg = data["message"]
                if msg.get("tool_calls"):
                    return json.dumps({"tool_calls": msg["tool_calls"]})
                return msg.get("content", "")

        return ""

    async def complete(
        self,
        prompt: str,
        max_tokens: int | None = None,
        **kwargs,
    ) -> str:
        """Send a completion request to Ollama."""
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx is required for Ollama client")

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": max_tokens or self.max_tokens,
            },
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")

    async def embed(
        self,
        texts: list[str],
        **kwargs,
    ) -> list[list[float]]:
        """Get embeddings from Ollama."""
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx is required for Ollama client")

        embeddings = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for text in texts:
                response = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model, "prompt": text},
                )
                response.raise_for_status()
                data = response.json()
                embeddings.append(data.get("embedding", []))

        return embeddings


class VLLMClient(BaseLLMClient):
    """vLLM server client."""

    def __init__(
        self,
        model: str = "meta-llama/Llama-3.2-70B-Instruct",
        base_url: str = "http://localhost:8000",
        api_key: str = "EMPTY",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        super().__init__(model, api_key, base_url, temperature, max_tokens)

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs,
    ) -> str:
        """Send a chat request to vLLM server."""
        import json

        try:
            import httpx
        except ImportError:
            raise ImportError("httpx is required for vLLM client")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            if "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                if "message" in choice:
                    msg = choice["message"]
                    if "tool_calls" in msg and msg["tool_calls"]:
                        return json.dumps({"tool_calls": msg["tool_calls"]})
                    return msg.get("content", "")

        return ""

    async def complete(
        self,
        prompt: str,
        max_tokens: int | None = None,
        **kwargs,
    ) -> str:
        """Send a completion request to vLLM server."""
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx is required for vLLM client")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "prompt": prompt,
            "temperature": self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/v1/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0].get("text", "")

        return ""

    async def embed(
        self,
        texts: list[str],
        **kwargs,
    ) -> list[list[float]]:
        """Get embeddings from vLLM server."""
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx is required for vLLM client")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "input": texts,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/v1/embeddings",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            return [item["embedding"] for item in data.get("data", [])]


class AzureOpenAIClient(OpenAIClient):
    """Azure OpenAI client."""

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        api_version: str = "2024-02-01",
    ):
        super().__init__(model, api_key, base_url, temperature, max_tokens)
        self.api_version = api_version
        if self.base_url and "/openai/" not in self.base_url:
            self.base_url = f"{self.base_url}/openai/deployments/{model}"

    async def chat(
        self,
        messages: list[dict[str, str]],
        tools: list[dict] | None = None,
        tool_choice: str | None = None,
        **kwargs,
    ) -> str:
        """Send a chat request to Azure OpenAI."""
        import json

        try:
            import httpx
        except ImportError:
            raise ImportError("httpx is required for Azure OpenAI client")

        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

        payload = {
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        if tools:
            payload["tools"] = tools
            if tool_choice:
                payload["tool_choice"] = tool_choice

        async with httpx.AsyncClient(timeout=60.0) as client:
            url = f"{self.base_url}/chat/completions?api-version={self.api_version}"
            response = await client.post(
                url,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            if "choices" in data and len(data["choices"]) > 0:
                choice = data["choices"][0]
                if "message" in choice:
                    msg = choice["message"]
                    if "tool_calls" in msg and msg["tool_calls"]:
                        return json.dumps({"tool_calls": msg["tool_calls"]})
                    return msg.get("content", "")

        return ""
