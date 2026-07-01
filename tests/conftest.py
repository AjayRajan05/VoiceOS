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


@pytest.fixture
def event_bus():
    from tests.real_stack import build_event_bus

    return build_event_bus()


@pytest.fixture
def orchestrator():
    from tests.real_stack import build_orchestrator

    return build_orchestrator()


@pytest.fixture
def gateway_adapter(orchestrator):
    from tests.real_stack import build_gateway_adapter

    return build_gateway_adapter(orchestrator)


@pytest.fixture
def gateway_config():
    from core.config_manager import GatewayConfig, WebhookRouteConfig

    return GatewayConfig(
        enabled=True,
        host="127.0.0.1",
        port=8765,
        api_key="test-key",
        webhooks={
            "alerts": WebhookRouteConfig(
                secret="webhook-secret",
                prompt_template="Alert: {body}",
            )
        },
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: async test marker")


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    try:
        import pytest_asyncio  # noqa: F401
    except ImportError:
        for item in items:
            if item.get_closest_marker("asyncio") is not None:
                item.add_marker(
                    pytest.mark.skip(reason="pytest-asyncio is required for async tests")
                )
