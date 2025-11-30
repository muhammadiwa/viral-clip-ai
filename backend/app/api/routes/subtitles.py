from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.models import Clip, SubtitleSegment, User
from app.schemas import SubtitleSegmentOut
from app.services import subtitles as subtitle_service

router = APIRouter(prefix="/viral-clip", tags=["subtitles"])


class TranslateRequest(BaseModel):
    target_language: str


@router.get("/clips/{clip_id}/subtitles", response_model=list[SubtitleSegmentOut])
def list_subtitles(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip or clip.batch.video.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Clip not found")
    return (
        db.query(SubtitleSegment)
        .filter(SubtitleSegment.clip_id == clip.id)
        .order_by(SubtitleSegment.start_time_sec)
        .all()
    )


@router.post("/clips/{clip_id}/subtitles/translate", response_model=list[SubtitleSegmentOut])
def translate_subtitles(
    clip_id: int,
    request: TranslateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip or clip.batch.video.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Clip not found")

    translated = subtitle_service.translate_subtitles(db=db, clip=clip, target_language=request.target_language)
    return translated


@router.get("/clips/{clip_id}/subtitles.srt", response_class=PlainTextResponse)
def download_srt(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip or clip.batch.video.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Clip not found")
    srt_content = subtitle_service.subtitle_srt_text(db, clip)
    return PlainTextResponse(content=srt_content, media_type="text/plain; charset=utf-8")
