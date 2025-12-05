"""
Smart Processing Service for Lazy Processing Flow.

This service implements the smart processing pipeline that:
1. Checks what processing steps are needed for a video
2. Skips steps that have already been completed
3. Always runs clip generation with new settings

Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7
"""
from dataclasses import dataclass
from typing import Callable, Optional

import structlog
from sqlalchemy.orm import Session

from app.models import VideoSource, TranscriptSegment, ClipBatch, ProcessingJob
from app.models.analysis import VideoAnalysis

logger = structlog.get_logger()


@dataclass
class ProcessingStatus:
    """
    Status of processing steps for a video.
    
    Attributes:
        video_id: ID of the video
        is_downloaded: Whether video file is downloaded
        has_transcript: Whether transcript segments exist
        has_analysis: Whether video analysis exists
        needs_download: Computed: not is_downloaded
        needs_transcript: Computed: not has_transcript
        needs_analysis: Computed: not has_analysis
        estimated_time_seconds: Estimated time for remaining steps
    """
    video_id: int
    is_downloaded: bool
    has_transcript: bool
    has_analysis: bool
    
    @property
    def needs_download(self) -> bool:
        """Check if download is needed."""
        return not self.is_downloaded
    
    @property
    def needs_transcript(self) -> bool:
        """Check if transcription is needed."""
        return not self.has_transcript
    
    @property
    def needs_analysis(self) -> bool:
        """Check if analysis is needed."""
        return not self.has_analysis
    
    @property
    def estimated_time_seconds(self) -> int:
        """
        Estimate time for remaining steps.
        
        Rough estimates:
        - Download: 60 seconds (varies by video length and connection)
        - Transcription: 120 seconds (varies by video length)
        - Analysis: 90 seconds (varies by video length)
        - Clip generation: 60 seconds (always runs)
        """
        time = 60  # Base time for clip generation (always runs)
        
        if self.needs_download:
            time += 60
        if self.needs_transcript:
            time += 120
        if self.needs_analysis:
            time += 90
        
        return time
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "video_id": self.video_id,
            "is_downloaded": self.is_downloaded,
            "has_transcript": self.has_transcript,
            "has_analysis": self.has_analysis,
            "needs_download": self.needs_download,
            "needs_transcript": self.needs_transcript,
            "needs_analysis": self.needs_analysis,
            "estimated_time_seconds": self.estimated_time_seconds,
        }



def check_processing_status(db: Session, video: VideoSource) -> ProcessingStatus:
    """
    Check what processing steps are needed for this video.
    
    This function examines the video's current state and determines
    which processing steps have been completed and which are still needed.
    
    Args:
        db: Database session
        video: VideoSource to check
        
    Returns:
        ProcessingStatus with flags indicating what's needed
        
    Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
    """
    # Check if video is downloaded
    is_downloaded = video.is_downloaded and video.file_path is not None
    
    # Check if transcript exists
    transcript_count = db.query(TranscriptSegment).filter(
        TranscriptSegment.video_source_id == video.id
    ).count()
    has_transcript = transcript_count > 0
    
    # Check if analysis exists
    analysis = db.query(VideoAnalysis).filter(
        VideoAnalysis.video_source_id == video.id
    ).first()
    has_analysis = analysis is not None
    
    status = ProcessingStatus(
        video_id=video.id,
        is_downloaded=is_downloaded,
        has_transcript=has_transcript,
        has_analysis=has_analysis,
    )
    
    logger.info(
        "smart_processing.status_checked",
        video_id=video.id,
        is_downloaded=is_downloaded,
        has_transcript=has_transcript,
        has_analysis=has_analysis,
        needs_download=status.needs_download,
        needs_transcript=status.needs_transcript,
        needs_analysis=status.needs_analysis,
    )
    
    return status


ProgressCallback = Callable[[str, float, str], None]


