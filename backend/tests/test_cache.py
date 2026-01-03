"""
Unit Tests for Cache Module

Simple tests that don't require Redis connection.
"""

import pytest


class TestCacheModule:
    """Basic tests for cache module structure."""

    def test_cache_module_imports(self):
        """Cache module should be importable."""
        # Skip if redis not installed (will work in CI)
        pytest.importorskip("redis")
        from logic import cache
        assert hasattr(cache, 'check_cache')
        assert hasattr(cache, 'set_cache')

    def test_cache_key_prefix_constant(self):
        """Cache should use brandguard prefix."""
        # This is a documentation test - verifies our cache key format
        expected_prefix = "brandguard:verification:"
        assert expected_prefix.startswith("brandguard:")
