from __future__ import annotations

from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..domain.transcripts import (
    AlignmentStatus,
    Transcript,
    TranscriptCreate,
    TranscriptSegment,
    TranscriptStatus,
)
from ..models.transcript import TranscriptModel


class TranscriptsRepository(Protocol):
    async def create(self, org_id: UUID, payload: TranscriptCreate) -> Transcript: ...

    async def get(self, transcript_id: UUID, org_id: UUID) -> Transcript | None: ...

    async def list_for_video(self, video_id: UUID, org_id: UUID) -> list[Transcript]: ...

    async def update_transcription(
        self,
        transcript_id: UUID,
        org_id: UUID,
        *,
        status: TranscriptStatus | None = None,
        segments: list[TranscriptSegment] | None = None,
        error: str | None = None,
    ) -> Transcript | None: ...

    async def update_alignment(
        self,
        transcript_id: UUID,
        org_id: UUID,
        *,
        status: AlignmentStatus | None = None,
        segments: list[TranscriptSegment] | None = None,
        error: str | None = None,
    ) -> Transcript | None: ...


class InMemoryTranscriptsRepository:
    """Ephemeral persistence for transcript records."""

    def __init__(self) -> None:
        self._transcripts: dict[UUID, Transcript] = {}

    async def create(self, org_id: UUID, payload: TranscriptCreate) -> Transcript:
        now = datetime.utcnow()
        transcript = Transcript(
            org_id=org_id,
            created_at=now,
            updated_at=now,
            **payload.model_dump(),
        )
        self._transcripts[transcript.id] = transcript
        return transcript

    async def get(self, transcript_id: UUID, org_id: UUID) -> Transcript | None:
        transcript = self._transcripts.get(transcript_id)
        if transcript and transcript.org_id == org_id:
            return transcript
        return None

    async def list_for_video(self, video_id: UUID, org_id: UUID) -> list[Transcript]:
        return [
            transcript
            for transcript in self._transcripts.values()
            if transcript.org_id == org_id and transcript.video_id == video_id
        ]

    async def update_transcription(
        self,
        transcript_id: UUID,
        org_id: UUID,
        *,
        status: TranscriptStatus | None = None,
        segments: list[TranscriptSegment] | None = None,
        error: str | None = None,
    ) -> Transcript | None:
        transcript = self._transcripts.get(transcript_id)
        if transcript is None or transcript.org_id != org_id:
            return None

        updates: dict[str, object] = {"updated_at": datetime.utcnow()}
        if status is not None:
            updates["status"] = status
            if status == TranscriptStatus.COMPLETED:
                updates["last_transcribed_at"] = datetime.utcnow()
        if segments is not None:
            updates["segments"] = segments
        if error is not None:
            updates["transcription_error"] = error

        updated = transcript.model_copy(update=updates)
        self._transcripts[transcript_id] = updated
        return updated


class SqlAlchemyTranscriptsRepository:
    """Transcript repository persisted via SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, org_id: UUID, payload: TranscriptCreate) -> Transcript:
        now = datetime.utcnow()
        model = TranscriptModel(
            org_id=org_id,
            project_id=payload.project_id,
            video_id=payload.video_id,
            language_code=payload.language_code,
            prompt=payload.prompt,
            status=TranscriptStatus.QUEUED.value,
            alignment_status=AlignmentStatus.NOT_REQUESTED.value,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.commit()
        return Transcript.model_validate(model)

    async def get(self, transcript_id: UUID, org_id: UUID) -> Transcript | None:
        result = await self._session.execute(
            select(TranscriptModel).where(
                TranscriptModel.id == transcript_id,
                TranscriptModel.org_id == org_id,
            )
        )
        model = result.scalar_one_or_none()
        if not model:
            return None
        return Transcript.model_validate(model)

    async def list_for_video(self, video_id: UUID, org_id: UUID) -> list[Transcript]:
        result = await self._session.execute(
            select(TranscriptModel)
            .where(
                TranscriptModel.video_id == video_id,
                TranscriptModel.org_id == org_id,
            )
            .order_by(TranscriptModel.created_at.asc())
        )
        return [Transcript.model_validate(row) for row in result.scalars().all()]

    async def _get_model(
        self, transcript_id: UUID, org_id: UUID
    ) -> TranscriptModel | None:
        result = await self._session.execute(
            select(TranscriptModel).where(
                TranscriptModel.id == transcript_id,
                TranscriptModel.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_transcription(
        self,
        transcript_id: UUID,
        org_id: UUID,
        *,
        status: TranscriptStatus | None = None,
        segments: list[TranscriptSegment] | None = None,
        error: str | None = None,
    ) -> Transcript | None:
        model = await self._get_model(transcript_id, org_id)
        if not model:
            return None
        now = datetime.utcnow()
        model.updated_at = now
        if status is not None:
            model.status = status.value
            if status == TranscriptStatus.COMPLETED:
                model.last_transcribed_at = now
        if segments is not None:
            model.segments = [segment.model_dump() for segment in segments]
        if error is not None:
            model.transcription_error = error
        await self._session.commit()
        await self._session.refresh(model)
        return Transcript.model_validate(model)

    async def update_alignment(
        self,
        transcript_id: UUID,
        org_id: UUID,
        *,
        status: AlignmentStatus | None = None,
        segments: list[TranscriptSegment] | None = None,
        error: str | None = None,
    ) -> Transcript | None:
        model = await self._get_model(transcript_id, org_id)
        if not model:
            return None
        now = datetime.utcnow()
        model.updated_at = now
        if status is not None:
            model.alignment_status = status.value
            if status == AlignmentStatus.ALIGNED:
                model.last_aligned_at = now
        if segments is not None:
            model.aligned_segments = [segment.model_dump() for segment in segments]
        if error is not None:
            model.alignment_error = error
        await self._session.commit()
        await self._session.refresh(model)
        return Transcript.model_validate(model)

    async def update_alignment(
        self,
        transcript_id: UUID,
        org_id: UUID,
        *,
        status: AlignmentStatus | None = None,
        segments: list[TranscriptSegment] | None = None,
        error: str | None = None,
    ) -> Transcript | None:
        transcript = self._transcripts.get(transcript_id)
        if transcript is None or transcript.org_id != org_id:
            return None

        updates: dict[str, object] = {"updated_at": datetime.utcnow()}
        if status is not None:
            updates["alignment_status"] = status
            if status == AlignmentStatus.ALIGNED:
                updates["last_aligned_at"] = datetime.utcnow()
        if segments is not None:
            updates["aligned_segments"] = segments
        if error is not None:
            updates["alignment_error"] = error

        updated = transcript.model_copy(update=updates)
        self._transcripts[transcript_id] = updated
        return updated

