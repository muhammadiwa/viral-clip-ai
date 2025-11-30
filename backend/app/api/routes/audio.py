from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
import os
import uuid

from app.api.deps import get_db, get_current_user
from app.core.config import get_settings
from app.models import Clip, AudioConfig, User
from app.schemas import AudioConfigUpdate, AudioConfigOut
from app.services import dubbing

settings = get_settings()
router = APIRouter(prefix="/viral-clip", tags=["audio"])


@router.post("/audio/upload-bgm")
async def upload_bgm(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    media_root = settings.media_root
    user_dir = os.path.join(media_root, "audio", "bgm", str(current_user.id))
    os.makedirs(user_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "")[1] or ".mp3"
    path = os.path.join(user_dir, f"{uuid.uuid4().hex}{ext}")
    with open(path, "wb") as f:
        f.write(await file.read())
    return {"path": path}


@router.get("/clips/{clip_id}/audio-config", response_model=AudioConfigOut)
def get_audio_config(
    clip_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip or clip.batch.video.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Clip not found")
    config = clip.audio_config or dubbing.ensure_audio_config(db, clip)
    return config


@router.post("/clips/{clip_id}/audio-config", response_model=AudioConfigOut)
def update_audio_config(
    clip_id: int,
    payload: AudioConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    clip = db.query(Clip).filter(Clip.id == clip_id).first()
    if not clip or clip.batch.video.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Clip not found")
    config = clip.audio_config or dubbing.ensure_audio_config(db, clip)
    for key, value in payload.model_dump().items():
        setattr(config, key if key != "bgm_path" else "bgm_track_id", value)
    db.commit()
    db.refresh(config)
    return config
