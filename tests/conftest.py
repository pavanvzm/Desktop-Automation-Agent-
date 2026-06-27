"""Pytest configuration and fixtures."""

import pytest
import asyncio
from pathlib import Path


@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory for tests."""
    return tmp_path


@pytest.fixture
def mock_llm_client():
    """Provide a mock LLM client for testing."""
    class MockLLMClient:
        async def chat(self, messages, tools=None, **kwargs):
            return "This is a mock response from the LLM."

        async def complete(self, prompt, **kwargs):
            return "This is a mock completion."

        async def embed(self, texts, **kwargs):
            return [[0.1] * 384 for _ in texts]

    return MockLLMClient()


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_vitals():
    """Provide sample vitals data for testing."""
    from src.monitor.collector import SystemVitals
    from datetime import datetime

    return SystemVitals(
        timestamp=datetime.now(),
        cpu_percent=45.5,
        cpu_count=8,
        memory_total_gb=32.0,
        memory_used_gb=16.0,
        memory_available_gb=16.0,
        memory_percent=50.0,
        disk_total_gb=500.0,
        disk_used_gb=200.0,
        disk_free_gb=300.0,
        disk_percent=40.0,
        network_bytes_sent=1000000,
        network_bytes_recv=2000000,
    )