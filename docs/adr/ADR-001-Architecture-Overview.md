# ADR-001: Win11-OmniAgent Architecture Overview

**Status**: Accepted  
**Date**: 2024-01-15  
**Deciders**: Win11-OmniAgent Team

---

## Context

We need to build a production-grade, local-first desktop automation agent for Windows 11 that:
- Translates natural language (chat/voice) into deterministic system actions
- Performs web interactions and proactive monitoring
- Maintains memory, planning, and safety guardrails
- Operates autonomously with user oversight

This is not a simple script runner but an autonomous agentic system requiring sophisticated orchestration.

---

## Decision

### High-Level Architecture

```
+------------------------------------------------------------------------------+
|                           WIN11-OMNIAGENT SYSTEM                             |
+------------------------------------------------------------------------------+
|                                                                              |
|  +---------------------------------------------------------------------+     |
|  |                    MULTIMODAL INPUT PIPELINE                       |     |
|  |  +----------+  +----------+  +----------+  +--------------------+  |     |
|  |  |  Voice   |  |  Chat    |  |  Vision  |  | Wake Word ("Hey   |  |     |
|  |  |  (STT)   |  |  (UI)    |  |  (OCR)   |  |   Omni")          |  |     |
|  |  +----+-----+  +----+-----+  +----+-----+  +--------+---------+  |     |
|  |       |             |             |                  |            |     |
|  |       +-------------+-------------+------------------+            |     |
|  |                            |                                       |     |
|  |                            v                                       |     |
|  |  +-----------------------------------------------------------------+ |     |
|  |  |              INPUT NORMALIZATION LAYER                          | |     |
|  |  |         (Intent Detection, Entity Extraction)                  | |     |
|  |  +-----------------------------------------------------------------+ |     |
|  +---------------------------------------------------------------------+     |
|                            |                                              |
|                            v                                              |
|  +---------------------------------------------------------------------+     |
|  |                      ORCHESTRATION LAYER                            |     |
|  |  +-----------------------------------------------------------------+ |     |
|  |  |                   AGENT CORE (ReAct Loop)                       | |     |
|  |  |  +----------+  +----------+  +----------+  +------------+     | |     |
|  |  |  |  Think   |--|  Plan    |--|  Act     |--|  Observe   |     | |     |
|  |  |  +----------+  +----------+  +----------+  +--------+--+     | |     |
|  |  |       |                                               |        | |     |
|  |  |       +-----------------------+-----------------------+        | |     |
|  |  |                           |                                  | |     |
|  |  |                    +------+------+                           | |     |
|  |  |                    |   LLM Hub   |                           | |     |
|  |  |                    | (Configurable)                          | |     |
|  |  |                    +--------------+                          | |     |
|  |  +-----------------------------------------------------------------+ |     |
|  +---------------------------------------------------------------------+     |
|                            |                                              |
|  +-------------------------+----------------------------------------------+ |
|  |                      MEMORY SYSTEM                                  | |
|  |  +------------------+  +--------------------+  +----------------+  | |
|  |  |  Short-Term      |  |   Long-Term (RAG)  |  |  Screen        |  | |
|  |  |  (Conversation)  |  |   (Vector DB)      |  |  Context       |  | |
|  |  +------------------+  +--------------------+  +----------------+  | |
|  +---------------------------------------------------------------------+     |
|                            |                                              |
|  +-------------------------+----------------------------------------------+ |
|  |                          TOOL LAYER                                  | |
|  |  +--------------+ +------------------------+ +-------------------+  | |
|  |  |   Browser    | |   Desktop App Control  | |   System          |  | |
|  |  |   (Playwright)| |   (UI Automation)      | |   Operations      |  | |
|  |  +--------------+ +------------------------+ +-------------------+  | |
|  |  +--------------+ +------------------------+ +-------------------+  | |
|  |  |   File       | |   Credential Vault     | |   YouTube         |  | |
|  |  |   Operations | |   (KeePassXC/Bitwarden)| |   Intelligence    |  | |
|  |  +--------------+ +------------------------+ +-------------------+  | |
|  +---------------------------------------------------------------------+     |
|                            |                                              |
|  +-------------------------+----------------------------------------------+ |
|  |                    SCHEDULER & MONITORING                           | |
|  |  +------------------+  +-----------------+  +---------------------+  | |
|  |  |   Intelligent    |  |   System Vitals |  |   Alert Manager     |  | |
|  |  |   Scheduler      |  |   Monitor       |  |   (Toast/Webhook)   |  | |
|  |  +------------------+  +-----------------+  +---------------------+  | |
|  +---------------------------------------------------------------------+     |
|                            |                                              |
|  +-------------------------+----------------------------------------------+ |
|  |                         SAFETY LAYER                                 | |
|  |  +------------------+  +-----------------+  +---------------------+  | |
|  |  |   Action         |  |   Rate Limiter  |  |   Audit Trail       |  | |
|  |  |   Sandbox        |  |   + Circuit     |  |   (Encrypted)       |  | |
|  |  |   (Dry-Run)      |  |   Breaker       |  |                     |  | |
|  |  +------------------+  +-----------------+  +---------------------+  | |
|  +---------------------------------------------------------------------+     |
|                                                                              |
+------------------------------------------------------------------------------+
```

