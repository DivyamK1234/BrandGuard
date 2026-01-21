"""
BrandGuard API - FastAPI Application

Main entry point for the Audio Safety Verification microservice.

Implements the verification flow from ADVERIFY-AI-1:
1. Check Override (ADVERIFY-UI-1)
2. Check Cache (ADVERIFY-BE-1)
3. AI Analysis on miss (ADVERIFY-AI-1)

Also provides Admin API for manual override management (ADVERIFY-UI-1 S-2.1.3).
"""

import logging
import time
import uuid
import json
from datetime import datetime
from typing import List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from models import (
    VerificationResult,
    AudioVerificationRequest,
    OverrideRequest,
    OverrideRecord,
    HealthResponse,
    BrandSafetyScore
)
from config import get_settings
from logic import overrides, cache, ai_engine
import telemetry
from confluent_kafka import Producer, Consumer
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler for startup/shutdown.
    
    Reference: ADVERIFY-BE-3 - Production deployment
    """
    # Startup
    logger.info("BrandGuard API starting up...")
    settings = get_settings()
    logger.info(f"Project: {settings.google_cloud_project}")
    logger.info(f"Redis: {settings.redis_host}:{settings.redis_port}")
    
    # Initialize OpenTelemetry
    telemetry.setup_telemetry()
    
    yield
    
    # Shutdown
    logger.info("BrandGuard API shutting down...")
    telemetry.shutdown_telemetry()


# Initialize FastAPI app
app = FastAPI(
    title="BrandGuard API",
    description="Audio Safety Verification Microservice - Powered by Gemini AI",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS
settings = get_settings()

# Instrument FastAPI with OpenTelemetry
telemetry.instrument_fastapi(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Middleware for request timing
# =============================================================================
def delivery_report(err, msg):
    if err:
        logger.error("Delivery failed:", err)
    else:
        logger.info(
            f"Delivered to {msg.topic()} "
            f"[partition={msg.partition()} offset={msg.offset()}]"
        )

@app.middleware("http")
async def add_timing_and_telemetry(request: Request, call_next):
    """
    Add response timing, request ID, and metrics collection.
    
    Reference: ADVERIFY-BE-3 (S-1.3.2) - Metrics Instrumentation
    """
    # Generate request ID for correlation
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    
    start_time = time.perf_counter()
    
    # Add request ID to span attributes
    telemetry.add_span_attributes({
        "http.request_id": request_id,
        "http.route": request.url.path
    })
    
    try:
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Trace-ID"] = telemetry.get_current_trace_id() or ""
        
        # Record metrics (skip health checks)
        if "/health" not in request.url.path:
            if telemetry.request_counter:
                telemetry.request_counter.add(
                    1,
                    {"method": request.method, "endpoint": request.url.path, "status": str(response.status_code)}
                )
            if telemetry.request_duration:
                telemetry.request_duration.record(
                    elapsed_ms,
                    {"method": request.method, "endpoint": request.url.path}
                )
        
        # Log warning if exceeds P95 target
        if elapsed_ms > settings.total_p95_target_ms and "/health" not in request.url.path:
            logger.warning(
                f"Request exceeded P95 target: {request.url.path} took {elapsed_ms:.2f}ms",
                extra={"trace_id": telemetry.get_current_trace_id(), "request_id": request_id}
            )
        
        return response
        
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        telemetry.record_exception(e)
        
        if telemetry.request_counter:
            telemetry.request_counter.add(
                1,
                {"method": request.method, "endpoint": request.url.path, "status": "500"}
            )
        raise e


# =============================================================================
# Health Check Endpoints
# =============================================================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint for load balancer and kubernetes probes.
    
    Reference: ADVERIFY-BE-1 (S-1.1.2) - API server with health check endpoints
    """
    redis_healthy = cache.health_check()
    
    # Firestore health check (simplified - just check client initialization)
    try:
        overrides.get_firestore_client()
        firestore_healthy = True
    except Exception:
        firestore_healthy = False
    
    return HealthResponse(
        status="healthy" if (redis_healthy and firestore_healthy) else "degraded",
        version=settings.app_version,
        timestamp=datetime.utcnow(),
        redis_connected=redis_healthy,
        firestore_connected=firestore_healthy
    )


@app.get("/health/ready", tags=["Health"])
async def readiness_check():
    """Kubernetes readiness probe."""
    redis_healthy = cache.health_check()
    if not redis_healthy:
        raise HTTPException(status_code=503, detail="Redis not ready")
    return {"status": "ready"}


@app.get("/health/live", tags=["Health"])
async def liveness_check():
    """Kubernetes liveness probe."""
    return {"status": "alive"}


# =============================================================================
# Main Verification API
# =============================================================================

