"""
BrandGuard Telemetry Module

OpenTelemetry-based observability for distributed tracing and metrics.
Dynamically supports both OTLP/gRPC (Production) and OTLP/HTTP (Local Dev).
"""

import logging
import os
from typing import Dict, Optional, Any

from opentelemetry import trace, metrics
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.trace import Status, StatusCode, Span
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator


from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

from config import get_settings

logger = logging.getLogger(__name__)


_tracer: Optional[trace.Tracer] = None
_initialized: bool = False


request_counter: Optional[metrics.Counter] = None
request_duration: Optional[metrics.Histogram] = None
cache_hit_counter: Optional[metrics.Counter] = None
cache_miss_counter: Optional[metrics.Counter] = None
gemini_duration: Optional[metrics.Histogram] = None
gemini_error_counter: Optional[metrics.Counter] = None
job_counter: Optional[metrics.Counter] = None


def setup_telemetry() -> None:
    
    global _initialized, _tracer
    if _initialized:
        return
    
    settings = get_settings()
    if not settings.otel_enabled:
        _initialized = True
        return

    # 1. Resource Metadata
    resource = Resource.create({
        SERVICE_NAME: os.environ.get("OTEL_SERVICE_NAME", settings.otel_service_name),
        SERVICE_VERSION: settings.otel_service_version,
        "deployment.environment": settings.otel_environment,
    })
    service_name = str(resource.attributes.get(SERVICE_NAME))
    
    # Determine Protocol (grpc vs http)
    # Default to grpc, but allow override via env var
    protocol = os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL", "grpc").lower()
    endpoint = settings.otel_exporter_endpoint
    
    logger.info(f"Initializing Telemetry for [{service_name}] via [{protocol}]")

    
    _setup_tracing(resource, endpoint, protocol, settings.otel_service_version)
    
    
    if not (":4317" in endpoint or ":4318" in endpoint):
        _setup_metrics(resource, endpoint, protocol)
    else:
        logger.info("Metrics export suppressed (standard Jaeger endpoint detected).")

    RedisInstrumentor().instrument()
    LoggingInstrumentor().instrument(set_logging_format=True, log_level=logging.INFO)

    _initialized = True
    logger.info("OpenTelemetry initialization complete.")


def _setup_tracing(resource: Resource, endpoint: str, protocol: str, version: str) -> None:
    """Configures tracing based on the selected protocol."""
    global _tracer
    provider = TracerProvider(resource=resource)
    
    if protocol == "grpc":
        # Production Standard: OTLP over gRPC
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        # gRPC doesn't use the http:// prefix
        sanitized_endpoint = endpoint.replace("http://", "").replace("https://", "")
        exporter = OTLPSpanExporter(endpoint=sanitized_endpoint, insecure=True)
        logger.info(f"Using OTLP/gRPC exporter -> {sanitized_endpoint}")
    else:
        # Dev Stability: OTLP over HTTP
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        if not endpoint.startswith("http"):
            endpoint = f"http://{endpoint}"
            
        # for Windows Dev Container bridge
        if ":4317" in endpoint:
            endpoint = endpoint.replace(":4317", ":4318")
        if not endpoint.endswith("/v1/traces"):
            endpoint = endpoint.rstrip("/") + "/v1/traces"
        exporter = OTLPSpanExporter(endpoint=endpoint, timeout=10)
        logger.info(f"Using OTLP/HTTP exporter -> {endpoint}")

    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(str(resource.attributes.get(SERVICE_NAME)), version)


def _setup_metrics(resource: Resource, endpoint: str, protocol: str) -> None:
    """Initializes global metric instruments."""
    global request_counter, request_duration, cache_hit_counter
    global cache_miss_counter, gemini_duration, gemini_error_counter, job_counter

    try:
        if protocol == "grpc":
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
            sanitized_endpoint = endpoint.replace("http://", "").replace("https://", "")
            exporter = OTLPMetricExporter(endpoint=sanitized_endpoint, insecure=True)
        else:
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
            metric_endpoint = endpoint.replace("/v1/traces", "/v1/metrics")
            exporter = OTLPMetricExporter(endpoint=metric_endpoint)

        reader = PeriodicExportingMetricReader(exporter, export_interval_millis=60000)
        provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(provider)
        
        meter = metrics.get_meter("brandguard.metrics")
        
        # Initialize 
        request_counter = meter.create_counter("http.requests.total", "1", "Total HTTP requests")
        request_duration = meter.create_histogram("http.request.duration", "ms", "Request duration")
        cache_hit_counter = meter.create_counter("cache.hits.total", "1", "Total cache hits")
        cache_miss_counter = meter.create_counter("cache.misses.total", "1", "Total cache misses")
        gemini_duration = meter.create_histogram("gemini.api.duration", "ms", "Gemini API latency")
        gemini_error_counter = meter.create_counter("gemini.api.errors.total", "1", "Gemini failures")
        job_counter = meter.create_counter("jobs.processed.total", "1", "Total background jobs")

    except Exception as e:
        logger.warning(f"Metrics initialization failed: {e}")


def instrument_fastapi(app) -> None:
    """Instrument FastAPI if OpenTelemetry is enabled."""
    if get_settings().otel_enabled:
        FastAPIInstrumentor.instrument_app(app, excluded_urls="health,health/live,health/ready")


# Public API Utilities

def get_tracer() -> trace.Tracer:
    return _tracer if _tracer else trace.get_tracer("brandguard.noop")

def get_current_trace_id() -> str:
    sc = trace.get_current_span().get_span_context()
    return format(sc.trace_id, '032x') if sc.is_valid else ""

def add_span_attributes(attrs: Dict[str, Any]) -> None:
    span = trace.get_current_span()
    if span:
        for k, v in attrs.items():
            if v is not None:
                span.set_attribute(k, v)

def record_exception(exc: Exception) -> None:
    span = trace.get_current_span()
    if span:
        span.record_exception(exc)
        span.set_status(Status(StatusCode.ERROR, str(exc)))


class SpanContext:
    """Convenience context manager for manual spans."""
    def __init__(self, name: str, attrs: Optional[Dict[str, Any]] = None):
        self.name, self.attrs = name, attrs or {}
        self._mgr = None
    
    def __enter__(self):
        self._mgr = get_tracer().start_as_current_span(self.name)
        span = self._mgr.__enter__()
        add_span_attributes(self.attrs)
        return span

    def __exit__(self, et, ev, tb):
        if ev:
            record_exception(ev)
        return self._mgr.__exit__(et, ev, tb)


def shutdown_telemetry() -> None:
    """Gracefully flushes all telemetry data."""
    trace.get_tracer_provider().shutdown()
    metrics.get_meter_provider().shutdown()
