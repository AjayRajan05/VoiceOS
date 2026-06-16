"""Backward-compatible streaming LLM wrapper delegating to LLMService."""

from typing import Any, AsyncIterator, List, Union

from llm.llm_service import LLMService
from llm.model_paths import get_llm_model_path


class StreamingLLM:

    def __init__(self, model_path: str = None):
        self._service = LLMService(
            provider="local",
            model_path=model_path or get_llm_model_path(),
        )

    def set_model_path(self, path: str) -> None:
        self._service.model_path = path
        self._service._llama = None

    def stream_response(self, prompt):
        import asyncio

        messages = prompt if isinstance(prompt, list) else [{"role": "user", "content": str(prompt)}]

        async def _collect():
            parts = []
            async for chunk in self._service.stream_messages(messages):
                parts.append(chunk)
            return parts

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                for part in []:
                    yield part
                text = self._service.format_messages(messages)
                yield f"[use stream_response_async in async context] {text[:200]}"
                return
            tokens = loop.run_until_complete(_collect())
        except RuntimeError:
            tokens = asyncio.run(_collect())

        for token in tokens:
            yield token

    async def stream_response_async(self, messages) -> AsyncIterator[str]:
        if isinstance(messages, str):
            messages = [{"role": "user", "content": messages}]
        async for chunk in self._service.stream_messages(messages):
            yield chunk
