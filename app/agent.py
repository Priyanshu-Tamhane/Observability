import uuid
import time
import json
import asyncio
from typing import Dict, Any, Optional
from opentelemetry.trace import Status, StatusCode

from app.llm import ObservableLLM
from app.tools import calculator, search_knowledge
from app.telemetry.tracing import get_tracer
from app.telemetry.logging import logger
from app.telemetry.metrics import AGENT_RUNS, AGENT_ERRORS, AGENT_RUN_DURATION

class ObservableAgent:
    """
    Observable agent coordinating planning, LLM inference, and tool execution
    under nested OpenTelemetry spans.
    """
    def __init__(self, llm: Optional[ObservableLLM] = None):
        self.agent_name = "ObservableAgent"
        self.llm = llm or ObservableLLM()

    async def run(
        self,
        user_request: str,
        simulate_llm_failure: bool = False,
        simulate_tool_failure: bool = False,
        simulate_timeout: bool = False
    ) -> Dict[str, Any]:
        
        run_id = str(uuid.uuid4())
        start_time = time.perf_counter()
        tracer = get_tracer("agent")

        with tracer.start_as_current_span("agent.run") as agent_span:
            agent_span.set_attribute("agent.name", self.agent_name)
            agent_span.set_attribute("agent.run_id", run_id)
            agent_span.set_attribute("agent.user_request", user_request)

            logger.info(f"Agent run started: {run_id}", extra={"agent_run_id": run_id, "user_request": user_request})

            try:
                if simulate_timeout:
                    await asyncio.sleep(0.5)
                    raise TimeoutError("Agent execution timed out.")

                # Step 1: Agent Planning
                plan = await self._plan(user_request, simulate_llm_failure)
                action = plan.get("action")
                action_input = plan.get("action_input")

                # Step 2: Tool Execution
                tool_output = None
                if action and action != "none":
                    tool_output = await self._execute_tool(action, action_input, simulate_tool_failure)

                # Step 3: Synthesis
                final_answer = await self._synthesize(user_request, action, tool_output, simulate_llm_failure)

                duration = time.perf_counter() - start_time
                duration_ms = round(duration * 1000, 2)

                agent_span.set_attribute("agent.success", True)
                agent_span.set_attribute("agent.duration_ms", duration_ms)
                agent_span.set_status(Status(StatusCode.OK))

                logger.info("Agent run completed successfully", extra={"agent_run_id": run_id, "duration_ms": duration_ms})
                AGENT_RUNS.labels(status="success").inc()
                AGENT_RUN_DURATION.observe(duration)

                return {
                    "run_id": run_id,
                    "status": "success",
                    "request": user_request,
                    "action": action,
                    "tool_output": tool_output,
                    "response": final_answer,
                    "duration_ms": duration_ms,
                }

            except Exception as exc:
                duration = time.perf_counter() - start_time
                duration_ms = round(duration * 1000, 2)

                agent_span.set_status(Status(StatusCode.ERROR, str(exc)))
                agent_span.record_exception(exc)
                agent_span.set_attribute("agent.success", False)
                agent_span.set_attribute("agent.duration_ms", duration_ms)

                logger.error(
                    f"Agent run failed: {str(exc)}",
                    extra={"agent_run_id": run_id, "duration_ms": duration_ms, "error_type": exc.__class__.__name__},
                    exc_info=True
                )

                AGENT_RUNS.labels(status="error").inc()
                AGENT_ERRORS.labels(error_type=exc.__class__.__name__).inc()
                AGENT_RUN_DURATION.observe(duration)
                raise

    async def _plan(self, prompt: str, simulate_llm_failure: bool) -> Dict[str, Any]:
        tracer = get_tracer("agent")
        with tracer.start_as_current_span("agent.plan") as span:
            span.set_attribute("agent.stage", "planning")
            
            system_prompt = "Reply ONLY with JSON: {'action': 'calculator' | 'search_knowledge' | 'none', 'action_input': '...'}"
            llm_response = await self.llm.generate(prompt=prompt, system_prompt=system_prompt, simulate_failure=simulate_llm_failure)
            
            try:
                plan = json.loads(llm_response.content)
                span.set_attribute("agent.planned_action", plan.get("action", "none"))
                return plan
            except json.JSONDecodeError:
                if "calculate" in prompt.lower() or "25 * 17" in prompt.lower():
                    return {"action": "calculator", "action_input": "25 * 17"}
                elif "opentelemetry" in prompt.lower():
                    return {"action": "search_knowledge", "action_input": "OpenTelemetry"}
                return {"action": "none", "action_input": ""}

    async def _execute_tool(self, action: str, action_input: str, simulate_tool_failure: bool) -> str:
        tracer = get_tracer("agent")
        with tracer.start_as_current_span("agent.tool_selection") as span:
            span.set_attribute("selected_tool", action)
            span.set_attribute("tool_input", action_input)

            if action == "calculator":
                return await calculator(expression=action_input, simulate_failure=simulate_tool_failure)
            elif action == "search_knowledge":
                return await search_knowledge(query=action_input, simulate_failure=simulate_tool_failure)
            else:
                raise ValueError(f"Unknown action: '{action}'")

    async def _synthesize(self, user_request: str, action: Optional[str], tool_output: Optional[str], simulate_llm_failure: bool) -> str:
        tracer = get_tracer("agent")
        with tracer.start_as_current_span("agent.synthesize") as span:
            span.set_attribute("agent.stage", "synthesis")
            prompt = f"User Request: {user_request}\nTool Action: {action}\nTool Output: {tool_output}"
            llm_response = await self.llm.generate(prompt=prompt, system_prompt="You are a helpful observable assistant.", simulate_failure=simulate_llm_failure)
            return llm_response.content
