"""Tests for turn policy and interrupt lifecycle."""

import asyncio

import pytest

from core.event import Event
from core.events.events import Events
from core.runtime.session import ExecutionSession
from interrupt.turn_policy import TurnPolicy, parse_turn_policy
from tests.real_stack import build_orchestrator


def test_parse_turn_policy():
    assert parse_turn_policy("queue") == TurnPolicy.QUEUE
    assert parse_turn_policy("steer") == TurnPolicy.STEER
    assert parse_turn_policy("unknown") == TurnPolicy.INTERRUPT


def test_execution_session_steering():
    session = ExecutionSession()
    session.add_steering("focus on pricing")
    session.add_steering("  ")
    msgs = session.pop_steering()
    assert msgs == ["focus on pricing"]
    assert session.pop_steering() == []


@pytest.mark.asyncio
async def test_orchestrator_queues_input_when_busy():
    orch = build_orchestrator(turn_policy="queue")
    session = ExecutionSession()
    task = asyncio.create_task(asyncio.sleep(10))
    session.register_task(task)
    orch._active_session = session

    await orch._handle_speech_input(Event(Events.SPEECH_TRANSCRIBED, {"text": "follow up"}, "stt"))
    assert orch._input_queue.qsize() == 1
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


@pytest.mark.asyncio
async def test_orchestrator_steers_active_session():
    orch = build_orchestrator(turn_policy="steer")
    session = ExecutionSession()
    task = asyncio.create_task(asyncio.sleep(10))
    session.register_task(task)
    orch._active_session = session

    await orch._handle_speech_input(
        Event(Events.SPEECH_TRANSCRIBED, {"text": "also check competitors"}, "stt")
    )
    assert session.steering_messages == ["also check competitors"]
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
