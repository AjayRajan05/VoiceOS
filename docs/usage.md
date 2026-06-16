# 📖 VoiceOS Usage Guide

This guide covers how to interact with VoiceOS through voice and CLI, how to use its capabilities, and best practices for getting the most out of each mode.

---

## 🚀 Starting VoiceOS

```bash
# Default: hybrid mode (voice + CLI simultaneously)
python main.py

# Voice only
python main.py --mode voice

# CLI only (no microphone required)
python main.py --mode cli

# Use a custom configuration file
python main.py --config config/voiceos.yaml

# System health check (no interaction)
python main.py --status

# Run system tests (no microphone required)
python main.py --test
```

Once started, VoiceOS displays a banner and shows:
- Number of registered tools
- Number of discovered plugins
- Execution mode (local / queued)
- Audit logging status

You'll then see the `VoiceOS>` prompt. Type or speak commands from here.

---

## 🎤 Voice Interaction

Voice mode uses:
- **Microphone** → `VoicePipeline` captures audio
- **Whisper STT** → transcribes speech to text
- **Interrupt handling** → you can speak while VoiceOS is responding to stop it

### Voice Tips

- Speak clearly and at a natural pace
- You can interrupt TTS playback by simply speaking
- Hold a short pause after your command for best STT accuracy
- If voice is not detected, check your microphone with `python scripts/verify_setup.py`

---

## 💻 CLI Interaction

At the `VoiceOS>` prompt, type any natural language command and press Enter. You can also use built-in control commands:

| Command | Description |
|---------|-------------|
| `help` | Show available commands and usage |
| `status` | Show system health and metrics |
| `clear` | Clear the terminal screen |
| `exit` / `quit` | Shut down VoiceOS gracefully |

---

## ⚡ Execution Modes by Task Type

### Simple Tasks (< 1 second)

Direct, single-action commands routed straight to a tool — no agent overhead.

**OS Control:**
```
"Open Chrome"
"Open Notepad"
"Switch window"
"Close current window"
"Take a screenshot"
"Type hello world"
"Press Enter"
"Copy to clipboard"
```

**File Operations:**
```
"Read config.json"
"List files in workspace"
"Create a new file called notes.txt"
```

---

### Complex Tasks (1–30 seconds)

Multi-step tasks that require a dynamic agent (Researcher, Developer, or Analyst).

**Web Research (Researcher Agent):**
```
"Research the latest developments in large language models"
"Find information about Python async programming best practices"
"Search for recent papers on transformer architecture"
"Summarize the latest AI news"
```

**Code Development (Developer Agent):**
```
"Write a Python function to parse a CSV file"
"Create a Flask REST API with CRUD endpoints"
"Generate a web scraper using BeautifulSoup"
"Review this Python code for bugs"
"Debug the script in workspace/task.py"
```

**Data Analysis (Analyst Agent):**
```
"Analyze the CSV file in workspace/sales_data.csv"
"Find patterns in workspace/user_behavior.json"
"Generate a summary report from workspace/report.pdf"
```

---

### Autonomous Tasks (1–5 minutes)

Open-ended goals that require the iterative `think → decide → act → observe` loop, potentially across many steps and tool calls.

**Full development workflows:**
```
"Build a Python web scraper for news articles and save the results"
"Create a complete REST API with authentication and write unit tests"
"Develop a data pipeline that reads CSV files and generates charts"
```

**Automation:**
```
"Automate my daily sales report generation from workspace/data/"
"Set up a task that backs up workspace files every hour"
"Create a monitoring script that checks website availability"
```

**Research + Code combined:**
```
"Research machine learning model architectures and write a comparison report"
"Find Python libraries for PDF processing and build a document analyzer"
```

---

## 🛠️ Built-in Capabilities

### OS Automation

VoiceOS can control your desktop via `pyautogui`, `pynput`, and `pygetwindow`:

```
"Open [application name]"          # Launch any app by name
"Switch to [window title]"         # Focus a specific window
"Close [window title]"             # Close a window
"Type [text]"                      # Type text at cursor position
"Press [key]"                      # Press keyboard shortcuts
"Take a screenshot"                # Capture screen to workspace/
"Copy [text] to clipboard"         # Set clipboard content
"Read clipboard"                   # Get current clipboard content
```

> **Note**: OS control operations require MEDIUM or HIGH permission. VoiceOS will prompt for approval.

---

### Web Research

Powered by DuckDuckGo search + BeautifulSoup + readability-lxml:

```
"Search for [topic]"
"Find information about [subject]"
"Research [topic] and write a report"
"Summarize this article: [URL]"
"Extract key points from [URL]"
"Compare sources on [topic]"
```

Results are saved to `workspace/task_[id]/output/` as markdown or text files.

---

### Code Development

The Developer Agent generates, executes, and iterates on code in the sandboxed workspace:

```
"Write a [language] script to [task]"
"Create a function that [description]"
"Fix the error in [file]"
"Add unit tests to [file]"
"Optimize this algorithm: [description]"
"Generate a [framework] project structure"
```

**IDE workflow example:**
```
"Open VS Code"
"Create file workspace/api.py with a Flask REST API"
"Run file workspace/api.py"
"Show me the output"
```

---

