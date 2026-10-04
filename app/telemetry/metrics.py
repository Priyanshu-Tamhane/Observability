from prometheus_client import Counter, Histogram

# Agent Metrics
AGENT_RUNS = Counter("agent_runs_total", "Total agent executions", ["status"])
AGENT_ERRORS = Counter("agent_errors_total", "Total agent errors", ["error_type"])
AGENT_RUN_DURATION = Histogram("agent_run_duration_seconds", "Agent run latency", buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0])

# LLM Metrics
LLM_CALLS = Counter("llm_calls_total", "Total LLM calls", ["provider", "model", "status"])
LLM_CALL_DURATION = Histogram("llm_call_duration_seconds", "LLM call latency", ["provider", "model"], buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0])
LLM_INPUT_TOKENS = Counter("llm_input_tokens_total", "LLM input tokens consumed", ["provider", "model"])
LLM_OUTPUT_TOKENS = Counter("llm_output_tokens_total", "LLM output tokens generated", ["provider", "model"])
LLM_TOTAL_TOKENS = Counter("llm_total_tokens_total", "Total LLM tokens", ["provider", "model"])
LLM_COST_USD = Counter("llm_cost_usd_total", "Estimated LLM cost in USD", ["provider", "model"])

# Tool Metrics
TOOL_CALLS = Counter("tool_calls_total", "Total tool calls", ["tool_name", "status"])
TOOL_CALL_DURATION = Histogram("tool_call_duration_seconds", "Tool call latency", ["tool_name"], buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0])

# Model pricing table per 1,000 tokens
MODEL_PRICING = {
    "mock-gpt-4o": {"input": 0.0001, "output": 0.0002},
    "gpt-4o": {"input": 0.0025, "output": 0.0100},
    "gemini-1.5-flash": {"input": 0.000075, "output": 0.0003},
}

def calculate_llm_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculates estimated USD cost based on token counts."""
    rates = MODEL_PRICING.get(model, {"input": 0.0001, "output": 0.0002})
    cost = (input_tokens / 1000.0 * rates["input"]) + (output_tokens / 1000.0 * rates["output"])
    return round(cost, 6)
