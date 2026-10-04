import logging
from typing import Optional
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME, SERVICE_VERSION
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as OTLPGrpcSpanExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as OTLPHttpSpanExporter

from app.config import settings

_tracer_provider: Optional[TracerProvider] = None

def init_tracing() -> TracerProvider:
    """Initializes OpenTelemetry TracerProvider with OTLP Exporter."""
    global _tracer_provider
    if _tracer_provider is not None:
        return _tracer_provider

    resource = Resource.create({
        SERVICE_NAME: settings.otel_service_name,
        SERVICE_VERSION: "0.1.0",
        "environment": settings.env,
    })

    provider = TracerProvider(resource=resource)
    endpoint = settings.otel_exporter_otlp_endpoint

    try:
        if settings.otel_exporter_otlp_protocol.lower() == "http":
            exporter = OTLPHttpSpanExporter(endpoint=f"{endpoint}/v1/traces")
        else:
            exporter = OTLPGrpcSpanExporter(endpoint=endpoint, insecure=True)

        provider.add_span_processor(BatchSpanProcessor(exporter))
    except Exception as err:
        logging.warning(f"OTLP Exporter init error: {err}. Falling back to console exporter.")

    if settings.enable_console_exporter:
        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _tracer_provider = provider
    return provider

def get_tracer(name: str = "observable-agent"):
    """Returns an OpenTelemetry tracer for the requested component."""
    return trace.get_tracer(name)
