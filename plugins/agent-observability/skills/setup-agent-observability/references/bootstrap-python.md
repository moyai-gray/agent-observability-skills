# Bootstrap: Python

Last verified: 2026-11-09 (`opentelemetry-sdk` 1.45.2, exporters 1.45.2).

Programmatic setup: one `telemetry.py` module per unit that builds the trace, metric and log providers, then registers the instrumentations. It reads the standard `OTEL_*` env vars itself, so the destination, protocol and per-signal on/off switches live in env, not code.

## Packages

- `opentelemetry-sdk`
- `opentelemetry-exporter-otlp-proto-http`, or `opentelemetry-exporter-otlp-proto-grpc` when the user chose gRPC
- the instrumentation packages from the plan

Install with the unit's package manager (`uv add`, `poetry add`, `pip install` plus a `requirements.txt` line, …), matching how the project already declares dependencies.

## Existing setup

If the unit already configures OTel (`TracerProvider` construction, `opentelemetry-instrument` in its start command, `logfire.configure()`, Sentry with OTel, `configure_azure_monitor()`, …), don't add this module. Keep its existing exporters and settings: replacing or removing one changes where the team's telemetry goes, so propose it and wait for a yes. Instead:

- Call each new instrumentor's `.instrument()` right after the existing setup runs.
- If the destination is new, add a `BatchSpanProcessor(OTLPSpanExporter(...))` to the existing `TracerProvider`. Do the same for metrics and logs only if the existing setup has those providers.
- If the existing setup uses `opentelemetry-instrument`, installing the instrumentation packages is enough: it discovers them through entry points. Only env vars need adding.

## `telemetry.py`

Put it beside the entrypoint (in the package, if the unit is a package):

```python
"""OpenTelemetry bootstrap. Import before anything that imports an LLM client.

Reads standard env: OTEL_SERVICE_NAME, OTEL_RESOURCE_ATTRIBUTES, OTEL_EXPORTER_OTLP_ENDPOINT,
OTEL_EXPORTER_OTLP_HEADERS, OTEL_EXPORTER_OTLP_PROTOCOL, and
OTEL_{TRACES,METRICS,LOGS}_EXPORTER (otlp | console | none, comma-separated).
"""
import os

from opentelemetry import _logs, metrics, trace
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogRecordExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import ConsoleMetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter


def _exporters(signal: str) -> list[str]:
    raw = os.environ.get(f"OTEL_{signal.upper()}_EXPORTER", "otlp")
    return [n.strip() for n in raw.split(",") if n.strip() and n.strip() != "none"]


def _grpc(signal: str) -> bool:
    proto = os.environ.get(f"OTEL_EXPORTER_OTLP_{signal.upper()}_PROTOCOL") or os.environ.get(
        "OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf"
    )
    return proto == "grpc"


def _otlp(signal: str):
    # Import lazily so only the installed transport (http or grpc) is needed.
    if _grpc(signal):
        from opentelemetry.exporter.otlp.proto.grpc import _log_exporter, metric_exporter, trace_exporter
    else:
        from opentelemetry.exporter.otlp.proto.http import _log_exporter, metric_exporter, trace_exporter
    return {
        "traces": trace_exporter.OTLPSpanExporter,
        "metrics": metric_exporter.OTLPMetricExporter,
        "logs": _log_exporter.OTLPLogExporter,
    }[signal]()


_CONSOLE = {"traces": ConsoleSpanExporter, "metrics": ConsoleMetricExporter, "logs": ConsoleLogRecordExporter}


def _make(signal: str, name: str):
    return _otlp(signal) if name == "otlp" else _CONSOLE[signal]()


resource = Resource.create()  # picks up OTEL_SERVICE_NAME and OTEL_RESOURCE_ATTRIBUTES

if names := _exporters("traces"):
    tracer_provider = TracerProvider(resource=resource)
    for n in names:
        tracer_provider.add_span_processor(BatchSpanProcessor(_make("traces", n)))
    trace.set_tracer_provider(tracer_provider)

if names := _exporters("metrics"):
    readers = [PeriodicExportingMetricReader(_make("metrics", n)) for n in names]
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=readers))

if names := _exporters("logs"):
    logger_provider = LoggerProvider(resource=resource)
    for n in names:
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(_make("logs", n)))
    _logs.set_logger_provider(logger_provider)

# Instrumentations go below this line, after the providers exist. Example:
# from opentelemetry.instrumentation.genai.openai import OpenAIInstrumentor
# OpenAIInstrumentor().instrument()
```

`_logs` and `opentelemetry.sdk._logs` are still underscore-private in 1.45. That is the documented way to configure logs; keep the import paths exactly as written. Providers shut down (and flush) at interpreter exit by default.

## Loading it first

Import `telemetry` as the first import of every entrypoint that leads to LLM calls (`main.py`, `app/__init__.py`, the CLI module, the Celery worker module, the Lambda handler module):

```python
import telemetry  # noqa: F401  (must stay first: sets up OpenTelemetry)
```

Mark it so formatters and import sorters leave it at the top (`# isort: skip` / `# noqa: E402` on the lines after, or the project's ruff/isort config). Process managers and reloaders (uvicorn `--reload`/`--workers`, gunicorn, Celery prefork) re-import the app module in each worker, so importing from the app module covers them. Importing `telemetry.py` from a launcher script that only spawns workers does not.

## Short-lived and serverless processes

- **Scripts and CLIs**: exit normally, so the atexit shutdown can flush. `os._exit()` skips it.
- **Lambda / Cloud Functions**: flush before the handler returns, because the instance can freeze before the batch processors export:

  ```python
  from opentelemetry import _logs, metrics, trace

  def flush_telemetry() -> None:
      for provider in (trace.get_tracer_provider(), metrics.get_meter_provider(), _logs.get_logger_provider()):
          if hasattr(provider, "force_flush"):
              provider.force_flush()
  ```

  Call it in a `finally:` at the end of the handler.

## Notebooks

Import `telemetry` in the first cell. Re-running that cell would set the providers twice, which OTel rejects with a warning; tell the user to restart the kernel instead.
