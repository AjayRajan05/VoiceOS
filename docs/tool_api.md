# 🛠️ VoiceOS Tool API Reference

Detailed API documentation for all five native VoiceOS tool classes, their methods, parameters, return values, and usage examples.

---

## Overview

VoiceOS provides five native tool classes, all registered in the `ToolRegistry` and gated by the `PermissionEngine`:

| Tool Class | Module | Category |
|-----------|--------|---------|
| `EnhancedFileManager` | `tools.file_tools.enhanced_file_manager` | File Operations |
| `BrowserTool` | `tools.web_tools.browser_tool` | Web Browsing |
| `CodeExecutor` | `tools.code_tools.code_executor` | Code Execution |
| `DocumentProcessor` | `tools.document_tools.document_processor` | Document Processing |
| `TaskScheduler` | `tools.scheduler_tools.task_scheduler` | Task Scheduling |

All tools:
- Accept a `workspace_root` parameter (defaults to `project_root/workspace`)
- Enforce workspace boundary — operations outside workspace raise `ValueError`
- Use `@check_permission(PermissionLevel.XXX)` decorators on every method
- Log all operations to `workspace/logs/[tool]_operations.log`

---

## Permission Levels

```python
from permissions.permission_engine import PermissionLevel

PermissionLevel.LOW     # Silent allow — read operations, searches
PermissionLevel.MEDIUM  # User confirmation required — writes, web access
PermissionLevel.HIGH    # Explicit approval required — deletes, code execution
```

---

## EnhancedFileManager

Safe file operations strictly within workspace boundaries.

**Module**: `tools.file_tools.enhanced_file_manager`  
**Import**: `from tools.file_tools.enhanced_file_manager import enhanced_file_manager`

### Constructor

```python
EnhancedFileManager(workspace_root: Optional[str] = None)
```

- `workspace_root`: Absolute path to workspace directory. Defaults to `{project_root}/workspace`.

---

### `read_file(path)`

```python
@check_permission(PermissionLevel.LOW)
def read_file(self, path: str) -> str
```

Read a file's content as UTF-8 text.

**Parameters:**
- `path` — Relative path to file within workspace (e.g., `"data/config.json"`)

**Returns:** File content as string

**Raises:**
- `FileNotFoundError` — File does not exist
- `ValueError` — Path resolves outside workspace
- `PermissionError` — Insufficient permission

**Example:**
```python
content = enhanced_file_manager.read_file("config/settings.json")
print(content)
```

---

### `write_file(path, content)`

```python
@check_permission(PermissionLevel.MEDIUM)
def write_file(self, path: str, content: str) -> str
```

Write text content to a file, creating parent directories if needed.

**Parameters:**
- `path` — Relative path within workspace
- `content` — Text content to write

**Returns:** Success message string (e.g., `"File written to config/settings.json"`)

**Raises:**
- `ValueError` — Path resolves outside workspace
- `PermissionError` — Write permission denied

**Example:**
```python
result = enhanced_file_manager.write_file(
    "output/report.md",
    "# Analysis Report\n\n## Findings\n..."
)
print(result)  # "File written to output/report.md"
```

---

### `create_file(path)`

```python
@check_permission(PermissionLevel.MEDIUM)
def create_file(self, path: str) -> str
```

Create an empty file (touches the file, creating parent directories).

**Parameters:**
- `path` — Relative path within workspace

**Returns:** Success message string

**Example:**
```python
result = enhanced_file_manager.create_file("scripts/runner.py")
```

---

### `delete_file(path)`

```python
@check_permission(PermissionLevel.HIGH)
def delete_file(self, path: str) -> str
```

Permanently delete a file from the workspace.

**Parameters:**
- `path` — Relative path within workspace

**Returns:** Success message string

**Raises:**
- `FileNotFoundError` — File does not exist
- `PermissionError` — Delete permission denied (requires HIGH level + explicit approval)

**Example:**
```python
result = enhanced_file_manager.delete_file("temp/old_data.csv")
```

---

### `list_directory(path=".")`

```python
@check_permission(PermissionLevel.LOW)
def list_directory(self, path: str = ".") -> List[Dict[str, Any]]
```

List contents of a directory within the workspace.

**Parameters:**
- `path` — Relative path to directory (defaults to workspace root)

**Returns:** List of dictionaries with file metadata:
```python
[
    {"name": "data.csv", "type": "file", "size": 1024, "modified": "2026-06-15T10:00:00"},
    {"name": "output/", "type": "directory", "size": 0, "modified": "2026-06-15T09:30:00"},
]
```

**Example:**
```python
items = enhanced_file_manager.list_directory("output")
for item in items:
    print(f"{item['name']} ({item['type']}, {item['size']} bytes)")
```

---

### `file_exists(path)`

```python
@check_permission(PermissionLevel.LOW)
def file_exists(self, path: str) -> bool
```