@app.post(
    "/api/v1/verify_audio",
    # response_model=VerificationResult,
    tags=["Verification"],
    summary="Verify Audio for Brand Safety",
    description="""
    Main verification endpoint implementing the Cache-First, AI-Fallback pattern.
    
    **Lookup Priority:**
    1. Manual Override (Firestore) - Highest priority
    2. Cache (Redis) - Target: <5ms
    3. AI Analysis (Gemini) - Fallback for cache misses
    
    Reference: ADVERIFY-AI-1 - AI Classification Endpoint
    """
)
async def verify_audio(
    audio_file: UploadFile = File(..., description="MP3 audio file to analyze"),
    audio_id: Optional[str] = Form(None, description="Optional custom audio ID"),
    client_policy: Optional[str] = Form(None, description="Optional client-specific policy")
):
    """
    Verify an audio file for brand safety.
    
    Implements the complete verification flow:
    1. Check check_override() - ADVERIFY-UI-1 (S-2.1.4)
    2. If Miss, Check check_cache() - ADVERIFY-BE-1 (S-1.1.3)
    3. If Miss, Call ai_engine.analyze() - ADVERIFY-AI-1
    4. Save result to Cache - ADVERIFY-AI-3
    
    Returns: VerificationResult JSON
    """
    start_time = time.perf_counter()
    
    # Generate audio_id if not provided
    if not audio_id:
        audio_id = f"audio_{int(time.time() * 1000)}"
    
    logger.info(f"Verification request for audio_id: {audio_id}")
    
    # Step 1: Check Override (highest priority)
    # Implements Logic S-2.1.4: Check high-priority Override Database first
    override_result = overrides.check_override(audio_id)
    if override_result:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"Override hit for {audio_id} (latency: {elapsed_ms:.2f}ms)")
        return {
            "job_id": None,
            "status": "complete",
            "result": override_result.model_dump() if hasattr(override_result, 'model_dump') else override_result.__dict__
        }
    
    # Step 2: Check Cache
    # Implements Logic S-1.1.3: Core Lookup Logic with in-memory cache
    cached_result = cache.check_cache(audio_id)
    if cached_result:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"Cache hit for {audio_id} (latency: {elapsed_ms:.2f}ms)")
        
        return {
            "job_id": None,
            "status": "complete",
            "result": cached_result.model_dump() if hasattr(cached_result, 'model_dump') else cached_result.__dict__
        }
        # return cached_result
    
    # Step 3: AI Analysis (cache miss)
    # Implements ADVERIFY-AI-1: AI Classification
    logger.info(f"Cache miss for {audio_id}, initiating AI analysis")
    
    try:
        from logic.jobs import get_job_queue
        queue = get_job_queue()
        job_id = queue.create_job(audio_url=None, audio_id=audio_id)

        # Read audio file
        audio_data = await audio_file.read()

        # Upload to GCS with telemetry
        with telemetry.SpanContext("gcs.upload", {
            "audio_id": audio_id,
            "audio_size_bytes": len(audio_data),
            "has_client_policy": client_policy is not None
        }) as span:
            gcs_uri = await ai_engine.upload_audio_to_gcs(audio_data, audio_id)
            if span:
                span.set_attribute("gcs_uri", gcs_uri)

        # Send to Kafka for async processing
        producer = Producer(settings.kafka_producer)

        # Inject trace context into Kafka headers
        trace_headers = {}
        propagator = TraceContextTextMapPropagator()
        propagator.inject(trace_headers)

        producer.produce(
            topic="audio-verification-non-url",
            value=json.dumps({
                "audio_id": audio_id,
                "audio_url": gcs_uri,
                "client_policy": client_policy,
                "job_id": job_id,
                "gcs_tag": "1"
            }),
            headers=[(k, v.encode()) for k, v in trace_headers.items()],
            callback=delivery_report
        )
        logger.info(f"Submitted job {job_id} to Kafka for processing")
        producer.poll(0)
        producer.flush()

        return {
            "job_id": job_id,
            "status": "processing",
            "message": "Job submitted. Poll /api/v1/job/{job_id} for status."
        }
        
    except Exception as e:
        logger.error(f"Verification failed for {audio_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Verification failed: {str(e)}")



@app.post(
    "/api/v1/verify_audio_async",
    tags=["Verification"],
    summary="Submit URL for Background Analysis",
    description="Submit a URL for background processing. Returns a job ID to poll for status."
)
async def verify_audio_async(request: AudioVerificationRequest):
    """
    Submit a URL for background analysis.
    
    Use this for long podcasts or videos that take more than 30 seconds to process.
    Returns a job_id that can be polled for status.
    """
    from logic.jobs import get_job_queue, process_url_job
    import asyncio
    
    if not request.audio_url:
        raise HTTPException(status_code=400, detail="audio_url is required")
    
    # Check cache first - if cached, return immediately
    cached_result = cache.check_cache(request.audio_id)
    if cached_result:
        return {
            "job_id": None,
            "status": "complete",
            "result": cached_result.model_dump() if hasattr(cached_result, 'model_dump') else cached_result.__dict__
        }
    
    # Create job
    queue = get_job_queue()
    job_id = queue.create_job(request.audio_url, request.audio_id)
    
    producer = Producer(settings.kafka_producer)

    # Inject trace context into Kafka headers
    trace_headers = {}
    propagator = TraceContextTextMapPropagator()
    propagator.inject(trace_headers)

    producer.produce(
            topic="audio-verification-non-url",
            value=json.dumps({
                "audio_id": request.audio_id,
                "audio_url": request.audio_url,
                "client_policy": request.client_policy,
                "job_id": job_id,
                "gcs_tag": "0"
            }),
            headers=[(k, v.encode()) for k, v in trace_headers.items()],
            callback=delivery_report
        )
    logger.info(f"Submitted job {job_id} to Kafka for processing")
    producer.poll(0)
    producer.flush()


    # Start background task
    # asyncio.create_task(
    #     process_url_job(job_id, request.audio_url, request.audio_id, request.client_policy)
    # )

    # logger.info(f"Submitted job {job_id} to url processor")
    
    return {
        "job_id": job_id,
        "status": "processing",
        "message": "Job submitted. Poll /api/v1/job/{job_id} for status."
    }


