from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class JobRecord:
    job_id: str
    status: str  # queued | running | done | error
    stage: str | None = None
    error: str | None = None
    artifact_id: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class JobQueue(ABC):
    """Swappable backend: in-memory now, Redis/RQ later."""

    @abstractmethod
    def create(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def get(self, job_id: str) -> JobRecord | None:
        raise NotImplementedError

    @abstractmethod
    def update(self, job_id: str, **kwargs: Any) -> None:
        raise NotImplementedError


class InMemoryJobQueue(JobQueue):
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = asyncio.Lock()

    def create(self) -> str:
        jid = str(uuid.uuid4())
        self._jobs[jid] = JobRecord(job_id=jid, status="queued")
        return jid

    def get(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    def update(self, job_id: str, **kwargs: Any) -> None:
        rec = self._jobs.get(job_id)
        if not rec:
            return
        for k, v in kwargs.items():
            if hasattr(rec, k):
                setattr(rec, k, v)


def get_default_queue() -> JobQueue:
    return _GLOBAL_QUEUE


_GLOBAL_QUEUE: JobQueue = InMemoryJobQueue()


def reset_job_queue_for_tests() -> None:
    global _GLOBAL_QUEUE
    _GLOBAL_QUEUE = InMemoryJobQueue()
