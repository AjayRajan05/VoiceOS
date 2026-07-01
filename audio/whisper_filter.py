"""Filter known Whisper hallucinations on silent or near-silent audio.

Whisper hallucination filter for VoiceOS STT pipeline.
"""

from __future__ import annotations

import re

WHISPER_HALLUCINATIONS = {
    "thank you.",
    "thank you",
    "thanks for watching.",
    "thanks for watching",
    "subscribe to my channel.",
    "subscribe to my channel",
    "like and subscribe.",
    "like and subscribe",
    "please subscribe.",
    "please subscribe",
    "thank you for watching.",
    "thank you for watching",
    "bye.",
    "bye",
    "you",
    "the end.",
    "the end",
    "продолжение следует",
    "продолжение следует...",
    "sous-titres",
    "sous-titres réalisés par la communauté d'amara.org",
    "sottotitoli creati dalla comunità amara.org",
    "untertitel von stephanie geiges",
    "amara.org",
    "www.mooji.org",
    "ご視聴ありがとうございました",
}

_HALLUCINATION_REPEAT_RE = re.compile(
    r"^(?:thank you|thanks|bye|you|ok|okay|the end|\.|\s|,|!)+$",
    flags=re.IGNORECASE,
)


def is_whisper_hallucination(transcript: str) -> bool:
    """Return True when transcript matches a known silence hallucination."""
    cleaned = transcript.strip().lower()
    if not cleaned:
        return True
    if cleaned.rstrip(".!") in WHISPER_HALLUCINATIONS or cleaned in WHISPER_HALLUCINATIONS:
        return True
    if _HALLUCINATION_REPEAT_RE.match(cleaned):
        return True
    return False


def filter_transcript(transcript: str, *, enabled: bool = True) -> str:
    """Return transcript text, or empty string if filtered as hallucination."""
    if not enabled or not transcript:
        return "" if not transcript else transcript.strip()
    text = transcript.strip()
    if is_whisper_hallucination(text):
        return ""
    return text
