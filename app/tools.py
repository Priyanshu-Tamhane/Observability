import time
import functools
import asyncio
from typing import Callable, Any
from opentelemetry.trace import Status, StatusCode

from app.telemetry.tracing import get_tracer
from app.telemetry.logging import logger
from app.telemetry.metrics import TOOL_CALLS, TOOL_CALL_DURATION

def observable_tool(name: str):
    """
    Decorator for tools.
    Creates an OpenTelemetry span, logs execution events, handles errors, and updates metrics.
    """
    def decorator(func: Callable[..., Any]):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.perf_counter()
            tool_name = name or func.__name__
            tracer = get_tracer("tools")

            with tracer.start_as_current_span("tool.call") as span:
                span.set_attribute("tool.name", tool_name)
                input_val = str(args[0]) if args else str(kwargs.get("expression") or kwargs.get("query") or "")
                span.set_attribute("tool.input", input_val)

                logger.info(f"Tool execution started: {tool_name}", extra={"tool_name": tool_name, "input": input_val})

                try:
                    result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
                    duration = time.perf_counter() - start_time
                    duration_ms = round(duration * 1000, 2)

                    span.set_attribute("tool.success", True)
                    span.set_attribute("tool.duration_ms", duration_ms)
                    span.set_status(Status(StatusCode.OK))

                    logger.info(
                        f"Tool execution succeeded: {tool_name}",
                        extra={"tool_name": tool_name, "duration_ms": duration_ms, "result": str(result)[:100]}
                    )

                    TOOL_CALLS.labels(tool_name=tool_name, status="success").inc()
                    TOOL_CALL_DURATION.labels(tool_name=tool_name).observe(duration)
                    return result

                except Exception as exc:
                    duration = time.perf_counter() - start_time
                    duration_ms = round(duration * 1000, 2)

                    span.set_status(Status(StatusCode.ERROR, str(exc)))
                    span.record_exception(exc)
                    span.set_attribute("tool.success", False)
                    span.set_attribute("tool.duration_ms", duration_ms)

                    logger.error(
                        f"Tool execution failed: {tool_name}",
                        extra={"tool_name": tool_name, "duration_ms": duration_ms, "error": str(exc)},
                        exc_info=True
                    )

                    TOOL_CALLS.labels(tool_name=tool_name, status="error").inc()
                    TOOL_CALL_DURATION.labels(tool_name=tool_name).observe(duration)
                    raise

        return wrapper
    return decorator


@observable_tool(name="calculator")
async def calculator(expression: str, simulate_failure: bool = False) -> str:
    """Evaluates basic math expressions safely."""
    if simulate_failure or "simulate tool failure" in expression.lower():
        raise ValueError(f"Simulated Calculator Failure for '{expression}'")

    sanitized = expression.replace("^", "**").strip()
    if not all(c in "0123456789+-*/(). " for c in sanitized):
        raise ValueError(f"Invalid characters in math expression: {expression}")

    try:
        return str(eval(sanitized, {"__builtins__": None}, {}))
    except Exception as e:
        raise ValueError(f"Failed to evaluate '{expression}': {str(e)}")


KNOWLEDGE_BASE = {
    "opentelemetry": "OpenTelemetry (OTel) is a CNCF framework providing standardized APIs, SDKs, and tools for generating and exporting telemetry.",
    "distributed tracing": "Distributed tracing tracks requests across service boundaries using Trace IDs and Span IDs.",
    "spans": "A span represents a single contiguous unit of work within a trace, storing timestamps, status, attributes, and events.",
    "log correlation": "Log correlation embeds trace_id and span_id in structured JSON logs to link log records with traces.",
    "metrics": "Metrics measure aggregated numeric values over time (counters, histograms) to track performance and error rates.",
}

@observable_tool(name="search_knowledge")
async def search_knowledge(query: str, simulate_failure: bool = False) -> str:
    """Searches local knowledge base."""
    if simulate_failure or "simulate tool failure" in query.lower():
        raise KeyError(f"Simulated Search Failure for '{query}'")

    query_lower = query.lower()
    for key, content in KNOWLEDGE_BASE.items():
        if key in query_lower:
            return f"Match for '{key}': {content}"

    return f"No exact match found in knowledge base for query: '{query}'."
    