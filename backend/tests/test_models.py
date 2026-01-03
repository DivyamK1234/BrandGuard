"""
Unit Tests for Pydantic Models

Tests data model validation and serialization.
"""

import pytest
from datetime import datetime


class TestVerificationResult:
    """Tests for VerificationResult model."""

    def test_valid_verification_result(self):
        """Valid data should create a VerificationResult."""
        from models import VerificationResult, BrandSafetyScore, VerificationSource
        
        result = VerificationResult(
            audio_id="test_audio_12345",
            brand_safety_score=BrandSafetyScore.SAFE,
            fraud_flag=False,
            category_tags=["music"],
            source=VerificationSource.AI_GENERATED
        )
        
        assert result.audio_id == "test_audio_12345"
        assert result.brand_safety_score == BrandSafetyScore.SAFE
        assert result.fraud_flag == False

    def test_brand_safety_score_enum(self):
        """BrandSafetyScore should have expected values."""
        from models import BrandSafetyScore
        
        assert BrandSafetyScore.SAFE.value == "SAFE"
        assert BrandSafetyScore.RISK_MEDIUM.value == "RISK_MEDIUM"
        assert BrandSafetyScore.RISK_HIGH.value == "RISK_HIGH"
        assert BrandSafetyScore.UNKNOWN.value == "UNKNOWN"

    def test_verification_source_enum(self):
        """VerificationSource should have expected values."""
        from models import VerificationSource
        
        # Updated to match actual enum values
        assert VerificationSource.CACHE.value == "CACHE"
        assert VerificationSource.MANUAL_OVERRIDE.value == "MANUAL_OVERRIDE"
        assert VerificationSource.AI_GENERATED.value == "AI_GENERATED"

    def test_verification_result_with_unsafe_segments(self):
        """VerificationResult should accept unsafe_segments."""
        from models import VerificationResult, BrandSafetyScore, VerificationSource
        
        result = VerificationResult(
            audio_id="test123",
            brand_safety_score=BrandSafetyScore.RISK_HIGH,
            fraud_flag=False,
            category_tags=["news"],
            source=VerificationSource.AI_GENERATED,
            unsafe_segments=[
                {"start": 10, "end": 20, "reason": "Violence"}
            ]
        )
        
        assert len(result.unsafe_segments) == 1
        assert result.unsafe_segments[0]["reason"] == "Violence"

    def test_verification_result_with_sensitive_segments(self):
        """VerificationResult should accept sensitive_segments."""
        from models import VerificationResult, BrandSafetyScore, VerificationSource
        
        result = VerificationResult(
            audio_id="test123",
            brand_safety_score=BrandSafetyScore.RISK_MEDIUM,
            fraud_flag=False,
            category_tags=["politics"],
            source=VerificationSource.AI_GENERATED,
            sensitive_segments=[
                {"start": 30, "end": 45, "topic": "Politics"}
            ]
        )
        
        assert len(result.sensitive_segments) == 1
        assert result.sensitive_segments[0]["topic"] == "Politics"

    def test_verification_result_serialization(self):
        """VerificationResult should serialize to dict correctly."""
        from models import VerificationResult, BrandSafetyScore, VerificationSource
        
        result = VerificationResult(
            audio_id="test123",
            brand_safety_score=BrandSafetyScore.SAFE,
            fraud_flag=False,
            category_tags=["music", "entertainment"],
            source=VerificationSource.CACHE
        )
        
        data = result.model_dump()
        
        assert data["audio_id"] == "test123"
        assert data["brand_safety_score"] == "SAFE"
        assert data["fraud_flag"] == False
        assert "music" in data["category_tags"]
