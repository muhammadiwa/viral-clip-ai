from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.clips import (
    Clip,
    ClipCreate,
    ClipStyleStatus,
    ClipVoiceRequest,
    ClipVoiceStatus,
    SubtitleStyleRequest,
)
from ..models.clip import ClipModel


class ClipsRepository(Protocol):
    async def replace_for_video(
        self,
        *,
        org_id: UUID,
        project_id: UUID,
        video_id: UUID,
        clips: list[ClipCreate],
    ) -> list[Clip]:
        ...

    async def list_for_video(self, *, video_id: UUID, org_id: UUID) -> list[Clip]:
        ...

    async def get(self, *, clip_id: UUID, org_id: UUID) -> Clip | None:
        ...

    async def update_metadata(
        self,
        *,
        clip_id: UUID,
        org_id: UUID,
        title: str | None = None,
        description: str | None = None,
        start_ms: int | None = None,
        end_ms: int | None = None,
    ) -> Clip | None:
        ...

    async def update_style_request(
        self,
        *,
        clip_id: UUID,
        org_id: UUID,
        payload: SubtitleStyleRequest,
    ) -> Clip | None:
        ...

    async def update_style_status(
        self,
        *,
        clip_id: UUID,
        org_id: UUID,
        status: ClipStyleStatus,
        error: str | None = None,
    ) -> Clip | None:
        ...

    async def update_voice_request(
        self,
        *,
        clip_id: UUID,
        org_id: UUID,
        payload: ClipVoiceRequest,
    ) -> Clip | None:
        ...

    async def update_voice_status(
        self,
        *,
        clip_id: UUID,
        org_id: UUID,
        status: ClipVoiceStatus,
        error: str | None = None,
    ) -> Clip | None:
        ...


