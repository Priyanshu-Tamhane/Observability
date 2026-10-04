import json
import logging
import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from app.agent import ObservableAgent
from app.llm import ObservableLLM
from app.tools import calculator
from app.telemetry.logging import JSONTraceFormatter

@pytest.fixture(scope="session")
def memory_exporter():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    return exporter

@pytest.fixture(autouse=True)
def clear_spans(memory_exporter):
    memory_exporter.clear()
    yield memory_exporter

@pytest.mark.asyncio
async def test_llm_call_creates_span(memory_exporter):
    llm = ObservableLLM(provider="mock", model="mock-gpt-4o")
    res = await llm.generate("Hello world")
    
    spans = memory_exporter.get_finished_spans()
    assert len(spans) == 1
    llm_span = spans[0]
    assert llm_span.name == "llm.call"
    assert llm_span.attributes["llm.provider"] == "mock"
    assert llm_span.attributes["llm.request_tokens"] > 0
    assert llm_span.attributes["llm.success"] is True

@pytest.mark.asyncio
async def test_tool_call_creates_span(memory_exporter):
    res = await calculator("10 + 5")
    assert res == "15"
    
    spans = memory_exporter.get_finished_spans()
    assert len(spans) == 1
    tool_span = spans[0]
    assert tool_span.name == "tool.call"
    assert tool_span.attributes["tool.name"] == "calculator"
    assert tool_span.attributes["tool.success"] is True

@pytest.mark.asyncio
async def test_agent_creates_nested_trace(memory_exporter):
    agent = ObservableAgent()
    await agent.run(user_request="Calculate 25 * 17")
    
    spans = memory_exporter.get_finished_spans()
    span_names = [s.name for s in spans]
    
    assert "agent.run" in span_names
    assert "agent.plan" in span_names
    assert "llm.call" in span_names
    assert "tool.call" in span_names

@pytest.mark.asyncio
async def test_errors_mark_span_as_error(memory_exporter):
    agent = ObservableAgent()
    with pytest.raises(Exception):
        await agent.run(user_request="Test prompt", simulate_llm_failure=True)
        
    spans = memory_exporter.get_finished_spans()
    error_spans = [s for s in spans if s.status.status_code == StatusCode.ERROR]
    assert len(error_spans) > 0

def test_logs_contain_trace_id():
    formatter = JSONTraceFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Test log message",
        args=(),
        exc_info=None
    )
    formatted = formatter.format(record)
    data = json.loads(formatted)
    
    assert "trace_id" in data
    assert "span_id" in data
    assert data["message"] == "Test log message"
