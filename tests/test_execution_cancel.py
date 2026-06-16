"""Execution cancellation tests."""

import asyncio
import pytest

from core.runtime.session import ExecutionSession


@pytest.mark.asyncio
async def test_session_cancel():
    session = ExecutionSession()
    done = False

    async def work():
        nonlocal done
        for _ in range(50):
            session.check_cancelled()
            await asyncio.sleep(0.01)
        done = True

    task = asyncio.create_task(work())
    session.register_task(task)
    await asyncio.sleep(0.05)
    session.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not done


def test_session_cancel_flag():
    session = ExecutionSession()
    assert not session.is_cancelled
    session.cancel()
    assert session.is_cancelled
