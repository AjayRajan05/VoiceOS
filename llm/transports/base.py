"""LLM transport abstraction layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional


class LLMTransport(ABC):
    @abstractmethod
    async def complete(self, messages: List[Dict[str, str]], **kwargs) -> str: ...

    @abstractmethod
    async def stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncIterator[str]: ...


def create_transport(name: str, **config) -> LLMTransport:
    normalized = (name or "ollama").lower().strip()
    if normalized in ("openai", "api", "remote"):
        from llm.transports.openai_compatible import OpenAICompatibleTransport

        return OpenAICompatibleTransport(**config)
    from llm.transports.ollama import OllamaTransport

    return OllamaTransport(**config)
