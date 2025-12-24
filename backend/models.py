"""
BrandGuard Data Models

Implements the VerificationResult schema from Source 15 of AdVerify Docs.
Adapted for Audio Safety Verification: Domain URL -> Audio File ID.

Reference: ADVERIFY-AI-1 (S-1.1.2) - JSON Schema Definition
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class BrandSafetyScore(str, Enum):
    """
    Brand safety classification levels.
    Maps to the risk assessment output from Gemini AI.
    
    Reference: Source 15 - Classification Levels
    """
    SAFE = "SAFE"
    RISK_HIGH = "RISK_HIGH"
    RISK_MEDIUM = "RISK_MEDIUM"
    UNKNOWN = "UNKNOWN"


class VerificationSource(str, Enum):
    """
    Source of the verification result.
    Implements the priority lookup pattern: Override > Cache > AI
    
    Reference: ADVERIFY-UI-1 (S-2.1.4) - Backend Integration
    """
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    CACHE = "CACHE"
    AI_GENERATED = "AI_GENERATED"


class VerificationResult(BaseModel):
    """
    Core verification result model matching JSON schema from Source 15.
    
    This is the primary response structure for the /api/v1/verify_audio endpoint.
    The schema is also used for Gemini's structured output validation.
    
    Reference: ADVERIFY-AI-1 (S-1.1.2) - Structured Output & JSON Schema
    """
    audio_id: str = Field(
        ...,
        description="Unique identifier for the audio file",
        examples=["audio_12345", "podcast_ep42"]
    )
    brand_safety_score: BrandSafetyScore = Field(
        ...,
        description="Overall brand safety classification"
    )
    fraud_flag: bool = Field(
        default=False,
        description="True if high Invalid Traffic (IVT) detected"
    )
    category_tags: List[str] = Field(
        default_factory=list,
        description="Content category labels (e.g., 'NEWS', 'SPORTS', 'ADULT')",
        examples=[["NEWS", "POLITICS"], ["ENTERTAINMENT", "MUSIC"]]
    )
    source: VerificationSource = Field(
        ...,
        description="Origin of this verification result"
    )
    confidence_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="AI confidence score (0.0-1.0), only present for AI_GENERATED results"
    )
    unsafe_segments: Optional[List[dict]] = Field(
        default=None,
        description="Timestamp ranges of unsafe content for waveform visualization",
        examples=[[{"start": 12.5, "end": 18.3, "reason": "explicit_language"}]]
    )
    sensitive_segments: Optional[List[dict]] = Field(
        default=None,
        description="Timestamp ranges of sensitive topic discussions (crime, violence, politics, etc.)",
        examples=[[{"start": 45.0, "end": 120.0, "topic": "crime discussion"}]]
    )
    transcript_snippet: Optional[str] = Field(
        default=None,
        description="Brief excerpt of the transcript for context"
    )
    content_summary: Optional[str] = Field(
        default=None,
        description="2-3 sentence summary of what the audio content is about"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when this result was generated"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "audio_id": "audio_12345",
                "brand_safety_score": "RISK_MEDIUM",
                "fraud_flag": False,
                "category_tags": ["NEWS", "POLITICS"],
                "source": "AI_GENERATED",
                "confidence_score": 0.87,
                "unsafe_segments": [
                    {"start": 12.5, "end": 18.3, "reason": "controversial_topic"}
                ],
                "transcript_snippet": "...discussing the heated political debate...",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }


class AudioVerificationRequest(BaseModel):
    """
    Request model for audio verification endpoint.
    
    Reference: ADVERIFY-AI-1 - Input specification
    """
    audio_id: str = Field(
        ...,
        description="Unique identifier for the audio file",
        min_length=1,
        max_length=255
    )
    audio_url: Optional[str] = Field(
        default=None,
        description="Optional URL to fetch audio from (if not uploading directly)"
    )
    client_policy: Optional[str] = Field(
        default=None,
        description="Optional client-specific policy rules for classification"
    )


class OverrideRequest(BaseModel):
    """
    Request model for creating/updating manual overrides.
    
    Reference: ADVERIFY-UI-1 (S-2.1.2) - Override Form
    """
    audio_id: str = Field(
        ...,
        description="Audio file ID to override"
    )
    brand_safety_score: BrandSafetyScore = Field(
        ...,
        description="Forced brand safety classification"
    )
    fraud_flag: bool = Field(
        default=False,
        description="Force fraud flag status"
    )
    category_tags: List[str] = Field(
        default_factory=list,
        description="Forced category tags"
    )
    reason: Optional[str] = Field(
        default=None,
        description="Reason for the manual override (audit trail)"
    )
    created_by: Optional[str] = Field(
        default=None,
        description="User who created the override"
    )


class OverrideRecord(OverrideRequest):
    """
    Extended override model with metadata for storage.
    
    Reference: ADVERIFY-UI-1 - Override persistence
    """
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str = "healthy"
    version: str = "1.0.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    redis_connected: bool = False
    firestore_connected: bool = False