@app.get(
    "/api/v1/job/{job_id}",
    tags=["Verification"],
    summary="Get Job Status"
)
async def get_job_status(job_id: str):
    """
    Get the status of a background analysis job.
    
    Poll this endpoint every 2-3 seconds until status is 'complete' or 'failed'.
    """
    from logic.jobs import get_job_queue
    
    queue = get_job_queue()
    job_data = queue.get_job(job_id)
    
    if not job_data:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    
    return job_data


# =============================================================================
# Admin Override API
# =============================================================================

@app.get(
    "/api/v1/admin/override",
    response_model=List[OverrideRecord],
    tags=["Admin"],
    summary="List Manual Overrides",
    description="Fetch paginated list of manual overrides. Implements S-2.1.1."
)
async def list_overrides_endpoint(
    limit: int = Query(100, ge=1, le=500, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Records to skip"),
    search: Optional[str] = Query(None, description="Search by audio_id prefix")
):
    """
    List all manual overrides with pagination and search.
    
    Implements ADVERIFY-UI-1 (S-2.1.1): UI Table & Search
    """
    if search:
        return overrides.search_overrides(search, limit)
    return overrides.list_overrides(limit, offset)


@app.post(
    "/api/v1/admin/override",
    response_model=OverrideRecord,
    tags=["Admin"],
    summary="Create Manual Override",
    description="Create a new manual override. Implements S-2.1.3 (Create)."
)
async def create_override_endpoint(override: OverrideRequest):
    """
    Create a new manual override.
    
    Implements ADVERIFY-UI-1 (S-2.1.3): Management API - Create
    
    Note: This also invalidates any cached result for this audio_id
    to ensure the override takes effect immediately.
    """
    # Invalidate cache to ensure override takes effect
    cache.invalidate_cache(override.audio_id)
    
    # Create the override record
    record = OverrideRecord(
        audio_id=override.audio_id,
        brand_safety_score=override.brand_safety_score,
        fraud_flag=override.fraud_flag,
        category_tags=override.category_tags,
        reason=override.reason,
        created_by=override.created_by
    )
    
    return overrides.create_override(record)


@app.put(
    "/api/v1/admin/override/{audio_id}",
    response_model=OverrideRecord,
    tags=["Admin"],
    summary="Update Manual Override",
    description="Update an existing manual override. Implements S-2.1.3 (Update)."
)
async def update_override_endpoint(audio_id: str, override: OverrideRequest):
    """
    Update an existing manual override.
    
    Implements ADVERIFY-UI-1 (S-2.1.3): Management API - Update
    """
    # Invalidate cache
    cache.invalidate_cache(audio_id)
    
    record = OverrideRecord(
        audio_id=audio_id,
        brand_safety_score=override.brand_safety_score,
        fraud_flag=override.fraud_flag,
        category_tags=override.category_tags,
        reason=override.reason,
        created_by=override.created_by
    )
    
    result = overrides.update_override(audio_id, record)
    if not result:
        raise HTTPException(status_code=404, detail=f"Override not found: {audio_id}")
    
    return result


@app.delete(
    "/api/v1/admin/override/{audio_id}",
    tags=["Admin"],
    summary="Delete Manual Override",
    description="Delete a manual override. Implements S-2.1.3 (Delete)."
)
async def delete_override_endpoint(audio_id: str):
    """
    Delete a manual override.
    
    Implements ADVERIFY-UI-1 (S-2.1.3): Management API - Delete
    """
    # Invalidate cache
    cache.invalidate_cache(audio_id)
    
    deleted = overrides.delete_override(audio_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Override not found: {audio_id}")
    
    return {"status": "deleted", "audio_id": audio_id}


# =============================================================================
# Metrics/Stats Endpoints
# =============================================================================

@app.get("/api/v1/stats/cache", tags=["Metrics"])
async def cache_stats():
    """
    Get cache statistics for monitoring.
    
    Reference: ADVERIFY-AI-3 (S-1.3.2) - Metrics Instrumentation
    """
    return cache.get_cache_stats()


# =============================================================================
# Error Handlers
# =============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
