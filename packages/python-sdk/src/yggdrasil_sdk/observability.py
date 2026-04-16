from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from time import perf_counter
from typing import Any, Iterator
from uuid import uuid4

from .observability_exporters import finish_otel_span, get_exporter_status, record_otel_metric, start_otel_span
from .support import append_jsonl, ensure_state_subdir, read_jsonl, utc_now


def _observability_dir(workspace_root: Path | None = None) -> Path:
    return ensure_state_subdir("observability", workspace_root)


def _observability_file(name: str, workspace_root: Path | None = None) -> Path:
    return _observability_dir(workspace_root) / name


def _new_trace_id() -> str:
    return uuid4().hex


def _new_span_id() -> str:
    return uuid4().hex[:16]


def record_metric(
    service_name: str,
    metric_name: str,
    value: float,
    *,
    kind: str = "counter",
    unit: str = "count",
    attributes: dict[str, Any] | None = None,
    workspace_root: Path | None = None,
) -> None:
    append_jsonl(
        _observability_file("metrics.jsonl", workspace_root),
        {
            "capturedAt": utc_now().isoformat(),
            "serviceName": service_name,
            "metricName": metric_name,
            "kind": kind,
            "unit": unit,
            "value": value,
            "attributes": dict(attributes or {}),
        },
    )
    try:
        record_otel_metric(service_name, metric_name, value, kind=kind, unit=unit, attributes=attributes)
    except Exception:
        pass


def record_log(
    service_name: str,
    level: str,
    message: str,
    *,
    attributes: dict[str, Any] | None = None,
    workspace_root: Path | None = None,
) -> None:
    append_jsonl(
        _observability_file("logs.jsonl", workspace_root),
        {
            "capturedAt": utc_now().isoformat(),
            "serviceName": service_name,
            "level": level,
            "message": message,
            "attributes": dict(attributes or {}),
        },
    )


@contextmanager
def observe_span(
    service_name: str,
    name: str,
    *,
    kind: str = "internal",
    trace_id: str | None = None,
    parent_span_id: str | None = None,
    attributes: dict[str, Any] | None = None,
    workspace_root: Path | None = None,
) -> Iterator[dict[str, Any]]:
    started_at = utc_now()
    started_counter = perf_counter()
    span_attributes = dict(attributes or {})
    otel_span = None
    try:
        otel_span = start_otel_span(service_name, name, kind=kind, attributes=span_attributes)
    except Exception:
        otel_span = None
    span_context = {
        "traceId": trace_id or (otel_span.trace_id if otel_span is not None else _new_trace_id()),
        "spanId": otel_span.span_id if otel_span is not None else _new_span_id(),
        "parentSpanId": parent_span_id or (otel_span.parent_span_id if otel_span is not None else None),
        "attributes": span_attributes,
    }
    status = "ok"

    try:
        yield span_context
    except Exception as exc:
        status = "error"
        span_attributes.setdefault("errorType", exc.__class__.__name__)
        span_attributes.setdefault("errorMessage", str(exc))
        raise
    finally:
        ended_at = utc_now()
        duration_ms = round((perf_counter() - started_counter) * 1000.0, 2)
        try:
            finish_otel_span(
                otel_span,
                status=status,
                attributes=span_attributes,
                error_message=str(span_attributes.get("errorMessage")) if status == "error" else None,
            )
        except Exception:
            pass
        append_jsonl(
            _observability_file("spans.jsonl", workspace_root),
            {
                "traceId": span_context["traceId"],
                "spanId": span_context["spanId"],
                "parentSpanId": span_context["parentSpanId"],
                "serviceName": service_name,
                "name": name,
                "kind": kind,
                "status": status,
                "startedAt": started_at.isoformat(),
                "endedAt": ended_at.isoformat(),
                "durationMs": duration_ms,
                "attributes": span_attributes,
            },
        )
        record_metric(
            service_name,
            "span.count",
            1,
            kind="counter",
            attributes={"name": name, "kind": kind, "status": status},
            workspace_root=workspace_root,
        )
        record_metric(
            service_name,
            "span.duration",
            duration_ms,
            kind="histogram",
            unit="ms",
            attributes={"name": name, "kind": kind, "status": status},
            workspace_root=workspace_root,
        )
        if status == "error":
            record_metric(
                service_name,
                "span.error",
                1,
                kind="counter",
                attributes={"name": name, "kind": kind},
                workspace_root=workspace_root,
            )