---

## Core Components

### 1. Orchestration Layer (Agent Core)

**Technology Choice**: LangGraph for stateful multi-step execution

**Rationale**:
- LangGraph provides native support for ReAct pattern with state persistence
- Built-in support for cycles and conditional branching
- Excellent TypeScript/Python interop for Windows integration
- Supports human-in-the-loop for approval workflows

**LLM Selection Strategy**:
```yaml
llm_config:
  primary:
    provider: "local"  # Privacy-first
    model: "llama-3.3-70b-instruct"
    backend: "ollama"  # or vLLM
    max_context: 128000
    
  fallback:
    provider: "openai"
    model: "gpt-4o"
    
  complex_reasoning:
    provider: "anthropic"
    model: "claude-sonnet-4-20250514"
```

**Agent Loop Implementation**:
```python
# ReAct Loop Pseudocode
while not task_complete:
    thought = llm.think(context + history + memory)
    if is_tool_call(thought):
        tool, params = parse_tool_call(thought)
        result = await sandbox.execute(tool, params)
        context += result
    else:
        response = thought
        break
```

---

### 2. Memory System

**Architecture**: Hybrid RAG with three tiers

| Tier | Storage | Purpose | TTL |
|------|---------|---------|-----|
| Short-term | In-memory | Conversation buffer, current task context | Session |
| Screen context | In-memory + SQLite | UI tree, last N screenshots | 5 minutes |
| Long-term | ChromaDB (local) | User preferences, task history, solutions | Persistent |

**Vector DB Configuration**:
```yaml
vector_store:
  provider: "chroma"
  persist_directory: "%APPDATA%/Win11-OmniAgent/vectors"
  collection_config:
    name: "agent_memory"
    metadata:
      - user_id
      - task_type
      - timestamp
```

---

### 3. Task Scheduler Design

**Architecture Decision**: Custom scheduler with Windows Task Scheduler bridge

**Rationale**:
- Windows Task Scheduler lacks DAG support and natural language parsing
- Custom scheduler provides full agent awareness and intelligent rescheduling
- Bridge to native scheduler for system-level reliability on heavy tasks

