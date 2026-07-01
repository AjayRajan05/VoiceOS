"""Session shell configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class SessionShellConfig:
    enabled: bool = False
    input_mode: str = "wake_word"  # always_on | wake_word | push_to_talk
    wake_phrases: tuple[str, ...] = ("hey voiceos", "voice os", "hey voice os")
    armed_timeout_s: float = 12.0
    capability_greeting: bool = True
    resume_on_start: bool = True
    push_to_talk_key: str = "space"

    @classmethod
    def from_mapping(cls, data: Optional[dict[str, Any]] = None) -> "SessionShellConfig":
        if not data:
            return cls()
        wake = data.get("wake_phrases")
        if isinstance(wake, list):
            wake_phrases = tuple(str(item).lower().strip() for item in wake if str(item).strip())
        elif isinstance(wake, str) and wake.strip():
            wake_phrases = tuple(part.strip() for part in wake.split(",") if part.strip())
        else:
            wake_phrases = cls().wake_phrases
        return cls(
            enabled=bool(data.get("enabled", True)),
            input_mode=str(data.get("input_mode", "wake_word")).lower().strip(),
            wake_phrases=wake_phrases,
            armed_timeout_s=float(data.get("armed_timeout_s", 12.0)),
            capability_greeting=bool(data.get("capability_greeting", True)),
            resume_on_start=bool(data.get("resume_on_start", True)),
            push_to_talk_key=str(data.get("push_to_talk_key", "space")).lower().strip(),
        )

    @classmethod
    def from_env(cls, base: Optional["SessionShellConfig"] = None) -> "SessionShellConfig":
        cfg = base or cls()
        enabled = os.getenv("VOICEOS_SHELL_ENABLED")
        if enabled is not None:
            cfg.enabled = enabled.lower() in ("1", "true", "yes", "on")
        mode = os.getenv("VOICEOS_SHELL_INPUT_MODE")
        if mode:
            cfg.input_mode = mode.lower().strip()
        wake = os.getenv("VOICEOS_WAKE_PHRASES")
        if wake:
            cfg.wake_phrases = tuple(part.strip().lower() for part in wake.split(",") if part.strip())
        ptt_key = os.getenv("VOICEOS_PTT_KEY")
        if ptt_key:
            cfg.push_to_talk_key = ptt_key.lower().strip()
        return cfg
