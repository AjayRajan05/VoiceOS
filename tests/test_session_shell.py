"""Tests for universal session shell (Phase D)."""

import pytest

from core.event import Event
from core.events.event_bus import EventBus
from core.events.events import Events
from core.session.session_db import SessionDB
from core.session.session_manager import SessionManager
from core.session_shell.capabilities import build_capability_summary, build_session_greeting
from core.session_shell.config import SessionShellConfig
from core.session_shell.resume import format_resume_context, is_continue_request
from core.session_shell.shell import SessionShell
from core.session_shell.state import ShellState
from core.session_shell.wake_word import detect_wake_word


class TestWakeWord:
    def test_detect_exact_phrase(self):
        match = detect_wake_word("Hey VoiceOS", ("hey voiceos",))
        assert match is not None
        assert match.command == ""

    def test_detect_phrase_with_command(self):
        match = detect_wake_word("hey voiceos open chrome", ("hey voiceos",))
        assert match is not None
        assert match.command == "open chrome"

    def test_no_match(self):
        assert detect_wake_word("open chrome", ("hey voiceos",)) is None


class TestSessionResume:
    def test_continue_request(self):
        assert is_continue_request("continue what we were doing") is True
        assert is_continue_request("open chrome") is False

    def test_format_resume_context(self):
        text = format_resume_context(
            [
                {"role": "user", "content": "Research docker deployment"},
                {"role": "assistant", "content": "Docker deployment uses compose files."},
            ],
            session_title="VoiceOS conversation",
        )
        assert "Continuing our session" in text
        assert "docker deployment" in text.lower()

    def test_session_manager_continue(self, tmp_path):
        db_path = tmp_path / "sessions.db"
        manager = SessionManager(db_path, enabled=True)
        sid = manager.ensure_active_session("voice")
        manager.record_user_message(sid, "Let's plan a vacation to Japan")
        manager.record_assistant_message(sid, "Japan has cherry blossom season in spring")
        answer = manager.try_session_continue("continue where we left off")
        assert answer is not None
        assert "japan" in answer.lower()
        manager.shutdown()


class TestCapabilitiesGreeting:
    def test_build_capability_summary(self):
        summary = build_capability_summary(
            runtime_info={"execution_mode": "queued", "worker_count": 2, "llm_provider": "api", "llm_api_base": "http://localhost:11434"},
            os_info={
                "display_name": "Windows",
                "intents": {"launch_app": {"supported": True}, "screenshot": {"supported": True}},
            },
            bridge_available=True,
        )
        assert "Windows" in summary
        assert "Docker workers" in summary
        assert "Host bridge" in summary

    def test_build_session_greeting_includes_resume_hint(self):
        greeting = build_session_greeting(resume_hint="Previous chat available.")
        assert "VoiceOS session ready" in greeting
        assert "Previous chat available" in greeting


@pytest.mark.asyncio
class TestSessionShell:
    async def test_wake_word_gates_until_armed(self):
        bus = EventBus()
        published = []

        async def capture(event):
            published.append(event)

        bus.subscribe(Events.USER_MESSAGE, capture)
        shell = SessionShell(
            bus,
            config=SessionShellConfig(enabled=True, input_mode="wake_word", wake_phrases=("hey voiceos",)),
        )
        shell.attach()

        await shell._on_speech_transcribed(
            Event(Events.SPEECH_TRANSCRIBED, {"text": "open chrome"}, "voice")
        )
        assert published == []

        await shell._on_speech_transcribed(
            Event(Events.SPEECH_TRANSCRIBED, {"text": "hey voiceos"}, "voice")
        )
        assert shell.state == ShellState.ARMED
        assert published == []

        await shell._on_speech_transcribed(
            Event(Events.SPEECH_TRANSCRIBED, {"text": "open chrome"}, "voice")
        )
        assert len(published) == 1
        assert published[0].payload["text"] == "open chrome"

    async def test_wake_word_inline_command(self):
        bus = EventBus()
        published = []

        async def capture(event):
            published.append(event)

        bus.subscribe(Events.USER_MESSAGE, capture)
        shell = SessionShell(
            bus,
            config=SessionShellConfig(enabled=True, input_mode="wake_word", wake_phrases=("hey voiceos",)),
        )
        shell.attach()

        await shell._on_speech_transcribed(
            Event(Events.SPEECH_TRANSCRIBED, {"text": "hey voiceos take a screenshot"}, "voice")
        )
        assert len(published) == 1
        assert published[0].payload["text"] == "take a screenshot"

    async def test_always_on_passes_through(self):
        bus = EventBus()
        published = []

        async def capture(event):
            published.append(event)

        bus.subscribe(Events.USER_MESSAGE, capture)
        shell = SessionShell(
            bus,
            config=SessionShellConfig(enabled=True, input_mode="always_on"),
        )
        shell.attach()

        await shell._on_speech_transcribed(
            Event(Events.SPEECH_TRANSCRIBED, {"text": "hello there"}, "voice")
        )
        assert len(published) == 1

    async def test_cli_submit_always_accepted(self):
        bus = EventBus()
        published = []

        async def capture(event):
            published.append(event)

        bus.subscribe(Events.USER_MESSAGE, capture)
        shell = SessionShell(
            bus,
            config=SessionShellConfig(enabled=True, input_mode="wake_word"),
        )
        await shell.submit_input("open notepad", source="cli")
        assert len(published) == 1
        assert published[0].payload["source"] == "cli"
