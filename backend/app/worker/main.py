import time
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import ProcessingJob


def process_job(db: Session, job: ProcessingJob):
    # TODO: isi pipeline transcription -> segmentation -> virality -> subtitles, dll.
    job.status = "completed"
    job.progress = 100.0
    db.commit()


def main_loop():
    while True:
        db = SessionLocal()
        job = None
        try:
            job = (
                db.query(ProcessingJob)
                .filter(ProcessingJob.status == "queued")
                .order_by(ProcessingJob.created_at.asc())
                .first()
            )
            if not job:
                time.sleep(3)
                continue
            job.status = "running"
            job.progress = 1.0
            db.commit()
            process_job(db, job)
        except Exception as e:
            print("Worker error:", e)
            if job is not None:
                job.status = "failed"
                db.commit()
        finally:
            db.close()


if __name__ == "__main__":
    main_loop()
