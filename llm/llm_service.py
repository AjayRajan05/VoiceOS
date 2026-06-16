"""Unified LLM inference facade for VoiceOS (local llama-cpp, Ollama API, hybrid)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional

from llm.model_paths import get_llm_model_path

logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    LOCAL = "local"
    API = "api"
    REMOTE = "remote"
    HYBRID = "hybrid"


class LLMService:
    """Single inference entry point used by agents, orchestrator, and workers."""

    def __init__(
        self,
        provider: str = "local",
        model_name: str = "mistral-7b-instruct",
        model_path: Optional[str] = None,
        api_base: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: float = 120.0,
    ):
        self.provider = self._normalize_provider(provider)
        self.model_name = model_name
        self.model_path = model_path or get_llm_model_path()
        self.api_base = api_base or os.getenv("VOICEOS_LLM_API_BASE") or os.getenv("LLM_ENDPOINT")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self._llama = None
        self._role_overrides: Dict[str, Dict[str, Any]] = {
            "researcher": {"temperature": 0.3, "max_tokens": 2048},
            "developer": {"temperature": 0.1, "max_tokens": 4096},
            "analyst": {"temperature": 0.5, "max_tokens": 3072},
            "summarizer": {"temperature": 0.3, "max_tokens": 2048},
        }

    @classmethod
    def from_voiceos_config(cls, llm_config) -> "LLMService":
        return cls(
            provider=getattr(llm_config, "provider", "local"),
            model_name=getattr(llm_config, "model_name", "mistral-7b-instruct"),
            model_path=getattr(llm_config, "model_path", None) or get_llm_model_path(),
            api_base=getattr(llm_config, "api_base", None),
            temperature=getattr(llm_config, "temperature", 0.7),
            max_tokens=getattr(llm_config, "max_tokens", 4096),
            timeout=getattr(llm_config, "timeout", 120.0),
        )

    @classmethod
    def from_env(cls) -> "LLMService":
        provider = os.getenv("LLM_PROVIDER", os.getenv("EXECUTION_MODE", "local"))
        if os.getenv("LLM_ENDPOINT") or os.getenv("VOICEOS_LLM_API_BASE"):
            provider = os.getenv("LLM_PROVIDER", "api")
        return cls(
            provider=provider,
            model_name=os.getenv("LLM_MODEL", "mistral"),
            api_base=os.getenv("VOICEOS_LLM_API_BASE") or os.getenv("LLM_ENDPOINT"),
        )

    @staticmethod
    def _normalize_provider(provider: str) -> LLMProvider:
        p = (provider or "local").lower().strip()
        if p in ("api", "remote"):
            return LLMProvider.API
        if p == "hybrid":
            return LLMProvider.HYBRID
        return LLMProvider.LOCAL

    @staticmethod
    def format_messages(messages: List[Dict[str, str]]) -> str:
        parts = []
        for msg in messages:
            if isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                parts.append(f"{role.upper()}: {content}")
            else:
                parts.append(str(msg))
        return "\n\n".join(parts)

    def _ensure_llama(self):
        if self._llama is None:
            from llama_cpp import Llama
            self._llama = Llama(model_path=self.model_path, n_ctx=4096)

    def _params_for_role(self, role: str) -> Dict[str, Any]:
        base = {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "model_name": self.model_name,
        }
        base.update(self._role_overrides.get(role or "general", {}))
        return base

    async def stream_messages(
        self, messages: List[Dict[str, str]], role: str = "general"
    ) -> AsyncIterator[str]:
        params = self._params_for_role(role)
        if self.provider == LLMProvider.API:
            async for chunk in self._stream_api(messages, params):
                yield chunk
            return
        if self.provider == LLMProvider.HYBRID:
            try:
                async for chunk in self._stream_local(messages, params):
                    yield chunk
                return
            except Exception as exc:
                logger.warning("Hybrid local failed, trying API: %s", exc)
            async for chunk in self._stream_api(messages, params):
                yield chunk
            return
        async for chunk in self._stream_local(messages, params):
            yield chunk

    async def complete_messages(self, messages: List[Dict[str, str]], role: str = "general") -> str:
        parts: List[str] = []
        async for chunk in self.stream_messages(messages, role=role):
            parts.append(chunk)
        return "".join(parts)

    async def _stream_local(self, messages: List[Dict[str, str]], params: Dict[str, Any]) -> AsyncIterator[str]:
        text = self.format_messages(messages)

        def _run():
            try:
                self._ensure_llama()
            except ImportError:
                return [f"[LLM unavailable — install llama-cpp-python] {text[:200]}"]
            except Exception as e:
                return [f"[LLM error: {e}]"]
            stream = self._llama(text, stream=True, temperature=params.get("temperature", 0.7))
            tokens = []
            for token in stream:
                if "choices" in token:
                    tokens.append(token["choices"][0]["text"])
            return tokens

        tokens = await asyncio.to_thread(_run)
        for token in tokens:
            yield token

    async def _stream_api(self, messages: List[Dict[str, str]], params: Dict[str, Any]) -> AsyncIterator[str]:
        base = self.api_base
        if not base:
            async for chunk in self._stream_local(messages, params):
                yield chunk
            return
        tokens = await asyncio.to_thread(self._collect_ollama_tokens, messages, params, base)
        for token in tokens:
            yield token

    def _ollama_generate_url(self, base_url: str) -> str:
        url = base_url.rstrip("/")
        if url.endswith("/api/generate"):
            return url
        if "/api/" in url:
            return url.split("/api/")[0] + "/api/generate"
        return url + "/api/generate"

    def _collect_ollama_tokens(
        self, messages: List[Dict[str, str]], params: Dict[str, Any], base_url: str
    ) -> List[str]:
        import requests

        url = self._ollama_generate_url(base_url)
        prompt = self.format_messages(messages)
        model = params.get("model_name", self.model_name)
        response = requests.post(
            url,
            json={
                "model": model,
                "prompt": prompt,
                "stream": True,
                "options": {"temperature": params.get("temperature", self.temperature)},
            },
            stream=True,
            timeout=self.timeout,
        )
        response.raise_for_status()
        tokens = []
        for line in response.iter_lines():
            if not line:
                continue
            data = json.loads(line.decode("utf-8") if isinstance(line, bytes) else line)
            token = data.get("response", "")
            if token:
                tokens.append(token)
            if data.get("done"):
                break
        return tokens
