"""Pre/post execution hooks: security, performance, error recovery."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Awaitable, Optional

from core.monitoring.error_recovery import ErrorCategory, ErrorSeverity
from core.monitoring.performance_monitor import MetricType

logger = logging.getLogger(__name__)


class ExecutionWrapper:
    """Wraps orchestrator.process_user_input with security and monitoring."""

    def __init__(self, security=None, performance_monitor=None, error_recovery=None):
        self.security = security
        self.performance_monitor = performance_monitor
        self.error_recovery = error_recovery

    async def run(
        self,
        user_input: str,
        execute_fn: Callable[[str], Awaitable[Any]],
    ) -> Any:
        if self.security:
            validation = self._validate_input(user_input)
            if not validation.get("allowed", True):
                raise PermissionError(validation.get("reason", "Input blocked by security policy"))

        timer_name = "orchestrator_request"
        timer_id = None
        start = time.time()
        if self.performance_monitor:
            timer_id = self.performance_monitor.start_timer(timer_name)

        try:
            return await execute_fn(user_input)
        except Exception as exc:
            if self.error_recovery:
                await self._record_error(exc, user_input)
            raise
        finally:
            if self.performance_monitor and timer_id is not None:
                self.performance_monitor.end_timer(timer_name, timer_id)
                self.performance_monitor.record_metric(
                    "request_latency_ms", (time.time() - start) * 1000, MetricType.GAUGE
                )

    def _validate_input(self, user_input: str) -> dict:
        try:
            result = self.security.validate_request(
                ip_address="127.0.0.1",
                user_agent="voiceos-cli",
                request_data=user_input,
            )
            return result
        except Exception as exc:
            logger.debug("Security validation skipped: %s", exc)
            return {"allowed": True}

    async def _record_error(self, exc: Exception, user_input: str) -> None:
        try:
            await self.error_recovery.handle_error(
                exc,
                context={
                    "component": "orchestrator",
                    "input": user_input[:200],
                    "category": ErrorCategory.AGENT.value,
                },
            )
        except Exception as record_exc:
            logger.debug("Error recovery record failed: %s", record_exc)
