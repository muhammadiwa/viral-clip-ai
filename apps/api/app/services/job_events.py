"""In-memory pub/sub broker for streaming job updates over WebSocket."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import AsyncIterator
from uuid import UUID

from ..domain.jobs import Job


class JobEventBroker:
    """Manages subscriptions for job status updates."""

    def __init__(self) -> None:
        self._subscribers: dict[UUID, set[asyncio.Queue[Job]]] = defaultdict(set)

    @asynccontextmanager
    async def _register_queue(
        self, job_id: UUID
    ) -> AsyncIterator[asyncio.Queue[Job]]:
        queue: asyncio.Queue[Job] = asyncio.Queue()
        self._subscribers[job_id].add(queue)
        try:
            yield queue
        finally:
            subscribers = self._subscribers.get(job_id)
            if subscribers:
                subscribers.discard(queue)
                if not subscribers:
                    self._subscribers.pop(job_id, None)

    async def subscribe(self, job_id: UUID) -> AsyncIterator[Job]:
        """Yields job updates for the given job identifier."""

        async with self._register_queue(job_id) as queue:
            while True:
                job = await queue.get()
                yield job

    async def publish(self, job: Job) -> None:
        """Broadcasts the latest job state to all listeners."""

        for queue in list(self._subscribers.get(job.id, set())):
            await queue.put(job)
