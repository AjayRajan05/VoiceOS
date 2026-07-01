"""Host-only OS intent executor — single entry point for desktop automation."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.os_layer.capabilities import intent_supported, unsupported_intent_message
from core.os_layer.intent import (
    INTENT_TO_ROUTER_ACTION,
    OSIntent,
    OSIntentError,
    OSIntentNotSupported,
    OSIntentRequest,
    normalize_params,
    tool_to_intent,
)
from tools.os_control.os_tool_router import OSToolRouter
from tools.os_control.platform import get_platform_adapter
from tools.os_control.platform.base import PlatformAdapter

logger = logging.getLogger(__name__)

_executor: Optional["OSIntentExecutor"] = None


class OSIntentExecutor:
    """
    Executes OS-neutral intents on the host via PlatformAdapter.

    This layer is host-only: workers and Docker queues must never invoke it.
    """

    HOST_ONLY = True

    def __init__(
        self,
        system_integration=None,
        adapter: Optional[PlatformAdapter] = None,
        *,
        local_only: bool = False,
    ):
        self._adapter = adapter or get_platform_adapter()
        self._router = OSToolRouter(system_integration=system_integration, adapter=self._adapter)
        self._local_only = local_only

    def supports(self, intent: OSIntent) -> bool:
        return intent_supported(intent, adapter=self._adapter)

    def list_supported_intents(self) -> Dict[str, bool]:
        return {intent.value: self.supports(intent) for intent in OSIntent}

    def execute_intent(self, intent: OSIntent, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.supports(intent):
            message = unsupported_intent_message(intent, adapter=self._adapter)
            raise OSIntentNotSupported(message)

        normalized = normalize_params(intent, params or {})
        bridge_result = self._try_bridge(intent, normalized)
        if bridge_result is not None:
            return bridge_result

        router_action = INTENT_TO_ROUTER_ACTION.get(intent)
        if not router_action:
            raise OSIntentError(f"No router action for intent {intent.value}")

        logger.info("OS intent %s on %s (local)", intent.value, self._adapter.platform_key)
        raw = self._router.execute(router_action, normalized)
        result = self._format_result(intent, raw, normalized)
        result["via"] = "local"
        return result

    def _try_bridge(self, intent: OSIntent, normalized: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if self._local_only:
            return None
        try:
            from host_bridge.client import get_bridge_client, should_use_bridge
            from host_bridge.config import bridge_mode

            client = get_bridge_client()
            if not should_use_bridge(client):
                if bridge_mode() == "bridge":
                    raise OSIntentError(
                        "VOICEOS_BRIDGE_MODE=bridge but host bridge is not running. "
                        "Start it with: voiceos-bridge"
                    )
                return None
            logger.info("OS intent %s via host bridge", intent.value)
            result = client.execute_intent(intent.value, normalized)
            result.setdefault("via", "host_bridge")
            return result
        except OSIntentError:
            raise
        except Exception as exc:
            from host_bridge.config import bridge_mode

            if bridge_mode() == "bridge":
                raise OSIntentError(f"Host bridge failed: {exc}") from exc
            logger.warning("Host bridge failed, using local router: %s", exc)
            return None

    def execute_request(self, request: OSIntentRequest) -> Dict[str, Any]:
        return self.execute_intent(request.intent, request.params)

    def execute_tool(self, tool_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Backward-compatible entry for legacy os_* tool names."""
        request = OSIntentRequest.from_tool(tool_name, params)
        return self.execute_request(request)

    @staticmethod
    def _format_result(intent: OSIntent, raw: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(raw, dict):
            success = raw.get("success", True)
            message = raw.get("message") or raw.get("error") or str(raw)
            return {
                "success": success,
                "intent": intent.value,
                "message": message,
                "result": raw,
                "params": params,
            }
        return {
            "success": True,
            "intent": intent.value,
            "message": str(raw),
            "result": raw,
            "params": params,
        }


def get_os_intent_executor(system_integration=None) -> OSIntentExecutor:
    global _executor
    if _executor is None or system_integration is not None:
        _executor = OSIntentExecutor(system_integration=system_integration)
    return _executor


def is_os_tool_name(tool_name: str) -> bool:
    return tool_to_intent(tool_name) is not None