class InMemoryClipsRepository:
    """Stores generated clips in memory for iterative development."""

    def __init__(self) -> None:
        self._clips_by_video: dict[UUID, list[Clip]] = {}
        self._clips_by_id: dict[UUID, Clip] = {}

    async def replace_for_video(
        self,
        *,
        org_id: UUID,
        project_id: UUID,
        video_id: UUID,
        clips: list[ClipCreate],
    ) -> list[Clip]:
        now = datetime.utcnow()
        existing = self._clips_by_video.get(video_id, [])
        for clip in existing:
            self._clips_by_id.pop(clip.id, None)
        stored: list[Clip] = []
        for clip in clips:
            item = Clip(
                org_id=org_id,
                project_id=project_id,
                video_id=video_id,
                created_at=now,
                updated_at=now,
                **clip.model_dump(),
            )
            self._clips_by_id[item.id] = item
            stored.append(item)
        self._clips_by_video[video_id] = stored
        return stored

    async def list_for_video(self, *, video_id: UUID, org_id: UUID) -> list[Clip]:
        clips = self._clips_by_video.get(video_id, [])
        return [clip for clip in clips if clip.org_id == org_id]

    async def get(self, *, clip_id: UUID, org_id: UUID) -> Clip | None:
        clip = self._clips_by_id.get(clip_id)
        if clip and clip.org_id == org_id:
            return clip
        return None

    async def update_metadata(
        self,
        *,
        clip_id: UUID,
        org_id: UUID,
        title: str | None = None,
        description: str | None = None,
        start_ms: int | None = None,
        end_ms: int | None = None,
    ) -> Clip | None:
        clip = await self.get(clip_id=clip_id, org_id=org_id)
        if clip is None:
            return None
        updates: dict[str, object] = {"updated_at": datetime.utcnow()}
        if title is not None:
            updates["title"] = title
        if description is not None:
            updates["description"] = description
        if start_ms is not None:
            updates["start_ms"] = start_ms
        if end_ms is not None:
            updates["end_ms"] = end_ms
        updated = clip.model_copy(update=updates)
        self._clips_by_id[clip_id] = updated
        self._clips_by_video[clip.video_id] = [
            updated if existing.id == clip_id else existing
            for existing in self._clips_by_video.get(clip.video_id, [])
        ]
        return updated

    async def update_style_request(
        self,
        *,
        clip_id: UUID,
        org_id: UUID,
        payload: SubtitleStyleRequest,
    ) -> Clip | None:
        clip = await self.get(clip_id=clip_id, org_id=org_id)
        if not clip:
            return None
        style_settings = payload.model_dump(exclude_none=True)
        style_settings.pop("preset", None)
        updated = clip.model_copy(
            update={
                "style_status": ClipStyleStatus.STYLE_QUEUED,
                "style_preset": payload.preset,
                "style_settings": style_settings or None,
                "style_error": None,
                "updated_at": datetime.utcnow(),
            }
        )
        self._clips_by_id[clip_id] = updated
        self._clips_by_video[clip.video_id] = [
            updated if existing.id == clip_id else existing
            for existing in self._clips_by_video.get(clip.video_id, [])
        ]
        return updated

    async def update_style_status(
        self,
        *,
        clip_id: UUID,
        org_id: UUID,
        status: ClipStyleStatus,
        error: str | None = None,
    ) -> Clip | None:
        clip = await self.get(clip_id=clip_id, org_id=org_id)
        if not clip:
            return None
        updates: dict[str, object] = {
            "style_status": status,
            "style_error": error,
            "updated_at": datetime.utcnow(),
        }
        if status == ClipStyleStatus.STYLED:
            updates["last_styled_at"] = datetime.utcnow()
        updated = clip.model_copy(update=updates)
        self._clips_by_id[clip_id] = updated
        self._clips_by_video[clip.video_id] = [
            updated if existing.id == clip_id else existing
            for existing in self._clips_by_video.get(clip.video_id, [])
        ]
        return updated

    async def update_voice_request(
        self,
        *,
        clip_id: UUID,
        org_id: UUID,
        payload: ClipVoiceRequest,
    ) -> Clip | None:
        clip = await self.get(clip_id=clip_id, org_id=org_id)
        if not clip:
            return None
        request_settings = payload.model_dump(exclude_none=True)
        language = request_settings.pop("language_code", None)
        voice_name = request_settings.pop("voice", None)
        updated = clip.model_copy(
            update={
                "voice_status": ClipVoiceStatus.VOICE_QUEUED,
                "voice_language": language or clip.voice_language,
                "voice_name": voice_name or clip.voice_name,
                "voice_settings": request_settings or None,
                "voice_error": None,
                "updated_at": datetime.utcnow(),
            }
        )
        self._clips_by_id[clip_id] = updated
        self._clips_by_video[clip.video_id] = [
            updated if existing.id == clip_id else existing
            for existing in self._clips_by_video.get(clip.video_id, [])
        ]
        return updated

    async def update_voice_status(
        self,
        *,
        clip_id: UUID,
        org_id: UUID,
        status: ClipVoiceStatus,
        error: str | None = None,
    ) -> Clip | None:
        clip = await self.get(clip_id=clip_id, org_id=org_id)
        if not clip:
            return None
        updates: dict[str, object] = {
            "voice_status": status,
            "voice_error": error,
            "updated_at": datetime.utcnow(),
        }
        if status == ClipVoiceStatus.SYNTHESIZED:
            updates["last_voiced_at"] = datetime.utcnow()
        updated = clip.model_copy(update=updates)
        self._clips_by_id[clip_id] = updated
        self._clips_by_video[clip.video_id] = [
            updated if existing.id == clip_id else existing
            for existing in self._clips_by_video.get(clip.video_id, [])
        ]
        return updated


