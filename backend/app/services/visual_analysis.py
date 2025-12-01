"""
Visual Analysis Service for Viral Clip Detection.

Analyzes video visuals to detect:
- Motion/activity levels
- Scene changes/cuts
- Face presence (using frame brightness patterns as proxy)
- Visual interest score
"""
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog

from app.core.config import get_settings
from app.services.utils import run_cmd, ensure_dir

logger = structlog.get_logger()
settings = get_settings()


def detect_scene_changes(video_path: str) -> List[Dict[str, Any]]:
    """
    Detect scene changes/cuts using ffmpeg's scene detection filter.
    
    Returns list of scene boundaries with:
    - time: timestamp of scene change
    - score: scene change confidence (0-1)
    """
    logger.info("visual_analysis.scene_detect_start", video_path=video_path)
    
    # Use scdet filter for scene detection
    cmd = [
        settings.ffmpeg_bin,
        "-i", video_path,
        "-vf", "select='gt(scene,0.3)',showinfo",
        "-f", "null",
        "-"
    ]
    
    code, _, stderr = run_cmd(cmd)
    if code != 0:
        logger.warning("visual_analysis.scene_detect_failed", error=stderr[:500])
        return []
    
    scenes = []
    # Parse showinfo output for timestamps
    time_pattern = re.compile(r"pts_time:([\d.]+)")
    
    for line in stderr.split("\n"):
        if "pts_time" in line:
            match = time_pattern.search(line)
            if match:
                time = float(match.group(1))
                scenes.append({
                    "time": time,
                    "type": "scene_cut",
                    "score": 0.8,
                })
    
    logger.info("visual_analysis.scene_detect_done", scenes_found=len(scenes))
    return scenes