async def run_pipeline(
    db: Session,
    video: VideoSource,
    clip_settings: dict,
    progress_callback: Optional[ProgressCallback] = None,
) -> ClipBatch:
    """
    Run smart processing pipeline, skipping completed steps.
    
    This function orchestrates the full processing pipeline:
    1. Download video (if not downloaded) - Requirements 3.1, 3.2
    2. Transcribe video (if no transcript) - Requirements 3.3, 3.4
    3. Analyze video (if no analysis) - Requirements 3.5, 3.6
    4. Generate clips (always runs) - Requirement 3.7
    
    Args:
        db: Database session
        video: VideoSource to process
        clip_settings: Settings for clip generation (aspect_ratio, etc.)
        progress_callback: Optional callback(step, progress, message)
            - step: Current step name (download, transcribe, analyze, generate)
            - progress: Progress within step (0.0 to 1.0)
            - message: Human-readable status message
            
    Returns:
        ClipBatch with generated clips
        
    Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7
    """
    from app.services.video_ingest import trigger_video_download
    from app.services import transcription, segmentation, virality
    from app.services.sentiment_analysis import analyze_segment
    from app.models.analysis import SegmentAnalysis
    
    def notify(step: str, progress: float, message: str):
        """Helper to call progress callback if provided."""
        if progress_callback:
            progress_callback(step, progress, message)
        logger.info(
            "smart_processing.progress",
            video_id=video.id,
            step=step,
            progress=progress,
            message=message,
        )
    
    # Check current status
    status = check_processing_status(db, video)
    
    # Step 1: Download (if needed)
    # Requirements 3.1, 3.2
    if status.needs_download:
        notify("download", 0.0, "Starting video download...")
        
        def download_progress(percent: float, msg: str):
            notify("download", percent / 100.0, msg)
        
        await trigger_video_download(db, video, progress_callback=download_progress)
        notify("download", 1.0, "Download complete")
    else:
        notify("download", 1.0, "Video already downloaded - skipping")
        logger.info(
            "smart_processing.skip_download",
            video_id=video.id,
            reason="already_downloaded",
        )
    
    # Refresh status after download
    db.refresh(video)
    
    # Step 2: Transcribe (if needed)
    # Requirements 3.3, 3.4
    if status.needs_transcript:
        notify("transcribe", 0.0, "Starting transcription...")
        
        def transcribe_progress(chunk_num: int, total_chunks: int, message: str = ""):
            progress = chunk_num / total_chunks if total_chunks > 0 else 0
            notify("transcribe", progress, f"Transcribing: chunk {chunk_num}/{total_chunks}")
        
        segments = transcription.transcribe_video(
            db, video, progress_callback=transcribe_progress
        )
        notify("transcribe", 1.0, f"Transcription complete - {len(segments)} segments")
    else:
        notify("transcribe", 1.0, "Transcript exists - skipping")
        logger.info(
            "smart_processing.skip_transcribe",
            video_id=video.id,
            reason="transcript_exists",
        )
        # Load existing segments for analysis
        segments = db.query(TranscriptSegment).filter(
            TranscriptSegment.video_source_id == video.id
        ).all()
    
    # Step 3: Analyze (if needed)
    # Requirements 3.5, 3.6
    if status.needs_analysis:
        notify("analyze", 0.0, "Starting video analysis...")
        
        duration = video.duration_seconds or 0.0
        
        def analysis_progress(progress: float, message: str):
            notify("analyze", progress * 0.8, message)  # 80% for main analysis
        
        # Perform comprehensive analysis
        analysis_data = segmentation.analyze_video_comprehensive(
            video.file_path, duration, segments, analysis_progress
        )
        
        # Save analysis to database
        ai_vision_summary = analysis_data.get("ai_vision_summary") or {}
        
        video_analysis = VideoAnalysis(
            video_source_id=video.id,
            analysis_version="v3",
            duration_analyzed=duration,
            avg_audio_energy=analysis_data.get("avg_audio_energy", 0.5),
            avg_visual_interest=analysis_data.get("avg_visual_interest", 0.5),
            avg_engagement=analysis_data.get("avg_engagement", 0.5),
            audio_peaks_count=len(analysis_data.get("audio_peaks", [])),
            visual_peaks_count=len(analysis_data.get("visual_peaks", [])),
            viral_moments_count=len(analysis_data.get("viral_moments", [])),
            audio_timeline_json=analysis_data.get("audio_timeline"),
            visual_timeline_json=analysis_data.get("visual_timeline"),
            combined_timeline_json=analysis_data.get("combined_timeline"),
            audio_peaks_json=analysis_data.get("audio_peaks"),
            visual_peaks_json=analysis_data.get("visual_peaks"),
            engagement_peaks_json=analysis_data.get("viral_moments"),
            ai_vision_enabled=analysis_data.get("ai_vision_enabled", False),
            ai_vision_timeline_json=analysis_data.get("ai_vision_timeline"),
            ai_vision_summary_json=ai_vision_summary,
            ai_viral_segments_json=analysis_data.get("ai_viral_segments"),
            avg_face_count=ai_vision_summary.get("avg_face_count"),
            face_presence_ratio=ai_vision_summary.get("face_presence_ratio"),
            dominant_scene_type=ai_vision_summary.get("dominant_scene_type"),
            emotion_distribution_json=ai_vision_summary.get("emotion_distribution"),
            engagement_indicators_json=ai_vision_summary.get("engagement_indicator_counts"),
        )
        db.add(video_analysis)
        db.commit()
        
        notify("analyze", 0.9, "Saving segment analyses...")
        
        # Save segment analysis for each transcript segment
        for seg in segments:
            existing = db.query(SegmentAnalysis).filter(
                SegmentAnalysis.transcript_segment_id == seg.id
            ).first()
            if not existing:
                analysis = analyze_segment(seg)
                segment_analysis = SegmentAnalysis(
                    transcript_segment_id=seg.id,
                    sentiment_score=analysis["sentiment"]["sentiment"],
                    sentiment_intensity=analysis["sentiment"]["intensity"],
                    emotion=analysis["sentiment"]["emotion"],
                    hook_word_count=analysis["hooks"]["total_count"],
                    hook_words_found=analysis["hooks"]["found_words"],
                    hook_score=analysis["hooks"]["hook_score"],
                    has_question=analysis["questions"]["has_question"],
                    has_cta=analysis["cta"]["has_cta"],
                    viral_potential=analysis["viral_potential"],
                )
                db.add(segment_analysis)
        db.commit()
        
        notify("analyze", 1.0, "Analysis complete")
    else:
        notify("analyze", 1.0, "Analysis exists - skipping")
        logger.info(
            "smart_processing.skip_analysis",
            video_id=video.id,
            reason="analysis_exists",
        )
    
    # Step 4: Generate clips (always runs)
    # Requirement 3.7
    notify("generate", 0.0, "Starting clip generation...")
    
    # Create clip batch
    clip_batch = ClipBatch(
        video_source_id=video.id,
        config_json=clip_settings,
        status="processing",
    )
    db.add(clip_batch)
    db.commit()
    db.refresh(clip_batch)
    
    # Create processing job for clip generation
    job = ProcessingJob(
        video_source_id=video.id,
        job_type="clip_generation",
        payload={
            "clip_batch_id": clip_batch.id,
            **clip_settings,
        },
        status="queued",
    )
    db.add(job)
    db.commit()
    
    notify("generate", 0.1, "Clip generation job queued")
    
    logger.info(
        "smart_processing.pipeline_complete",
        video_id=video.id,
        clip_batch_id=clip_batch.id,
        job_id=job.id,
        skipped_download=not status.needs_download,
        skipped_transcribe=not status.needs_transcript,
        skipped_analysis=not status.needs_analysis,
    )
    
    return clip_batch
