# 📚 VoiceOS API Reference

Complete API reference for VoiceOS core modules, agents, tools, audio, LLM, memory, and plugins.

---

## Table of Contents

- [Core API](#-core-api)
- [Tools API](#️-tools-api)
- [Permissions API](#-permissions-api)
- [Agents API](#-agents-api)
- [Tool Registry API](#-tool-registry-api)
- [Audio API](#-audio-api)
- [LLM API](#-llm-api)
- [Memory API](#-memory-api)
- [Plugin API](#-plugin-api)
- [Core Integration Systems API](#-core-integration-systems-api)
- [Usage Examples](#-usage-examples)

---

## 🏗️ Core API

### `core.config.Config`

Central configuration singleton for VoiceOS.

```python
class Config:
    @property
    def project_root(self) -> Path:
        """Absolute path to the project root directory"""

    @property
    def workspace(self) -> Path:
        """Absolute path to the workspace directory"""

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by dotted key (e.g. 'voice.enable_interrupts')"""

    def set_config(self, key: str, value: Any) -> None:
        """Set a configuration value at runtime"""

    def load_from_file(self, config_path: Path) -> None:
        """Load configuration from a YAML file"""
```

---

### `core.config_manager.ConfigManager`

Loads and manages the main `voiceos.yaml` configuration.

```python
class ConfigManager:
    def __init__(self, config_file: str = "config/voiceos.yaml"):
        """Initialize with path to the YAML config file"""

    def get_config(self) -> VoiceOSConfig:
        """Return the parsed VoiceOS configuration dataclass"""

    def reload(self) -> None:
        """Reload configuration from file (picks up changes without restart)"""
```

---

### `core.events.event_bus.EventBus`

Async pub/sub event bus — the backbone of inter-component communication.

```python
class EventBus:
    def subscribe(self, event_type: str, callback: Callable[[Event], Awaitable]) -> str:
        """Subscribe to an event type. Returns subscription_id."""

    def unsubscribe(self, subscription_id: str) -> None:
        """Cancel a subscription by ID"""

    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribers (async, non-blocking)"""

    def publish_sync(self, event: Event) -> None:
        """Publish an event synchronously (blocks until all handlers complete)"""
```

**Event types** (from `core.events.events.Events`):

```python
class Events:
    USER_VOICE_INPUT       = "user.voice_input"
    USER_CLI_INPUT         = "user.cli_input"
    ORCHESTRATOR_RESPONSE  = "orchestrator.response"
    TASK_STARTED           = "task.started"
    TASK_COMPLETED         = "task.completed"
    TASK_FAILED            = "task.failed"
    INTERRUPT_REQUESTED    = "interrupt.requested"
    TTS_STARTED            = "tts.started"
    TTS_STOPPED            = "tts.stopped"
    AGENT_ACTION           = "agent.action"
    PERMISSION_REQUESTED   = "permission.requested"
    PERMISSION_GRANTED     = "permission.granted"
    PERMISSION_DENIED      = "permission.denied"
```

---

### `core.event.Event`

Base event dataclass published on the EventBus.

```python
@dataclass
class Event:
    type: str                         # Event type string (from Events enum)
    payload: Dict[str, Any]           # Event data
    source: str                       # Publisher identifier
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_id: str = field(default_factory=lambda: str(uuid4()))
```

---

### `core.orchestrator.Orchestrator`

The top-level coordinator that processes user inputs and drives the agent/tool pipeline.

```python
class Orchestrator:
    def __init__(
        self,
        event_bus: EventBus,
        tool_executor: ToolExecutor,
        permission_engine: PermissionEngine,
        config: OrchestratorConfig,
        agent_llm: LLMClient,
        runtime_context: RuntimeContext,
    ):
        """Initialize orchestrator with all required subsystems"""

    async def process_input(self, user_input: str, source: str = "cli") -> str:
        """Process a user command and return the response text"""

    async def health_check(self) -> Dict[str, Any]:
        """Check health status of all subsystems. Returns {'status': 'ok'|'degraded'|'error'}"""

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics (total requests, success rate, etc.)"""
```

**OrchestratorConfig:**

```python
@dataclass
class OrchestratorConfig:
    enable_interrupts: bool = True
    max_execution_time: float = 300.0       # seconds
    enable_workspace_isolation: bool = True
    enable_agent_memory: bool = True
    safety_mode: str = "strict"             # "strict" | "permissive"
```

---

### `core.logger.VoiceOSLogger`

Structured JSON logger for all VoiceOS components.

```python
class VoiceOSLogger:
    def log_tool_execution(
        self,
        tool_name: str,
        method: str,
        result: Any,
        error: Optional[str] = None,
        execution_time: float = 0.0
    ) -> None:
        """Log a tool execution with structured data"""

    def log_agent_action(
        self,
        agent_type: str,
        action: str,
        context: Dict[str, Any]
    ) -> None:
        """Log an agent's reasoning step or action"""

    def log_security_event(
        self,
        event_type: str,
        details: Dict[str, Any]
    ) -> None:
        """Log security-relevant events (permission checks, denials, etc.)"""

    def get_logs(
        self,
        level: Optional[str] = None,
        limit: int = 100,
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve recent log entries with optional filtering"""
```

---

## 🛠️ Tools API

### `tools.file_tools.enhanced_file_manager.EnhancedFileManager`

See **[Tool API Reference](tool_api.md)** for full documentation.

Quick reference:

```python
class EnhancedFileManager:
    def read_file(self, path: str) -> str                              # LOW
    def write_file(self, path: str, content: str) -> str              # MEDIUM
    def create_file(self, path: str) -> str                           # MEDIUM
    def delete_file(self, path: str) -> str                           # HIGH
    def list_directory(self, path: str = ".") -> List[Dict[str, Any]] # LOW
    def file_exists(self, path: str) -> bool                          # LOW
```

### `tools.web_tools.browser_tool.BrowserTool`

```python
class BrowserTool:
    def search_web(self, query: str, max_results: int = 10) -> List[Dict[str, Any]] # LOW
    def open_page(self, url: str) -> Dict[str, Any]                                  # MEDIUM
    def scrape_content(self, url: str, selectors: Optional[List[str]] = None) -> Dict[str, Any] # MEDIUM
    def get_page_info(self, url: str) -> Dict[str, Any]                              # LOW
```

### `tools.code_tools.code_executor.CodeExecutor`

```python
class CodeExecutor:
    def execute_code(self, code: str, language: str = "python") -> Dict[str, Any]   # HIGH
```

### `tools.document_tools.document_processor.DocumentProcessor`

```python
class DocumentProcessor:
    def extract_text(self, file_path: str) -> Dict[str, Any]                        # LOW
    def summarize_document(self, file_path: str, max_length: int = 500) -> Dict[str, Any] # LOW
    def search_in_document(self, file_path: str, query: str) -> Dict[str, Any]      # LOW
    def analyze_document(self, file_path: str) -> Dict[str, Any]                    # MEDIUM
    def convert_document(self, file_path: str, output_format: str) -> Dict[str, Any] # MEDIUM
```

### `tools.scheduler_tools.task_scheduler.TaskScheduler`

```python
class TaskScheduler:
    def schedule_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]            # MEDIUM
    def list_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]      # LOW
    def get_task_status(self, task_id: str) -> Dict[str, Any]                       # LOW
    def cancel_task(self, task_id: str) -> Dict[str, Any]                           # MEDIUM
    def reschedule_task(self, task_id: str, new_time: datetime) -> Dict[str, Any]   # MEDIUM
```

---

## 🔐 Permissions API

### `permissions.permission_engine.PermissionEngine`

```python
class PermissionEngine:
    def check_tool_permission(self, required_level: PermissionLevel) -> bool:
        """Check if current permission level allows the required level"""

    def set_user_permission_level(self, level: PermissionLevel) -> None:
        """Override the active permission level"""

    def get_user_permission_level(self) -> PermissionLevel:
        """Get the current active permission level"""

    async def request_permission(
        self,
        operation: str,
        level: PermissionLevel,
        context: Dict[str, Any] = None
    ) -> bool:
        """Interactively prompt the user for permission. Returns True if granted."""
```

### `PermissionLevel` Enum

```python
from permissions.permission_engine import PermissionLevel

PermissionLevel.LOW     # Read operations — silent allow
PermissionLevel.MEDIUM  # Write/network operations — user confirmation
PermissionLevel.HIGH    # Destructive/exec operations — explicit approval
```

### `check_permission` Decorator

```python
from permissions.permission_engine import check_permission, PermissionLevel

@check_permission(PermissionLevel.MEDIUM)
def my_write_function(path: str, content: str) -> str:
    """This function will check permission before executing"""
    ...
```

---

## 🤖 Agents API

### `agents.core.planner.Planner`

```python
class Planner:
    async def analyze_input(self, user_input: str) -> TaskPlan:
        """Analyze and classify user input into a TaskPlan"""

    async def generate_plan(
        self,
        task_type: str,
        input_data: Dict[str, Any]
    ) -> TaskPlan:
        """Generate a detailed execution plan"""

    def estimate_execution_time(self, plan: TaskPlan) -> float:
        """Estimate task duration in seconds"""
```

**TaskPlan dataclass:**

```python
@dataclass
class TaskPlan:
    type: str                          # "simple" | "complex" | "autonomous"
    goal: str                          # User's original intent
    domain: Optional[str] = None       # "researcher" | "developer" | "analyst"
    tool: Optional[str] = None         # For simple tasks: specific tool name
    estimated_time: float = 0.0
    required_permissions: List[PermissionLevel] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
```

---

### `agents.core.router.Router`

```python
class Router:
    async def route_task(self, task_plan: TaskPlan) -> Any:
        """Route a classified task to the appropriate executor"""

    def select_dynamic_agent(
        self,
        domain: str,
        requirements: Dict[str, Any]
    ) -> DynamicAgent:
        """Select the best dynamic agent for the domain"""

    async def coordinate_parallel(
        self,
        sub_tasks: List[TaskPlan]
    ) -> List[Result]:
        """Execute multiple sub-tasks in parallel (Meta-Planner)"""
```

---

### `agents.core.safety.Safety`

```python
class Safety:
    async def assess_risk(self, task: TaskPlan) -> RiskLevel:
        """Assess the risk level of a task plan"""

    def validate_action(self, action: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate a proposed action. Returns (is_safe, reason)."""

    def check_path_safety(self, path: str) -> bool:
        """Check if a file path is safe (within workspace, not blocked)"""

    def check_code_safety(self, code: str) -> Tuple[bool, List[str]]:
        """Check code for dangerous patterns. Returns (is_safe, violations)."""
```

---

### `agents.autonomous.agent_loop.AutonomousAgentLoop`

```python
class AutonomousAgentLoop:
    def __init__(
        self,
        goal: str,
        tools: List[str],
        workspace_id: str,
        max_iterations: int = 20,
        max_time_seconds: float = 300.0
    ):
        """Initialize the autonomous loop with a goal and available tools"""

    async def execute(self) -> AutonomousResult:
        """Run the think → decide → act → observe loop until goal met or limits hit"""

    async def think_phase(self) -> Thought:
        """Analyze state, completed actions, and plan the next step"""

    async def decide_phase(self, thought: Thought) -> Decision:
        """Select the optimal action based on the thought"""

    async def act_phase(self, decision: Decision) -> ActionResult:
        """Execute the chosen action (tool call or code execution)"""

    async def observe_phase(self, result: ActionResult) -> Observation:
        """Assess results and update task state"""

    async def generate_tool(self, tool_spec: str) -> str:
        """Generate a new tool on-the-fly using the LLM"""
```

**AutonomousResult:**

```python
@dataclass
class AutonomousResult:
    success: bool
    goal: str
    iterations: int
    total_time: float
    artifacts: List[str]           # Paths to created files
    summary: str
    actions_taken: List[str]       # Human-readable action log
```

---

### `agents.agent_tool_integration.AgentToolManager`

High-level manager for agent-initiated tool execution.

```python
class AgentToolManager:
    async def execute_agent_task(
        self,
        agent_type: str,
        task_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a task plan for a specific agent type"""

    def get_agent_capabilities(self, agent_type: str) -> Dict[str, Any]:
        """Get a summary of what tools and capabilities an agent type has"""

    async def execute_tool_for_agent(
        self,
        agent_type: str,
        tool_name: str,
        method_name: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Execute a specific tool method on behalf of an agent (with permission check)"""
```

---

## 🔧 Tool Registry API

### `tools.tool_registry.ToolRegistry`

```python
class ToolRegistry:
    def register_tool(self, tool_class: Type) -> bool:
        """Register a tool class. Returns True on success."""

    def get_tool(self, tool_name: str) -> Optional[ToolRegistration]:
        """Get the registration record for a tool"""

    def list_tools(self, category: Optional[ToolCategory] = None) -> List[str]:
        """List all registered tool names, optionally filtered by category"""

    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> Any:
        """Execute a tool by name with given parameters"""

    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get tool metadata, permission level, and available methods"""
```

**ToolCategory enum:**

```python
class ToolCategory:
    FILE_OPERATIONS
    WEB_OPERATIONS
    CODE_EXECUTION
    DOCUMENT_PROCESSING
    TASK_SCHEDULING
    OS_CONTROL
    COMMUNICATION
    UTILITY
```

---

## 🎵 Audio API

### `audio.voice_pipeline.VoicePipeline`

```python
class VoicePipeline:
    def __init__(
        self,
        event_bus: EventBus,
        speech_state: SpeechState,
        voice_config: VoiceConfig
    ):
        """Initialize voice pipeline with bus, state tracker, and config"""

    async def start(self) -> None:
        """Start microphone capture and STT streaming"""

    async def stop(self) -> None:
        """Stop microphone and release audio resources"""
```

---

### `audio.streaming_stt.StreamingSTT`

```python
class StreamingSTT:
    def __init__(self, model_name: str = "base"):
        """Initialize with Whisper model name: tiny|base|small|medium|large"""

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[bytes]
    ) -> AsyncIterator[str]:
        """Stream audio chunks and yield transcription fragments"""

    def transcribe_file(self, audio_file: Path) -> str:
        """Transcribe a saved audio file and return full text"""
```

---

### `interrupt.tts_controller.TTSController`

```python
class TTSController:
    def __init__(
        self,
        event_bus: EventBus,
        tts_engine: TTSEngine,
        speech_state: SpeechState
    ):
        """Initialize TTS controller"""

    async def speak(self, text: str) -> None:
        """Synthesize text and play through speakers (interruptible)"""

    def stop(self) -> None:
        """Immediately stop current TTS playback"""

    def is_speaking(self) -> bool:
        """True if TTS is currently playing audio"""
```

---

### TTS Engine Factory

```python
# tts/engine_factory.py
def create_tts_engine(voice_config: VoiceConfig) -> TTSEngine:
    """Create the appropriate TTS engine based on configuration.
    Returns KokoroEngine by default, CoquiEngine if configured."""
```

---

## 🔍 LLM API

### `llm.llm_client.LLMClient`

```python
class LLMClient:
    def __init__(
        self,
        model_name: str,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None
    ):
        """Initialize LLM client (supports local GGUF, Ollama, OpenAI-compatible APIs)"""

    async def generate_response(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        stop: Optional[List[str]] = None
    ) -> str:
        """Generate a single response from a prompt"""

    async def generate_with_context(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> str:
        """Generate response with chat history (list of {role, content} dicts)"""

    def get_model_info(self) -> Dict[str, Any]:
        """Return model name, provider, context length, and capabilities"""
```

**Messages format:**
```python
messages = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "What is Python?"},
    {"role": "assistant", "content": "Python is a programming language..."},
    {"role": "user", "content": "Give me an example"},
]
```

---

### `llm.conversation_engine.ConversationEngine`

```python
class ConversationEngine:
    def __init__(self, llm_client: LLMClient, max_history: int = 20):
        """Initialize conversation engine with LLM client"""

    def add_message(self, role: str, content: str) -> None:
        """Append a message to conversation history"""

    def get_context(self, max_messages: int = 10) -> List[Dict[str, str]]:
        """Get recent conversation history for LLM context window"""

    async def generate_response(self, user_input: str) -> str:
        """Generate a contextual response to user input"""

    def clear_conversation(self) -> None:
        """Reset conversation history"""
```

---

## 🧠 Memory API

### `memory.memory_manager.MemoryManager`

```python
class MemoryManager:
    def store_memory(
        self,
        key: str,
        value: Any,
        category: str = "general",
        importance: float = 0.5,
        tags: List[str] = None
    ) -> str:
        """Store a value with metadata. Returns the memory key."""

    def retrieve_memory(self, key: str) -> Optional[Any]:
        """Retrieve a value by exact key"""

    def search_memories(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 10
    ) -> List[MemoryEntry]:
        """Full-text search across all memory entries"""

    def semantic_search(
        self,
        query: str,
        threshold: float = 0.7
    ) -> List[MemoryEntry]:
        """Vector similarity search (requires ChromaDB)"""

    def get_recent_memories(
        self,
        limit: int = 10,
        category: Optional[str] = None
    ) -> List[MemoryEntry]:
        """Get recently stored or accessed entries"""

    def update_memory(
        self,
        key: str,
        value: Any,
        importance: Optional[float] = None
    ) -> bool:
        """Update an existing entry"""

    def delete_memory(self, key: str) -> bool:
        """Delete a memory entry by key"""

    def cleanup_old_memories(self, max_age: timedelta) -> int:
        """Remove entries older than max_age. Returns count deleted."""
```

---

## 🔌 Plugin API

### `plugins.plugin_loader.PluginLoader`

```python
class PluginLoader:
    def __init__(self, plugin_directory: Path):
        """Initialize with path to plugins directory"""

    def discover_plugins(self) -> List[PluginInfo]:
        """Scan directory and return list of available plugins"""

    def load_plugin(self, plugin_name: str) -> Plugin:
        """Load and initialize a specific plugin"""

    def validate_plugin(self, plugin_path: Path) -> Tuple[bool, List[str]]:
        """Validate plugin for security and compatibility. Returns (valid, errors)."""

    def unload_plugin(self, plugin_name: str) -> bool:
        """Gracefully unload a plugin and release its resources"""

    def list_loaded_plugins(self) -> List[str]:
        """Return names of all currently loaded plugins"""
```

### Plugin Interface

```python
class Plugin:
    """Base interface all VoiceOS plugins must implement"""

    @property
    def name(self) -> str: ...
    @property
    def version(self) -> str: ...
    @property
    def description(self) -> str: ...

    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize plugin with system configuration"""

    def get_tools(self) -> List[Tool]:
        """Return list of tools this plugin contributes"""

    async def cleanup(self) -> None:
        """Release all plugin resources gracefully"""
```

---

## 🔧 Core Integration Systems API

### Plugin System

```python
from core.plugins.complete_plugin_integration import get_complete_plugin_system

system = get_complete_plugin_system()
await system.enable_plugin("my_plugin")
await system.disable_plugin("my_plugin")
status = await system.get_system_status()
```

### Plugin Registry

```python
from core.plugins.plugin_registry import get_plugin_registry

registry = get_plugin_registry()
discovered = await registry.discover_plugins()
result = await registry.register_plugin(plugin_path)
state = registry.get_registry_state()
```

### Plugin Lifecycle

```python
from core.plugins.plugin_lifecycle import get_lifecycle_manager

lifecycle = get_lifecycle_manager()
await lifecycle.load_plugin("my_plugin")
await lifecycle.activate_plugin("my_plugin")
await lifecycle.suspend_plugin("my_plugin", reason="Maintenance")
```

**Plugin states:** `DISCOVERED → LOADING → LOADED → INITIALIZING → ACTIVE → SUSPENDED`

### Plugin Configuration

```python
from core.plugins.plugin_configuration import get_plugin_config_manager, ConfigScope

config = get_plugin_config_manager()
await config.set_config("my_plugin", "key", "value", ConfigScope.GLOBAL)
value = await config.get_config("my_plugin", "key", ConfigScope.GLOBAL)
```

**Config scopes:** `GLOBAL`, `PLUGIN`, `USER`, `WORKSPACE`, `SESSION`

### Extension System

```python
from core.extensions.extension_point_system import (
    before_tool_execution, after_tool_execution,
    before_llm_request, after_llm_response,
    data_processing, error_handling, logging_decorator
)

@before_tool_execution
async def my_hook(context: Dict[str, Any]) -> Dict[str, Any]:
    """Runs before any tool execution"""
    context["start_time"] = time.time()
    return context

@after_tool_execution
async def my_after_hook(context: Dict[str, Any]) -> Dict[str, Any]:
    """Runs after any tool execution"""
    duration = time.time() - context.get("start_time", time.time())
    print(f"Tool took {duration:.2f}s")
    return context
```

**Extension points:** `BEFORE_TOOL_EXECUTION`, `AFTER_TOOL_EXECUTION`, `BEFORE_LLM_REQUEST`, `AFTER_LLM_RESPONSE`, `DATA_PROCESSING`, `USER_INPUT_VALIDATION`, `ERROR_HANDLING`, `LOGGING_EXTENSION`, `SYSTEM_STARTUP`, `SYSTEM_SHUTDOWN`

### Controlled Execution

```python
from core.integration.controlled_execution import get_controlled_execution_manager, ExecutionLimits

manager = get_controlled_execution_manager()
result = await manager.execute_with_limits(
    target_function,
    args=(arg1, arg2),
    kwargs={"key": "val"},
    limits=ExecutionLimits(
        max_execution_time=30.0,
        max_memory_mb=512,
        max_cpu_percent=80
    )
)
```

### Unified Dashboard

```python
from core.system.unified_integration_dashboard import get_unified_integration_dashboard

dashboard = get_unified_integration_dashboard()
status = dashboard.get_system_status()     # Overall system health
metrics = dashboard.get_system_metrics()   # Real-time performance metrics
views = dashboard.get_available_views()    # OVERVIEW | PLUGINS | HELPERS | ...
```

### System Verification

```python
from core.system.system_verification import VoiceOSSystemVerification

verifier = VoiceOSSystemVerification()
results = await verifier.verify_all_systems()

if results.overall_status == "PASSED":
    print("All systems ready!")
else:
    for component, result in results.component_results.items():
        if result.status != "PASSED":
            print(f"  {component}: {result.message}")
```

---

## 📝 Usage Examples

### Basic Tool Usage

```python
from tools.file_tools.enhanced_file_manager import enhanced_file_manager
from tools.web_tools.browser_tool import browser_tool
from permissions.permission_engine import PermissionLevel, permission_engine

# Set permission level (skip interactive prompts in scripts)
permission_engine.set_user_permission_level(PermissionLevel.MEDIUM)

# File operations
enhanced_file_manager.write_file("output/result.txt", "Hello, VoiceOS!")
content = enhanced_file_manager.read_file("output/result.txt")

# Web research
results = browser_tool.search_web("Python asyncio tutorial", max_results=3)
for r in results:
    print(f"{r['title']}: {r['url']}")
```

---

### Running the Full Orchestrator

```python
import asyncio
from core.events.event_bus import EventBus
from core.orchestrator import Orchestrator, OrchestratorConfig
from core.runtime.bootstrap import build_runtime_context
from core.config_manager import ConfigManager

async def main():
    config_manager = ConfigManager("config/voiceos.yaml")
    config = config_manager.get_config()

    bus = EventBus()
    orchestrator_config = OrchestratorConfig(
        enable_interrupts=True,
        max_execution_time=300.0,
        enable_workspace_isolation=True,
        enable_agent_memory=True,
        safety_mode="strict",
    )

    ctx = build_runtime_context(config, bus, safety_mode="strict")
    orchestrator = Orchestrator(
        event_bus=bus,
        tool_executor=ctx.tool_executor,
        permission_engine=ctx.permission_engine,
        config=orchestrator_config,
        agent_llm=ctx.agent_llm,
        runtime_context=ctx,
    )

    response = await orchestrator.process_input("Write a Python hello world script")
    print(response)

asyncio.run(main())
```

---

### Agent Tool Manager Usage

```python
from agents.agent_tool_integration import AgentToolManager
import asyncio

async def main():
    manager = AgentToolManager()

    result = await manager.execute_agent_task(
        agent_type="developer",
        task_plan={
            "steps": [
                {
                    "tool": "enhanced_file_manager",
                    "method": "write_file",
                    "parameters": {
                        "path": "hello.py",
                        "content": "print('Hello, World!')"
                    }
                },
                {
                    "tool": "code_executor",
                    "method": "execute_code",
                    "parameters": {
                        "code": "exec(open('hello.py').read())",
                        "language": "python"
                    }
                }
            ]
        }
    )
    print(result)

asyncio.run(main())
```

---

### Creating and Loading a Plugin

```python
# my_plugin/plugin.py
from core.plugins.secure_plugin_integration import VoiceOSPluginInterface

class MyPlugin(VoiceOSPluginInterface):
    def __init__(self):
        super().__init__(
            name="my_plugin",
            version="1.0.0",
            description="Example custom plugin",
            author="Your Name"
        )

    async def initialize(self, context):
        self.logger.info("MyPlugin initialized")

    async def execute(self, command: str, context: Dict) -> Optional[str]:
        if command == "hello":
            return "Hello from MyPlugin!"
        return None

    async def cleanup(self):
        self.logger.info("MyPlugin cleaned up")
```

```python
# Load the plugin
from core.plugins.complete_plugin_integration import get_complete_plugin_system

system = get_complete_plugin_system()
await system.enable_plugin("my_plugin")
```