Check whether a file exists within the workspace.

**Parameters:**
- `path` — Relative path within workspace

**Returns:** `True` if exists, `False` otherwise

**Example:**
```python
if enhanced_file_manager.file_exists("config/settings.json"):
    config = enhanced_file_manager.read_file("config/settings.json")
```

---

## BrowserTool

Safe web browsing, searching, and content scraping with URL validation and content size limits.

**Module**: `tools.web_tools.browser_tool`  
**Import**: `from tools.web_tools.browser_tool import browser_tool`

### Constructor

```python
BrowserTool(workspace_root: Optional[str] = None)
```

---

### `search_web(query, max_results=10)`

```python
@check_permission(PermissionLevel.LOW)
def search_web(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]
```

Perform a web search using DuckDuckGo.

**Parameters:**
- `query` — Search query string
- `max_results` — Maximum number of results (default: 10)

**Returns:**
```python
[
    {
        "title": "Python Tutorial for Beginners",
        "url": "https://example.com/python-tutorial",
        "snippet": "Learn Python from scratch with...",
        "source": "example.com"
    },
    ...
]
```

**Example:**
```python
results = browser_tool.search_web("Python async programming best practices", max_results=5)
for r in results:
    print(f"{r['title']} — {r['url']}")
```

---

### `open_page(url)`

```python
@check_permission(PermissionLevel.MEDIUM)
def open_page(self, url: str) -> Dict[str, Any]
```

Fetch a web page and return its readable content.

**Parameters:**
- `url` — Full URL of the page (must be `http://` or `https://`)

**Returns:**
```python
{
    "url": "https://example.com",
    "status_code": 200,
    "title": "Example Page",
    "content": "Full readable text content...",
    "content_length": 15234
}
```

**Raises:**
- `ValueError` — Invalid URL or blocked domain
- `PermissionError` — Insufficient permission

**Example:**
```python
page = browser_tool.open_page("https://docs.python.org/3/")
print(f"Title: {page['title']}")
print(f"Content length: {page['content_length']} chars")
```

---

### `scrape_content(url, selectors=None)`

```python
@check_permission(PermissionLevel.MEDIUM)
def scrape_content(self, url: str, selectors: Optional[List[str]] = None) -> Dict[str, Any]
```

Scrape specific content from a web page using CSS selectors.

**Parameters:**
- `url` — Full URL of the page
- `selectors` — Optional list of CSS selectors to extract specific elements

**Returns:**
```python
{
    "url": "https://example.com",
    "content": "Extracted text from selected elements...",
    "elements": {"h1": ["Title"], ".article": ["Body text"]},
    "metadata": {"word_count": 512, "links": 23}
}
```

**Example:**
```python
result = browser_tool.scrape_content(
    "https://news.ycombinator.com",
    selectors=[".titleline", ".score"]
)
```

---

### `get_page_info(url)`

```python
@check_permission(PermissionLevel.LOW)
def get_page_info(self, url: str) -> Dict[str, Any]
```

Get basic page information without fetching full content (fast HEAD request).

**Parameters:**
- `url` — URL to check

**Returns:**
```python
{
    "url": "https://example.com",
    "accessible": True,
    "status_code": 200,
    "content_type": "text/html",
    "content_length": 15234
}
```

**Example:**
```python
info = browser_tool.get_page_info("https://api.example.com/health")
if info["accessible"] and info["status_code"] == 200:
    data = browser_tool.open_page("https://api.example.com/data")
```

---

## CodeExecutor

Sandboxed code execution with security validation, resource limits, and output capture.

**Module**: `tools.code_tools.code_executor`  
**Import**: `from tools.code_tools.code_executor import code_executor`

> ⚠️ All `execute_code` calls require **HIGH permission** and explicit user approval.

### Constructor

```python
CodeExecutor(workspace_root: Optional[str] = None)
```

---

### `execute_code(code, language="python")`

```python
@check_permission(PermissionLevel.HIGH)
def execute_code(self, code: str, language: str = "python") -> Dict[str, Any]
```

Execute code in a sandboxed subprocess within the workspace.

**Parameters:**
- `code` — Source code to execute
- `language` — Programming language: `"python"`, `"bash"`, `"javascript"` (default: `"python"`)

**Returns:**
```python
{
    "success": True,
    "output": "Hello, World!\n",
    "error": None,
    "execution_time": 0.35,
    "exit_code": 0,
    "language": "python"
}
```

On failure:
```python
{
    "success": False,
    "output": "",
    "error": "NameError: name 'x' is not defined",
    "execution_time": 0.1,
    "exit_code": 1,
    "language": "python"
}
```

**Security checks performed before execution:**
- Scans for dangerous imports (`os.system`, `subprocess.call`, `__import__`, etc.)
- Validates language is in the supported list
- Enforces execution time limit (default: 30 seconds)
- Enforces memory limit (default: 256 MB)

