"""Shared workspace path resolution for VoiceOS tools."""

from pathlib import Path


def resolve_within_workspace(workspace_root: Path, path: str) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        return (workspace_root / candidate).resolve()
    return candidate.resolve()


def assert_within_workspace(workspace_root: Path, resolved: Path) -> None:
    root = workspace_root.resolve()
    if not str(resolved).startswith(str(root)):
        raise PermissionError(f"Path {resolved} is outside workspace bounds")
