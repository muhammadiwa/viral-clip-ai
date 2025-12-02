"""
Progress Tracker for Worker Jobs.

Provides real-time progress updates with:
- Percentage progress
- Current step description
- Step number / total steps
- Estimated time remaining (optional)
"""
from typing import Callable, Optional
from dataclasses import dataclass
import time

import structlog
from sqlalchemy.orm import Session

from app.models import ProcessingJob

logger = structlog.get_logger()


@dataclass
class ProgressStep:
    """Defines a step in the processing pipeline."""
    name: str
    description: str
    weight: float  # Weight of this step in overall progress (0-1)


class ProgressTracker:
    """
    Tracks and updates job progress in real-time.
    
    Usage:
        tracker = ProgressTracker(db, job, [
            ProgressStep("download", "Downloading video", 0.1),
            ProgressStep("transcribe", "Transcribing audio", 0.4),
            ProgressStep("analyze", "Analyzing content", 0.3),
            ProgressStep("generate", "Generating clips", 0.2),
        ])
        
        tracker.start_step("download")
        tracker.update(0.5, "Downloaded 50%")
        tracker.complete_step()
        
        tracker.start_step("transcribe")
        for i, chunk in enumerate(chunks):
            tracker.update(i / len(chunks), f"Transcribing chunk {i+1}/{len(chunks)}")
        tracker.complete_step()
    """
    
    def __init__(
        self,
        db: Session,
        job: ProcessingJob,
        steps: list[ProgressStep],
    ):
        self.db = db
        self.job = job
        self.steps = steps
        self.total_steps = len(steps)
        self.current_step_idx = -1
        self.step_start_time: Optional[float] = None
        
        # Calculate cumulative weights
        total_weight = sum(s.weight for s in steps)
        self.normalized_weights = [s.weight / total_weight for s in steps]
        self.cumulative_weights = []
        cumsum = 0.0
        for w in self.normalized_weights:
            self.cumulative_weights.append(cumsum)
            cumsum += w
        
        # Initialize job
        self.job.total_steps = self.total_steps
        self.job.current_step_num = 0
        self.job.progress = 0.0
        self.job.progress_message = "Starting..."
        self.db.commit()
    
    def start_step(self, step_name: str, message: Optional[str] = None):
        """Start a new step."""
        # Find step index
        for i, step in enumerate(self.steps):
            if step.name == step_name:
                self.current_step_idx = i
                break
        else:
            logger.warning("progress.unknown_step", step_name=step_name)
            return
        
        self.step_start_time = time.time()
        step = self.steps[self.current_step_idx]
        
        self.job.current_step = step_name
        self.job.current_step_num = self.current_step_idx + 1
        self.job.progress_message = message or step.description
        
        # Calculate progress at start of this step
        base_progress = self.cumulative_weights[self.current_step_idx] * 100
        self.job.progress = base_progress
        
        self.db.commit()
        
        logger.info(
            "progress.step_start",
            job_id=self.job.id,
            step=step_name,
            step_num=self.current_step_idx + 1,
            total_steps=self.total_steps,
            progress=base_progress,
        )
    
    def update(
        self,
        step_progress: float,
        message: Optional[str] = None,
        sub_step: Optional[str] = None,
    ):
        """
        Update progress within current step.
        
        Args:
            step_progress: Progress within this step (0.0 to 1.0)
            message: Optional message to display
            sub_step: Optional sub-step description (e.g., "chunk 3/10")
        """
        if self.current_step_idx < 0:
            return
        
        step_progress = max(0.0, min(1.0, step_progress))
        
        # Calculate overall progress
        base_progress = self.cumulative_weights[self.current_step_idx]
        step_weight = self.normalized_weights[self.current_step_idx]
        overall_progress = (base_progress + step_progress * step_weight) * 100
        
        self.job.progress = overall_progress
        
        if message:
            if sub_step:
                self.job.progress_message = f"{message} ({sub_step})"
            else:
                self.job.progress_message = message
        elif sub_step:
            step = self.steps[self.current_step_idx]
            self.job.progress_message = f"{step.description} ({sub_step})"
        
        self.db.commit()
    
    def complete_step(self, message: Optional[str] = None):
        """Mark current step as complete."""
        if self.current_step_idx < 0:
            return
        
        step = self.steps[self.current_step_idx]
        elapsed = time.time() - self.step_start_time if self.step_start_time else 0
        
        # Progress at end of this step
        if self.current_step_idx < len(self.cumulative_weights) - 1:
            end_progress = self.cumulative_weights[self.current_step_idx + 1] * 100
        else:
            end_progress = 100.0
        
        self.job.progress = end_progress
        self.job.progress_message = message or f"{step.description} - Done"
        self.db.commit()
        
        logger.info(
            "progress.step_complete",
            job_id=self.job.id,
            step=step.name,
            elapsed_sec=round(elapsed, 1),
            progress=end_progress,
        )
    
    def set_message(self, message: str):
        """Update just the message without changing progress."""
        self.job.progress_message = message
        self.db.commit()
    
    def complete(self, message: str = "Completed"):
        """Mark job as complete."""
        self.job.progress = 100.0
        self.job.progress_message = message
        self.job.current_step = "done"
        self.db.commit()
        
        logger.info("progress.job_complete", job_id=self.job.id)
    
    def fail(self, error: str):
        """Mark job as failed."""
        self.job.progress_message = f"Failed: {error[:100]}"
        self.db.commit()


def create_transcription_tracker(db: Session, job: ProcessingJob) -> ProgressTracker:
    """Create tracker for transcription_and_segmentation job."""
    return ProgressTracker(db, job, [
        ProgressStep("init", "Initializing", 0.02),
        ProgressStep("extract_audio", "Extracting audio", 0.08),
        ProgressStep("transcribe", "Transcribing audio with AI", 0.45),
        ProgressStep("audio_analysis", "Analyzing audio patterns", 0.15),
        ProgressStep("visual_analysis", "Analyzing visual content", 0.15),
        ProgressStep("segmentation", "Detecting scenes", 0.10),
        ProgressStep("finalize", "Finalizing analysis", 0.05),
    ])


def create_clip_generation_tracker(db: Session, job: ProcessingJob) -> ProgressTracker:
    """Create tracker for clip_generation job."""
    return ProgressTracker(db, job, [
        ProgressStep("init", "Initializing", 0.02),
        ProgressStep("analyze", "Analyzing video content", 0.20),
        ProgressStep("find_peaks", "Finding engagement peaks", 0.10),
        ProgressStep("llm_select", "AI selecting best clips", 0.15),
        ProgressStep("score_clips", "Scoring clips", 0.08),
        ProgressStep("generate_subtitles", "Generating subtitles", 0.05),
        ProgressStep("render_clips", "Rendering clip videos", 0.35),
        ProgressStep("finalize", "Finalizing", 0.05),
    ])


def create_export_tracker(db: Session, job: ProcessingJob) -> ProgressTracker:
    """Create tracker for export_clip job."""
    return ProgressTracker(db, job, [
        ProgressStep("init", "Preparing export", 0.05),
        ProgressStep("prepare_audio", "Preparing audio", 0.15),
        ProgressStep("prepare_subtitles", "Preparing subtitles", 0.10),
        ProgressStep("render", "Rendering video", 0.60),
        ProgressStep("finalize", "Finalizing export", 0.10),
    ])