**Example:**
```python
code = """
import json

data = [{"name": "Alice", "score": 95}, {"name": "Bob", "score": 87}]
avg = sum(d["score"] for d in data) / len(data)
print(f"Average score: {avg:.1f}")
print(json.dumps(data, indent=2))
"""

result = code_executor.execute_code(code, "python")
if result["success"]:
    print(result["output"])
else:
    print(f"Error: {result['error']}")
```

---

## DocumentProcessor

Extract, analyze, search, and convert documents (PDF, DOCX, TXT).

**Module**: `tools.document_tools.document_processor`  
**Import**: `from tools.document_tools.document_processor import document_processor`

### Constructor

```python
DocumentProcessor(workspace_root: Optional[str] = None)
```

---

### `extract_text(file_path)`

```python
@check_permission(PermissionLevel.LOW)
def extract_text(self, file_path: str) -> Dict[str, Any]
```

Extract all text content from a document.

**Supported formats:** `.pdf`, `.docx`, `.txt`, `.md`

**Returns:**
```python
{
    "success": True,
    "text": "Full extracted text content...",
    "page_count": 12,
    "word_count": 3456,
    "format": "pdf"
}
```

**Example:**
```python
result = document_processor.extract_text("reports/annual_report.pdf")
print(f"Pages: {result['page_count']}, Words: {result['word_count']}")
print(result["text"][:500])
```

---

### `summarize_document(file_path, max_length=500)`

```python
@check_permission(PermissionLevel.LOW)
def summarize_document(self, file_path: str, max_length: int = 500) -> Dict[str, Any]
```

Generate a concise summary of a document using the LLM.

**Parameters:**
- `file_path` — Path to document within workspace
- `max_length` — Maximum summary length in words (default: 500)

**Returns:**
```python
{
    "success": True,
    "summary": "This report covers Q3 2024 financial performance...",
    "key_points": ["Revenue grew 15% YoY", "Operating costs reduced by 8%"],
    "word_count": 245
}
```

**Example:**
```python
summary = document_processor.summarize_document("reports/q3_report.pdf", max_length=200)
print(summary["summary"])
```

---

### `search_in_document(file_path, query)`

```python
@check_permission(PermissionLevel.LOW)
def search_in_document(self, file_path: str, query: str) -> Dict[str, Any]
```

Search for text or a phrase within a document.

**Returns:**
```python
{
    "success": True,
    "query": "revenue growth",
    "total_matches": 5,
    "matches": [
        {"page": 2, "context": "...revenue growth accelerated to 15%...", "position": 1234},
        ...
    ]
}
```

**Example:**
```python
result = document_processor.search_in_document("reports/annual.pdf", "machine learning")
print(f"Found {result['total_matches']} matches")
for match in result["matches"]:
    print(f"Page {match['page']}: {match['context']}")
```

---

### `analyze_document(file_path)`

```python
@check_permission(PermissionLevel.MEDIUM)
def analyze_document(self, file_path: str) -> Dict[str, Any]
```

Analyze a document's structure, metadata, and statistics.

**Returns:**
```python
{
    "success": True,
    "metadata": {
        "title": "Annual Report 2024",
        "author": "Finance Team",
        "created": "2024-01-15",
        "pages": 45
    },
    "statistics": {
        "word_count": 12500,
        "paragraph_count": 320,
        "section_count": 8,
        "image_count": 12,
        "table_count": 5
    },
    "structure": ["Executive Summary", "Financial Overview", "...]
}
```

---

### `convert_document(file_path, output_format)`

```python
@check_permission(PermissionLevel.MEDIUM)
def convert_document(self, file_path: str, output_format: str) -> Dict[str, Any]
```

Convert a document to a different format.

**Supported output formats:** `"txt"`, `"md"`, `"json"`

**Returns:**
```python
{
    "success": True,
    "output_path": "reports/annual_report.txt",
    "message": "Successfully converted to txt",
    "size": 45678
}
```

**Example:**
```python
result = document_processor.convert_document("reports/spec.pdf", "md")
print(f"Converted to: {result['output_path']}")
```

---

## TaskScheduler

Schedule, manage, and monitor timed or recurring tasks.

**Module**: `tools.scheduler_tools.task_scheduler`  
**Import**: `from tools.scheduler_tools.task_scheduler import task_scheduler`

### Constructor

```python
TaskScheduler(workspace_root: Optional[str] = None)
```

---

### `schedule_task(task_data)`

```python
@check_permission(PermissionLevel.MEDIUM)
def schedule_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]
```

Schedule a new task for future execution.

**Parameters — `task_data` dictionary:**

