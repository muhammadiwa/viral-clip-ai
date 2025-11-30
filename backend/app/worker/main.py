import time
import traceback
from pathlib import Path

import structlog
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import ProcessingJob, ClipBatch, ExportJob
from app.services import transcription, segmentation, virality, subtitles, exporting, utils

logger = structlog.get_logger()
settings = get_settings()


def _complete_job(db: Session, job: ProcessingJob, summary: dict | None = None):
    job.status = "completed"
    job.progress = 100.0
    if summary:
        job.result_summary = summary
    db.commit()


def _fail_job(db: Session, job: ProcessingJob, error: str):
    job.status = "failed"
    job.error_message = error
    if job.video:
        job.video.status = "failed"
    db.commit()


def _process_transcription_and_segmentation(db: Session, job: ProcessingJob):
    video = job.video
    if not video:
        raise ValueError("Video not found for job")
    video.status = "processing"
    db.commit()

    segments = transcription.transcribe_video(db, video)
    job.progress = 40.0
    job.result_summary = {"transcript_segments": len(segments)}
    db.commit()

    scenes = segmentation.detect_scenes(db, video)
    job.progress = 80.0
    summary = job.result_summary or {}
    summary["scene_segments"] = len(scenes)
    job.result_summary = summary
    video.status = "analyzed"
    db.commit()
    _complete_job(db, job)


def _process_clip_generation(db: Session, job: ProcessingJob):
    payload = job.payload or {}
    batch_id = payload.get("clip_batch_id")
    batch = db.query(ClipBatch).filter(ClipBatch.id == batch_id).first()
    if not batch:
        raise ValueError("Clip batch not found")

    clips, clip_meta = virality.generate_clips_for_batch(db, batch, payload)
    for clip in clips:
        subtitles.generate_for_clip(db, clip)
    
    job.progress = 60.0
    db.commit()

    # Auto-generate video clip files
    aspect_ratio = payload.get("aspect_ratio", "9:16")
    video_path = batch.video.file_path
    clips_rendered = 0
    
    if video_path:
        for idx, clip in enumerate(clips):
            clip_dir = utils.ensure_dir(Path(settings.media_root) / "clips" / str(clip.id))
            output_path = clip_dir / f"preview_{clip.id}.mp4"
            
            logger.info(
                "clip.render_start",
                clip_id=clip.id,
                clip_index=idx + 1,
                total_clips=len(clips),
            )
            
            success = utils.render_clip_preview(
                source_path=video_path,
                output_path=str(output_path),
                start_sec=clip.start_time_sec,
                duration_sec=clip.duration_sec,
                aspect_ratio=aspect_ratio,
            )
            
            if success:
                try:
                    relative = output_path.relative_to(Path(settings.media_root))
                    clip.video_path = f"{settings.media_base_url}/{relative.as_posix()}"
                except Exception:
                    clip.video_path = str(output_path)
                clip.status = "ready"
                clips_rendered += 1
                logger.info("clip.render_done", clip_id=clip.id, video_path=clip.video_path)
            else:
                logger.warning("clip.render_failed", clip_id=clip.id)
            
            # Update progress
            progress = 60.0 + (30.0 * (idx + 1) / len(clips))
            job.progress = progress
            db.commit()

    batch.video.status = "ready"
    job.progress = 95.0
    db.commit()
    
    summary = {"clips_created": len(clips), "clips_rendered": clips_rendered, **clip_meta}
    _complete_job(db, job, summary=summary)


def _process_export(db: Session, job: ProcessingJob):
    payload = job.payload or {}
    export_id = payload.get("export_id")
    export = db.query(ExportJob).filter(ExportJob.id == export_id).first()
    if not export:
        raise ValueError("Export not found")
    export.status = "running"
    export.progress = 10.0
    job.progress = 20.0
    db.commit()

    max_retries = settings.export_retries
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("export.attempt", attempt=attempt, max_retries=max_retries, export_id=export_id)
            exporting.render_export(
                db=db,
                export_job=export,
                use_brand_kit=payload.get("use_brand_kit", True),
                use_ai_dub=payload.get("use_ai_dub", True),
            )
            if export.status == "completed":
                logger.info("export.success", export_id=export_id, attempt=attempt)
                last_error = None
                break
            elif export.status == "failed":
                raise RuntimeError(export.error_message or "Export failed")
        except Exception as exc:
            last_error = exc
            logger.warning("export.retry_failed", attempt=attempt, error=str(exc))
            if attempt < max_retries:
                export.status = "running"
                export.error_message = None
                db.commit()
                time.sleep(settings.retry_delay_seconds)
            else:
                export.status = "failed"
                export.error_message = f"Failed after {max_retries} attempts: {str(exc)}"
                db.commit()

    job.progress = 90.0
    export.progress = 90.0 if export.status != "failed" else export.progress
    db.commit()

    if last_error and export.status == "failed":
        raise last_error

    _complete_job(db, job, summary={"output_path": export.output_path})


def process_job(db: Session, job: ProcessingJob):
    logger.info("worker.job_start", job_id=job.id, job_type=job.job_type)
    if job.job_type == "transcription_and_segmentation":
        _process_transcription_and_segmentation(db, job)
    elif job.job_type == "clip_generation":
        _process_clip_generation(db, job)
    elif job.job_type == "export_clip":
        _process_export(db, job)
    else:
        raise ValueError(f"Unknown job type: {job.job_type}")
    logger.info("worker.job_done", job_id=job.id, status=job.status)


def main_loop():
    logger.info("worker.start", msg="worker loop started")
    idle_ticks = 0
    while True:
        db = SessionLocal()
        job: ProcessingJob | None = None
        try:
            job = (
                db.query(ProcessingJob)
                .filter(ProcessingJob.status == "queued")
                .order_by(ProcessingJob.created_at.asc())
                .first()
            )
            if not job:
                idle_ticks += 1
                if idle_ticks % 20 == 0:
                    logger.info("worker.idle", msg="no queued jobs found")
                time.sleep(3)
                continue
            idle_ticks = 0
            job.status = "running"
            job.progress = 1.0
            db.commit()
            process_job(db, job)
        except Exception as e:
            logger.error("worker.job_error", error=str(e), traceback=traceback.format_exc())
            if job is not None:
                _fail_job(db, job, error=str(e))
        finally:
            db.close()


if __name__ == "__main__":
    main_loop()
