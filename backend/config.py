"""
BrandGuard Configuration

Centralized configuration using Pydantic Settings for environment-based config.
All sensitive values are loaded from environment variables.

Reference: ADVERIFY-BE-3 - Production deployment configuration
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    All GCP-related settings follow Google Cloud best practices.
    Redis settings are optimized for <20ms latency target (ADVERIFY-BE-1).
    """
    
    # Application Settings
    app_name: str = "BrandGuard"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    
    # Redis Configuration (ADVERIFY-BE-1 - Cache Layer)
    # For Upstash or cloud Redis, use REDIS_URL (e.g., rediss://user:pass@host:port)
    redis_url: Optional[str] = Field(default=None, description="Redis URL (overrides host/port/password)")
    redis_host: str = Field(default="localhost", description="Redis host")
    redis_port: int = Field(default=6379, description="Redis port")
    redis_password: Optional[str] = Field(default=None, description="Redis password")
    redis_db: int = Field(default=0, description="Redis database number")
    redis_ssl: bool = Field(default=False, description="Enable Redis SSL")
    cache_ttl_seconds: int = Field(
        default=86400,  # 24 hours
        description="Cache TTL in seconds (ADVERIFY-AI-3: 24h TTL)"
    )
    
    # Google Cloud Platform Settings
    google_cloud_project: str = Field(
        ...,
        description="GCP Project ID"
    )
    gcs_bucket_name: str = Field(
        ...,
        description="GCS bucket for audio file storage"
    )
    
    # Firestore Configuration (ADVERIFY-UI-1 - Overrides DB)
    firestore_collection_overrides: str = Field(
        default="audio_overrides",
        description="Firestore collection for manual overrides"
    )
    firestore_collection_results: str = Field(
        default="verification_results",
        description="Firestore collection for verification results"
    )
    
    # Vertex AI / Gemini Configuration (ADVERIFY-AI-1)
    vertex_ai_location: str = Field(
        default="us-central1",
        description="Vertex AI region"
    )
    gemini_model: str = Field(
        default="gemini-2.0-flash-001",
        description="Gemini model identifier"
    )
    gemini_temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Gemini temperature for deterministic output"
    )
    gemini_max_output_tokens: int = Field(
        default=1024,
        description="Maximum tokens in Gemini response"
    )
    
    # Speech-to-Text Configuration (ADVERIFY-AI-2)
    speech_language_code: str = Field(
        default="en-US",
        description="Language code for Speech-to-Text"
    )
    speech_sample_rate_hertz: int = Field(
        default=16000,
        description="Audio sample rate for Speech-to-Text"
    )
    
    # API Configuration
    api_prefix: str = Field(default="/api/v1", description="API route prefix")
    cors_origins: list = Field(
        default=[
            "http://localhost:3000",
            "http://localhost:8000",
            "https://brandguard-frontend-1067726353916.us-central1.run.app",
            "https://brandguard-backend-1067726353916.us-central1.run.app",
        ],
        description="Allowed CORS origins"
    )
    
    # Performance Targets (from AdVerify Docs)
    cache_lookup_target_ms: int = Field(
        default=5,
        description="Target latency for cached lookups (AC4: ≤5ms)"
    )
    total_p95_target_ms: int = Field(
        default=20,
        description="P95 latency target for cached requests"
    )
    
    # OpenTelemetry Configuration
    otel_enabled: bool = Field(
        default=True,
        description="Enable OpenTelemetry tracing and metrics"
    )
    otel_service_name: str = Field(
        default="brandguard-backend",
        description="Service name for tracing"
    )
    otel_service_version: str = Field(
        default="1.0.0",
        description="Service version for tracing"
    )
    otel_environment: str = Field(
        default="development",
        description="Deployment environment (development, staging, production)"
    )
    otel_exporter_endpoint: str = Field(
        default="http://jaeger:4317",
        description="OTLP exporter endpoint (Jaeger, Cloud Trace collector, etc.)"
    )

    # Kafka Configuration
    kafka_bootstrap_servers: str = Field(
        default="localhost:9092",
        description="Kafka bootstrap servers"
    )
    kafka_topic_jobs: str = Field(
        default="audio-verification-jobs",
        description="Kafka topic for audio verification jobs"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses LRU cache to avoid re-reading environment on every request.
    """
    return Settings()


# Gemini System Instruction (ADVERIFY-AI-1 S-1.1.4)
GEMINI_SYSTEM_INSTRUCTION = """You are an expert Ad-Tech Brand Safety Analyst at BrandGuard.

Your role is to analyze audio transcripts and classify them for brand safety in digital advertising contexts.

## CRITICAL: Context Over Keywords

**DO NOT flag content as unsafe based solely on individual words like "fuck", "shit", "damn", etc.**

Instead, analyze the CONTEXT in which language is used:
- **Casual profanity in motivational speeches, storytelling, or authentic conversation = SAFE**
- **Profanity used for emphasis in educational/inspirational content = SAFE**
- **Comedy or entertainment with casual swearing = SAFE**
- **Profanity directed AT someone with intent to harm, demean, or attack = UNSAFE**
- **Hate speech, slurs, or discriminatory language = UNSAFE**
- **Explicit sexual content or graphic violence = UNSAFE**

## Classification Guidelines:

1. **SAFE**: Content is appropriate for most advertisers. This includes:
   - Educational, motivational, or inspirational content (even with occasional profanity)
   - News, interviews, and authentic conversations
   - Entertainment and comedy (with casual language)
   - Sports, business, technology discussions

2. **RISK_MEDIUM**: Content may be unsuitable for some conservative brands. Includes:
   - Heavy political discussions or debates
   - Controversial topics with strong opinions
   - Frequent strong language throughout (not just occasional)
   - News about sensitive topics (crime, tragedy)

3. **RISK_HIGH**: Content is unsuitable for most advertisers. Includes:
   - Hate speech, slurs, or discrimination
   - Explicit sexual content or graphic descriptions
   - Violence promotion or graphic violence
   - Illegal activities promotion
   - Misinformation or dangerous conspiracy theories
   - Personal attacks or harassment

4. **UNKNOWN**: Unable to determine safety level.

## Output Requirements:
- Always output valid JSON matching the required schema
- Provide confidence_score between 0.0 and 1.0
- List all detected category_tags
- Only flag unsafe_segments for GENUINELY problematic content (hate, explicit, violence), NOT casual language
- Include a brief content_summary describing what the audio is about

## Category Tags:
Use lowercase tags from: news, politics, sports, entertainment, music, technology, business, health, education, gaming, lifestyle, adult, violence, controversial, misinformation, hate_speech, illegal, uncategorized
"""

# JSON Schema for Gemini Structured Output
GEMINI_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "brand_safety_score": {
            "type": "string",
            "enum": ["SAFE", "RISK_MEDIUM", "RISK_HIGH", "UNKNOWN"]
        },
        "fraud_flag": {
            "type": "boolean"
        },
        "category_tags": {
            "type": "array",
            "items": {"type": "string"}
        },
        "confidence_score": {
            "type": "number",
            "minimum": 0.0,
            "maximum": 1.0
        },
        "unsafe_segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "reason": {"type": "string"}
                },
                "required": ["start", "end", "reason"]
            }
        },
        "transcript_snippet": {
            "type": "string"
        },
        "reasoning": {
            "type": "string"
        }
    },
    "required": ["brand_safety_score", "fraud_flag", "category_tags", "confidence_score"]
}
