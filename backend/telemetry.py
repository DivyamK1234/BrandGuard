"""
BrandGuard Telemetry Module

OpenTelemetry-based observability for distributed tracing, metrics, and logging.
Supports Jaeger (local) and OTLP-compatible backends (GCP Cloud Trace via collector).

Reference: Production-grade observability best practices
"""

import logging
import os
from functools import lru_cache
from typing import Optional

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.trace import Status, StatusCode, Span
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

logger = logging.getLogger(__name__)

# Global instances
_tracer: Optional[trace.Tracer] = None
_meter: Optional[metrics.Meter] = None
_initialized: bool = False

# Metrics instruments (initialized in setup_telemetry)
request_counter: Optional[metrics.Counter] = None
request_duration: Optional[metrics.Histogram] = None
cache_hit_counter: Optional[metrics.Counter] = None
cache_miss_counter: Optional[metrics.Counter] = None
gemini_duration: Optional[metrics.Histogram] = None
gemini_error_counter: Optional[metrics.Counter] = None
job_counter: Optional[metrics.Counter] = None


def get_resource() -> Resource:
    """Create OpenTelemetry resource with service metadata."""
    from config import get_settings
    settings = get_settings()
    
    return Resource.create({
        SERVICE_NAME: settings.otel_service_name,
        SERVICE_VERSION: settings.otel_service_version,
        "deployment.environment": settings.otel_environment,
        "service.namespace": "brandguard",
    })


def setup_telemetry() -> None:
    """
    Initialize OpenTelemetry tracing, metrics, and logging instrumentation.
    
    Should be called once during application startup (in lifespan handler).
    Configures exporters based on environment variables for flexibility.
    """
    global _tracer, _meter, _initialized
    global request_counter, request_duration
    global cache_hit_counter, cache_miss_counter
    global gemini_duration, gemini_error_counter, job_counter
    
    if _initialized:
        logger.warning("Telemetry already initialized, skipping...")
        return
    
    from config import get_settings
    settings = get_settings()
    
    if not settings.otel_enabled:
        logger.info("OpenTelemetry disabled via configuration")
        _initialized = True
        return
    
    logger.info(f"Initializing OpenTelemetry for service: {settings.otel_service_name}")
    logger.info(f"Exporter endpoint: {settings.otel_exporter_endpoint}")
    
    resource = get_resource()
    
    # ==========================================================================
    # Tracing Setup
    # ==========================================================================
    tracer_provider = TracerProvider(resource=resource)
    
    # Configure OTLP exporter (works with Jaeger, Cloud Trace collector, etc.)
    otlp_exporter = OTLPSpanExporter(
        endpoint=settings.otel_exporter_endpoint,
        insecure=not settings.otel_exporter_endpoint.startswith("https")
    )
    
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    trace.set_tracer_provider(tracer_provider)
    
    _tracer = trace.get_tracer(
        settings.otel_service_name,
        settings.otel_service_version
    )
    
    # ==========================================================================
    # Metrics Setup
    # ==========================================================================
    metric_exporter = OTLPMetricExporter(
        endpoint=settings.otel_exporter_endpoint,
        insecure=not settings.otel_exporter_endpoint.startswith("https")
    )
    
    metric_reader = PeriodicExportingMetricReader(
        metric_exporter,
        export_interval_millis=60000  # Export every 60 seconds
    )
    
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=[metric_reader]
    )
    metrics.set_meter_provider(meter_provider)
    
    _meter = metrics.get_meter(
        settings.otel_service_name,
        settings.otel_service_version
    )
    
    # Create metric instruments
    request_counter = _meter.create_counter(
        "http.requests.total",
        description="Total HTTP requests",
        unit="1"
    )
    
    request_duration = _meter.create_histogram(
        "http.request.duration",
        description="HTTP request duration in milliseconds",
        unit="ms"
    )
    
    cache_hit_counter = _meter.create_counter(
        "cache.hits.total",
        description="Total cache hits",
        unit="1"
    )
    
    cache_miss_counter = _meter.create_counter(
        "cache.misses.total",
        description="Total cache misses",
        unit="1"
    )
    
    gemini_duration = _meter.create_histogram(
        "gemini.api.duration",
        description="Gemini API call duration in milliseconds",
        unit="ms"
    )
    
    gemini_error_counter = _meter.create_counter(
        "gemini.api.errors.total",
        description="Total Gemini API errors",
        unit="1"
    )
    
    job_counter = _meter.create_counter(
        "jobs.processed.total",
        description="Total background jobs processed",
        unit="1"
    )
    
    # ==========================================================================
    # Auto-instrumentation
    # ==========================================================================
    # Redis instrumentation (auto-traces all Redis operations)
    RedisInstrumentor().instrument()
    
    # Logging instrumentation (adds trace context to logs)
    LoggingInstrumentor().instrument(
        set_logging_format=True,
        log_level=logging.INFO
    )
    
    _initialized = True
    logger.info("OpenTelemetry initialization complete")


