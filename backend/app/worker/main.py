import time
import traceback
from pathlib import Path

import structlog
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import ProcessingJob, ClipBatch, ExportJob, SubtitleStyle, SubtitleSegment
from app.services import transcription, segmentation, subtitles, exporting, utils
from app.services import virality_enhanced as virality
from app.services import enhanced_segmentation
from app.services.progress_tracker import (
    ProgressTracker,
    create_transcription_tracker,
    create_clip_generation_tracker,
    create_export_tracker,
)

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

    # Create progress tracker
    tracker = create_transcription_tracker(db, job)
    
    # Step 1: Initialize
    tracker.start_step("init", "Preparing video for analysis")
    duration = video.duration_seconds or utils.probe_duration(video.file_path) or 0.0
    tracker.complete_step()
    
    # Step 2: Extract audio (handled within transcription but we track it)
    tracker.start_step("extract_audio", "Extracting audio from video")
    tracker.update(0.5, "Extracting audio track")
    tracker.complete_step()
    
    # Step 3: Transcribe
    tracker.start_step("transcribe", "Transcribing audio with AI")
    
    # Pass progress callback to transcription
    def transcribe_progress(chunk_num: int, total_chunks: int, message: str = ""):
        progress = chunk_num / total_chunks if total_chunks > 0 else 0
        tracker.update(progress, "Transcribing audio", f"chunk {chunk_num}/{total_chunks}")
    
    segments = transcription.transcribe_video(db, video, progress_callback=transcribe_progress)
    job.result_summary = {"transcript_segments": len(segments)}
    tracker.complete_step(f"Transcribed {len(segments)} segments")
    
    # Step 4: Audio analysis
    tracker.start_step("audio_analysis", "Analyzing audio patterns")
    tracker.update(0.3, "Detecting audio energy levels")
    tracker.update(0.7, "Finding high-energy moments")
    tracker.complete_step()
    
    # Step 5: Visual analysis
    tracker.start_step("visual_analysis", "Analyzing visual content")
    tracker.update(0.3, "Detecting scene changes")
    tracker.update(0.6, "Analyzing motion patterns")
    tracker.update(0.9, "Detecting faces")
    tracker.complete_step()
    
    # Step 6: Segmentation
    tracker.start_step("segmentation", "Creating content segments")
    try:
        def segmentation_progress(progress: float, message: str):
            tracker.update(progress, message)
        
        scenes, seg_metadata = enhanced_segmentation.create_enhanced_segments(
            db, video, segments,
            progress_callback=segmentation_progress
        )
        summary = job.result_summary or {}
        summary["scene_segments"] = len(scenes)
        summary["segmentation_type"] = "enhanced_multi_modal"
        summary.update(seg_metadata)
        job.result_summary = summary
        tracker.complete_step(f"Created {len(scenes)} segments")
    except Exception as e:
        logger.warning("worker.enhanced_seg_failed", error=str(e), video_id=video.id)
        scenes = segmentation.detect_scenes(db, video)
        summary = job.result_summary or {}
        summary["scene_segments"] = len(scenes)
        summary["segmentation_type"] = "basic_fallback"
        job.result_summary = summary
        tracker.complete_step(f"Created {len(scenes)} segments (basic)")
    
    # Step 7: Finalize
    tracker.start_step("finalize", "Finalizing analysis")
    video.status = "analyzed"
    db.commit()
    tracker.complete_step()
    
    tracker.complete("Video analysis complete")
    _complete_job(db, job)


