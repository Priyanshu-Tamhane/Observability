from contextlib import asynccontextmanager
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from prometheus_client import make_asgi_app
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.config import settings
from app.telemetry.logging import setup_logging, logger
from app.telemetry.tracing import init_tracing
from app.agent import ObservableAgent
from app.tools import calculator, search_knowledge

class AgentRunRequest(BaseModel):
    prompt: str = Field(..., description="User prompt for the agent")
    simulate_llm_failure: bool = Field(False, description="Force LLM service failure")
    simulate_tool_failure: bool = Field(False, description="Force tool execution failure")
    simulate_timeout: bool = Field(False, description="Force agent execution timeout")

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)
    init_tracing()
    logger.info("Observable Agent API initialized.")
    yield

app = FastAPI(
    title="Observable Agent System",
    description="Production-style agentic AI system for learning OpenTelemetry observability.",
    version="0.1.0",
    lifespan=lifespan
)

# Auto-instrument FastAPI incoming HTTP requests
FastAPIInstrumentor.instrument_app(app)

# Mount Prometheus metrics endpoint
app.mount("/metrics", make_asgi_app())

agent = ObservableAgent()

@app.get("/health")
async def health_check() -> Dict[str, str]:
    return {"status": "ok", "service": settings.otel_service_name}

@app.post("/agent/run")
async def run_agent(request: AgentRunRequest) -> Dict[str, Any]:
    try:
        return await agent.run(
            user_request=request.prompt,
            simulate_llm_failure=request.simulate_llm_failure,
            simulate_tool_failure=request.simulate_tool_failure,
            simulate_timeout=request.simulate_timeout
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

@app.get("/tool")
async def test_tool(
    name: str = Query("calculator", description="Tool name: calculator or search_knowledge"),
    input: str = Query("25 * 17", description="Input string"),
    failure: bool = Query(False, description="Trigger failure scenario")
) -> Dict[str, Any]:
    try:
        if name == "calculator":
            res = await calculator(expression=input, simulate_failure=failure)
        elif name == "search_knowledge":
            res = await search_knowledge(query=input, simulate_failure=failure)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown tool: {name}")

        return {"tool": name, "input": input, "output": res, "status": "success"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
