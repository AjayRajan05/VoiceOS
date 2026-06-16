"""
Event Handlers Module - Comprehensive event handling for VoiceOS
Provides handlers for orchestrator, agent lifecycle, workspace, and task events
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
import time
import json

from core.events.event_bus import EventBus
from core.events.events import Events
from core.event import Event
from memory.agent_memory import AgentMemory, MemoryType, MemoryPriority

logger = logging.getLogger(__name__)

@dataclass
class EventHandlerConfig:
    enable_logging: bool = True
    enable_memory_storage: bool = True
    enable_metrics: bool = True
    max_event_history: int = 1000
    event_timeout: float = 30.0

class EventHandlers:
    def __init__(self, event_bus: EventBus, memory_manager: AgentMemory = None, 
                 config: EventHandlerConfig = None):
        self.event_bus = event_bus
        self.memory_manager = memory_manager
        self.config = config or EventHandlerConfig()
        
        # Event history
        self.event_history: list = []
        self.event_metrics: Dict[str, Any] = {
            "events_processed": 0,
            "events_by_type": {},
            "processing_times": {},
            "errors": 0
        }
        
        # Handler mappings
        self.handler_mappings = {
            Events.ORCHESTRATOR_RESPONSE: self._handle_orchestrator_response,
            Events.ORCHESTRATOR_ERROR: self._handle_orchestrator_error,
            Events.PERMISSION_REQUESTED: self._handle_permission_requested,
            Events.INTERRUPT_REQUESTED: self._handle_interrupt_requested,
            Events.AGENT_CREATED: self._handle_agent_created,
            Events.AGENT_STARTED: self._handle_agent_started,
            Events.AGENT_COMPLETED: self._handle_agent_completed,
            Events.AGENT_FAILED: self._handle_agent_failed,
            Events.WORKSPACE_CREATED: self._handle_workspace_created,
            Events.WORKSPACE_CLEANUP: self._handle_workspace_cleanup,
            Events.TASK_PLANNED: self._handle_task_planned,
            Events.TASK_ROUTED: self._handle_task_routed,
            Events.TASK_COMPLETED: self._handle_task_completed,
            Events.TASK_FAILED: self._handle_task_failed
        }
        
        # Register all handlers
        self._register_handlers()
    
    def _register_handlers(self):
        """
        Register all event handlers with the event bus
        """
        for event_type, handler in self.handler_mappings.items():
            self.event_bus.subscribe(event_type, handler)
            logger.debug(f"Registered handler for event: {event_type}")
    
    async def _handle_orchestrator_response(self, event: Event):
        """
        Handle orchestrator response events
        """
        start_time = time.time()
        try:
            response_text = event.data.get("text", "")
            source = event.data.get("source", "unknown")
            
            if self.config.enable_logging:
                logger.info(f"Orchestrator response from {source}: {response_text[:100]}...")
            
            # Store in memory if available
            if self.memory_manager and self.config.enable_memory_storage:
                self.memory_manager.store_memory(
                    MemoryType.CONVERSATION,
                    {
                        "type": "orchestrator_response",
                        "text": response_text,
                        "source": source,
                        "timestamp": event.timestamp
                    },
                    priority=MemoryPriority.MEDIUM,
                    tags=["orchestrator", "response", source]
                )
            
            # Update metrics
            self._update_event_metrics(Events.ORCHESTRATOR_RESPONSE, time.time() - start_time)
            
        except Exception as e:
            logger.error(f"Error handling orchestrator response: {e}")
            self.event_metrics["errors"] += 1
    
    async def _handle_orchestrator_error(self, event: Event):
        """
        Handle orchestrator error events
        """
        start_time = time.time()
        try:
            error_message = event.data.get("error", "Unknown error")
            user_input = event.data.get("input", "")
            
            if self.config.enable_logging:
                logger.error(f"Orchestrator error: {error_message} (input: {user_input[:50]}...)")
            
            # Store error in memory
            if self.memory_manager and self.config.enable_memory_storage:
                self.memory_manager.store_memory(
                    MemoryType.AGENT_STATE,
                    {
                        "type": "orchestrator_error",
                        "error": error_message,
                        "input": user_input,
                        "timestamp": event.timestamp
                    },
                    priority=MemoryPriority.HIGH,
                    tags=["orchestrator", "error"]
                )
            
            # Update metrics
            self._update_event_metrics(Events.ORCHESTRATOR_ERROR, time.time() - start_time)
            
        except Exception as e:
            logger.error(f"Error handling orchestrator error event: {e}")
            self.event_metrics["errors"] += 1
    
    async def _handle_permission_requested(self, event: Event):
        """
        Handle permission request events
        """
        start_time = time.time()
        try:
            intent = event.data.get("intent", "")
            tools = event.data.get("tools", [])
            user_input = event.data.get("user_input", "")
            plan_type = event.data.get("plan_type", "")
            
            if self.config.enable_logging:
                logger.info(f"Permission requested for {intent} with tools {tools}")
            
            # Store permission request
            if self.memory_manager and self.config.enable_memory_storage:
                self.memory_manager.store_memory(
                    MemoryType.TASK_CONTEXT,
                    {
                        "type": "permission_request",
                        "intent": intent,
                        "tools": tools,
                        "user_input": user_input,
                        "plan_type": plan_type,
                        "timestamp": event.timestamp
                    },
                    priority=MemoryPriority.HIGH,
                    tags=["permission", "request", intent]
                )
            
            # Update metrics
            self._update_event_metrics(Events.PERMISSION_REQUESTED, time.time() - start_time)
            
        except Exception as e:
            logger.error(f"Error handling permission requested event: {e}")
            self.event_metrics["errors"] += 1
    
    async def _handle_interrupt_requested(self, event: Event):
        """
        Handle interrupt request events
        """
        start_time = time.time()
        try:
            reason = event.data.get("reason", "User interrupt")
            context = event.data.get("context", {})
            
            if self.config.enable_logging:
                logger.info(f"Interrupt requested: {reason}")
            
            # Store interrupt event
            if self.memory_manager and self.config.enable_memory_storage:
                self.memory_manager.store_memory(
                    MemoryType.AGENT_STATE,
                    {
                        "type": "interrupt_request",
                        "reason": reason,
                        "context": context,
                        "timestamp": event.timestamp
                    },
                    priority=MemoryPriority.HIGH,
                    tags=["interrupt", "request"]
                )
            
            # Update metrics
            self._update_event_metrics(Events.INTERRUPT_REQUESTED, time.time() - start_time)
            
        except Exception as e:
            logger.error(f"Error handling interrupt requested event: {e}")
            self.event_metrics["errors"] += 1
    
    async def _handle_agent_created(self, event: Event):
        """
        Handle agent creation events
        """
        start_time = time.time()
        try:
            agent_id = event.data.get("agent_id", "")
            agent_type = event.data.get("agent_type", "")
            role = event.data.get("role", "")
            
            if self.config.enable_logging:
                logger.info(f"Agent created: {agent_id} ({agent_type}/{role})")
            
            # Store agent creation
            if self.memory_manager and self.config.enable_memory_storage:
                self.memory_manager.store_memory(
                    MemoryType.AGENT_STATE,
                    {
                        "type": "agent_created",
                        "agent_id": agent_id,
                        "agent_type": agent_type,
                        "role": role,
                        "timestamp": event.timestamp
                    },
                    priority=MemoryPriority.MEDIUM,
                    tags=["agent", "created", role]
                )
            
            # Update metrics
            self._update_event_metrics(Events.AGENT_CREATED, time.time() - start_time)
            
        except Exception as e:
            logger.error(f"Error handling agent created event: {e}")
            self.event_metrics["errors"] += 1
    
    async def _handle_agent_started(self, event: Event):
        """
        Handle agent start events
        """
        start_time = time.time()
        try:
            agent_id = event.data.get("agent_id", "")
            task = event.data.get("task", "")
            
            if self.config.enable_logging:
                logger.info(f"Agent started: {agent_id} for task: {task}")
            
            # Store agent start
            if self.memory_manager and self.config.enable_memory_storage:
                self.memory_manager.store_memory(
                    MemoryType.AGENT_STATE,
                    {
                        "type": "agent_started",
                        "agent_id": agent_id,
                        "task": task,
                        "timestamp": event.timestamp
                    },
                    priority=MemoryPriority.MEDIUM,
                    tags=["agent", "started"]
                )
            
            # Update metrics
            self._update_event_metrics(Events.AGENT_STARTED, time.time() - start_time)
            
        except Exception as e:
            logger.error(f"Error handling agent started event: {e}")
            self.event_metrics["errors"] += 1
    
    async def _handle_agent_completed(self, event: Event):
        """
        Handle agent completion events
        """
        start_time = time.time()
        try:
            agent_id = event.data.get("agent_id", "")
            result = event.data.get("result", "")
            execution_time = event.data.get("execution_time", 0)
            
            if self.config.enable_logging:
                logger.info(f"Agent completed: {agent_id} in {execution_time:.2f}s")
            
            # Store agent completion
            if self.memory_manager and self.config.enable_memory_storage:
                self.memory_manager.store_memory(
                    MemoryType.AGENT_STATE,
                    {
                        "type": "agent_completed",
                        "agent_id": agent_id,
                        "result": result,
                        "execution_time": execution_time,
                        "timestamp": event.timestamp
                    },
                    priority=MemoryPriority.MEDIUM,
                    tags=["agent", "completed"]
                )
            
            # Update metrics
            self._update_event_metrics(Events.AGENT_COMPLETED, time.time() - start_time)
            
        except Exception as e:
            logger.error(f"Error handling agent completed event: {e}")
            self.event_metrics["errors"] += 1
    
    async def _handle_agent_failed(self, event: Event):
        """
        Handle agent failure events
        """
        start_time = time.time()
        try:
            agent_id = event.data.get("agent_id", "")
            error = event.data.get("error", "")
            execution_time = event.data.get("execution_time", 0)
            
            if self.config.enable_logging:
                logger.error(f"Agent failed: {agent_id} - {error}")
            
            # Store agent failure
            if self.memory_manager and self.config.enable_memory_storage:
                self.memory_manager.store_memory(
                    MemoryType.AGENT_STATE,
                    {
                        "type": "agent_failed",
                        "agent_id": agent_id,
                        "error": error,
                        "execution_time": execution_time,
                        "timestamp": event.timestamp
                    },
                    priority=MemoryPriority.HIGH,
                    tags=["agent", "failed", "error"]
                )
            
            # Update metrics
            self._update_event_metrics(Events.AGENT_FAILED, time.time() - start_time)
            
        except Exception as e:
            logger.error(f"Error handling agent failed event: {e}")
            self.event_metrics["errors"] += 1
    
    async def _handle_workspace_created(self, event: Event):
        """
        Handle workspace creation events
        """
        start_time = time.time()
        try:
            workspace_id = event.data.get("workspace_id", "")
            agent_name = event.data.get("agent_name", "")
            
            if self.config.enable_logging:
                logger.info(f"Workspace created: {workspace_id} for {agent_name}")
            
            # Store workspace creation
            if self.memory_manager and self.config.enable_memory_storage:
                self.memory_manager.store_memory(
                    MemoryType.WORKSPACE,
                    {
                        "type": "workspace_created",
                        "workspace_id": workspace_id,
                        "agent_name": agent_name,
                        "timestamp": event.timestamp
                    },
                    priority=MemoryPriority.MEDIUM,
                    tags=["workspace", "created"]
                )
            
            # Update metrics
            self._update_event_metrics(Events.WORKSPACE_CREATED, time.time() - start_time)
            
        except Exception as e:
            logger.error(f"Error handling workspace created event: {e}")
            self.event_metrics["errors"] += 1
    
    async def _handle_workspace_cleanup(self, event: Event):
        """
        Handle workspace cleanup events
        """
        start_time = time.time()
        try:
            workspace_id = event.data.get("workspace_id", "")
            reason = event.data.get("reason", "cleanup")
            
            if self.config.enable_logging:
                logger.info(f"Workspace cleanup: {workspace_id} ({reason})")
            
            # Store workspace cleanup
            if self.memory_manager and self.config.enable_memory_storage:
                self.memory_manager.store_memory(
                    MemoryType.WORKSPACE,
                    {
                        "type": "workspace_cleanup",
                        "workspace_id": workspace_id,
                        "reason": reason,
                        "timestamp": event.timestamp
                    },
                    priority=MemoryPriority.LOW,
                    tags=["workspace", "cleanup"]
                )
            
            # Update metrics
            self._update_event_metrics(Events.WORKSPACE_CLEANUP, time.time() - start_time)
            
        except Exception as e:
            logger.error(f"Error handling workspace cleanup event: {e}")
            self.event_metrics["errors"] += 1
    
    async def _handle_task_planned(self, event: Event):
        """
        Handle task planning events
        """
        start_time = time.time()
        try:
            task_type = event.data.get("type", "")
            intent = event.data.get("intent", "")
            steps = event.data.get("steps", [])
            
            if self.config.enable_logging:
                logger.info(f"Task planned: {task_type}/{intent} with {len(steps)} steps")
            
            # Store task plan
            if self.memory_manager and self.config.enable_memory_storage:
                self.memory_manager.store_memory(
                    MemoryType.TASK_CONTEXT,
                    {
                        "type": "task_planned",
                        "task_type": task_type,
                        "intent": intent,
                        "steps": steps,
                        "timestamp": event.timestamp
                    },
                    priority=MemoryPriority.MEDIUM,
                    tags=["task", "planned", task_type]
                )
            
            # Update metrics
            self._update_event_metrics(Events.TASK_PLANNED, time.time() - start_time)
            
        except Exception as e:
            logger.error(f"Error handling task planned event: {e}")
            self.event_metrics["errors"] += 1
    
    async def _handle_task_routed(self, event: Event):
        """
        Handle task routing events
        """
        start_time = time.time()
        try:
            execution_path = event.data.get("execution_path", "")
            intent = event.data.get("intent", "")
            
            if self.config.enable_logging:
                logger.info(f"Task routed: {intent} via {execution_path}")
            
            # Store task routing
            if self.memory_manager and self.config.enable_memory_storage:
                self.memory_manager.store_memory(
                    MemoryType.TASK_CONTEXT,
                    {
                        "type": "task_routed",
                        "execution_path": execution_path,
                        "intent": intent,
                        "timestamp": event.timestamp
                    },
                    priority=MemoryPriority.MEDIUM,
                    tags=["task", "routed", execution_path]
                )
            
            # Update metrics
            self._update_event_metrics(Events.TASK_ROUTED, time.time() - start_time)
            
        except Exception as e:
            logger.error(f"Error handling task routed event: {e}")
            self.event_metrics["errors"] += 1
    
    async def _handle_task_completed(self, event: Event):
        """
        Handle task completion events
        """
        start_time = time.time()
        try:
            task_id = event.data.get("task_id", "")
            result = event.data.get("result", "")
            execution_time = event.data.get("execution_time", 0)
            
            if self.config.enable_logging:
                logger.info(f"Task completed: {task_id} in {execution_time:.2f}s")
            
            # Store task completion
            if self.memory_manager and self.config.enable_memory_storage:
                self.memory_manager.store_memory(
                    MemoryType.TASK_CONTEXT,
                    {
                        "type": "task_completed",
                        "task_id": task_id,
                        "result": result,
                        "execution_time": execution_time,
                        "timestamp": event.timestamp
                    },
                    priority=MemoryPriority.MEDIUM,
                    tags=["task", "completed"]
                )
            
            # Update metrics
            self._update_event_metrics(Events.TASK_COMPLETED, time.time() - start_time)
            
        except Exception as e:
            logger.error(f"Error handling task completed event: {e}")
            self.event_metrics["errors"] += 1
    
    async def _handle_task_failed(self, event: Event):
        """
        Handle task failure events
        """
        start_time = time.time()
        try:
            task_id = event.data.get("task_id", "")
            error = event.data.get("error", "")
            execution_time = event.data.get("execution_time", 0)
            
            if self.config.enable_logging:
                logger.error(f"Task failed: {task_id} - {error}")
            
            # Store task failure
            if self.memory_manager and self.config.enable_memory_storage:
                self.memory_manager.store_memory(
                    MemoryType.TASK_CONTEXT,
                    {
                        "type": "task_failed",
                        "task_id": task_id,
                        "error": error,
                        "execution_time": execution_time,
                        "timestamp": event.timestamp
                    },
                    priority=MemoryPriority.HIGH,
                    tags=["task", "failed", "error"]
                )
            
            # Update metrics
            self._update_event_metrics(Events.TASK_FAILED, time.time() - start_time)
            
        except Exception as e:
            logger.error(f"Error handling task failed event: {e}")
            self.event_metrics["errors"] += 1
    
    def _update_event_metrics(self, event_type: str, processing_time: float):
        """
        Update event processing metrics
        """
        self.event_metrics["events_processed"] += 1
        self.event_metrics["events_by_type"][event_type] = self.event_metrics["events_by_type"].get(event_type, 0) + 1
        
        # Update processing times
        if event_type not in self.event_metrics["processing_times"]:
            self.event_metrics["processing_times"][event_type] = []
        self.event_metrics["processing_times"][event_type].append(processing_time)
        
        # Keep only recent processing times
        if len(self.event_metrics["processing_times"][event_type]) > 100:
            self.event_metrics["processing_times"][event_type] = \
                self.event_metrics["processing_times"][event_type][-50:]
        
        # Add to event history
        event_record = {
            "type": event_type,
            "timestamp": time.time(),
            "processing_time": processing_time
        }
        self.event_history.append(event_record)
        
        # Limit history size
        if len(self.event_history) > self.config.max_event_history:
            self.event_history = self.event_history[-self.config.max_event_history//2:]
    
    def get_event_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive event metrics
        """
        # Calculate average processing times
        avg_processing_times = {}
        for event_type, times in self.event_metrics["processing_times"].items():
            if times:
                avg_processing_times[event_type] = sum(times) / len(times)
        
        return {
            **self.event_metrics,
            "average_processing_times": avg_processing_times,
            "event_history_size": len(self.event_history),
            "registered_handlers": len(self.handler_mappings)
        }
    
    def get_recent_events(self, limit: int = 50, event_type: str = None) -> list:
        """
        Get recent events
        """
        events = self.event_history
        if event_type:
            events = [e for e in events if e["type"] == event_type]
        
        return events[-limit:]
    
    def clear_event_history(self):
        """
        Clear event history
        """
        self.event_history.clear()
        logger.info("Event history cleared")
    
    def register_custom_handler(self, event_type: str, handler: Callable):
        """
        Register a custom event handler
        """
        self.handler_mappings[event_type] = handler
        self.event_bus.subscribe(event_type, handler)
        logger.info(f"Registered custom handler for event: {event_type}")
    
    def unregister_handler(self, event_type: str):
        """
        Unregister an event handler
        """
        if event_type in self.handler_mappings:
            handler = self.handler_mappings[event_type]
            self.event_bus.unsubscribe(event_type, handler)
            del self.handler_mappings[event_type]
            logger.info(f"Unregistered handler for event: {event_type}")
    
    async def shutdown(self):
        """
        Shutdown event handlers
        """
        # Unregister all handlers
        for event_type, handler in list(self.handler_mappings.items()):
            self.event_bus.unsubscribe(event_type, handler)
        
        self.handler_mappings.clear()
        logger.info("Event handlers shutdown complete")


_handlers_instance = None


def get_event_handlers(event_bus, memory_manager=None, config=None):
    """Return shared EventHandlers instance."""
    global _handlers_instance
    if _handlers_instance is None:
        _handlers_instance = EventHandlers(event_bus, memory_manager, config)
    return _handlers_instance
