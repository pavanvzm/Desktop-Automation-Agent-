from __future__ import annotations
"""
LLM (Large Language Model) Integration Package

Supports multiple LLM providers with unified interface:
- OpenAI (GPT-4o, GPT-4-turbo)
- Anthropic (Claude)
- Local (Ollama, vLLM)
- Azure OpenAI
"""

from .client import LLMClient, LLMProvider
from .base import BaseLLMClient

__all__ = [
    "LLMClient",
    "LLMProvider",
    "BaseLLMClient",
]
