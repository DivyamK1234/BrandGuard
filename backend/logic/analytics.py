"""
BrandGuard Analytics Engine

Tracks and aggregates verification statistics for the Analytics Dashboard.
Stores metrics in Redis with time-series data for trend analysis.

Reference: Custom Analytics Feature
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict

import redis

from config import get_settings
from models import BrandSafetyScore, VerificationSource

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """
    Analytics engine for tracking verification metrics.
    
    Stores:
    - Total verification count
    - Classification breakdown (SAFE, RISK_HIGH, RISK_MEDIUM, UNKNOWN)
    - Processing time statistics
    - Recent verifications (last 50)
    - Daily trend data (last 7 days)
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[redis.Redis] = None
        
        # Redis keys
        self._stats_key = "analytics:stats"
        self._recent_key = "analytics:recent"
        self._daily_prefix = "analytics:daily:"
        
        # TTLs
        self._stats_ttl = 86400 * 30  # 30 days
        self._recent_ttl = 86400 * 7   # 7 days
        self._daily_ttl = 86400 * 30   # 30 days
    
    @property
    def client(self) -> redis.Redis:
        """Get Redis client (lazy initialization)."""
        if self._client is None:
            if self.settings.redis_url:
                self._client = redis.from_url(
                    self.settings.redis_url,
                    decode_responses=True,
                    socket_timeout=5.0,
                    socket_connect_timeout=5.0
                )
            else:
                self._client = redis.Redis(
                    host=self.settings.redis_host,
                    port=self.settings.redis_port,
                    decode_responses=True
                )
            logger.info("Initialized analytics Redis client")
        return self._client
    
    def track_verification(
        self,
        audio_id: str,
        brand_safety_score: BrandSafetyScore,
        source: VerificationSource,
        processing_time_ms: float,
        fraud_flag: bool = False,
        category_tags: Optional[List[str]] = None
    ):
        """
        Track a verification event.
        
        Args:
            audio_id: Audio file identifier
            brand_safety_score: Classification result
            source: Where the result came from (CACHE, AI, OVERRIDE)
            processing_time_ms: Time taken to process
            fraud_flag: Whether fraud was detected
            category_tags: Content categories
        """
        try:
            # Update global stats
            self._update_global_stats(
                brand_safety_score,
                source,
                processing_time_ms,
                fraud_flag
            )
            
            # Add to recent verifications
            self._add_recent_verification(
                audio_id,
                brand_safety_score,
                source,
                processing_time_ms,
                category_tags or []
            )
            
            # Update daily stats
            self._update_daily_stats(brand_safety_score)
            
            logger.debug(f"Tracked verification: {audio_id} -> {brand_safety_score.value}")
            
        except Exception as e:
            logger.error(f"Failed to track verification: {e}")
    
    def _update_global_stats(
        self,
        brand_safety_score: BrandSafetyScore,
        source: VerificationSource,
        processing_time_ms: float,
        fraud_flag: bool
    ):
        """Update global statistics."""
        stats = self._get_stats()
        
        # Increment counters
        stats["total_verifications"] += 1
        stats["classification_breakdown"][brand_safety_score.value] += 1
        stats["source_breakdown"][source.value] += 1
        
        if fraud_flag:
            stats["fraud_detections"] += 1
        
        # Update processing time stats
        stats["processing_times"].append(processing_time_ms)
        # Keep only last 1000 processing times
        if len(stats["processing_times"]) > 1000:
            stats["processing_times"] = stats["processing_times"][-1000:]
        
        # Calculate average
        if stats["processing_times"]:
            stats["avg_processing_time_ms"] = sum(stats["processing_times"]) / len(stats["processing_times"])
        
        # Save back to Redis
        self.client.setex(
            self._stats_key,
            self._stats_ttl,
            json.dumps(stats)
        )
    
    def _get_stats(self) -> Dict[str, Any]:
        """Get current global stats or initialize if not exists."""
        data = self.client.get(self._stats_key)
        if data:
            return json.loads(data)
        
        # Initialize default stats
        return {
            "total_verifications": 0,
            "fraud_detections": 0,
            "classification_breakdown": {
                "SAFE": 0,
                "RISK_HIGH": 0,
                "RISK_MEDIUM": 0,
                "UNKNOWN": 0
            },
            "source_breakdown": {
                "AI_GENERATED": 0,
                "CACHE": 0,
                "MANUAL_OVERRIDE": 0
            },
            "processing_times": [],
            "avg_processing_time_ms": 0.0
        }
    
    def _add_recent_verification(
        self,
        audio_id: str,
        brand_safety_score: BrandSafetyScore,
        source: VerificationSource,
        processing_time_ms: float,
        category_tags: List[str]
    ):
        """Add to recent verifications list (FIFO, max 50)."""
        verification = {
            "audio_id": audio_id,
            "brand_safety_score": brand_safety_score.value,
            "source": source.value,
            "processing_time_ms": round(processing_time_ms, 2),
            "category_tags": category_tags,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add to list (left push)
        self.client.lpush(self._recent_key, json.dumps(verification))
        
        # Trim to keep only last 50
        self.client.ltrim(self._recent_key, 0, 49)
        
        # Set expiry
        self.client.expire(self._recent_key, self._recent_ttl)
    
    def _update_daily_stats(self, brand_safety_score: BrandSafetyScore):
        """Update daily statistics for trend analysis."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        key = f"{self._daily_prefix}{today}"
        
        # Get existing daily stats
        data = self.client.get(key)
        if data:
            daily_stats = json.loads(data)
        else:
            daily_stats = {
                "date": today,
                "total": 0,
                "safe": 0,
                "risk_high": 0,
                "risk_medium": 0,
                "unknown": 0
            }
        
        # Update counts
        daily_stats["total"] += 1
        if brand_safety_score == BrandSafetyScore.SAFE:
            daily_stats["safe"] += 1
        elif brand_safety_score == BrandSafetyScore.RISK_HIGH:
            daily_stats["risk_high"] += 1
        elif brand_safety_score == BrandSafetyScore.RISK_MEDIUM:
            daily_stats["risk_medium"] += 1
        else:
            daily_stats["unknown"] += 1
        
        # Save back
        self.client.setex(key, self._daily_ttl, json.dumps(daily_stats))
    
    def get_analytics_summary(self) -> Dict[str, Any]:
        """
        Get complete analytics summary for the dashboard.
        
        Returns:
            Dictionary with all analytics data
        """
        stats = self._get_stats()
        
        # Get today's count
        today = datetime.utcnow().strftime("%Y-%m-%d")
        today_key = f"{self._daily_prefix}{today}"
        today_data = self.client.get(today_key)
        today_count = json.loads(today_data)["total"] if today_data else 0
        
        # Get recent verifications
        recent_raw = self.client.lrange(self._recent_key, 0, 9)  # Last 10
        recent_verifications = [json.loads(r) for r in recent_raw]
        
        # Get 7-day trend
        trend_data = self._get_trend_data(7)
        
        # Calculate success rate (SAFE / total)
        total = stats["total_verifications"]
        safe_count = stats["classification_breakdown"]["SAFE"]
        success_rate = (safe_count / total * 100) if total > 0 else 0.0
        
        # Calculate classification percentages
        classification_percentages = {}
        if total > 0:
            for category, count in stats["classification_breakdown"].items():
                classification_percentages[category.lower()] = round(count / total * 100, 1)
        else:
            classification_percentages = {
                "safe": 0,
                "risk_high": 0,
                "risk_medium": 0,
                "unknown": 0
            }
        
        return {
            "total_verifications": total,
            "today_count": today_count,
            "success_rate": round(success_rate, 1),
            "avg_processing_time_ms": round(stats["avg_processing_time_ms"], 2),
            "fraud_detections": stats["fraud_detections"],
            "classification_breakdown": stats["classification_breakdown"],
            "classification_percentages": classification_percentages,
            "source_breakdown": stats["source_breakdown"],
            "recent_verifications": recent_verifications,
            "trend_data": trend_data,
            "last_updated": datetime.utcnow().isoformat()
        }
    
    def _get_trend_data(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get daily trend data for the last N days."""
        trend = []
        
        for i in range(days - 1, -1, -1):
            date = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
            key = f"{self._daily_prefix}{date}"
            data = self.client.get(key)
            
            if data:
                trend.append(json.loads(data))
            else:
                # No data for this day
                trend.append({
                    "date": date,
                    "total": 0,
                    "safe": 0,
                    "risk_high": 0,
                    "risk_medium": 0,
                    "unknown": 0
                })
        
        return trend
    
    def reset_stats(self):
        """Reset all analytics data (for testing/demo purposes)."""
        # Delete all analytics keys
        self.client.delete(self._stats_key)
        self.client.delete(self._recent_key)
        
        # Delete daily stats for last 30 days
        for i in range(30):
            date = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
            key = f"{self._daily_prefix}{date}"
            self.client.delete(key)
        
        logger.info("Analytics stats reset")


# Global instance
_analytics_engine: Optional[AnalyticsEngine] = None


def get_analytics_engine() -> AnalyticsEngine:
    """Get or create analytics engine instance."""
    global _analytics_engine
    if _analytics_engine is None:
        _analytics_engine = AnalyticsEngine()
    return _analytics_engine
