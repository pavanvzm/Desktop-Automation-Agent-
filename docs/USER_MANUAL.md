# Win11-OmniAgent User Manual

## Table of Contents

1. [Getting Started](#getting-started)
2. [Voice Commands](#voice-commands)
3. [Chat Commands](#chat-commands)
4. [Safety Features](#safety-features)
5. [Scheduler](#scheduler)
6. [Monitoring](#monitoring)

---

## Getting Started

### Starting the Agent

```bash
# Start with full UI
omniagent run --ui

# Start with voice
omniagent run --voice

# Headless mode
omniagent run --headless
```

### Wake Word

Default wake word: **"Hey Omni"**

To activate voice commands:
1. Say "Hey Omni"
2. Wait for the confirmation sound
3. Speak your command
4. Wait for execution confirmation

---

## Voice Commands

### Basic Commands

| Command | Description |
|---------|-------------|
| "Hey Omni, open Notepad" | Launch an application |
| "Hey Omni, take a screenshot" | Capture the screen |
| "Hey Omni, what's my CPU usage?" | Get system information |
| "Hey Omni, schedule a backup" | Create a scheduled task |
| "Hey Omni, stop" | Stop current operation |

### System Commands

```
- "What's the weather?" → Opens weather in browser
- "Play some music" → Opens music player
- "Check my email" → Opens email client
- "Set a timer for 10 minutes" → Creates a timer
```

### File Commands

```
- "Open document.docx in Documents"
- "Create a new folder called Projects"
- "Delete temporary files"
- "Copy file.txt to Desktop"
```

---

## Chat Commands

### General Commands

```
help              - Show available commands
status            - Show agent status
metrics           - Display performance metrics
history           - Show command history
clear             - Clear conversation
```

### System Commands

```
sysinfo           - Display system information
processes         - List running processes
kill <name>       - Terminate a process
screenshot        - Take a screenshot
clipboard         - Show clipboard contents
```

### File Commands

```
ls <path>         - List directory contents
cat <file>        - Read file contents
mkdir <name>      - Create directory
rm <path>         - Delete file (with confirmation)
cp <src> <dst>    - Copy file
mv <src> <dst>    - Move file
```

### Browser Commands

```
browse <url>      - Navigate to URL
click <selector>  - Click element
type <text>       - Type text
screenshot        - Take page screenshot
back/forward      - Navigate history
```

---

## Safety Features

### Confirmation Mode

All destructive actions require confirmation:

```
Agent: "I will delete the folder 'temp_files'. This cannot be undone. Confirm? [yes/no]"
User: "yes"
```

### Dry Run Mode

Preview actions without executing:

```
Agent: "[DRY RUN] Would execute: delete_file(path='temp/*')"
```

### Risk Levels

Actions are color-coded by risk:

- 🟢 **LOW** (green): Safe, read-only actions
- 🟡 **MEDIUM** (yellow): Actions that modify state
- 🟠 **HIGH** (orange): Destructive actions
- 🔴 **CRITICAL** (red): System-critical actions

### Audit Trail

All actions are logged. To view:

```
audit --last 10        # Show last 10 actions
audit --tool delete    # Show all delete actions
audit --export log.json  # Export to file
```

---

## Scheduler

### Creating Scheduled Tasks

Natural language scheduling:

```
"Schedule a backup every Sunday at 2am"
"Remind me to take breaks every hour"
"Run cleanup every weekday at 5pm"
```

### Managing Tasks

```
schedule --list           # List all tasks
schedule --pause <id>     # Pause a task
schedule --resume <id>    # Resume a task
schedule --delete <id>    # Remove a task
```

### Task Status

- ⏳ **Pending**: Waiting to run
- ✅ **Scheduled**: Active and scheduled
- 🔄 **Running**: Currently executing
- ✅ **Completed**: Finished successfully
- ❌ **Failed**: Encountered an error

---

## Monitoring

### Dashboard

Real-time system dashboard shows:

- CPU usage (current + graph)
- Memory usage
- Disk space
- Network activity
- Active alerts
- Recent tasks

### Alerts

Alert severity levels:

```
INFO    - Informational messages
WARNING - Attention needed
CRITICAL - Immediate action required
```

### Alert Notifications

Configure notifications:

```
notify --channel toast     # Windows notifications
notify --channel email     # Email alerts
notify --channel webhook   # Webhook calls
notify --channel slack     # Slack messages
```

### System Health

Health status indicators:

- 🟢 **Healthy**: All systems normal
- 🟡 **Warning**: Some metrics elevated
- 🔴 **Critical**: Immediate attention required

---

## Configuration

### Voice Settings

```yaml
voice:
  wake_word: "Hey Omni"
  sensitivity: 0.7
  timeout_seconds: 30
```

### Notification Settings

```yaml
notifications:
  enabled: true
  channels:
    - windows_toast
    - email
  min_severity: warning
```

### Security Settings

```yaml
security:
  confirm_destructive: true
  max_actions_per_minute: 10
  enable_audit_log: true
```

---

## Troubleshooting

### Common Issues

**Voice not responding**
- Check microphone permissions
- Verify wake word is enabled
- Reduce background noise

**Commands not executing**
- Check if confirmation is pending
- Verify network connectivity
- Review audit log for errors

**High resource usage**
- Reduce sampling interval
- Disable unused features
- Check for runaway processes