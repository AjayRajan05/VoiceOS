"""Multi-model advisory loop (MoA) for second opinions."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MoaLoop:
    def __init__(self, agent_llm, *, reference_roles: Optional[List[str]] = None, max_advisors: int = 3):
        self.agent_llm = agent_llm
        self.reference_roles = reference_roles or ["researcher", "analyst", "developer"]
        self.max_advisors = max(1, max_advisors)

    async def advise(self, question: str, *, context: str = "") -> Dict[str, Any]:
        advisors = self.reference_roles[: self.max_advisors]
        opinions: List[Dict[str, str]] = []
        for role in advisors:
            prompt = (
                f"You are a {role} advisor. Give a concise second opinion.\n"
                f"Question: {question}\n"
            )
            if context:
                prompt += f"Context:\n{context}\n"
            try:
                chunks: List[str] = []
                async for chunk in self.agent_llm.stream_messages(
                    [{"role": "user", "content": prompt}],
                    role=role,
                ):
                    chunks.append(chunk)
                opinions.append({"role": role, "opinion": "".join(chunks)[:2000]})
            except Exception as exc:
                logger.debug("MoA advisor %s failed: %s", role, exc)
                opinions.append({"role": role, "opinion": f"(unavailable: {exc})"})

        synthesis_prompt = (
            "Synthesize these advisor opinions into one actionable answer.\n"
            f"Question: {question}\n\n"
            + "\n\n".join(f"{o['role']}: {o['opinion']}" for o in opinions)
        )
        synth_chunks: List[str] = []
        async for chunk in self.agent_llm.stream_messages(
            [{"role": "user", "content": synthesis_prompt}],
            role="general",
        ):
            synth_chunks.append(chunk)
        return {
            "success": True,
            "question": question,
            "opinions": opinions,
            "synthesis": "".join(synth_chunks)[:4000],
        }
