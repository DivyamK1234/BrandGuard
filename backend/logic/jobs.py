# BrandGuard - Background Job Queue
# Uses Redis for job status tracking and result storage

import json
import uuid
import asyncio
import logging
import time
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

import redis

from config import get_settings
import telemetry

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    ANALYZING = "analyzing"
    COMPLETE = "complete"
    FAILED = "failed"


class JobQueue:
    """
    Simple job queue using Redis for status tracking.
    
    Jobs are processed in the same process using asyncio.create_task().
    For production, consider using Celery or Cloud Tasks.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[redis.Redis] = None
        self._job_prefix = "job:"
        self._job_ttl = 3600 * 24  # 24 hours
    
    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            # Use URL if available (for Upstash/cloud), otherwise use host/port
            if self.settings.redis_url:
                self._client = redis.from_url(
                    self.settings.redis_url,
                    decode_responses=True,
                    socket_timeout=5.0,
                    socket_connect_timeout=5.0
                )
                logger.info(f"Initialized job queue Redis client from URL")
            else:
                self._client = redis.Redis(
                    host=self.settings.redis_host,
                    port=self.settings.redis_port,
                    decode_responses=True
                )
                logger.info(f"Initialized job queue Redis client: {self.settings.redis_host}")
        return self._client
    
    def create_job(self, audio_url: Optional[str], audio_id: Optional[str] = None) -> str:
        """Create a new job and return job ID."""
        job_id = str(uuid.uuid4())[:12]
        
        job_data = {
            "job_id": job_id,
            "audio_url": audio_url,
            "audio_id": audio_id or f"job_{job_id}",
            "status": JobStatus.PENDING.value,
            "progress": 0,
            "message": "Job created, waiting to start...",
            "result": None,
            "error": None,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        self.client.setex(
            f"{self._job_prefix}{job_id}",
            self._job_ttl,
            json.dumps(job_data)
        )
        
        logger.info(f"Created job {job_id} for URL: {audio_url}")
        return job_id
    
    def update_job(
        self,
        job_id: str,
        status: Optional[JobStatus] = None,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        result: Optional[Dict] = None,
        error: Optional[str] = None
    ):
        """Update job status and progress."""
        job_data = self.get_job(job_id)
        if not job_data:
            logger.warning(f"Job not found: {job_id}")
            return
        
        if status:
            job_data["status"] = status.value
        if progress is not None:
            job_data["progress"] = progress
        if message:
            job_data["message"] = message
        if result:
            job_data["result"] = result
        if error:
            job_data["error"] = error
        
        job_data["updated_at"] = datetime.utcnow().isoformat()
        
        self.client.setex(
            f"{self._job_prefix}{job_id}",
            self._job_ttl,
            json.dumps(job_data)
        )
        
        logger.info(f"Updated job {job_id}: status={status}, progress={progress}")
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job data by ID."""
        data = self.client.get(f"{self._job_prefix}{job_id}")
        if data:
            return json.loads(data)
        return None
    
    def delete_job(self, job_id: str):
        """Delete a job."""
        self.client.delete(f"{self._job_prefix}{job_id}")


# Global instance
_job_queue: Optional[JobQueue] = None


def get_job_queue() -> JobQueue:
    """Get or create job queue instance."""
    global _job_queue
    if _job_queue is None:
        _job_queue = JobQueue()
    return _job_queue


async def process_url_job(job_id: str, audio_url: str, audio_id: str, client_policy: Optional[str] = None):
    """
    Process a URL analysis job in the background.
    
    Updates job status as it progresses through stages.
    """
    from logic.ai_engine import analyze_from_url_full
    
    queue = get_job_queue()
    start_time = time.perf_counter()
    
    with telemetry.SpanContext("job.process_url", {
        "job_id": job_id,
        "audio_id": audio_id,
        "audio_url": audio_url[:100] if audio_url else None  # Truncate URL for safety
    }) as span:
        try:
            # Stage 1: Downloading
            queue.update_job(
                job_id,
                status=JobStatus.DOWNLOADING,
                progress=10,
                message="Downloading audio from URL..."
            )
            if span:
                span.set_attribute("job.status", "downloading")
            
            # Run the full analysis (which includes download + AI)
            result = await analyze_from_url_full(
                audio_url,
                audio_id,
                client_policy,
                progress_callback=lambda p, m: queue.update_job(job_id, progress=p, message=m)
            )
            
            # Stage 3: Complete
            # Convert result to JSON-serializable dict
            if hasattr(result, 'model_dump'):
                result_dict = result.model_dump(mode='json')
            else:
                # Manually serialize datetime fields
                result_dict = {}
                for key, value in result.__dict__.items():
                    if isinstance(value, datetime):
                        result_dict[key] = value.isoformat()
                    elif hasattr(value, 'value'):  # Enum
                        result_dict[key] = value.value
                    else:
                        result_dict[key] = value
            
            queue.update_job(
                job_id,
                status=JobStatus.COMPLETE,
                progress=100,
                message="Analysis complete!",
                result=result_dict
            )
            
            # Save to cache for future lookups
            from logic.cache import set_cache
            set_cache(audio_id, result)
            
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            logger.info(f"Job {job_id} completed successfully, cached with audio_id: {audio_id} (duration: {elapsed_ms:.0f}ms)")
            
            if span:
                span.set_attribute("job.status", "complete")
                span.set_attribute("job.duration_ms", elapsed_ms)
            
            # Record job completion metric
            if telemetry.job_counter:
                telemetry.job_counter.add(1, {"status": "complete", "job_id": job_id})
            
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            telemetry.record_exception(e)
            
            queue.update_job(
                job_id,
                status=JobStatus.FAILED,
                progress=0,
                message="Analysis failed",
                error=str(e)
            )
            
            if span:
                span.set_attribute("job.status", "failed")
                span.set_attribute("job.error", str(e))
            
            # Record job failure metric
            if telemetry.job_counter:
                telemetry.job_counter.add(1, {"status": "failed", "job_id": job_id, "error_type": type(e).__name__})
