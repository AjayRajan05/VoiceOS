"""Universal session shell: persistent voice/CLI session with wake word gating."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from core.event import Event
from core.events.events import Events
from core.session_shell.capabilities import build_session_greeting
from core.session_shell.config import SessionShellConfig
from core.session_shell.state import ShellState
from core.session_shell.wake_word import detect_wake_word

logger = logging.getLogger(__name__)


class SessionShell:
    """
    Middle-layer session UX:
    - gates voice input (always-on, wake word, or push-to-talk)
    - publishes unified USER_MESSAGE events for the orchestrator
    - greets with capability-aware summary on startup
    """

    def __init__(
        self,
        event_bus,
        *,
        config: Optional[SessionShellConfig] = None,
        session_manager=None,
        runtime_info: Optional[Dict[str, Any]] = None,
    ):
        self.event_bus = event_bus
        self.config = config or SessionShellConfig()
        self.session_manager = session_manager
        self.runtime_info = runtime_info or {}
        self.state = ShellState.IDLE
        self._armed_at: Optional[float] = None
        self._ptt_active = False
        self._attached = False
        self._ptt_listener = None
        self._disarm_task: Optional[asyncio.Task] = None

    @property
    def ptt_active(self) -> bool:
        return self._ptt_active

    def attach(self) -> None:
        if self._attached:
            return
        self.event_bus.subscribe(Events.SPEECH_TRANSCRIBED, self._on_speech_transcribed)
        self.event_bus.subscribe(Events.ORCHESTRATOR_RESPONSE, self._on_orchestrator_done)
        self.event_bus.subscribe(Events.ORCHESTRATOR_ERROR, self._on_orchestrator_done)
        self._attached = True
        if self.config.input_mode == "push_to_talk":
            self._start_ptt_listener()
        logger.info("Session shell attached (input_mode=%s)", self.config.input_mode)

    def detach(self) -> None:
        if not self._attached:
            return
        self._stop_ptt_listener()
        self._attached = False

    async def startup(self) -> Optional[str]:
        """Return optional greeting text after session shell starts."""
        if not self.config.enabled:
            return None

        resume_hint = None
        if self.config.resume_on_start and self.session_manager and self.session_manager.enabled:
            sid = self.session_manager.ensure_active_session("voice")
            messages = self.session_manager.db.get_messages(sid, limit=3) if self.session_manager.db else []
            if messages:
                resume_hint = "Your last conversation is available; say 'continue what we were doing' to resume."

        if not self.config.capability_greeting:
            return resume_hint

        os_info: Dict[str, Any] = {}
        bridge_available: Optional[bool] = None
        try:
            from tools.os_control.platform import get_os_capabilities

            os_info = get_os_capabilities()
        except Exception as exc:
            logger.debug("OS capabilities unavailable for greeting: %s", exc)
        try:
            from host_bridge.client import BridgeClient
            from host_bridge.config import bridge_mode

            if bridge_mode() != "local":
                bridge_available = BridgeClient().is_available()
        except Exception:
            bridge_available = None

        greeting = build_session_greeting(
            runtime_info=self.runtime_info,
            os_info=os_info,
            bridge_available=bridge_available,
            resume_hint=resume_hint,
        )
        await self._publish_state()
        return greeting

    async def submit_input(self, text: str, *, source: str = "cli") -> bool:
        """Unified entry for CLI/gateway text; always accepted."""
        if not text.strip():
            return False
        await self._publish_user_message(text.strip(), source=source)
        return True

    def set_ptt_active(self, active: bool) -> None:
        self._ptt_active = bool(active)
        if self._ptt_active and self.config.input_mode == "push_to_talk":
            self.state = ShellState.ARMED
        elif not self._ptt_active and self.config.input_mode == "push_to_talk":
            self.state = ShellState.IDLE

    async def _on_speech_transcribed(self, event: Event) -> None:
        if not self.config.enabled:
            await self._publish_user_message(event.payload.get("text", ""), source="voice")
            return

        text = (event.payload.get("text") or "").strip()
        if not text:
            return

        accepted, command = self._evaluate_voice_input(text)
        if not accepted:
            logger.debug("Voice input gated (state=%s): %s", self.state.value, text[:80])
            return

        if not command:
            return

        await self._publish_user_message(command, source="voice", raw_text=text)

    def _evaluate_voice_input(self, text: str) -> tuple[bool, str]:
        mode = self.config.input_mode
        if mode == "always_on":
            return True, text

        if mode == "push_to_talk":
            if not self._ptt_active:
                return False, ""
            return True, text

        # wake_word mode
        self._expire_armed_if_needed()
        match = detect_wake_word(text, self.config.wake_phrases)
        if match is not None:
            if match.command:
                self._disarm()
                return True, match.command
            self._arm()
            return False, ""

        if self.state == ShellState.ARMED:
            self._disarm()
            return True, text

        return False, ""

    def _arm(self) -> None:
        self.state = ShellState.ARMED
        self._armed_at = time.monotonic()
        self._schedule_disarm()

    def _disarm(self) -> None:
        self.state = ShellState.IDLE
        self._armed_at = None
        if self._disarm_task and not self._disarm_task.done():
            self._disarm_task.cancel()
        self._disarm_task = None

    def _expire_armed_if_needed(self) -> None:
        if self.state != ShellState.ARMED or self._armed_at is None:
            return
        if time.monotonic() - self._armed_at > self.config.armed_timeout_s:
            self._disarm()

    def _schedule_disarm(self) -> None:
        if self._disarm_task and not self._disarm_task.done():
            self._disarm_task.cancel()

        async def _timeout():
            try:
                await asyncio.sleep(self.config.armed_timeout_s)
                if self.state == ShellState.ARMED:
                    self._disarm()
                    await self._publish_state()
            except asyncio.CancelledError:
                pass

        try:
            loop = asyncio.get_running_loop()
            self._disarm_task = loop.create_task(_timeout())
        except RuntimeError:
            self._disarm_task = None

    async def _publish_user_message(self, text: str, *, source: str, raw_text: Optional[str] = None) -> None:
        if not text.strip():
            return
        self.state = ShellState.PROCESSING
        await self._publish_state()
        await self.event_bus.publish(
            Event(
                Events.USER_MESSAGE,
                {
                    "text": text.strip(),
                    "source": source,
                    "raw_text": raw_text or text,
                },
                "session_shell",
            )
        )

    async def mark_idle(self) -> None:
        if self.config.input_mode == "push_to_talk" and self._ptt_active:
            self.state = ShellState.ARMED
        elif self.config.input_mode == "wake_word":
            self.state = ShellState.IDLE
        else:
            self.state = ShellState.IDLE
        await self._publish_state()

    async def _on_orchestrator_done(self, event: Event) -> None:
        await self.mark_idle()

    async def _publish_state(self) -> None:
        await self.event_bus.publish(
            Event(
                Events.SHELL_STATE_CHANGED,
                {
                    "state": self.state.value,
                    "input_mode": self.config.input_mode,
                    "ptt_active": self._ptt_active,
                },
                "session_shell",
            )
        )

    def _start_ptt_listener(self) -> None:
        try:
            from core.session_shell.ptt import PushToTalkListener

            self._ptt_listener = PushToTalkListener(
                key=self.config.push_to_talk_key,
                on_change=self.set_ptt_active,
            )
            self._ptt_listener.start()
        except Exception as exc:
            logger.warning("Push-to-talk listener unavailable: %s", exc)

    def _stop_ptt_listener(self) -> None:
        if self._ptt_listener:
            self._ptt_listener.stop()
            self._ptt_listener = None
