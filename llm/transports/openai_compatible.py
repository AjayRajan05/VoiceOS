"""OpenAI-compatible chat transport."""

from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator, Dict, List

import requests


class OpenAICompatibleTransport:
    def __init__(
        self,
        *,
        api_base: str | None = None,
        api_key: str | None = None,
        model_name: str = "gpt-4o-mini",
        temperature: float = 0.7,
        timeout: float = 120.0,
        **_: Any,
    ):
        self.api_base = (api_base or os.getenv("OPENAI_API_BASE") or "https://api.openai.com/v1").rstrip("/")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model_name = model_name
        self.temperature = temperature
        self.timeout = timeout

    async def complete(self, messages: List[Dict[str, str]], **kwargs) -> str:
        chunks = []
        async for chunk in self.stream(messages, **kwargs):
            chunks.append(chunk)
        return "".join(chunks)

    async def stream(self, messages: List[Dict[str, str]], **kwargs) -> AsyncIterator[str]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": kwargs.get("model", self.model_name),
            "messages": messages,
            "stream": True,
            "temperature": kwargs.get("temperature", self.temperature),
        }
        url = f"{self.api_base}/chat/completions"
        with requests.post(url, headers=headers, json=payload, stream=True, timeout=self.timeout) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0]["delta"].get("content", "")
                except (KeyError, json.JSONDecodeError, IndexError):
                    delta = ""
                if delta:
                    yield delta
