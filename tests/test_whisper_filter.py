"""Tests for Whisper hallucination filter."""

from audio.whisper_filter import filter_transcript, is_whisper_hallucination


def test_empty_transcript_is_hallucination():
    assert is_whisper_hallucination("") is True
    assert is_whisper_hallucination("   ") is True


def test_known_hallucinations():
    assert is_whisper_hallucination("Thank you.") is True
    assert is_whisper_hallucination("thank you") is True
    assert is_whisper_hallucination("Thanks for watching.") is True
    assert is_whisper_hallucination("Subscribe to my channel.") is True


def test_repetitive_hallucination_pattern():
    assert is_whisper_hallucination("Thank you. Thank you. Thank you.") is True


def test_real_speech_passes():
    assert is_whisper_hallucination("Open Chrome and search for weather") is False
    assert is_whisper_hallucination("What's on my calendar today?") is False


def test_filter_transcript_disabled():
    assert filter_transcript("Thank you.", enabled=False) == "Thank you."


def test_filter_transcript_removes_hallucination():
    assert filter_transcript("Thank you.", enabled=True) == ""


def test_filter_transcript_keeps_real_text():
    text = "Remind me to call mom at five"
    assert filter_transcript(text, enabled=True) == text