### Document Processing

Supports PDF, DOCX, and TXT files:

```
"Summarize workspace/report.pdf"
"Extract text from workspace/document.docx"
"Search for 'revenue' in workspace/annual_report.pdf"
"Analyze the structure of workspace/data.txt"
"Convert workspace/document.pdf to text"
```

---

### Task Scheduling

Schedule and manage recurring or one-off tasks:

```
"Schedule a task to run workspace/report.py every day at 9am"
"Show all scheduled tasks"
"Cancel task [task_id]"
"Check the status of task [task_id]"
```

---

### Communication (via Plugins)

With the messaging plugins configured:

```
"Send a Telegram message to [contact]: [message]"
"Check my WhatsApp messages"
"Send an email to [address] with subject [subject]: [body]"
"Check my inbox"
```

---

## 🔐 Permission System in Action

When VoiceOS needs to perform a MEDIUM or HIGH permission action, it will prompt you:

```
VoiceOS: I need to write to workspace/output.py — Allow? [y/N]
> y
VoiceOS: Writing file... Done.
```

For HIGH permission actions (e.g., execute code, delete files):
```
VoiceOS: I need to execute code in the sandbox — this requires explicit approval. Allow? [y/N]
```

You can configure the default permission level in `.env`:
```bash
PERMISSION_LEVEL=medium    # low | medium | high
```

Setting `PERMISSION_LEVEL=high` pre-approves all actions (use with caution).

---

## 📊 Monitoring and Status

### System Health

```bash
python main.py --status
```

Output includes:
- Core system health (OK / DEGRADED / ERROR)
- Number of registered tools
- Active execution mode (local / queued)
- Redis and distributed worker status
- OS control capabilities

### Task Progress

From within VoiceOS:
```
"Show active tasks"
"Show task progress"
"Show logs for the latest task"
"Check workspace task_abc123"
```

### Performance Metrics

The `--status` command also shows:
- Total requests processed
- Success rate
- Per-tool usage statistics

---

## 🔄 Distributed Mode Usage

When running with `EXECUTION_MODE=queued`:

```bash
# Start main VoiceOS process
python main.py

# Start role-specific workers in separate terminals
python workers/agent_worker.py --roles researcher
python workers/agent_worker.py --roles developer,analyst
```

Workers register with the main process via Redis. Complex and autonomous tasks are queued and picked up by available workers. Worker health is visible in `python main.py --status`.

---

## 🎯 Best Practices

### Writing Effective Commands

| ✅ Good | ❌ Avoid |
|--------|---------|
| "Open Chrome and navigate to github.com" | "Do something with Chrome" |
| "Write a Python script to parse CSV files with pandas" | "Write code" |
| "Research quantum computing trends from 2024 and summarize findings" | "Research stuff" |
| "Build a web scraper for https://news.ycombinator.com top stories" | "Make a scraper" |

**Rules of thumb:**
1. Be specific about what you want
2. Include file paths when referring to existing files
3. Specify programming language for code tasks
4. For autonomous tasks, clearly define the success criteria

### Organizing Your Workspace

All agent work lives in `workspace/`. You can reference files directly in commands:

```
"Analyze workspace/sales_2024.csv"
"Edit workspace/api.py and add error handling"
"Run workspace/scraper.py and show the output"
```

### Managing Long Autonomous Tasks

For long-running tasks:
- VoiceOS streams progress updates to the terminal as it works
- You can say "stop" or press Ctrl+C to cancel gracefully
- Results so far are preserved in the workspace directory

---

## 🚨 Troubleshooting Common Issues

### Voice Not Being Recognized

```bash
# Check and list microphone devices
python -c "import sounddevice; print(sounddevice.query_devices())"

# Set a specific device in .env
MICROPHONE_DEVICE=1    # Use device index from above
```

### LLM Not Responding

```bash
# Check Ollama is running (if using Ollama)
curl http://localhost:11434/api/generate -d '{"model":"mistral","prompt":"hi"}'

# Check LLM config
python main.py --status    # Shows LLM endpoint and provider
```

### Task Stuck or Not Progressing

- Press Ctrl+C to interrupt gracefully
- Check `workspace/logs/agent_operations.log` for the last recorded action
- Run `python main.py --test` to verify all subsystems are healthy

### Out of Memory

```bash
# Use a smaller Whisper model
WHISPER_MODEL=tiny

# Use a smaller/quantized LLM
LLM_MODEL=mistral:7b-instruct-q4_0
```

---

## 📚 Additional Resources

| Resource | Path |
|---------|------|
| Setup & Installation | [docs/setup.md](setup.md) |
| Architecture Overview | [docs/architecture.md](architecture.md) |
| Agent System | [docs/agents.md](agents.md) |
| Tool API Reference | [docs/tool_api.md](tool_api.md) |
| Full API Reference | [docs/api_reference.md](api_reference.md) |
| Memory System | [docs/memory_design.md](memory_design.md) |
| Core Integration | [docs/core_integration_systems.md](core_integration_systems.md) |
| Docker Setup | [docker-instructions.md](../docker-instructions.md) |

---

*VoiceOS is continuously evolving. Check the [Roadmap](../README.md#-roadmap) in the README for upcoming features.*