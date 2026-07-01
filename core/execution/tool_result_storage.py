"""Tool result persistence — spill large outputs to workspace files."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any, List, Optional

from core.execution.budget_config import DEFAULT_BUDGET, BudgetConfig, DEFAULT_PREVIEW_SIZE_CHARS

logger = logging.getLogger(__name__)

PERSISTED_OUTPUT_TAG = "<persisted-output>"
PERSISTED_OUTPUT_CLOSING_TAG = "</persisted-output>"
_BUDGET_TOOL_NAME = "__budget_enforcement__"
_UNSAFE_RESULT_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9_.-]+")
_MAX_RESULT_FILENAME_STEM = 120


def result_to_text(result: Any) -> str:
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, indent=2, default=str)
    except (TypeError, ValueError):
        return str(result)


def generate_preview(content: str, max_chars: int = DEFAULT_PREVIEW_SIZE_CHARS) -> tuple[str, bool]:
    if len(content) <= max_chars:
        return content, False
    truncated = content[:max_chars]
    last_nl = truncated.rfind("\n")
    if last_nl > max_chars // 2:
        truncated = truncated[: last_nl + 1]
    return truncated, True


def _safe_result_filename(tool_use_id: str) -> str:
    raw_id = str(tool_use_id or "tool_result")
    safe_stem = _UNSAFE_RESULT_FILENAME_CHARS.sub("_", raw_id).strip("._-")
    changed = safe_stem != raw_id
    if not safe_stem:
        safe_stem = "tool_result"
        changed = True
    if changed or len(safe_stem) > _MAX_RESULT_FILENAME_STEM:
        digest = hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:12]
        safe_stem = safe_stem[:_MAX_RESULT_FILENAME_STEM].rstrip("._-") or "tool_result"
        safe_stem = f"{safe_stem}_{digest}"
    return f"{safe_stem}.txt"


def _build_persisted_message(
    preview: str,
    has_more: bool,
    original_size: int,
    file_path: str,
) -> str:
    size_kb = original_size / 1024
    size_str = f"{size_kb / 1024:.1f} MB" if size_kb >= 1024 else f"{size_kb:.1f} KB"
    msg = f"{PERSISTED_OUTPUT_TAG}\n"
    msg += f"This tool result was too large ({original_size:,} characters, {size_str}).\n"
    msg += f"Full output saved to: {file_path}\n"
    msg += "Use read_file with offset and limit to access specific sections.\n\n"
    msg += f"Preview (first {len(preview)} chars):\n"
    msg += preview
    if has_more:
        msg += "\n..."
    msg += f"\n{PERSISTED_OUTPUT_CLOSING_TAG}"
    return msg


def _write_result_file(content: str, storage_dir: Path, tool_use_id: str) -> Optional[str]:
    try:
        storage_dir.mkdir(parents=True, exist_ok=True)
        filename = _safe_result_filename(tool_use_id)
        path = storage_dir / filename
        path.write_text(content, encoding="utf-8")
        return str(path)
    except OSError as exc:
        logger.warning("Failed to spill tool result to %s: %s", storage_dir, exc)
        return None


def maybe_persist_tool_result(
    content: str,
    tool_name: str,
    tool_use_id: str,
    *,
    storage_dir: Path,
    config: BudgetConfig = DEFAULT_BUDGET,
    threshold: int | float | None = None,
    registry=None,
) -> str:
    if not config.enabled:
        return content

    effective_threshold = (
        threshold if threshold is not None else config.resolve_threshold(tool_name, registry=registry)
    )
    if effective_threshold == float("inf"):
        return content
    if len(content) <= effective_threshold:
        return content

    preview, has_more = generate_preview(content, max_chars=config.preview_size)
    file_path = _write_result_file(content, storage_dir, tool_use_id)
    if file_path:
        logger.info(
            "Spilled large tool result: %s (%s, %d chars -> %s)",
            tool_name,
            tool_use_id,
            len(content),
            file_path,
        )
        return _build_persisted_message(preview, has_more, len(content), file_path)

    logger.info("Inline-truncating large tool result: %s (%d chars)", tool_name, len(content))
    return (
        f"{preview}\n\n"
        f"[Truncated: tool response was {len(content):,} chars. "
        f"Full output could not be saved to workspace.]"
    )


def enforce_turn_budget(
    results: List[dict],
    *,
    storage_dir: Path,
    config: BudgetConfig = DEFAULT_BUDGET,
    registry=None,
) -> List[dict]:
    """Spill largest non-persisted results until aggregate content is under budget."""
    if not config.enabled:
        return results

    candidates = []
    total_size = 0
    for i, entry in enumerate(results):
        content = result_to_text(entry.get("result", ""))
        size = len(content)
        total_size += size
        if PERSISTED_OUTPUT_TAG not in content:
            candidates.append((i, size, content))

    if total_size <= config.turn_budget:
        return results

    candidates.sort(key=lambda x: x[1], reverse=True)
    for idx, size, content in candidates:
        if total_size <= config.turn_budget:
            break
        tool_use_id = results[idx].get("tool_call_id", f"budget_{idx}")
        replacement = maybe_persist_tool_result(
            content=content,
            tool_name=_BUDGET_TOOL_NAME,
            tool_use_id=tool_use_id,
            storage_dir=storage_dir,
            config=config,
            threshold=0,
            registry=registry,
        )
        if replacement != content:
            total_size -= size
            total_size += len(replacement)
            results[idx]["result"] = replacement
            logger.info("Turn budget enforcement: spilled result %s (%d chars)", tool_use_id, size)
    return results
