"""TTS factory tests."""

from unittest.mock import patch, MagicMock
from dataclasses import dataclass


@dataclass
class VoiceCfg:
    tts_engine: str = "auto"
    tts_model: str = "coqui-tts"


def test_tts_factory_text_fallback():
    from tts.engine_factory import create_tts_engine
    from tts.text_engine import TextTTSEngine

    with patch("tts.coqui_engine.TTSEngine", side_effect=Exception("no coqui")):
        with patch("tts.kokoro_engine.KokoroTTSEngine") as k:
            inst = MagicMock()
            inst._available = False
            k.return_value = inst
            eng = create_tts_engine(VoiceCfg())
            assert isinstance(eng, TextTTSEngine)
