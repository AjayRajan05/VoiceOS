"""Ollama / OpenAI-compatible HTTP transport."""

from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator, Dict, List

import requests


class OllamaTransport:
    def __init__(
        self,
        *,
        api_base: str | None = None,
        model_name: str = "llama3",
        temperature: float = 0.7,
        timeout: float = 120.0,
        **_: Any,
    ):
        self.api_base = (api_base or os.getenv("VOICEOS_LLM_API_BASE") or "http://localhost:11434").rstrip("/")
        self.model_name = model_name
        self.temperature = temperature
        self.timeout = timeout

    async def complete(self, messages: List[Dict[str, str]], **kwargs) -> str:
        chunks = []
        async for chunk in self.stream(messages, **kwargs):
            chunks.append(chunk)
        return "".join(chunks)

    async def stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncIterator[str]:
        payload = {
            "model": kwargs.get("model", self.model_name),
            "messages": messages,
            "stream": True,
            "options": {"temperature": kwargs.get("temperature", self.temperature)},
        }
        url = f"{self.api_base}/api/chat"
        with requests.post(url, json=payload, stream=True, timeout=self.timeout) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    delta = chunk.get("message", {}).get("content", "")
                except json.JSONDecodeError:
                    delta = ""
                if delta:
                    yield delta
