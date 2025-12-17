
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any
from logic.cache import get_redis_client

logger = logging.getLogger(__name__)

# Redis Keys
KEY_TOTAL_REQUESTS = "stats:requests:total"
KEY_DAILY_REQUESTS_PREFIX = "stats:requests:daily:"  # + YYYY-MM-DD
KEY_TOTAL_TOKENS = "stats:tokens:total"
KEY_DAILY_TOKENS_PREFIX = "stats:tokens:daily:"      # + YYYY-MM-DD
KEY_LATENCY_HISTORY = "stats:latency:history"        # List of last N latencies

def _get_today_str() -> str:
    return datetime.utcnow().strftime("%Y-%m-%d")

def increment_request_count():
    """Increment total and daily request counters."""
    try:
        redis = get_redis_client()
        if not redis:
            return

        today = _get_today_str()
        
        # Pipeline for atomicity
        pipe = redis.pipeline()
        pipe.incr(KEY_TOTAL_REQUESTS)
        pipe.incr(f"{KEY_DAILY_REQUESTS_PREFIX}{today}")
        # Set expiry for daily key (retain for 30 days)
        pipe.expire(f"{KEY_DAILY_REQUESTS_PREFIX}{today}", 60*60*24*30)
        pipe.execute()
        
    except Exception as e:
        logger.error(f"Failed to update request stats: {e}")

def increment_token_usage(prompt_tokens: int, candidates_tokens: int):
    """Track AI token usage."""
    try:
        redis = get_redis_client()
        if not redis:
            return

        total_tokens = prompt_tokens + candidates_tokens
        today = _get_today_str()
        
        pipe = redis.pipeline()
        pipe.incrby(KEY_TOTAL_TOKENS, total_tokens)
        pipe.incrby(f"{KEY_DAILY_TOKENS_PREFIX}{today}", total_tokens)
        pipe.expire(f"{KEY_DAILY_TOKENS_PREFIX}{today}", 60*60*24*30)
        pipe.execute()
        
    except Exception as e:
        logger.error(f"Failed to update token stats: {e}")

def record_latency(latency_ms: float):
    """Record request latency for average calculation."""
    try:
        redis = get_redis_client()
        if not redis:
            return
            
        # Store in a capped list (keep last 1000 requests)
        pipe = redis.pipeline()
        pipe.lpush(KEY_LATENCY_HISTORY, latency_ms)
        pipe.ltrim(KEY_LATENCY_HISTORY, 0, 999)
        pipe.execute()
        
    except Exception as e:
        logger.error(f"Failed to record latency: {e}")

def get_dashboard_stats() -> Dict[str, Any]:
    """Retrieve all aggregated stats for the dashboard."""
    # Mock Data for fallback
    mock_data = {
        "requests": {
            "total": 1250,
            "today": 45
        },
        "tokens": {
            "total": 850000,
            "today": 12500,
            "estimated_cost_today_usd": 1.85
        },
        "performance": {
            "avg_latency_ms": 145.2,
            "cache_hit_rate_percent": 82.5,
            "cache_hits": 850,
            "cache_misses": 150
        },
        "system": {
            "redis_status": "mock (redis unavailable)",
            "last_updated": datetime.utcnow().isoformat()
        }
    }

    try:
        redis = get_redis_client()
        if not redis:
            return mock_data
            
        # Quick check for connection
        try:
            if not redis.ping():
                return mock_data
        except Exception:
            return mock_data
            
        today = _get_today_str()
        
        # Fetch basic counters
        total_reqs = redis.get(KEY_TOTAL_REQUESTS) or 0
        today_reqs = redis.get(f"{KEY_DAILY_REQUESTS_PREFIX}{today}") or 0
        total_tokens = redis.get(KEY_TOTAL_TOKENS) or 0
        today_tokens = redis.get(f"{KEY_DAILY_TOKENS_PREFIX}{today}") or 0
        
        # Calculate Average Latency
        latencies = redis.lrange(KEY_LATENCY_HISTORY, 0, -1)
        avg_latency = 0
        if latencies:
            # Convert bytes to floats and calculate mean
            lat_values = [float(x) for x in latencies]
            avg_latency = sum(lat_values) / len(lat_values)

        # Get Cache Stats from Redis INFO
        info = redis.info('stats')
        keyspace_hits = info.get('keyspace_hits', 0)
        keyspace_misses = info.get('keyspace_misses', 0)
        total_ops = keyspace_hits + keyspace_misses
        hit_rate = (keyspace_hits / total_ops * 100) if total_ops > 0 else 0

        # Estimate Cost (Rough approx using Gemini Flash pricing: ~$0.15 / 1M tokens combined avg)
        # This is a ballpark for the "Intuitive" aspect
        estimated_cost_today = (int(today_tokens) / 1_000_000) * 0.15
        
        return {
            "requests": {
                "total": int(total_reqs),
                "today": int(today_reqs)
            },
            "tokens": {
                "total": int(total_tokens),
                "today": int(today_tokens),
                "estimated_cost_today_usd": round(estimated_cost_today, 4)
            },
            "performance": {
                "avg_latency_ms": round(avg_latency, 2),
                "cache_hit_rate_percent": round(hit_rate, 2),
                "cache_hits": keyspace_hits,
                "cache_misses": keyspace_misses
            },
            "system": {
                "redis_status": "connected",
                "last_updated": datetime.utcnow().isoformat()
            }
        }
        
    except Exception as e:
        logger.warning(f"Redis stats fetch failed ({e}), returning mock data.")
        return mock_data
