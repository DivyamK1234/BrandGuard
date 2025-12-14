"""
BrandGuard Cache Logic

Implements Story ADVERIFY-BE-1 (S-1.1.3): Core Lookup Logic with Redis Cache.

Performance Target: Cached lookups must complete in ≤5ms (AC4 from ADVERIFY-AI-1)
TTL: 24 hours as per ADVERIFY-AI-3 (Cache Management)

The cache layer sits between Override checks and AI generation:
Override > Cache > AI Generated
"""

import json
import logging
import time
from typing import Optional

import redis
from redis.exceptions import RedisError

from models import VerificationResult, BrandSafetyScore, VerificationSource
from config import get_settings

logger = logging.getLogger(__name__)

# Redis client (lazy initialized)
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """
    Get or create Redis client with connection pooling.
    
    Uses lazy initialization to avoid connection issues during import.
    Connection pool enables high-throughput, low-latency operations.
    
    Supports both URL-based connection (for Upstash/cloud) and host/port.
    
    Reference: ADVERIFY-BE-1 - Ultra-low latency lookups
    """
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        
        # If REDIS_URL is provided, use it (for Upstash/cloud Redis)
        if settings.redis_url:
            _redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_timeout=5.0,  # Longer timeout for cloud
                socket_connect_timeout=5.0,
                retry_on_timeout=True
            )
            logger.info(f"Initialized Redis client from URL (SSL enabled)")
        else:
            # Configure connection pool for local Redis
            pool = redis.ConnectionPool(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password,
                db=settings.redis_db,
                decode_responses=True,
                max_connections=50,
                socket_timeout=0.1,  # 100ms timeout for fast fail
                socket_connect_timeout=0.1,
                retry_on_timeout=True
            )
            
            _redis_client = redis.Redis(connection_pool=pool)
            logger.info(f"Initialized Redis client: {settings.redis_host}:{settings.redis_port}")
    
    return _redis_client


def _get_cache_key(audio_id: str) -> str:
    """
    Generate consistent cache key for audio_id.
    
    Uses namespaced key pattern for multi-tenant support.
    """
    return f"brandguard:verification:{audio_id}"


def check_cache(audio_id: str) -> Optional[VerificationResult]:
    """
    Check if a cached verification result exists for the given audio_id.
    
    Implements Logic S-1.1.3 from AdVerify Docs:
    "Implement the primary function to look up a domain [audio] in the in-memory cache."
    
    Performance Target: ≤5ms for cache hits (AC4 from ADVERIFY-AI-1)
    
    Args:
        audio_id: Unique identifier for the audio file
        
    Returns:
        VerificationResult if cached, None on cache miss
        
    Reference: ADVERIFY-BE-1 - Core Lookup Logic
    """
    start_time = time.perf_counter()
    
    try:
        client = get_redis_client()
        cache_key = _get_cache_key(audio_id)
        
        cached_data = client.get(cache_key)
        
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        
        if cached_data:
            # Parse cached JSON
            data = json.loads(cached_data)
            
            result = VerificationResult(
                audio_id=audio_id,
                brand_safety_score=BrandSafetyScore(data.get("brand_safety_score", "UNKNOWN")),
                fraud_flag=data.get("fraud_flag", False),
                category_tags=data.get("category_tags", []),
                source=VerificationSource.CACHE,  # Mark as from cache
                confidence_score=data.get("confidence_score"),
                unsafe_segments=data.get("unsafe_segments"),
                transcript_snippet=data.get("transcript_snippet"),
                created_at=data.get("created_at")
            )
            
            logger.info(f"Cache HIT for audio_id: {audio_id} (latency: {elapsed_ms:.2f}ms)")
            
            # Log warning if latency exceeds target
            if elapsed_ms > 5:
                logger.warning(f"Cache lookup exceeded 5ms target: {elapsed_ms:.2f}ms")
            
            return result
        
        logger.debug(f"Cache MISS for audio_id: {audio_id} (latency: {elapsed_ms:.2f}ms)")
        return None
        
    except RedisError as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.error(f"Redis error checking cache for {audio_id}: {e} (latency: {elapsed_ms:.2f}ms)")
        # On Redis error, return None to fall through to AI
        # This prevents cache issues from blocking requests
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in cache for {audio_id}: {e}")
        # Delete corrupted cache entry
        try:
            client = get_redis_client()
            client.delete(_get_cache_key(audio_id))
        except Exception:
            pass
        return None


def set_cache(audio_id: str, result: VerificationResult) -> bool:
    """
    Store verification result in cache.
    
    Implements S-1.3.1 from ADVERIFY-AI-3:
    "Implement Redis TTL configuration for cached results."
    
    TTL: 24 hours (86400 seconds) as per ADVERIFY-AI-3 AC1
    
    Args:
        audio_id: Unique identifier for the audio file
        result: Verification result to cache
        
    Returns:
        True if successful, False on error
        
    Reference: ADVERIFY-AI-3 - Cache Management
    """
    settings = get_settings()
    
    try:
        client = get_redis_client()
        cache_key = _get_cache_key(audio_id)
        
        # Serialize result to JSON (exclude source field as it will be set to CACHE on read)
        cache_data = {
            "brand_safety_score": result.brand_safety_score.value,
            "fraud_flag": result.fraud_flag,
            "category_tags": result.category_tags,
            "confidence_score": result.confidence_score,
            "unsafe_segments": result.unsafe_segments,
            "transcript_snippet": result.transcript_snippet,
            "created_at": result.created_at.isoformat() if result.created_at else None
        }
        
        # Set with TTL (24 hours)
        client.setex(
            cache_key,
            settings.cache_ttl_seconds,
            json.dumps(cache_data)
        )
        
        logger.info(f"Cached verification result for audio_id: {audio_id} (TTL: {settings.cache_ttl_seconds}s)")
        return True
        
    except RedisError as e:
        logger.error(f"Redis error caching result for {audio_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Error caching result for {audio_id}: {e}")
        return False


def invalidate_cache(audio_id: str) -> bool:
    """
    Remove cached verification result.
    
    Used when a manual override is created/updated to ensure
    the override takes effect immediately.
    
    Args:
        audio_id: Unique identifier for the audio file
        
    Returns:
        True if deleted (or not found), False on error
    """
    try:
        client = get_redis_client()
        cache_key = _get_cache_key(audio_id)
        
        deleted = client.delete(cache_key)
        
        if deleted:
            logger.info(f"Invalidated cache for audio_id: {audio_id}")
        else:
            logger.debug(f"No cache entry to invalidate for audio_id: {audio_id}")
        
        return True
        
    except RedisError as e:
        logger.error(f"Redis error invalidating cache for {audio_id}: {e}")
        return False


def get_cache_stats() -> dict:
    """
    Get cache statistics for monitoring.
    
    Implements S-1.3.2 from ADVERIFY-AI-3:
    "Implement metrics instrumentation"
    
    Returns:
        Dictionary with cache stats
    """
    try:
        client = get_redis_client()
        info = client.info("stats")
        
        return {
            "hits": info.get("keyspace_hits", 0),
            "misses": info.get("keyspace_misses", 0),
            "hit_rate": info.get("keyspace_hits", 0) / max(
                info.get("keyspace_hits", 0) + info.get("keyspace_misses", 0), 1
            ),
            "total_keys": client.dbsize()
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {"error": str(e)}


def health_check() -> bool:
    """
    Check Redis connectivity for health endpoint.
    
    Returns:
        True if Redis is healthy, False otherwise
    """
    try:
        client = get_redis_client()
        return client.ping()
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return False
