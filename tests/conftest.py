"""Pytest configuration — ensure project root is on sys.path."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _init_permission_engine():
    from permissions.permission_engine import PermissionEngine, set_permission_engine
    engine = PermissionEngine()
    set_permission_engine(engine)
    yield engine
