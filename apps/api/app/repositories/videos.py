from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.videos import Video, VideoIngestRequest, VideoStatus
from ..models.video import VideoModel


class VideosRepository(Protocol):
    async def create(self, org_id: UUID, payload: VideoIngestRequest) -> Video: ...

    async def get(self, video_id: UUID, org_id: UUID) -> Video | None: ...

    async def update_status(
        self, video_id: UUID, org_id: UUID, status: VideoStatus
    ) -> Video | None: ...

    async def set_upload_key(
        self, video_id: UUID, org_id: UUID, upload_key: str
    ) -> Video | None: ...

    async def update_metadata(
        self,
        video_id: UUID,
        org_id: UUID,
        *,
        duration_ms: int | None = None,
        frame_rate: float | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> Video | None: ...

    async def list_for_project(
        self, project_id: UUID, org_id: UUID
    ) -> list[Video]: ...


class InMemoryVideosRepository:
    """Ephemeral storage that mimics persistence for early iterations."""

    def __init__(self) -> None:
        self._videos: dict[UUID, Video] = {}

    async def create(self, org_id: UUID, payload: VideoIngestRequest) -> Video:
        now = datetime.utcnow()
        video = Video(
            org_id=org_id,
            status=VideoStatus.INGEST_QUEUED,
            created_at=now,
            updated_at=now,
            **payload.model_dump(),
        )
        self._videos[video.id] = video
        return video

    async def get(self, video_id: UUID, org_id: UUID) -> Video | None:
        video = self._videos.get(video_id)
        if video and video.org_id == org_id:
            return video
        return None

    async def update_status(
        self,
        video_id: UUID,
        org_id: UUID,
        status: VideoStatus,
    ) -> Video | None:
        video = self._videos.get(video_id)
        if video and video.org_id == org_id:
            updated = video.model_copy(
                update={"status": status, "updated_at": datetime.utcnow()}
            )
            self._videos[video_id] = updated
            return updated
        return None

    async def set_upload_key(
        self, video_id: UUID, org_id: UUID, upload_key: str
    ) -> Video | None:
        video = self._videos.get(video_id)
        if video and video.org_id == org_id:
            updated = video.model_copy(
                update={
                    "upload_key": upload_key,
                    "updated_at": datetime.utcnow(),
                }
            )
            self._videos[video_id] = updated
            return updated
        return None

    async def update_metadata(
        self,
        video_id: UUID,
        org_id: UUID,
        *,
        duration_ms: int | None = None,
        frame_rate: float | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> Video | None:
        video = self._videos.get(video_id)
        if video and video.org_id == org_id:
            updates: dict[str, object] = {"updated_at": datetime.utcnow()}
            if duration_ms is not None:
                updates["duration_ms"] = duration_ms
            if frame_rate is not None:
                updates["frame_rate"] = frame_rate
            if width is not None:
                updates["width"] = width
            if height is not None:
                updates["height"] = height
            updated = video.model_copy(update=updates)
            self._videos[video_id] = updated
            return updated
        return None

    async def list_for_project(
        self, project_id: UUID, org_id: UUID
    ) -> list[Video]:
        return [
            video
            for video in self._videos.values()
            if video.org_id == org_id and video.project_id == project_id
        ]


class SqlAlchemyVideosRepository:
    """Video repository backed by SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, org_id: UUID, payload: VideoIngestRequest) -> Video:
        now = datetime.utcnow()
        model = VideoModel(
            org_id=org_id,
            status=VideoStatus.INGEST_QUEUED.value,
            created_at=now,
            updated_at=now,
            **payload.model_dump(),
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        await self._session.commit()
        return Video.model_validate(model)

    async def get(self, video_id: UUID, org_id: UUID) -> Video | None:
        result = await self._session.execute(
            select(VideoModel).where(
                VideoModel.id == video_id,
                VideoModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return Video.model_validate(model)

    async def update_status(
        self, video_id: UUID, org_id: UUID, status: VideoStatus
    ) -> Video | None:
        result = await self._session.execute(
            select(VideoModel).where(
                VideoModel.id == video_id,
                VideoModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        model.status = status.value
        model.updated_at = datetime.utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return Video.model_validate(model)

    async def set_upload_key(
        self, video_id: UUID, org_id: UUID, upload_key: str
    ) -> Video | None:
        result = await self._session.execute(
            select(VideoModel).where(
                VideoModel.id == video_id,
                VideoModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        model.upload_key = upload_key
        model.updated_at = datetime.utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return Video.model_validate(model)

    async def update_metadata(
        self,
        video_id: UUID,
        org_id: UUID,
        *,
        duration_ms: int | None = None,
        frame_rate: float | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> Video | None:
        result = await self._session.execute(
            select(VideoModel).where(
                VideoModel.id == video_id,
                VideoModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        if duration_ms is not None:
            model.duration_ms = duration_ms
        if frame_rate is not None:
            model.frame_rate = frame_rate
        if width is not None:
            model.width = width
        if height is not None:
            model.height = height
        model.updated_at = datetime.utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return Video.model_validate(model)

    async def list_for_project(self, project_id: UUID, org_id: UUID) -> list[Video]:
        result = await self._session.execute(
            select(VideoModel)
            .where(
                VideoModel.project_id == project_id,
                VideoModel.org_id == org_id,
            )
            .order_by(VideoModel.created_at.desc())
        )
        return [Video.model_validate(row) for row in result.scalars().all()]

