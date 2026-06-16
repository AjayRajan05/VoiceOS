"""Single source of truth for local LLM model paths."""

import os
from pathlib import Path
from typing import Optional

_resolved_llm_path: Optional[str] = None


def set_llm_model_path(path: str) -> None:
    global _resolved_llm_path
    _resolved_llm_path = str(path)
    os.environ["VOICEOS_LLM_PATH"] = _resolved_llm_path


def get_llm_model_path() -> str:
    global _resolved_llm_path
    if _resolved_llm_path and Path(_resolved_llm_path).exists():
        return _resolved_llm_path

    env_path = os.getenv("VOICEOS_LLM_PATH")
    if env_path and Path(env_path).exists():
        _resolved_llm_path = env_path
        return env_path

    try:
        from core.config_manager import ConfigManager
        cfg_path = ConfigManager().get_config().llm.model_path
        if cfg_path and Path(cfg_path).exists():
            set_llm_model_path(cfg_path)
            return cfg_path
    except Exception:
        pass

    models_dir = Path("models")
    if models_dir.is_dir():
        for candidate in sorted(models_dir.glob("*.gguf"), key=lambda p: p.stat().st_size, reverse=True):
            if candidate.stat().st_size > 1024 * 1024:
                set_llm_model_path(str(candidate))
                return str(candidate)

    fallback = env_path or "models/mistral-7b-instruct-v0.2.Q4_K_M.gguf"
    return fallback


def apply_model_manager_result(model_paths: dict) -> str:
    llm_path = model_paths.get("llm") if model_paths else None
    if llm_path:
        set_llm_model_path(llm_path)
    else:
        get_llm_model_path()
    return get_llm_model_path()