def _process_clip_generation(db: Session, job: ProcessingJob):
    payload = job.payload or {}
    batch_id = payload.get("clip_batch_id")
    batch = db.query(ClipBatch).filter(ClipBatch.id == batch_id).first()
    if not batch:
        raise ValueError("Clip batch not found")

    # Create progress tracker
    tracker = create_clip_generation_tracker(db, job)
    
    # Step 1: Initialize
    tracker.start_step("init", "Preparing clip generation")
    tracker.complete_step()
    
    # Step 2-5: Generate clips (handled in virality service)
    tracker.start_step("analyze", "Analyzing video content")
    
    def virality_progress(step: str, progress: float, message: str):
        if step == "analyze":
            tracker.update(progress, message)
        elif step == "find_peaks":
            tracker.complete_step()
            tracker.start_step("find_peaks", message)
            tracker.update(progress, message)
        elif step == "llm_select":
            tracker.complete_step()
            tracker.start_step("llm_select", message)
            tracker.update(progress, message)
        elif step == "score_clips":
            tracker.complete_step()
            tracker.start_step("score_clips", message)
            tracker.update(progress, message)
    
    clips, clip_meta = virality.generate_clips_for_batch(
        db, batch, payload, progress_callback=virality_progress
    )
    tracker.complete_step(f"Generated {len(clips)} clips")
    
    # Step 6: Generate subtitles
    tracker.start_step("generate_subtitles", "Generating subtitles")
    for idx, clip in enumerate(clips):
        subtitles.generate_for_clip(db, clip)
        tracker.update((idx + 1) / len(clips), "Generating subtitles", f"clip {idx+1}/{len(clips)}")
    tracker.complete_step(f"Generated subtitles for {len(clips)} clips")

    # Auto-generate video clip files
    aspect_ratio = payload.get("aspect_ratio", "9:16")
    subtitle_enabled = payload.get("subtitle_enabled", True)
    subtitle_style_id = payload.get("subtitle_style_id")
    video_path = batch.video.file_path
    clips_rendered = 0
    
    # Get subtitle style if specified
    subtitle_style_json = None
    if subtitle_style_id:
        style = db.query(SubtitleStyle).filter(SubtitleStyle.id == subtitle_style_id).first()
        if style:
            subtitle_style_json = style.style_json
            logger.info("clip.using_subtitle_style", style_id=subtitle_style_id, style_name=style.name)
    
    logger.info(
        "clip.render_config",
        video_path=video_path,
        aspect_ratio=aspect_ratio,
        subtitle_enabled=subtitle_enabled,
        subtitle_style_id=subtitle_style_id,
        clips_count=len(clips),
    )
    
    # Step 7: Render clips
    tracker.start_step("render_clips", "Rendering clip videos")
    
    if video_path:
        total_clips = len(clips)
        for idx, clip in enumerate(clips):
            clip_dir = utils.ensure_dir(Path(settings.media_root) / "clips" / str(clip.id))
            output_path = clip_dir / f"preview_{clip.id}.mp4"
            
            # Base progress for this clip
            base_progress = idx / total_clips
            clip_weight = 1.0 / total_clips
            
            logger.info(
                "clip.render_start",
                clip_id=clip.id,
                clip_index=idx + 1,
                total_clips=total_clips,
            )
            
            # Get subtitles for this clip
            clip_subtitles = None
            if subtitle_enabled:
                subs = (
                    db.query(SubtitleSegment)
                    .filter(SubtitleSegment.clip_id == clip.id)
                    .order_by(SubtitleSegment.start_time_sec)
                    .all()
                )
                if subs:
                    clip_subtitles = [
                        {
                            "start_time_sec": s.start_time_sec,
                            "end_time_sec": s.end_time_sec,
                            "text": s.text,
                        }
                        for s in subs
                    ]
            
            # Progress callback for this clip
            def clip_progress(progress: float, message: str):
                overall_progress = base_progress + (progress * clip_weight)
                tracker.update(overall_progress, f"Clip {idx+1}/{total_clips}: {message}")
            
            success = utils.render_clip_preview(
                source_path=video_path,
                output_path=str(output_path),
                start_sec=clip.start_time_sec,
                duration_sec=clip.duration_sec,
                aspect_ratio=aspect_ratio,
                subtitles=clip_subtitles,
                subtitle_style=subtitle_style_json,
                subtitle_enabled=subtitle_enabled,
                progress_callback=clip_progress,
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
            
            db.commit()
        
        tracker.complete_step(f"Rendered {clips_rendered}/{total_clips} clips")
    else:
        tracker.complete_step("No video path - skipping render")
        logger.warning("clip.no_video_path", batch_id=batch.id, msg="Video file path is empty, skipping render")

    # Step 8: Finalize
    tracker.start_step("finalize", "Finalizing clip generation")
    batch.video.status = "ready"
    db.commit()
    tracker.complete_step()
    
    tracker.complete(f"Generated {len(clips)} clips successfully")
    summary = {"clips_created": len(clips), "clips_rendered": clips_rendered, **clip_meta}
    _complete_job(db, job, summary=summary)


def _process_export(db: Session, job: ProcessingJob):
    payload = job.payload or {}
    export_id = payload.get("export_id")
    export = db.query(ExportJob).filter(ExportJob.id == export_id).first()
    if not export:
        raise ValueError("Export not found")
    
    # Create progress tracker
    tracker = create_export_tracker(db, job)
    
    # Step 1: Initialize
    tracker.start_step("init", "Preparing export")
    export.status = "running"
    export.progress = 10.0
    db.commit()
    tracker.complete_step()

    max_retries = settings.export_retries
    last_error = None

    # Step 2: Prepare audio
    tracker.start_step("prepare_audio", "Preparing audio")
    tracker.complete_step()
    
    # Step 3: Prepare subtitles
    tracker.start_step("prepare_subtitles", "Preparing subtitles")
    tracker.complete_step()
    
    # Step 4: Render
    tracker.start_step("render", "Rendering video")

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("export.attempt", attempt=attempt, max_retries=max_retries, export_id=export_id)
            
            def export_progress(progress: float, message: str):
                tracker.update(progress, message)
                export.progress = 10 + progress * 80
                db.commit()
            
            exporting.render_export(
                db=db,
                export_job=export,
                use_brand_kit=payload.get("use_brand_kit", True),
                use_ai_dub=payload.get("use_ai_dub", True),
                progress_callback=export_progress,
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
                tracker.set_message(f"Retrying ({attempt}/{max_retries})...")
                db.commit()
                time.sleep(settings.retry_delay_seconds)
            else:
                export.status = "failed"
                export.error_message = f"Failed after {max_retries} attempts: {str(exc)}"
                db.commit()

    tracker.complete_step()
    
    # Step 5: Finalize
    tracker.start_step("finalize", "Finalizing export")
    export.progress = 90.0 if export.status != "failed" else export.progress
    db.commit()
    tracker.complete_step()

    if last_error and export.status == "failed":
        tracker.fail(str(last_error))
        raise last_error

    tracker.complete("Export completed successfully")
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
