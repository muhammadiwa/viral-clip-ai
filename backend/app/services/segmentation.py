from typing import List

import structlog
from sqlalchemy.orm import Session

from app.models import VideoSource, SceneSegment
from app.services import utils

logger = structlog.get_logger()


def _parse_silence(stderr: str, duration: float) -> List[SceneSegment]:
    silences = []
    for line in stderr.splitlines():
        if "silence_start" in line:
            try:
                silences.append(("start", float(line.strip().split("silence_start:")[1].strip())))
            except Exception:
                continue
        if "silence_end" in line:
            parts = line.strip().split("silence_end:")
            if len(parts) > 1:
                try:
                    ts = float(parts[1].split("|")[0].strip())
                    silences.append(("end", ts))
                except Exception:
                    continue
    # Build segments between silence markers.
    silences_sorted = sorted([t for t in silences if isinstance(t[1], float)], key=lambda x: x[1])
    segments = []
    last = 0.0
    for typ, ts in silences_sorted:
        if typ == "start" and ts > last:
            segments.append((last, ts))
        if typ == "end":
            last = ts
    if last < duration:
        segments.append((last, duration))
    return [
        SceneSegment(
            video_source_id=None,  # set later
            start_time_sec=start,
            end_time_sec=end,
            score_energy=1.0,
            score_change=0.5,
        )
        for start, end in segments
        if end - start > 1.0
    ]


def detect_scenes(db: Session, video: VideoSource) -> List[SceneSegment]:
    """
    Run ffmpeg silencedetect to approximate scene/energy changes.
    """
    if not video.file_path:
        raise ValueError("Video file_path missing for scene detection")
    logger.info("segmentation.start", video_id=video.id)
    duration = video.duration_seconds or utils.probe_duration(video.file_path) or 0.0
    db.query(SceneSegment).filter(SceneSegment.video_source_id == video.id).delete()

    cmd = [
        utils.settings.ffmpeg_bin,
        "-i",
        video.file_path,
        "-af",
        "silencedetect=n=-30dB:d=0.6",
        "-f",
        "null",
        "-",
    ]
    code, _, err = utils.run_cmd(cmd)
    if code != 0:
        logger.warning("segmentation.ffmpeg_failed", error=err)
        scenes = []
    else:
        scenes = _parse_silence(err, duration)

    if not scenes:
        # fallback evenly sized segments
        window = max(duration / 5, 15.0) if duration else 30.0
        t = 0.0
        scenes = []
        while t < (duration or window * 3):
            start = t
            end = min(duration or t + window, t + window)
            scenes.append(
                SceneSegment(
                    video_source_id=None,
                    start_time_sec=start,
                    end_time_sec=end,
                    score_energy=0.8,
                    score_change=0.5,
                )
            )
            t = end

    for seg in scenes:
        seg.video_source_id = video.id
        db.add(seg)
    db.commit()
    logger.info("segmentation.done", video_id=video.id, scenes=len(scenes))
    return scenes
