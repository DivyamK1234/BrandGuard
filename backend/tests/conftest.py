"""
Pytest Configuration and Fixtures

Shared fixtures for all tests.
"""

import sys
import os
import pytest

# Add backend to path so we can import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def sample_audio_id():
    """Sample audio ID for testing."""
    return "test_audio_12345"


@pytest.fixture
def sample_verification_result():
    """Sample verification result dictionary."""
    return {
        "audio_id": "test_audio_12345",
        "brand_safety_score": "SAFE",
        "fraud_flag": False,
        "category_tags": ["music", "entertainment"],
        "confidence_score": 0.95,
        "unsafe_segments": [],
        "sensitive_segments": [],
        "transcript_snippet": "This is a sample transcript...",
        "content_summary": "A music entertainment podcast."
    }
