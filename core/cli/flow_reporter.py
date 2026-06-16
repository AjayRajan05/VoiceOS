"""Subscribe to VoiceOS events and render live flow output in the CLI."""

from __future__ import annotations

import logging

from core.cli.console import VoiceConsole
from core.events.events import Events
from core.event import Event

logger = logging.getLogger(__name__)


class CLIFlowReporter:
    """Color-coded event trail for planning, agents, tools, and permissions."""

    def __init__(self, event_bus, enabled: bool = True):
        self.event_bus = event_bus
        self.enabled = enabled
        self._subscribed = False

    def attach(self) -> None:
        if self._subscribed or not self.enabled:
            return
        handlers = {
            Events.TASK_PLANNED: self._on_task_planned,
            Events.TASK_ROUTED: self._on_task_routed,
            Events.AGENT_STARTED: self._on_agent_started,
            Events.AGENT_COMPLETED: self._on_agent_completed,
            Events.AGENT_FAILED: self._on_agent_failed,
            Events.TOOL_EXECUTE: self._on_tool_execute,
            Events.PERMISSION_REQUESTED: self._on_permission_requested,
            Events.PERMISSION_GRANTED: self._on_permission_granted,
            Events.PERMISSION_DENIED: self._on_permission_denied,
            Events.ORCHESTRATOR_RESPONSE: self._on_response,
            Events.ORCHESTRATOR_ERROR: self._on_error,
            Events.TASK_COMPLETED: self._on_task_completed,
            Events.TASK_FAILED: self._on_task_failed,
            Events.SPEECH_TRANSCRIBED: self._on_speech,
        }
        for event_name, handler in handlers.items():
            self.event_bus.subscribe(event_name, handler)
        self._subscribed = True

    async def _on_task_planned(self, event: Event):
        payload = event.payload or {}
        nodes = payload.get("nodes", "?")
        VoiceConsole.flow("Planning", f"{nodes} step(s)")

    async def _on_task_routed(self, event: Event):
        payload = event.payload or {}
        path = payload.get("path", payload.get("execution_path", "unknown"))
        VoiceConsole.flow("Routing", str(path))

    async def _on_agent_started(self, event: Event):
        payload = event.payload or {}
        role = payload.get("role", "agent")
        VoiceConsole.agent(role, "started")

    async def _on_agent_completed(self, event: Event):
        payload = event.payload or {}
        role = payload.get("role", "agent")
        VoiceConsole.agent(role, "completed")

    async def _on_agent_failed(self, event: Event):
        payload = event.payload or {}
        VoiceConsole.error(f"Agent failed: {payload.get('error', payload)}")

    async def _on_tool_execute(self, event: Event):
        payload = event.payload or {}
        tool = payload.get("tool") or payload.get("name", "unknown")
        VoiceConsole.tool(str(tool))

    async def _on_permission_requested(self, event: Event):
        payload = event.payload or {}
        target = payload.get("target") or payload.get("operation", "operation")
        VoiceConsole.permission(f"Approval needed for {target}")

    async def _on_permission_granted(self, event: Event):
        VoiceConsole.success("Permission granted")

    async def _on_permission_denied(self, event: Event):
        VoiceConsole.warning("Permission denied")

    async def _on_response(self, event: Event):
        if event.source == "voice_cli_integration":
            return
        text = (event.payload or {}).get("text", "")
        if text:
            VoiceConsole.response(text)

    async def _on_error(self, event: Event):
        VoiceConsole.error(str((event.payload or {}).get("error", "Unknown error")))

    async def _on_task_completed(self, event: Event):
        VoiceConsole.success("Task completed")

    async def _on_task_failed(self, event: Event):
        VoiceConsole.error(f"Task failed: {(event.payload or {}).get('error', '')}")

    async def _on_speech(self, event: Event):
        text = (event.payload or {}).get("text", "")
        if text:
            VoiceConsole.voice(text)