**Job Store Schema**:
```sql
CREATE TABLE scheduled_jobs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    schedule_type TEXT CHECK(schedule_type IN ('cron', 'interval', 'one_time', 'dag')),
    schedule_expr TEXT,  -- Cron expression or ISO 8601
    timezone TEXT DEFAULT 'UTC',
    last_run TIMESTAMP,
    next_run TIMESTAMP,
    retry_policy JSON,
    dependencies TEXT[],  -- DAG: list of job IDs
    user_tags TEXT[],
    status TEXT CHECK(status IN ('active', 'paused', 'failed', 'completed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Natural Language to Cron Mapping**:
```python
nl_to_cron_mappings = {
    "every weekday at 9am": "0 9 * * 1-5",
    "3 days before month-end": "0 9 * * L-3",
    "every monday at 8am": "0 8 * * 1",
    "every 15 minutes": "*/15 * * * *",
    "every hour": "0 * * * *",
    "every day at midnight": "0 0 * * *",
}
```

---

### 4. Security Model

**Principle of Least Privilege**:
- Agent runs as standard user by default
- Elevated actions trigger UAC prompt + explicit confirmation
- No auto-elevation without user consent

**Action Classification**:
```yaml
action_risk_levels:
  LOW:
    - read_system_info
    - get_window_list
    - capture_screen
    
  MEDIUM:
    - click_element
    - type_text
    - navigate_url
    
  HIGH:
    - delete_file
    - modify_registry
    - execute_command
    
  CRITICAL:
    - format_drive
    - delete_system_files
```

**Safety Mechanisms**:
1. **Dry-Run Mode**: All destructive operations show preview first
2. **Rate Limiting**: Max 10 actions/min unless overridden
3. **Circuit Breaker**: Auto-halt after 3 consecutive failures
4. **Audit Trail**: Immutable, encrypted log of all actions

---

### 5. Multimodal Input Pipeline

**Voice Processing**:
```yaml
voice_config:
  stt_provider: "local"  # Privacy
  model: "whisper-large-v3-turbo"
  vad:
    provider: "silero-vad"
    threshold: 0.5
    
  wake_word:
    phrase: "Hey Omni"
    engine: "openwakeword"
```

**Vision Pipeline**:
- Periodic screenshots (configurable: 1-60 second interval)
- UI Automation API tree extraction for accessible apps
- PaddleOCR fallback for non-accessible apps
- Screen context fed to LLM for grounding

---

### 6. Browser & Desktop Automation

**Browser Stack**:
- Playwright for Chromium/Edge/Firefox
- Persistent contexts with cookie/storage management
- Anti-detection measures for legitimate automation

**Desktop Control Stack**:
- Primary: Windows UI Automation API (COM interop)
- Fallback: PyAutoGUI + PaddleOCR for legacy apps
- Never use mouse simulation as primary method

---

### 7. YouTube Intelligence Pipeline

**Processing Flow**:
```
Video URL -> yt-dlp (metadata + subtitles) 
         -> Cache check (video ID)
         -> If no subs: Audio download + Whisper
         -> Chunk transcript
         -> Map-reduce summarization (LLM)
         -> Structured output + Vector DB storage
```

---

## Consequences

### Positive
- Modular architecture allows independent upgrades of each component
- Local-first design ensures privacy and offline capability
- Hybrid scheduler provides both reliability and intelligence
- Comprehensive safety measures reduce risk of unintended actions

### Negative
- Complex architecture requires careful testing
- Multiple LLM providers increase configuration complexity
- Local vector DB requires periodic maintenance

### Trade-offs
- **Privacy vs Capability**: Local STT/LLM is slower but more private
- **Reliability vs Intelligence**: Windows Task Scheduler is more reliable but less intelligent
- **Safety vs Usability**: Strict safety measures may slow down some workflows

---

## Alternatives Considered

### Option 1: AutoGen-based Architecture
- **Pros**: Native multi-agent support, Microsoft backing
- **Cons**: Less flexible for our specific needs, heavier weight

### Option 2: LangChain-only Implementation
- **Pros**: Simpler initial setup
- **Cons**: Less control over state management, less suitable for complex agent loops

### Option 3: Custom React implementation
- **Pros**: Full control
- **Cons**: Significant development time, maintenance burden

---

## References

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- [Windows UI Automation API](https://learn.microsoft.com/en-us/windows/win32/winauto/entry-uiauto-win32)
- [Whisper: General Purpose Speech Recognition](https://arxiv.org/abs/2210.03743)