def instrument_fastapi_app(app: Any, service_name: str) -> None:
    if getattr(app.state, "yggdrasil_observability_enabled", False):
        return

    app.state.yggdrasil_observability_enabled = True

    @app.middleware("http")
    async def _observability_http_middleware(request, call_next):
        path = str(getattr(request.url, "path", "/"))
        method = str(getattr(request, "method", "GET"))
        with observe_span(
            service_name,
            f"{method} {path}",
            kind="http.server",
            attributes={
                "http.method": method,
                "http.path": path,
                "http.query": str(getattr(request.url, "query", "")),
            },
        ) as span:
            try:
                response = await call_next(request)
            except Exception as exc:
                record_log(
                    service_name,
                    "error",
                    f"Unhandled request failure: {method} {path}",
                    attributes={
                        "traceId": span["traceId"],
                        "spanId": span["spanId"],
                        "errorType": exc.__class__.__name__,
                        "errorMessage": str(exc),
                    },
                )
                raise

            status_code = int(getattr(response, "status_code", 200))
            span["attributes"]["http.statusCode"] = status_code
            response.headers["x-yggdrasil-trace-id"] = span["traceId"]
            response.headers["x-yggdrasil-span-id"] = span["spanId"]
            record_metric(
                service_name,
                "http.request",
                1,
                kind="counter",
                attributes={
                    "http.method": method,
                    "http.path": path,
                    "http.statusCode": status_code,
                },
            )
            if status_code >= 500:
                record_log(
                    service_name,
                    "error",
                    f"Server error response: {method} {path}",
                    attributes={
                        "traceId": span["traceId"],
                        "spanId": span["spanId"],
                        "http.statusCode": status_code,
                    },
                )
            return response


def summarize_observability(
    *,
    limit: int = 60,
    service_name: str | None = None,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    spans = read_jsonl(_observability_file("spans.jsonl", workspace_root), limit=None)
    logs = read_jsonl(_observability_file("logs.jsonl", workspace_root), limit=None)
    metrics = read_jsonl(_observability_file("metrics.jsonl", workspace_root), limit=None)

    if service_name is not None:
        spans = [row for row in spans if row.get("serviceName") == service_name]
        logs = [row for row in logs if row.get("serviceName") == service_name]
        metrics = [row for row in metrics if row.get("serviceName") == service_name]

    service_names = sorted(
        {
            *(str(row.get("serviceName")) for row in spans if row.get("serviceName")),
            *(str(row.get("serviceName")) for row in logs if row.get("serviceName")),
            *(str(row.get("serviceName")) for row in metrics if row.get("serviceName")),
        }
    )

    service_summaries: list[dict[str, Any]] = []
    for candidate in service_names:
        service_spans = [row for row in spans if row.get("serviceName") == candidate]
        service_logs = [row for row in logs if row.get("serviceName") == candidate]
        service_metrics = [row for row in metrics if row.get("serviceName") == candidate]
        durations = [float(row.get("durationMs") or 0.0) for row in service_spans]
        counters: dict[str, float] = {}
        gauges: dict[str, float] = {}
        for metric in service_metrics:
            metric_name = str(metric.get("metricName") or "unknown")
            metric_kind = str(metric.get("kind") or "counter")
            metric_value = float(metric.get("value") or 0.0)
            if metric_kind == "counter":
                counters[metric_name] = counters.get(metric_name, 0.0) + metric_value
            else:
                gauges[metric_name] = metric_value
        service_summaries.append(
            {
                "serviceName": candidate,
                "spanCount": len(service_spans),
                "errorCount": len([row for row in service_spans if row.get("status") == "error"])
                + len([row for row in service_logs if str(row.get("level") or "info").lower() == "error"]),
                "avgDurationMs": round(sum(durations) / len(durations), 2) if durations else 0.0,
                "lastSeenAt": max(
                    [str(row.get("endedAt") or row.get("capturedAt") or "") for row in [*service_spans, *service_logs, *service_metrics]],
                    default=None,
                ),
                "counters": counters,
                "gauges": gauges,
            }
        )

    return {
        "generatedAt": utc_now().isoformat(),
        "serviceSummaries": service_summaries,
        "recentSpans": list(reversed(spans[-limit:])),
        "recentLogs": list(reversed(logs[-limit:])),
        "metricSamples": list(reversed(metrics[-limit:])),
        "totalSpans": len(spans),
        "totalLogs": len(logs),
        "totalMetrics": len(metrics),
        "exporters": get_exporter_status(),
    }