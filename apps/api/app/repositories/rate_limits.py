"""In-memory rate limiting repository for development."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timedelta
from time import time
from typing import DefaultDict, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.rate_limits import RateLimitStatus
from ..models.rate_limit import RateLimitCounterModel


class RateLimitRepository(ABC):
    """Interface describing operations for tracking request quotas."""

    @abstractmethod
    async def hit(
        self,
        *,
        scope: str,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitStatus:
        """Record a request and return the latest quota status."""


class InMemoryRateLimitRepository(RateLimitRepository):
    """Simple rate limiter using per-scope timestamp buckets."""

    def __init__(self) -> None:
        self._buckets: DefaultDict[Tuple[str, str], list[float]] = defaultdict(list)

    async def hit(
        self,
        *,
        scope: str,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitStatus:
        now = time()
        bucket_key = (scope, key)
        entries = self._buckets[bucket_key]
        window_start = now - window_seconds
        # Drop timestamps that are outside of the active window
        entries[:] = [timestamp for timestamp in entries if timestamp > window_start]

        if len(entries) >= limit:
            retry_after = int(max(entries[0] + window_seconds - now, 0))
            return RateLimitStatus(
                allowed=False,
                limit=limit,
                remaining=0,
                retry_after_seconds=retry_after,
            )

        entries.append(now)
        remaining = max(limit - len(entries), 0)
        return RateLimitStatus(
            allowed=True,
            limit=limit,
            remaining=remaining,
            retry_after_seconds=0,
        )


class SqlAlchemyRateLimitRepository(RateLimitRepository):
    """Persists rate limit counters to Postgres."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def hit(
        self,
        *,
        scope: str,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> RateLimitStatus:
        now = datetime.utcnow()
        window_start = now - timedelta(seconds=window_seconds)
        result = await self._session.execute(
            select(RateLimitCounterModel).where(
                RateLimitCounterModel.scope == scope,
                RateLimitCounterModel.identity == key,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            model = RateLimitCounterModel(
                scope=scope,
                identity=key,
                window_started_at=now,
                count=1,
            )
            self._session.add(model)
            await self._session.commit()
            return RateLimitStatus(
                allowed=True,
                limit=limit,
                remaining=limit - 1,
                retry_after_seconds=0,
            )

        if model.window_started_at <= window_start:
            model.window_started_at = now
            model.count = 1
            await self._session.commit()
            return RateLimitStatus(
                allowed=True,
                limit=limit,
                remaining=limit - 1,
                retry_after_seconds=0,
            )

        if model.count >= limit:
            elapsed = (now - model.window_started_at).total_seconds()
            retry_after = max(int(window_seconds - elapsed), 0)
            return RateLimitStatus(
                allowed=False,
                limit=limit,
                remaining=0,
                retry_after_seconds=retry_after,
            )

        model.count += 1
        await self._session.commit()
        remaining = max(limit - model.count, 0)
        return RateLimitStatus(
            allowed=True,
            limit=limit,
            remaining=remaining,
            retry_after_seconds=0,
        )
