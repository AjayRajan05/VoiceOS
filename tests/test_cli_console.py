"""Tests for VoiceOS CLI console."""

from core.cli.console import VoiceConsole


def test_console_banner_does_not_raise():
    VoiceConsole.banner()


def test_console_message_methods():
    VoiceConsole.info("info")
    VoiceConsole.success("ok")
    VoiceConsole.warning("warn")
    VoiceConsole.error("err")
    VoiceConsole.flow("stage", "detail")
    VoiceConsole.agent("researcher", "working")
    VoiceConsole.tool("code_executor")