def analyze_motion(
    video_path: str,
    sample_interval: float = 1.0,
    duration: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Analyze motion/activity levels throughout the video.
    
    Uses frame difference analysis via ffmpeg.
    
    Returns per-interval:
    - time: timestamp
    - motion_score: 0-1 (higher = more motion)
    """
    logger.info("visual_analysis.motion_start", video_path=video_path)
    
    # Use blend filter to detect frame differences
    # This measures how much each frame differs from the previous
    cmd = [
        settings.ffmpeg_bin,
        "-i", video_path,
        "-vf", f"select='not(mod(n,{int(30 * sample_interval)}))',tblend=all_mode=difference,blackframe=amount=98:threshold=32",
        "-f", "null",
        "-"
    ]
    
    code, _, stderr = run_cmd(cmd)
    
    # Parse blackframe output - frames that are "black" after difference = no motion
    # If the frame is NOT black after difference = motion detected
    motion_data = _parse_motion_from_blend(stderr, sample_interval, duration)
    
    if not motion_data and duration:
        # Fallback: assume moderate motion throughout
        motion_data = []
        t = 0.0
        while t < duration:
            motion_data.append({
                "time": t,
                "motion_score": 0.5,
            })
            t += sample_interval
    
    logger.info("visual_analysis.motion_done", samples=len(motion_data))
    return motion_data


def _parse_motion_from_blend(
    stderr: str,
    interval: float,
    duration: Optional[float],
) -> List[Dict[str, Any]]:
    """Parse motion data from ffmpeg blend filter output."""
    results = []
    
    # Look for frame information
    frame_pattern = re.compile(r"frame=\s*(\d+)")
    blackframe_pattern = re.compile(r"blackframe:(\d+)")
    
    # Count frames and black frames
    total_frames = 0
    black_frames = set()
    
    for line in stderr.split("\n"):
        frame_match = frame_pattern.search(line)
        if frame_match:
            total_frames = int(frame_match.group(1))
        
        black_match = blackframe_pattern.search(line)
        if black_match:
            black_frames.add(int(black_match.group(1)))
    
    # Generate timeline based on duration
    if duration:
        t = 0.0
        frame_idx = 0
        samples_per_second = 30 / (30 * interval)  # Approximate
        
        while t < duration:
            # Check if corresponding frame range was mostly black (no motion)
            frame_start = int(frame_idx)
            frame_end = int(frame_idx + samples_per_second)
            
            black_count = sum(1 for f in range(frame_start, frame_end) if f in black_frames)
            total_in_range = max(1, frame_end - frame_start)
            
            # Motion score is inverse of black frame ratio
            motion_score = 1.0 - (black_count / total_in_range)
            motion_score = max(0.1, min(1.0, motion_score))
            
            results.append({
                "time": t,
                "motion_score": motion_score,
            })
            
            t += interval
            frame_idx += samples_per_second
    
    return results


def analyze_brightness(
    video_path: str,
    sample_interval: float = 1.0,
    duration: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Analyze frame brightness throughout the video.
    
    High variance in brightness can indicate:
    - Scene changes
    - Visual interest
    - Face close-ups (often brighter due to lighting)
    """
    logger.info("visual_analysis.brightness_start", video_path=video_path)
    
    # Use signalstats filter for brightness analysis
    fps = int(1 / sample_interval)
    cmd = [
        settings.ffmpeg_bin,
        "-i", video_path,
        "-vf", f"fps={fps},signalstats=stat=brng",
        "-f", "null",
        "-"
    ]
    
    code, _, stderr = run_cmd(cmd)
    
    brightness_data = []
    brng_pattern = re.compile(r"YAVG:([\d.]+)")
    
    time = 0.0
    for line in stderr.split("\n"):
        match = brng_pattern.search(line)
        if match:
            brightness = float(match.group(1)) / 255.0  # Normalize to 0-1
            brightness_data.append({
                "time": time,
                "brightness": brightness,
            })
            time += sample_interval
    
    if not brightness_data and duration:
        # Fallback
        t = 0.0
        while t < duration:
            brightness_data.append({
                "time": t,
                "brightness": 0.5,
            })
            t += sample_interval
    
    logger.info("visual_analysis.brightness_done", samples=len(brightness_data))
    return brightness_data


def estimate_face_presence(
    brightness_data: List[Dict[str, Any]],
    motion_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Estimate face/person presence based on visual patterns.
    
    Heuristics:
    - Moderate brightness (face lighting)
    - Low-medium motion (talking head)
    - Consistent patterns (person speaking)
    
    Note: This is a heuristic approximation. For accurate face detection,
    use a proper CV library or API.
    """
    results = []
    
    # Create time-indexed lookup
    motion_lookup = {m["time"]: m["motion_score"] for m in motion_data}
    
    for b in brightness_data:
        time = b["time"]
        brightness = b["brightness"]
        motion = motion_lookup.get(time, 0.5)
        
        # Face presence heuristic:
        # - Brightness between 0.3-0.7 (typical face lighting)
        # - Motion between 0.2-0.6 (talking, not static, not chaotic)
        brightness_score = 1.0 - abs(brightness - 0.5) * 2  # Peak at 0.5
        motion_score = 1.0 - abs(motion - 0.4) * 2  # Peak at 0.4
        
        face_likelihood = (brightness_score * 0.4 + motion_score * 0.6)
        face_likelihood = max(0, min(1, face_likelihood))
        
        results.append({
            "time": time,
            "face_likelihood": face_likelihood,
            "brightness": brightness,
            "motion": motion,
        })
    
    return results


def calculate_visual_timeline(
    video_path: str,
    duration: float,
    sample_interval: float = 1.0,
) -> List[Dict[str, Any]]:
    """
    Calculate comprehensive visual timeline for the entire video.
    
    Returns per-interval:
    - time: timestamp
    - motion_score: 0-1
    - brightness: 0-1
    - visual_interest: combined score 0-1
    - face_likelihood: estimated 0-1
    """
    logger.info("visual_analysis.timeline_start", video_path=video_path, duration=duration)
    
    # Get scene cuts
    scene_cuts = detect_scene_changes(video_path)
    scene_cut_times = set(int(s["time"]) for s in scene_cuts)
    
    # Get motion data
    motion_data = analyze_motion(video_path, sample_interval, duration)
    
    # Get brightness data
    brightness_data = analyze_brightness(video_path, sample_interval, duration)
    
    # Estimate face presence
    face_data = estimate_face_presence(brightness_data, motion_data)
    
    # Combine into timeline
    timeline = []
    motion_lookup = {int(m["time"]): m for m in motion_data}
    brightness_lookup = {int(b["time"]): b for b in brightness_data}
    face_lookup = {int(f["time"]): f for f in face_data}
    
    t = 0.0
    while t < duration:
        t_int = int(t)
        
        motion = motion_lookup.get(t_int, {}).get("motion_score", 0.5)
        brightness = brightness_lookup.get(t_int, {}).get("brightness", 0.5)
        face = face_lookup.get(t_int, {}).get("face_likelihood", 0.5)
        
        # Check if near scene cut (interesting moment)
        near_scene_cut = any(abs(t_int - sc) <= 2 for sc in scene_cut_times)
        scene_cut_boost = 0.2 if near_scene_cut else 0
        
        # Visual interest combines motion, brightness variance, and face presence
        visual_interest = (
            motion * 0.3 +
            face * 0.4 +
            brightness * 0.1 +
            scene_cut_boost +
            0.2  # Base score
        )
        visual_interest = min(1.0, visual_interest)
        
        timeline.append({
            "time": t,
            "motion_score": motion,
            "brightness": brightness,
            "face_likelihood": face,
            "visual_interest": visual_interest,
            "has_scene_cut": near_scene_cut,
        })
        
        t += sample_interval
    
    logger.info("visual_analysis.timeline_done", samples=len(timeline))
    return timeline


def find_visual_peaks(
    timeline: List[Dict[str, Any]],
    min_duration: float = 5.0,
    top_n: int = 20,
) -> List[Dict[str, Any]]:
    """
    Find peak visual interest moments.
    
    Returns top N peaks with:
    - start_time, end_time
    - peak_score
    - reason
    """
    if not timeline:
        return []
    
    peaks = []
    i = 0
    threshold = 0.5
    
    while i < len(timeline):
        if timeline[i]["visual_interest"] >= threshold:
            start_idx = i
            peak_score = timeline[i]["visual_interest"]
            
            # Extend while score stays reasonable
            while i < len(timeline) and timeline[i]["visual_interest"] >= threshold * 0.7:
                peak_score = max(peak_score, timeline[i]["visual_interest"])
                i += 1
            
            end_idx = i
            if end_idx > start_idx:
                duration = timeline[end_idx - 1]["time"] - timeline[start_idx]["time"]
                
                if duration >= min_duration:
                    # Determine reason
                    avg_motion = sum(t["motion_score"] for t in timeline[start_idx:end_idx]) / (end_idx - start_idx)
                    avg_face = sum(t["face_likelihood"] for t in timeline[start_idx:end_idx]) / (end_idx - start_idx)
                    has_cuts = any(t["has_scene_cut"] for t in timeline[start_idx:end_idx])
                    
                    if has_cuts:
                        reason = "dynamic_editing"
                    elif avg_face > 0.6:
                        reason = "face_focused"
                    elif avg_motion > 0.6:
                        reason = "high_action"
                    else:
                        reason = "visually_engaging"
                    
                    peaks.append({
                        "start_time": timeline[start_idx]["time"],
                        "end_time": timeline[end_idx - 1]["time"],
                        "duration": duration,
                        "peak_score": peak_score,
                        "reason": reason,
                        "avg_motion": avg_motion,
                        "avg_face_likelihood": avg_face,
                    })
        else:
            i += 1
    
    peaks.sort(key=lambda x: x["peak_score"], reverse=True)
    return peaks[:top_n]
