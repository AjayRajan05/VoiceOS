"""
VoiceOS Permission Engine

This module provides permission management and validation for VoiceOS operations,
ensuring safe and controlled access to system resources and tools.
"""

from enum import Enum
from functools import wraps
from typing import Callable, Any, Iterable, Optional, TYPE_CHECKING
import asyncio
import logging
from core.events.events import Events
from core.event import Event
from core.logger import logger
from permissions.audit_log import AuditLog


class PermissionLevel(Enum):
    """
    Permission levels for VoiceOS operations.
    
    Defines hierarchical permission levels for controlling access
    to different types of operations and resources.
    """
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PermissionEngine:
    """
    Permission validation and management system for VoiceOS.
    """

    HIGH_TOOLS = frozenset({
        "marketplace", "ide_workflow", "code_executor", "os_close_app",
        "os_screenshot", "os_click", "os_type_text",
    })
    HIGH_INTENTS = frozenset({
        "install_plugin", "close_application", "run_code", "create_file",
        "edit_file", "multi_agent_workflow", "autonomous_build",
    })

    def __init__(self, event_bus=None, safety_mode: str = "strict", policy_engine=None):
        self.event_bus = event_bus
        self.current_user_level = PermissionLevel.MEDIUM
        self.safety_mode = safety_mode
        self.policy = policy_engine
        self.audit = AuditLog()
        
        if event_bus:
            event_bus.subscribe(Events.LLM_DECISION, self.check_permission)

    async def is_permission_required(
        self,
        intent: str,
        tools: Iterable[str],
        plan_type: str | None = None,
    ) -> bool:
        if self.safety_mode == "permissive":
            return False
        tools = list(tools or [])
        if self.policy:
            from core.policy.surface import execution_surface

            decision = self.policy.evaluate(
                intent,
                tools,
                plan_type=plan_type,
                surface=execution_surface(),
            )
            return decision.requires_approval
        for tool in tools:
            if tool in self.HIGH_TOOLS or tool.startswith("os_"):
                return True
        if intent in self.HIGH_INTENTS:
            return True
        return False

    async def prompt_for_approval(
        self, intent: str, tools: Iterable[str], user_input: str, timeout: float = 30.0
    ) -> bool:
        tools = list(tools or [])
        if self.policy:
            from core.policy.surface import execution_surface

            decision = self.policy.evaluate(intent, tools, surface=execution_surface())
            if decision.auto_deny:
                self.audit.record(
                    "policy_auto_deny",
                    {"intent": intent, "tools": tools, "reason": decision.reason, "profile": self.policy.profile_name},
                )
                return False
        from core.cli.console import VoiceConsole

        VoiceConsole.permission(f"Intent: {intent} | Tools: {', '.join(tools) or 'none'}")
        VoiceConsole.dim(f"Input: {user_input[:120]}")
        prompt = f"{VoiceConsole.PROMPT}Allow? [y/N]: "
        loop = asyncio.get_event_loop()
        try:
            answer = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: input(prompt)),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            self.audit.record("permission_timeout", {"intent": intent, "tools": tools})
            return False

        approved = answer.strip().lower() in ("y", "yes")
        self.audit.record(
            "permission_granted" if approved else "permission_denied",
            {"intent": intent, "tools": tools, "user_input": user_input[:200]},
        )
        if self.event_bus:
            event = Events.PERMISSION_GRANTED if approved else Events.PERMISSION_DENIED
            await self.event_bus.publish(Event(event, {"intent": intent, "tools": tools}, "permission_engine"))
        return approved

    async def check_permission(self, event):
        """
        Check permission for LLM decision event.
        
        Args:
            event: Permission check event with decision payload
        """
        decision = event.payload

        if decision["requires_permission"]:
            logger.info("\nAssistant:")
            logger.info(decision["reasoning"])
            logger.info("Do you approve? (yes/no)")

            answer = input("> ")

            if answer.lower() == "yes":
                await self.event_bus.publish(
                    Event(
                        Events.PERMISSION_GRANTED,
                        decision,
                        "permission_engine"
                    )
                )
            else:
                await self.event_bus.publish(
                    Event(
                        Events.PERMISSION_DENIED,
                        decision,
                        "permission_engine"
                    )
                )

    def set_user_permission_level(self, level: PermissionLevel):
        """
        Set the current user's permission level.
        
        Args:
            level (PermissionLevel): Permission level to set
        """
        self.current_user_level = level
        logger.info(f"User permission level set to: {level.value}")

    def check_tool_permission(self, required_level: PermissionLevel) -> bool:
        """
        Check if current user has permission for required level.
        
        Args:
            required_level (PermissionLevel): Required permission level
            
        Returns:
            bool: True if user has sufficient permissions
        """
        level_hierarchy = {
            PermissionLevel.LOW: 0,
            PermissionLevel.MEDIUM: 1,
            PermissionLevel.HIGH: 2
        }
        
        user_level = level_hierarchy.get(self.current_user_level, 0)
        required_level_value = level_hierarchy.get(required_level, 0)
        
        return user_level >= required_level_value

    def request_permission(self, tool_name: str, method: str, required_level: PermissionLevel, context: dict = None) -> bool:
        """
        Request permission for a tool operation.
        
        Args:
            tool_name (str): Name of the tool
            method (str): Method name
            required_level (PermissionLevel): Required permission level
            context (dict, optional): Additional context
            
        Returns:
            bool: True if permission granted
        """
        if self.check_tool_permission(required_level):
            logger.info(f"Permission granted for {tool_name}.{method} (level: {required_level.value})")
            return True
        
        logger.warning(f"Permission denied for {tool_name}.{method} - requires {required_level.value}, user has {self.current_user_level.value}")
        
        # Could implement interactive permission request here
        if self.event_bus:
            # Publish permission request event
            pass
        
        return False


_engine: Optional["PermissionEngine"] = None


def set_permission_engine(engine: "PermissionEngine") -> None:
    global _engine
    _engine = engine


def get_permission_engine() -> "PermissionEngine":
    if _engine is None:
        raise RuntimeError(
            "PermissionEngine not initialized. Call set_permission_engine() during startup."
        )
    return _engine


def get_permission_engine_optional() -> Optional["PermissionEngine"]:
    return _engine


class _PermissionEngineProxy:
    """Proxy so legacy `permission_engine.foo` works after set_permission_engine."""

    def __getattr__(self, name):
        return getattr(get_permission_engine(), name)

    def __setattr__(self, name, value):
        setattr(get_permission_engine(), name, value)


permission_engine = _PermissionEngineProxy()


def check_permission(required_level: PermissionLevel):
    """
    Decorator to check permissions before executing a method.
    
    Args:
        required_level (PermissionLevel): Required permission level
        
    Returns:
        Callable: Decorated function with permission checking
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Get tool name from class if available
            tool_name = "unknown"
            if args and hasattr(args[0], '__class__'):
                tool_name = args[0].__class__.__name__.lower()
            
            method_name = func.__name__
            
            # Check permission
            if not permission_engine.check_tool_permission(required_level):
                raise PermissionError(f"Insufficient permissions for {tool_name}.{method_name}. Requires: {required_level.value}")
            
            # Execute function
            return func(*args, **kwargs)
        
        return wrapper
    return decorator