def instrument_fastapi(app) -> None:
    """
    Instrument FastAPI application with OpenTelemetry.
    
    Should be called after app creation and setup_telemetry().
    """
    from config import get_settings
    settings = get_settings()
    
    if not settings.otel_enabled:
        return
    
    FastAPIInstrumentor.instrument_app(
        app,
        excluded_urls="health,health/live,health/ready"  # Don't trace health checks
    )
    logger.info("FastAPI instrumentation complete")


def get_tracer() -> Optional[trace.Tracer]:
    """Get the configured tracer for manual instrumentation."""
    return _tracer


def get_meter() -> Optional[metrics.Meter]:
    """Get the configured meter for custom metrics."""
    return _meter


def get_current_trace_id() -> Optional[str]:
    """Get the current trace ID for log correlation."""
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return format(span.get_span_context().trace_id, '032x')
    return None


def get_current_span_id() -> Optional[str]:
    """Get the current span ID for log correlation."""
    span = trace.get_current_span()
    if span and span.get_span_context().is_valid:
        return format(span.get_span_context().span_id, '016x')
    return None


def add_span_attributes(attributes: dict) -> None:
    """Add attributes to the current span."""
    span = trace.get_current_span()
    if span:
        for key, value in attributes.items():
            span.set_attribute(key, value)


def record_exception(exception: Exception) -> None:
    """Record an exception on the current span."""
    span = trace.get_current_span()
    if span:
        span.record_exception(exception)
        span.set_status(Status(StatusCode.ERROR, str(exception)))


class SpanContext:
    """
    Context manager for creating spans with automatic error handling.
    
    Usage:
        with SpanContext("operation_name", {"key": "value"}) as span:
            # do work
            if span:
                span.set_attribute("result", "success")
    """
    
    def __init__(self, name: str, attributes: Optional[dict] = None):
        self.name = name
        self.attributes = attributes or {}
        self.span: Optional[Span] = None
        self._context_manager = None
    
    def __enter__(self) -> Optional[Span]:
        tracer = get_tracer()
        if tracer:
            # Use start_as_current_span which properly manages the context
            self._context_manager = tracer.start_as_current_span(self.name)
            self.span = self._context_manager.__enter__()
            for key, value in self.attributes.items():
                if value is not None:  # Skip None values
                    self.span.set_attribute(key, value)
            return self.span
        return None
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._context_manager:
            if exc_val and self.span:
                self.span.record_exception(exc_val)
                self.span.set_status(Status(StatusCode.ERROR, str(exc_val)))
            elif self.span:
                self.span.set_status(Status(StatusCode.OK))
            # Let the context manager handle span ending
            self._context_manager.__exit__(exc_type, exc_val, exc_tb)
        return False


def shutdown_telemetry() -> None:
    """
    Gracefully shutdown telemetry exporters.
    
    Should be called during application shutdown.
    """
    tracer_provider = trace.get_tracer_provider()
    if hasattr(tracer_provider, 'shutdown'):
        tracer_provider.shutdown()
    
    meter_provider = metrics.get_meter_provider()
    if hasattr(meter_provider, 'shutdown'):
        meter_provider.shutdown()
    
    logger.info("OpenTelemetry shutdown complete")
