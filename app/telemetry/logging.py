import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict
from opentelemetry import trace

class JSONTraceFormatter(logging.Formatter):
    """
    Structured JSON log formatter that dynamically injects trace_id and span_id
    from the current OpenTelemetry context into every log record.
    """
    def format(self, record: logging.LogRecord) -> str:
        span = trace.get_current_span()
        span_ctx = span.get_span_context() if span else None

        trace_id = f"{span_ctx.trace_id:032x}" if (span_ctx and span_ctx.is_valid) else "0" * 32
        span_id = f"{span_ctx.span_id:016x}" if (span_ctx and span_ctx.is_valid) else "0" * 16

        log_record: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": trace_id,
            "span_id": span_id,
        }

        # Include custom extra fields passed to logger calls
        ignored_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message"
        }
        for key, val in record.__dict__.items():
            if key not in ignored_attrs and not key.startswith("_"):
                log_record[key] = val

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record)

def setup_logging(log_level: str = "INFO") -> logging.Logger:
    """Configures root logger with JSONTraceFormatter."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONTraceFormatter())
    root_logger.addHandler(handler)

    # Silence noisy default access loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    return root_logger

logger = logging.getLogger("observable-agent")
