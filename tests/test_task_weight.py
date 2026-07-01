"""Tests for task weight classification and distributed routing."""

import os

import pytest

from agents.core.planner import Planner, TaskPlan, TaskType
from agents.core.task_weight import TaskWeight, classify_task_weight, requires_local_execution
from core.distributed.routing import is_queued_execution, should_offload_to_workers


class TestTaskWeight:
    def test_os_tools_force_local(self):
        plan = Planner().analyze_input("open chrome")
        assert plan.type == TaskType.SIMPLE
        assert requires_local_execution(plan)
        assert classify_task_weight(plan) == TaskWeight.LIGHT

    def test_web_search_simple_is_heavy(self):
        plan = Planner().analyze_input("search for quantum computing trends")
        assert plan.type == TaskType.SIMPLE
        assert plan.intent == "web_search_simple"
        assert classify_task_weight(plan) == TaskWeight.HEAVY

    def test_complex_research_is_heavy(self):
        plan = Planner().analyze_input("investigate machine learning trends")
        assert plan.type == TaskType.COMPLEX
        assert classify_task_weight(plan) == TaskWeight.HEAVY

    def test_autonomous_is_heavy(self):
        plan = Planner().analyze_input("build a python script to scrape product prices")
        assert plan.type == TaskType.AUTONOMOUS
        assert classify_task_weight(plan) == TaskWeight.HEAVY

    def test_screenshot_stays_light(self):
        plan = Planner().analyze_input("screenshot")
        assert classify_task_weight(plan) == TaskWeight.LIGHT


class TestShouldOffload:
    def test_no_offload_when_local_mode(self, monkeypatch):
        monkeypatch.setenv("EXECUTION_MODE", "local")
        plan = Planner().analyze_input("research neural networks")
        assert not should_offload_to_workers(plan)

    def test_offload_complex_when_queued(self, monkeypatch):
        monkeypatch.setenv("EXECUTION_MODE", "queued")
        plan = Planner().analyze_input("research neural networks")
        assert should_offload_to_workers(plan)

    def test_no_offload_os_when_queued(self, monkeypatch):
        monkeypatch.setenv("EXECUTION_MODE", "queued")
        plan = Planner().analyze_input("open notepad")
        assert not should_offload_to_workers(plan)

    def test_offload_web_search_when_queued(self, monkeypatch):
        monkeypatch.setenv("EXECUTION_MODE", "queued")
        plan = Planner().analyze_input("search for rust async patterns")
        assert should_offload_to_workers(plan)

    def test_is_queued_execution_reads_env(self, monkeypatch):
        monkeypatch.setenv("EXECUTION_MODE", "queued")
        assert is_queued_execution()
        monkeypatch.setenv("EXECUTION_MODE", "local")
        assert not is_queued_execution()
