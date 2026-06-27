# Win11-OmniAgent

<div align="center">

![OmniAgent Banner](https://img.shields.io/badge/Win11-OmniAgent-0078D4?style=for-the-badge&logo=microsoft&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Status](https://img.shields.io/badge/Status-Alpha-orange?style=flat-square)

**A Multimodal Desktop Automation Orchestrator for Windows 11**

[Features](#features) • [Architecture](#architecture) • [Installation](#installation) • [Quick Start](#quick-start) • [Documentation](#documentation)

</div>

---

## 🎯 Overview

Win11-OmniAgent is a production-grade, local-first desktop automation agent that translates natural language (chat/voice) into deterministic system actions, web interactions, and proactive monitoring. Built for Windows 11 (23H2+), it provides an autonomous agentic system with memory, planning, and comprehensive safety guardrails.

## ✨ Features

### 🤖 Core Agentic Architecture
- **ReAct/Plan-and-Solve Loop**: Stateful multi-step task execution
- **Multi-Modal Input**: Voice (Whisper), Chat, Vision (Screen capture)
- **Hybrid Memory**: Short-term (conversation buffer) + Long-term (Vector DB/RAG)
- **Configurable LLM**: Support for OpenAI, Anthropic, Ollama, vLLM, Azure OpenAI

### 📅 Advanced Task Scheduler
- **Natural Language Parsing**: "Every weekday at 9am" → cron expressions
- **SQLite-backed Job Store**: Persistent job registry with metadata
- **DAG-based Execution**: Dependency-aware task chains
- **Windows Task Scheduler Bridge**: Hybrid reliability + intelligence
- **Smart Rescheduling**: Auto-adjust for missed tasks

### 🌐 Web & Application Automation
- **Browser Control**: Playwright with Chrome/Edge/Firefox support
- **Desktop App Control**: Windows UI Automation API (primary) + PyAutoGUI fallback
- **Form Intelligence**: Auto-detect fields, credential vault integration
- **CAPTCHA Handling**: Third-party solver integration

### 📺 YouTube Intelligence Pipeline
- **Transcript Extraction**: yt-dlp + Whisper fallback
- **LLM Summarization**: Map-reduce chunking strategy
- **Vector Caching**: Avoid reprocessing with ChromaDB
- **Channel Monitoring**: RSS feed polling with alerts

### 📊 System Vitals Monitoring
- **Telemetry Collection**: CPU, GPU, RAM, Disk, Network, Temperature
- **Anomaly Detection**: Z-score, EWMA statistical models
- **Alert Routing**: Windows Toast, Email, Webhook, Slack
- **Self-Healing**: Pre-approved remediation scripts

### 🔒 Security & Safety
- **Principle of Least Privilege**: Standard user by default
- **Action Sandbox**: Dry-run mode for destructive operations
- **Audit Trail**: Immutable, encrypted logging with hash chains
- **Rate Limiting & Circuit Breakers**: Prevent runaway loops
- **PII Redaction**: Automatic privacy protection

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      WIN11-OMNIAGENT                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │   Voice     │  │    Chat     │  │   Vision    │  Input      │
│  │   (STT)     │  │    (UI)     │  │   (OCR)     │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                   ORCHESTRATION LAYER                      ││
│  │              Agent Core (ReAct Loop)                       ││
│  │  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐                    ││
│  │  │Think │──│ Plan │──│ Act  │──│Observe│                   ││
│  │  └──────┘  └──────┘  └──────┘  └──────┘                    ││
│  └─────────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────┐  ┌───────────┐  ┌───────────┐                   │
│  │Short-Term │  │Long-Term  │  │  Screen   │  Memory           │
│  │ (Buffer)  │  │  (RAG)    │  │  Context  │                   │
│  └───────────┘  └───────────┘  └───────────┘                   │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐              │
│  │ Browser │ │ Desktop │ │  File   │ │ YouTube │  Tools        │
│  │(Playwr.)│ │(UI Auto)│ │(System) │ │ Intel.  │              │
│  └─────────┘ └─────────┘ └─────────┘ └─────────┘              │
├─────────────────────────────────────────────────────────────────┤
│  ┌───────────┐  ┌───────────┐  ┌───────────┐                   │
│  │ Scheduler │  │  Monitor  │  │  Safety   │  System          │
│  │  + Cron   │  │  Vitals   │  │  Guardrails│                  │
│  └───────────┘  └───────────┘  └───────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

## 📦 Installation

### Prerequisites

- Windows 11 (23H2+) or Windows Server 2022+
- Python 3.11 or higher
- 8GB RAM minimum (16GB recommended)
- Optional: NVIDIA GPU for local LLM/STT

### Quick Install

```bash
# Clone the repository
git clone https://github.com/omniagent/win11-omniagent.git
cd win11-omniagent

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install with all dependencies
pip install -e ".[all]"

# Install Playwright browsers (if using browser automation)
playwright install chromium
```

### Using uv (Recommended)

```bash
# Install uv if not already installed
pip install uv

# Create project and install
uv venv
uv pip install -e ".[all]"
```

## 🚀 Quick Start

### 1. Configuration

Create `config.yaml`:

```yaml
llm:
  provider: "openai"  # or "anthropic", "ollama", "vllm", "azure"
  model: "gpt-4o"
  api_key: "your-api-key"  # or set OPENAI_API_KEY env var

voice:
  enabled: true
  wake_word: "Hey Omni"
  stt_provider: "openai"  # or "local" (Whisper)

scheduler:
  check_interval_seconds: 30
  max_concurrent_jobs: 4

monitor:
  sample_interval_seconds: 5
  alert_enabled: true
```

### 2. Run the Agent

```bash
# Start with chat UI
omniagent run --ui

# Start with voice enabled
omniagent run --voice

# Start in headless mode
omniagent run --headless
```

### 3. Example Commands

```
You: "Open Notepad and type 'Hello World'"
You: "Take a screenshot of my current screen"
You: "Schedule a backup every Sunday at 2am"
You: "What's my CPU usage right now?"
You: "Summarize this YouTube video: https://youtube.com/watch?v=..."
```

## 📚 Documentation

| Document | Description |
|---------|-------------|
| [Architecture ADR](docs/adr/ADR-001-Architecture-Overview.md) | Detailed architecture decisions |
| [Developer Guide](docs/DEVELOPER_GUIDE.md) | Tool schema authoring, plugin development |
| [User Manual](docs/USER_MANUAL.md) | Voice commands, safety features |
| [API Reference](docs/API.md) | Python API documentation |

## 🧪 Testing

```bash
# Run all tests
pytest

# Run unit tests only
pytest tests/unit/

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/unit/test_core.py -v
```

## 🔧 Development

### Project Structure

```
win11-omniagent/
├── src/
│   ├── core/          # Agent core (ReAct loop, memory, state)
│   ├── llm/           # LLM client integrations
│   ├── scheduler/     # Task scheduler and cron
│   ├── tools/         # Browser, desktop, file, system tools
│   ├── youtube/       # YouTube intelligence pipeline
│   ├── monitor/       # System vitals monitoring
│   └── safety/        # Audit, rate limiting, sandbox
├── tests/
│   ├── unit/          # Unit tests
│   ├── integration/    # Integration tests
│   └── e2e/           # End-to-end tests
├── docs/              # Documentation
│   └── adr/           # Architecture Decision Records
└── pyproject.toml     # Project configuration
```

### Adding Custom Tools

```python
from src.core.tool_schema import Tool, ToolParameter, ActionRiskLevel, register_tool

# Define your tool
my_tool = Tool(
    name="my_custom_action",
    description="Perform a custom action",
    parameters=[
        ToolParameter(name="param1", type="string", description="A parameter"),
    ],
    risk_level=ActionRiskLevel.MEDIUM,
)

@register_tool(my_tool)
async def my_custom_action(param1: str):
    # Your implementation
    return {"result": f"Action completed with {param1}"}
```

## 📋 Success Criteria

| Metric | Target |
|--------|--------|
| Task success rate | ≥ 92% |
| Voice-to-action latency | < 1.5s (local STT) / < 3s (cloud) |
| Scheduler reliability | 0 missed executions (30-day test) |
| Security vulnerabilities | Zero critical (third-party audit) |
| Memory footprint | < 500MB idle, < 1.5GB active |

## 🤝 Contributing

Contributions are welcome! Please read our contributing guidelines before submitting PRs.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built on [LangGraph](https://langchain-ai.github.io/langgraph/) for agent orchestration
- Uses [Playwright](https://playwright.dev/) for browser automation
- Powered by [Whisper](https://github.com/openai/whisper) for speech recognition
- Inspired by [OpenHands](https://github.com/All-Hands.ai) architecture patterns

---

<div align="center">

**Built with ❤️ for Windows 11 users who want AI-powered automation**

[Back to Top](#win11-omniagent)

</div>