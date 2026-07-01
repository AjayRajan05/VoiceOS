"""Proactive scheduled assistance via simple interval/cron jobs."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class CronJob:
    name: str
    message: str
    every_minutes: int = 0
    cron: str = ""
    enabled: bool = True
    source: str = "scheduler"
    last_run: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class CronScheduler:
    """Run proactive messages on interval or cron expression (croniter optional)."""

    def __init__(self, jobs_path: str | Path, adapter, *, tick_seconds: float = 30.0) -> None:
        self.jobs_path = Path(jobs_path)
        self.adapter = adapter
        self.tick_seconds = tick_seconds
        self._jobs: List[CronJob] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def load_jobs(self) -> None:
        self._jobs.clear()
        if not self.jobs_path.exists():
            logger.info("Cron jobs file not found: %s", self.jobs_path)
            return
        try:
            data = yaml.safe_load(self.jobs_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            logger.error("Failed to load cron jobs: %s", exc)
            return
        for entry in data.get("jobs", []):
            if not isinstance(entry, dict):
                continue
            self._jobs.append(
                CronJob(
                    name=str(entry.get("name", "job")),
                    message=str(entry.get("message", "")),
                    every_minutes=int(entry.get("every_minutes", 0) or 0),
                    cron=str(entry.get("cron", "") or ""),
                    enabled=bool(entry.get("enabled", True)),
                    source=str(entry.get("source", "scheduler")),
                    metadata=dict(entry.get("metadata") or {}),
                )
            )

    async def start(self) -> None:
        self.load_jobs()
        if not self._jobs:
            logger.info("No cron jobs configured")
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Cron scheduler started (%s jobs)", len(self._jobs))

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        while self._running:
            now = datetime.now()
            for job in self._jobs:
                if not job.enabled or not job.message:
                    continue
                if self._should_run(job, now):
                    await self._run_job(job, now)
            await asyncio.sleep(self.tick_seconds)

    def _should_run(self, job: CronJob, now: datetime) -> bool:
        if job.cron:
            return self._cron_due(job, now)
        if job.every_minutes > 0:
            if job.last_run is None:
                return True
            elapsed = (now - job.last_run).total_seconds() / 60.0
            return elapsed >= job.every_minutes
        return False

    def _cron_due(self, job: CronJob, now: datetime) -> bool:
        try:
            from croniter import croniter
        except ImportError:
            logger.debug("croniter not installed; skipping cron job %s", job.name)
            return False
        base = job.last_run or now
        itr = croniter(job.cron, base)
        next_run = itr.get_next(datetime)
        return next_run <= now

    async def _run_job(self, job: CronJob, now: datetime) -> None:
        job.last_run = now
        logger.info("Running cron job: %s", job.name)
        try:
            await self.adapter.process_message(
                job.message,
                session_id=f"scheduler:{job.name}",
                source=job.source,
                metadata={"job": job.name, **job.metadata},
            )
        except Exception as exc:
            logger.error("Cron job %s failed: %s", job.name, exc)
