"""Worker safety tests."""

from tools.register_tools import register_worker_tools
from permissions.permission_engine import PermissionEngine, set_permission_engine


def test_worker_registry_excludes_os_tools():
    registry = register_worker_tools()
    names = registry.list_tools()
    assert not any(n.startswith("os_") for n in names)


def test_worker_permission_denies_os_intent():
    import asyncio
    from workers.agent_worker import WorkerPermissionEngine

    pe = WorkerPermissionEngine(safety_mode="strict")
    set_permission_engine(pe)

    async def check():
        required = await pe.is_permission_required("open_application", ["os_open_app"])
        if required:
            return await pe.prompt_for_approval("open_application", ["os_open_app"], "open x")
        return True

    allowed = asyncio.run(check())
    assert allowed is False
