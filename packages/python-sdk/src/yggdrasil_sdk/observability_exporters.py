from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os
import socket
import threading
import time
from typing import Any
from urllib.parse import urlparse

_logger = logging.getLogger(__name__)

try:
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace import SpanKind, Status, StatusCode, format_span_id, format_trace_id
except Exception:  # pragma: no cover - optional runtime dependency
    OTLPMetricExporter = None
    OTLPSpanExporter = None
    MeterProvider = None
    PeriodicExportingMetricReader = None
    Resource = None
    TracerProvider = None
    BatchSpanProcessor = None
    SpanKind = None
    Status = None
    StatusCode = None
    format_span_id = None
    format_trace_id = None

try:
    from langfuse import Langfuse as LangfuseClient
except Exception:  # pragma: no cover - optional runtime dependency
    LangfuseClient = None


@dataclass(slots=True)
class ActiveOTelSpan:
    context_manager: Any
    span: Any
    trace_id: str
    span_id: str
    parent_span_id: str | None = None


@dataclass(slots=True)
class _TraceRuntime:
    provider: Any
    tracer: Any


@dataclass(slots=True)
class _MetricRuntime:
    provider: Any
    meter: Any
    instruments: dict[tuple[str, str, str], Any] = field(default_factory=dict)


def _env(name: str, fallback: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return fallback
    return value.strip()


def _signal_endpoint(signal: str) -> str | None:
    explicit = _env(f"YGGDRASIL_OTEL_EXPORTER_OTLP_{signal.upper()}_ENDPOINT") or _env(f"OTEL_EXPORTER_OTLP_{signal.upper()}_ENDPOINT")
    if explicit:
        return explicit
    base = _env("YGGDRASIL_OTEL_EXPORTER_OTLP_ENDPOINT") or _env("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not base:
        return None
    return f"{base.rstrip('/')}/v1/{signal}"


def _parse_headers() -> dict[str, str]:
    raw = _env("YGGDRASIL_OTEL_EXPORTER_OTLP_HEADERS") or _env("OTEL_EXPORTER_OTLP_HEADERS") or ""
    headers: dict[str, str] = {}
    for item in raw.split(","):
        chunk = item.strip()
        if not chunk or "=" not in chunk:
            continue
        key, value = chunk.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            headers[key] = value
    return headers


def _truthy_env(name: str, *, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _langfuse_public_key() -> str | None:
    return _env("LANGFUSE_PUBLIC_KEY") or _env("YGGDRASIL_LANGFUSE_PUBLIC_KEY")


def _langfuse_secret_key() -> str | None:
    return _env("LANGFUSE_SECRET_KEY") or _env("YGGDRASIL_LANGFUSE_SECRET_KEY")


def _langfuse_base_url() -> str | None:
    return _env("LANGFUSE_BASE_URL") or _env("YGGDRASIL_LANGFUSE_BASE_URL") or "http://127.0.0.1:3100"


def _sanitize_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in list(value)[:32]]
    return str(value)


def _sanitize_attributes(attributes: dict[str, Any] | None) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in dict(attributes or {}).items():
        normalized = _sanitize_value(value)
        if normalized is not None:
            sanitized[str(key)] = normalized
    return sanitized


class _ExporterState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._trace_runtimes: dict[tuple[str, str], _TraceRuntime] = {}
        self._metric_runtimes: dict[tuple[str, str], _MetricRuntime] = {}
        self._langfuse_client: Any | None = None
        self._langfuse_identity: tuple[str, str, str | None] | None = None
        self._endpoint_health: dict[str, tuple[float, bool]] = {}

    def _endpoint_available(self, endpoint: str) -> bool:
        parsed = urlparse(endpoint)
        host = (parsed.hostname or "").strip().lower()
        # Only probe loopback/local endpoints; remote endpoints remain untouched.
        if host not in {"127.0.0.1", "localhost", "::1"}:
            return True

        now = time.monotonic()
        cached = self._endpoint_health.get(endpoint)
        if cached is not None and now - cached[0] < 60.0:
            return cached[1]

        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        available = True
        try:
            with socket.create_connection((host, port), timeout=0.2):
                available = True
        except OSError:
            available = False

        self._endpoint_health[endpoint] = (now, available)
        if not available:
            _logger.debug("Observability endpoint unreachable, exporter disabled for now: %s", endpoint)
        return available

    def _resource(self, service_name: str):
        if Resource is None:
            return None
        return Resource.create(
            {
                "service.name": service_name,
                "service.namespace": "yggdrasil",
                "deployment.environment": _env("YGGDRASIL_DEPLOYMENT_ENV") or _env("LANGFUSE_TRACING_ENVIRONMENT") or "local",
            }
        )

    def trace_runtime(self, service_name: str) -> _TraceRuntime | None:
        endpoint = _signal_endpoint("traces")
        if endpoint is None or TracerProvider is None or OTLPSpanExporter is None or BatchSpanProcessor is None:
            return None
        if not self._endpoint_available(endpoint):
            return None

        cache_key = (service_name, endpoint)
        runtime = self._trace_runtimes.get(cache_key)
        if runtime is not None:
            return runtime

        with self._lock:
            runtime = self._trace_runtimes.get(cache_key)
            if runtime is not None:
                return runtime
            exporter = OTLPSpanExporter(endpoint=endpoint, headers=_parse_headers() or None)
            provider = TracerProvider(resource=self._resource(service_name))
            provider.add_span_processor(BatchSpanProcessor(exporter))
            tracer = provider.get_tracer("yggdrasil.observability", "0.1.0")
            runtime = _TraceRuntime(provider=provider, tracer=tracer)
            self._trace_runtimes[cache_key] = runtime
            return runtime

    def metric_runtime(self, service_name: str) -> _MetricRuntime | None:
        endpoint = _signal_endpoint("metrics")
        if endpoint is None or MeterProvider is None or OTLPMetricExporter is None or PeriodicExportingMetricReader is None:
            return None
        if not self._endpoint_available(endpoint):
            return None

        cache_key = (service_name, endpoint)
        runtime = self._metric_runtimes.get(cache_key)
        if runtime is not None:
            return runtime

        with self._lock:
            runtime = self._metric_runtimes.get(cache_key)
            if runtime is not None:
                return runtime
            interval_ms = max(1000, int(_env("YGGDRASIL_OTEL_EXPORT_INTERVAL_MS") or "5000"))
            exporter = OTLPMetricExporter(endpoint=endpoint, headers=_parse_headers() or None)
            reader = PeriodicExportingMetricReader(exporter, export_interval_millis=interval_ms)
            provider = MeterProvider(resource=self._resource(service_name), metric_readers=[reader])
            meter = provider.get_meter("yggdrasil.observability", "0.1.0")
            runtime = _MetricRuntime(provider=provider, meter=meter)
            self._metric_runtimes[cache_key] = runtime
            return runtime

    def langfuse_client(self) -> Any | None:
        public_key = _langfuse_public_key()
        secret_key = _langfuse_secret_key()
        base_url = _langfuse_base_url()
        if public_key is None or secret_key is None or LangfuseClient is None:
            return None
        if not _truthy_env("LANGFUSE_TRACING_ENABLED", default=True):
            return None
        if base_url is None or not self._endpoint_available(base_url):
            return None

        identity = (public_key, secret_key, base_url)
        if self._langfuse_identity == identity and self._langfuse_client is not None:
            return self._langfuse_client

        with self._lock:
            if self._langfuse_identity == identity and self._langfuse_client is not None:
                return self._langfuse_client
            client = LangfuseClient(public_key=public_key, secret_key=secret_key, base_url=base_url)
            self._langfuse_client = client
            self._langfuse_identity = identity
            return client

    def flush(self) -> None:
        for runtime in list(self._trace_runtimes.values()):
            try:
                runtime.provider.force_flush()
            except Exception:
                continue
        for runtime in list(self._metric_runtimes.values()):
            try:
                runtime.provider.force_flush()
            except Exception:
                continue
        client = self.langfuse_client()
        if client is not None:
            try:
                client.flush()
            except Exception as exc:  # noqa: BLE001
                _logger.debug("Langfuse client flush failed (non-fatal): %s", exc)


_STATE = _ExporterState()

_SPAN_KIND_MAP = {
    "internal": SpanKind.INTERNAL if SpanKind is not None else None,
    "server": SpanKind.SERVER if SpanKind is not None else None,
    "client": SpanKind.CLIENT if SpanKind is not None else None,
    "producer": SpanKind.PRODUCER if SpanKind is not None else None,
    "consumer": SpanKind.CONSUMER if SpanKind is not None else None,
    "http.server": SpanKind.SERVER if SpanKind is not None else None,
    "http.client": SpanKind.CLIENT if SpanKind is not None else None,
    "evaluation": SpanKind.INTERNAL if SpanKind is not None else None,
}


def get_exporter_status() -> dict[str, Any]:
    traces_endpoint = _signal_endpoint("traces")
    metrics_endpoint = _signal_endpoint("metrics")
    otel_configured = bool(traces_endpoint or metrics_endpoint)
    otel_ready = bool(otel_configured and TracerProvider is not None and MeterProvider is not None)
    public_key = _langfuse_public_key()
    secret_key = _langfuse_secret_key()
    langfuse_host = _langfuse_base_url()
    langfuse_configured = bool(public_key and secret_key)
    langfuse_endpoint_available = True if not langfuse_configured else bool(langfuse_host and _STATE._endpoint_available(langfuse_host))
    langfuse_ready = bool(
        langfuse_configured
        and LangfuseClient is not None
        and _truthy_env("LANGFUSE_TRACING_ENABLED", default=True)
        and langfuse_endpoint_available
    )
    if langfuse_ready or not langfuse_configured:
        langfuse_detail = None
    elif LangfuseClient is None:
        langfuse_detail = "langfuse sdk is unavailable"
    elif not _truthy_env("LANGFUSE_TRACING_ENABLED", default=True):
        langfuse_detail = "langfuse tracing is disabled"
    elif not langfuse_endpoint_available:
        langfuse_detail = "langfuse local endpoint is unavailable; exporter is optional and disabled for now"
    else:
        langfuse_detail = "langfuse project keys are missing or invalid"
    return {
        "otel": {
            "configured": otel_configured,
            "enabled": otel_ready,
            "ready": otel_ready,
            "transport": "otlp/http",
            "tracesEndpoint": traces_endpoint,
            "metricsEndpoint": metrics_endpoint,
            "detail": None if otel_ready or not otel_configured else "opentelemetry exporter dependencies are unavailable",
        },
        "langfuse": {
            "configured": langfuse_configured,
            "enabled": langfuse_ready,
            "ready": langfuse_ready,
            "host": langfuse_host,
            "detail": langfuse_detail,
        },
    }


def start_otel_span(
    service_name: str,
    name: str,
    *,
    kind: str,
    attributes: dict[str, Any] | None = None,
) -> ActiveOTelSpan | None:
    runtime = _STATE.trace_runtime(service_name)
    if runtime is None or SpanKind is None or format_trace_id is None or format_span_id is None:
        return None

    span_kind = _SPAN_KIND_MAP.get(kind) or SpanKind.INTERNAL
    context_manager = runtime.tracer.start_as_current_span(name, kind=span_kind, attributes=_sanitize_attributes(attributes))
    span = context_manager.__enter__()
    span_context = span.get_span_context()
    parent_context = getattr(span, "parent", None)
    parent_span_id = None
    if parent_context is not None and getattr(parent_context, "span_id", 0):
        parent_span_id = format_span_id(parent_context.span_id)
    return ActiveOTelSpan(
        context_manager=context_manager,
        span=span,
        trace_id=format_trace_id(span_context.trace_id),
        span_id=format_span_id(span_context.span_id),
        parent_span_id=parent_span_id,
    )


def finish_otel_span(
    active_span: ActiveOTelSpan | None,
    *,
    status: str,
    attributes: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    if active_span is None:
        return
    try:
        for key, value in _sanitize_attributes(attributes).items():
            active_span.span.set_attribute(key, value)
        if status == "error" and Status is not None and StatusCode is not None:
            active_span.span.set_status(Status(StatusCode.ERROR, description=error_message or "error"))
    finally:
        active_span.context_manager.__exit__(None, None, None)


def record_otel_metric(
    service_name: str,
    metric_name: str,
    value: float,
    *,
    kind: str,
    unit: str,
    attributes: dict[str, Any] | None = None,
) -> None:
    runtime = _STATE.metric_runtime(service_name)
    if runtime is None:
        return

    instrument_key = (metric_name, kind, unit)
    instrument = runtime.instruments.get(instrument_key)
    if instrument is None:
        if kind == "histogram":
            instrument = runtime.meter.create_histogram(metric_name, unit=unit)
        elif kind == "updowncounter":
            instrument = runtime.meter.create_up_down_counter(metric_name, unit=unit)
        else:
            instrument = runtime.meter.create_counter(metric_name, unit=unit)
        runtime.instruments[instrument_key] = instrument

    metric_attributes = _sanitize_attributes(attributes)
    if kind == "histogram":
        instrument.record(float(value), attributes=metric_attributes)
    else:
        instrument.add(float(value), attributes=metric_attributes)


def start_langfuse_generation(
    *,
    trace_id: str | None,
    name: str,
    input_payload: Any,
    model: str | None,
    model_parameters: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> Any | None:
    client = _STATE.langfuse_client()
    if client is None:
        return None
    try:
        trace_context = {"trace_id": trace_id} if trace_id else None
        return client.start_observation(
            trace_context=trace_context,
            name=name,
            as_type="generation",
            input=input_payload,
            metadata=metadata,
            model=model,
            model_parameters=model_parameters,
        )
    except Exception:
        return None


def finish_langfuse_generation(
    generation: Any | None,
    *,
    output: Any = None,
    metadata: dict[str, Any] | None = None,
    usage_details: dict[str, int] | None = None,
    cost_details: dict[str, float] | None = None,
    model: str | None = None,
    level: str | None = None,
    status_message: str | None = None,
) -> None:
    if generation is None:
        return
    try:
        update_payload: dict[str, Any] = {}
        if output is not None:
            update_payload["output"] = output
        if metadata is not None:
            update_payload["metadata"] = metadata
        if usage_details is not None:
            update_payload["usage_details"] = usage_details
        if cost_details is not None:
            update_payload["cost_details"] = cost_details
        if model is not None:
            update_payload["model"] = model
        if level is not None:
            update_payload["level"] = level
        if status_message is not None:
            update_payload["status_message"] = status_message
        if update_payload:
            generation.update(**update_payload)
    finally:
        try:
            generation.end()
        except Exception as exc:  # noqa: BLE001
            _logger.debug("Langfuse generation.end() failed (non-fatal): %s", exc)


def flush_observability_exporters() -> None:
    _STATE.flush()
