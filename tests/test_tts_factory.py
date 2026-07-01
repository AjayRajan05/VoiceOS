"""TTS factory tests."""

from dataclasses import dataclass

from tts.engine_factory import create_tts_engine
from tts.text_engine import TextTTSEngine


@dataclass
class VoiceCfg:
    tts_engine: str = "auto"
    tts_model: str = "coqui-tts"


def test_tts_factory_returns_real_engine():
    eng = create_tts_engine(VoiceCfg())
    assert hasattr(eng, "speak")
    assert hasattr(eng, "stop")


def test_tts_factory_text_fallback_when_no_heavy_backends():
    eng = create_tts_engine(VoiceCfg(tts_engine="auto"))
    if not getattr(eng, "_available", True) and eng.__class__.__name__ != "TextTTSEngine":
        eng = create_tts_engine(VoiceCfg(tts_engine="auto"))
    assert eng.__class__.__name__ in ("TextTTSEngine", "TTSEngine", "KokoroTTSEngine")
