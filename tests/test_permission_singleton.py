"""Permission engine singleton tests."""

from permissions.permission_engine import (
    PermissionEngine,
    set_permission_engine,
    get_permission_engine,
    permission_engine,
)


def test_set_get_permission_engine():
    a = PermissionEngine()
    set_permission_engine(a)
    assert get_permission_engine() is a


def test_proxy_uses_same_engine():
    b = PermissionEngine()
    set_permission_engine(b)
    permission_engine.set_user_permission_level(permission_engine.current_user_level)
    assert get_permission_engine().current_user_level == b.current_user_level
