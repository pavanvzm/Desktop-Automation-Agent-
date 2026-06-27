"""Unit tests for core modules."""

import pytest
from datetime import datetime
from src.core.state import AgentState, Message, MessageRole, Turn, TurnStatus
from src.core.tool_schema import Tool, ToolParameter, ActionRiskLevel
from src.core.memory import ShortTermMemory, LongTermMemory, MemorySystem


class TestAgentState:
    """Tests for AgentState."""

    def test_add_message(self):
        """Test adding messages to state."""
        state = AgentState()

        state.add_message(MessageRole.USER, "Hello")
        state.add_message(MessageRole.ASSISTANT, "Hi there")

        assert len(state.messages) == 2
        assert state.messages[0].role == MessageRole.USER
        assert state.messages[1].role == MessageRole.ASSISTANT

    def test_get_recent_messages(self):
        """Test getting recent messages."""
        state = AgentState()

        for i in range(15):
            state.add_message(MessageRole.USER, f"Message {i}")

        recent = state.get_recent_messages(5)
        assert len(recent) == 5


class TestTool:
    """Tests for Tool schema."""

    def test_tool_validation(self):
        """Test tool argument validation."""
        tool = Tool(
            name="test_tool",
            description="A test tool",
            parameters=[
                ToolParameter(name="name", type="string", description="Name", required=True),
                ToolParameter(name="count", type="number", description="Count", required=False, minimum=0, maximum=100),
            ],
        )

        # Valid arguments
        valid, error = tool.validate_arguments({"name": "test"})
        assert valid is True

        # Missing required
        valid, error = tool.validate_arguments({})
        assert valid is False
        assert "name" in error.lower()

        # Out of range
        valid, error = tool.validate_arguments({"name": "test", "count": 150})
        assert valid is False

    def test_tool_to_openai_function(self):
        """Test conversion to OpenAI function format."""
        tool = Tool(
            name="test_tool",
            description="A test tool",
            parameters=[
                ToolParameter(name="arg", type="string", description="An argument"),
            ],
        )

        result = tool.to_openai_function()

        assert result["type"] == "function"
        assert result["function"]["name"] == "test_tool"
        assert "arg" in result["function"]["parameters"]["properties"]


class TestShortTermMemory:
    """Tests for ShortTermMemory."""

    def test_add_and_retrieve_messages(self):
        """Test adding and retrieving messages."""
        memory = ShortTermMemory(max_messages=10)

        memory.add_message(Message(role=MessageRole.USER, content="Hello"))
        memory.add_message(Message(role=MessageRole.ASSISTANT, content="Hi"))

        messages = memory.get_recent_messages()
        assert len(messages) == 2

    def test_context_for_llm(self):
        """Test generating context for LLM."""
        memory = ShortTermMemory()
        memory.add_message(Message(role=MessageRole.USER, content="What's the weather?"))
        memory.add_message(Message(role=MessageRole.ASSISTANT, content="It's sunny."))

        context = memory.get_context_for_llm()

        assert "What's the weather?" in context
        assert "It's sunny." in context


class TestMemorySystem:
    """Tests for MemorySystem."""

    def test_full_context(self):
        """Test generating full context."""
        memory = MemorySystem()

        memory.add_user_message("Test message")

        context = memory.get_full_context(include_screen=False, include_memory=False)

        assert "Test message" in context
