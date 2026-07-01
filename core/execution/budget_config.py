"""Budget constants for tool result persistence."""

from dataclasses import dataclass, field
from typing import Dict

PINNED_THRESHOLDS: Dict[str, float] = {
    "read_file": float("inf"),
}

DEFAULT_RESULT_SIZE_CHARS: int = 100_000
DEFAULT_TURN_BUDGET_CHARS: int = 200_000
DEFAULT_PREVIEW_SIZE_CHARS: int = 1_500


@dataclass(frozen=True)
class BudgetConfig:
    default_result_size: int = DEFAULT_RESULT_SIZE_CHARS
    turn_budget: int = DEFAULT_TURN_BUDGET_CHARS
    preview_size: int = DEFAULT_PREVIEW_SIZE_CHARS
    tool_overrides: Dict[str, int] = field(default_factory=dict)
    enabled: bool = True

    def resolve_threshold(self, tool_name: str, registry=None) -> int | float:
        if tool_name in PINNED_THRESHOLDS:
            return PINNED_THRESHOLDS[tool_name]
        if tool_name in self.tool_overrides:
            return self.tool_overrides[tool_name]
        if registry is not None:
            getter = getattr(registry, "get_max_result_size", None)
            if callable(getter):
                value = getter(tool_name, default=self.default_result_size)
                if value == float("inf"):
                    return value
                return min(value, self.default_result_size)
        return self.default_result_size


DEFAULT_BUDGET = BudgetConfig()