```python
{
    "name": "daily_backup",                       # Required: unique task name
    "task_type": "file_operation",                # Required: task category
    "scheduled_time": "2026-06-17T09:00:00",     # Required: ISO 8601 datetime
    "parameters": {                               # Optional: task-specific config
        "source": "workspace/data",
        "destination": "workspace/backup"
    },
    "recurring": False,                           # Optional: set True for recurring
    "interval_seconds": 86400                     # Optional: recurrence interval
}
```

**Returns:**
```python
{
    "success": True,
    "task_id": "task_1718607600_daily_backup",
    "message": "Task scheduled successfully",
    "scheduled_time": "2026-06-17T09:00:00"
}
```

**Example:**
```python
from datetime import datetime, timedelta

result = task_scheduler.schedule_task({
    "name": "weekly_report",
    "task_type": "code_execution",
    "scheduled_time": (datetime.now() + timedelta(days=7)).isoformat(),
    "parameters": {"script": "workspace/generate_report.py"}
})
print(f"Scheduled with ID: {result['task_id']}")
```

---

### `list_tasks(status=None)`

```python
@check_permission(PermissionLevel.LOW)
def list_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]
```

List all scheduled tasks, optionally filtered by status.

**Parameters:**
- `status` — Filter: `"scheduled"`, `"running"`, `"completed"`, `"cancelled"` (omit for all)

**Returns:** List of task dictionaries with full metadata

**Example:**
```python
# All pending tasks
tasks = task_scheduler.list_tasks("scheduled")
for t in tasks:
    print(f"{t['name']} — {t['scheduled_time']} ({t['status']})")
```

---

### `get_task_status(task_id)`

```python
@check_permission(PermissionLevel.LOW)
def get_task_status(self, task_id: str) -> Dict[str, Any]
```

Get the current status and details of a specific task.

**Returns:**
```python
{
    "task_id": "task_1718607600_daily_backup",
    "name": "daily_backup",
    "status": "scheduled",
    "scheduled_time": "2026-06-17T09:00:00",
    "created_at": "2026-06-16T10:00:00",
    "last_run": None,
    "next_run": "2026-06-17T09:00:00"
}
```

---

### `cancel_task(task_id)`

```python
@check_permission(PermissionLevel.MEDIUM)
def cancel_task(self, task_id: str) -> Dict[str, Any]
```

Cancel a scheduled or recurring task.

**Returns:**
```python
{
    "success": True,
    "task_id": "task_1718607600_daily_backup",
    "message": "Task cancelled successfully"
}
```

---

### `reschedule_task(task_id, new_time)`

```python
@check_permission(PermissionLevel.MEDIUM)
def reschedule_task(self, task_id: str, new_time: datetime) -> Dict[str, Any]
```

Change the scheduled time of an existing task.

**Example:**
```python
from datetime import datetime, timedelta

new_time = datetime.now() + timedelta(hours=3)
result = task_scheduler.reschedule_task("task_1718607600_daily_backup", new_time)
```

---

## Tool Registry Integration

All tools are auto-registered at startup via `VoiceOSToolsIntegration`:

```python
from tools.voiceos_tools_integration import initialize_voiceos_tools_integration
from tools.tool_registry import ToolRegistry

tool_registry = ToolRegistry()
integration = initialize_voiceos_tools_integration(tool_registry)
count = integration.register_voiceos_tools()
print(f"Registered {count} tools")
```

### Programmatic Tool Access

```python
from tools.tool_registry import ToolRegistry

registry = ToolRegistry()

# List all registered tools
tools = registry.list_tools()
print(tools)  # ['enhanced_file_manager', 'browser_tool', ...]

# Get tool metadata
info = registry.get_tool_info("enhanced_file_manager")

# Execute tool programmatically
result = await registry.execute_tool("enhanced_file_manager", {
    "method": "write_file",
    "path": "output/result.txt",
    "content": "Hello VoiceOS!"
})
```

---

## Error Handling

All tools follow a consistent error pattern:

```python
try:
    result = enhanced_file_manager.read_file("data.txt")
except FileNotFoundError as e:
    print(f"File not found: {e}")
except ValueError as e:
    # Path outside workspace, invalid URL, etc.
    print(f"Invalid input: {e}")
except PermissionError as e:
    # Permission denied (user declined or insufficient level)
    print(f"Permission denied: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

---

## Audit Logs

All tool operations are automatically logged:

| Tool | Log File |
|------|---------|
| `EnhancedFileManager` | `workspace/logs/file_operations.log` |
| `BrowserTool` | `workspace/logs/browser_operations.log` |
| `CodeExecutor` | `workspace/logs/code_execution.log` |
| `DocumentProcessor` | `workspace/logs/document_operations.log` |
| `TaskScheduler` | `workspace/logs/scheduler_operations.log` |

Each log entry contains: timestamp, agent type, tool name, method, parameters (sanitized), result status, and execution time.