# Win11-OmniAgent Developer Guide

## Table of Contents

1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Creating Custom Tools](#creating-custom-tools)
4. [Plugin Development](#plugin-development)
5. [Testing](#testing)
6. [Contributing](#contributing)

---

## Introduction

This guide covers how to develop extensions, plugins, and custom tools for Win11-OmniAgent.

## Project Structure

```
src/
├── core/           # Core agent framework
│   ├── agent.py    # Main ReAct agent
│   ├── state.py     # State management
│   ├── memory.py    # Memory system
│   └── tool_schema.py  # Tool definitions
├── llm/            # LLM integrations
├── scheduler/      # Task scheduling
├── tools/          # Built-in tools
├── youtube/        # YouTube intelligence
├── monitor/        # System monitoring
└── safety/        # Security features
```

## Creating Custom Tools

### Step 1: Define the Tool Schema

```python
from src.core.tool_schema import Tool, ToolParameter, ActionRiskLevel

my_tool = Tool(
    name="my_custom_action",
    description="Performs a custom action",
    parameters=[
        ToolParameter(
            name="input_text",
            type="string",
            description="The text to process",
            required=True,
        ),
        ToolParameter(
            name="count",
            type="number",
            description="Number of times to repeat",
            required=False,
            default=1,
            minimum=1,
            maximum=100,
        ),
    ],
    risk_level=ActionRiskLevel.MEDIUM,
    category="custom",
)
```

### Step 2: Implement the Handler

```python
async def my_custom_action_handler(input_text: str, count: int = 1) -> dict:
    """Handle the custom action."""
    result = (input_text + " ") * count
    
    return {
        "success": True,
        "result": result.strip(),
        "input_length": len(input_text),
        "repeat_count": count,
    }
```

### Step 3: Register the Tool

```python
from src.core.tool_schema import get_registry

registry = get_registry()
registry.register(my_tool, my_custom_action_handler)
```

Or use the decorator:

```python
from src.core.tool_schema import register_tool

@register_tool(my_tool)
async def my_custom_action_handler(input_text: str, count: int = 1) -> dict:
    return {"success": True, "result": input_text * count}
```

## Tool Schema Reference

### ActionRiskLevel

- **LOW**: Read-only actions (get info, capture screen)
- **MEDIUM**: Actions that modify state (click, type)
- **HIGH**: Destructive actions (delete, terminate)
- **CRITICAL**: System-critical actions (format, registry edit)

### ToolParameter Types

| Type | Description | Validation |
|------|-------------|------------|
| `string` | Text input | `enum`, `pattern` |
| `number` | Numeric input | `minimum`, `maximum` |
| `boolean` | True/false | - |
| `array` | List of items | `minItems`, `maxItems` |
| `object` | Nested object | Nested schema |

## Plugin Development

Plugins extend OmniAgent with additional capabilities.

### Plugin Structure

```
my_plugin/
├── __init__.py
├── plugin.yaml       # Plugin manifest
├── tools/            # Custom tools
├── handlers/        # Event handlers
└── config/          # Configuration
```

### Plugin Manifest (plugin.yaml)

```yaml
name: my-plugin
version: 1.0.0
description: My custom plugin
author: Developer Name
requirements:
  - package1>=1.0
  - package2>=2.0

tools:
  - tools/my_tool.py
  - tools/another_tool.py

permissions:
  - file:read
  - system:info
```

## Testing

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/unit/test_core.py -v

# With coverage
pytest --cov=src --cov-report=html

# Watch mode
ptw  # pytest-watch
```

### Writing Tests

```python
import pytest
from src.core.agent import OmniAgent

@pytest.mark.asyncio
async def test_agent_response():
    """Test that agent generates a response."""
    agent = OmniAgent()
    
    response = await agent.process("Hello, how are you?")
    
    assert isinstance(response, str)
    assert len(response) > 0
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

### Code Style

- Follow PEP 8
- Use type hints
- Write docstrings for public APIs
- Keep functions focused and small