"""
Unit Tests for API

Note: Full API tests require all dependencies (Google Cloud, Redis, etc.)
These are basic import tests that work without full setup.
"""

import pytest


class TestAPIImports:
    """Test that API modules are importable."""

    def test_models_import(self):
        """Models should be importable."""
        from models import VerificationResult, BrandSafetyScore
        assert VerificationResult is not None
        assert BrandSafetyScore is not None

    def test_config_import(self):
        """Config should be importable."""
        from config import Settings
        assert Settings is not None


class TestAPIStructure:
    """Test API structure without full initialization."""

    def test_brand_safety_score_values(self):
        """BrandSafetyScore should have 4 values."""
        from models import BrandSafetyScore
        
        values = [e.value for e in BrandSafetyScore]
        assert len(values) == 4
        assert "SAFE" in values
        assert "RISK_HIGH" in values
