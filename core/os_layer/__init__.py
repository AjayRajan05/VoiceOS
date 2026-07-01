"""VoiceOS OS Abstraction Layer (OAL) — neutral intents between agents and any OS."""

from core.os_layer.capabilities import get_intent_capabilities, intent_supported
from core.os_layer.executor import OSIntentExecutor, get_os_intent_executor, is_os_tool_name
from core.os_layer.intent import (
    ALL_OS_TOOL_NAMES,
    OSIntent,
    OSIntentError,
    OSIntentNotSupported,
    OSIntentRequest,
    tool_to_intent,
)

__all__ = [
    "ALL_OS_TOOL_NAMES",
    "OSIntent",
    "OSIntentError",
    "OSIntentExecutor",
    "OSIntentNotSupported",
    "OSIntentRequest",
    "get_intent_capabilities",
    "get_os_intent_executor",
    "intent_supported",
    "is_os_tool_name",
    "tool_to_intent",
]