class SqlAlchemyClipsRepository:
    """Clip repository backed by Postgres via SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_for_video(
        self,
        *,
        org_id: UUID,
        project_id: UUID,
        video_id: UUID,
        clips: list[ClipCreate],
    ) -> list[Clip]:
        await self._session.execute(
            delete(ClipModel).where(
                ClipModel.org_id == org_id,
                ClipModel.project_id == project_id,
                ClipModel.video_id == video_id,
            )
        )
        now = datetime.utcnow()
        models: list[ClipModel] = []
        for clip in clips:
            model = ClipModel(
                org_id=org_id,
                project_id=project_id,
                video_id=video_id,
                start_ms=clip.start_ms,
                end_ms=clip.end_ms,
                title=clip.title,
                description=clip.description,
                confidence=clip.confidence,
                score_components=clip.score_components,
                created_at=now,
                updated_at=now,
            )
            self._session.add(model)
            models.append(model)
        await self._session.flush()
        await self._session.commit()
        return [Clip.model_validate(model) for model in models]

    async def list_for_video(self, *, video_id: UUID, org_id: UUID) -> list[Clip]:
        result = await self._session.execute(
            select(ClipModel)
            .where(
                ClipModel.video_id == video_id,
                ClipModel.org_id == org_id,
            )
            .order_by(ClipModel.created_at.asc())
        )
        return [Clip.model_validate(row) for row in result.scalars().all()]

    async def get(self, *, clip_id: UUID, org_id: UUID) -> Clip | None:
        result = await self._session.execute(
            select(ClipModel).where(
                ClipModel.id == clip_id,
                ClipModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return Clip.model_validate(model)

    async def _get_model(self, clip_id: UUID, org_id: UUID) -> ClipModel | None:
        result = await self._session.execute(
            select(ClipModel).where(
                ClipModel.id == clip_id,
                ClipModel.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_metadata(
        self,
        *,
        clip_id: UUID,
        org_id: UUID,
        title: str | None = None,
        description: str | None = None,
        start_ms: int | None = None,
        end_ms: int | None = None,
    ) -> Clip | None:
        model = await self._get_model(clip_id, org_id)
        if not model:
            return None
        now = datetime.utcnow()
        model.updated_at = now
        if title is not None:
            model.title = title
        if description is not None:
            model.description = description
        if start_ms is not None:
            model.start_ms = start_ms
        if end_ms is not None:
            model.end_ms = end_ms
        await self._session.commit()
        await self._session.refresh(model)
        return Clip.model_validate(model)

    async def update_style_request(
        self,
        *,
        clip_id: UUID,
        org_id: UUID,
        payload: SubtitleStyleRequest,
    ) -> Clip | None:
        model = await self._get_model(clip_id, org_id)
        if not model:
            return None
        style_settings = payload.model_dump(exclude_none=True)
        style_settings.pop("preset", None)
        model.style_status = ClipStyleStatus.STYLE_QUEUED.value
        model.style_preset = payload.preset
        model.style_settings = style_settings or None
        model.style_error = None
        model.updated_at = datetime.utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return Clip.model_validate(model)

    async def update_style_status(
        self,
        *,
        clip_id: UUID,
        org_id: UUID,
        status: ClipStyleStatus,
        error: str | None = None,
    ) -> Clip | None:
        model = await self._get_model(clip_id, org_id)
        if not model:
            return None
        now = datetime.utcnow()
        model.style_status = status.value
        model.updated_at = now
        model.style_error = error
        if status == ClipStyleStatus.STYLED:
            model.last_styled_at = now
        await self._session.commit()
        await self._session.refresh(model)
        return Clip.model_validate(model)

    async def update_voice_request(
        self,
        *,
        clip_id: UUID,
        org_id: UUID,
        payload: ClipVoiceRequest,
    ) -> Clip | None:
        model = await self._get_model(clip_id, org_id)
        if not model:
            return None
        request_settings = payload.model_dump(exclude_none=True)
        language = request_settings.pop("language_code", None)
        voice_name = request_settings.pop("voice", None)
        model.voice_status = ClipVoiceStatus.VOICE_QUEUED.value
        model.voice_language = language or model.voice_language
        model.voice_name = voice_name or model.voice_name
        model.voice_settings = request_settings or None
        model.voice_error = None
        model.updated_at = datetime.utcnow()
        await self._session.commit()
        await self._session.refresh(model)
        return Clip.model_validate(model)

    async def update_voice_status(
        self,
        *,
        clip_id: UUID,
        org_id: UUID,
        status: ClipVoiceStatus,
        error: str | None = None,
    ) -> Clip | None:
        model = await self._get_model(clip_id, org_id)
        if not model:
            return None
        now = datetime.utcnow()
        model.voice_status = status.value
        model.voice_error = error
        model.updated_at = now
        if status == ClipVoiceStatus.SYNTHESIZED:
            model.last_voiced_at = now
        await self._session.commit()
        await self._session.refresh(model)
        return Clip.model_validate(model)
