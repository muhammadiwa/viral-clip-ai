
from workers.start import celery_app

@celery_app.task(name="transcode.process")
def transcode_process(video_key: str) -> dict:
    # TODO: s3_download + ffmpeg HLS
    return {"ok": True, "step": "transcode", "video_key": video_key}
