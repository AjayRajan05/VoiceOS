"""Tests for cron scheduler."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from core.scheduler.cron.scheduler import CronScheduler
from tests.real_stack import build_gateway_adapter


@pytest.mark.asyncio
async def test_cron_scheduler_runs_interval_job():
    with tempfile.TemporaryDirectory() as tmp:
        jobs_path = Path(tmp) / "jobs.yaml"
        jobs_path.write_text(
            "jobs:\n  - name: ping\n    every_minutes: 5\n    message: help\n",
            encoding="utf-8",
        )
        adapter = build_gateway_adapter()
        scheduler = CronScheduler(jobs_path, adapter, tick_seconds=0.01)
        scheduler.load_jobs()
        job = scheduler._jobs[0]
        assert scheduler._should_run(job, datetime.now()) is True
        await scheduler._run_job(job, datetime.now())
