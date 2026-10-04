import time
import json
import asyncio
from dataclasses import dataclass
from typing import Dict, Any, Optional
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from app.config import settings
from app.telemetry.tracing import get_tracer
from app.telemetry.logging import logger
from app.telemetry.metrics import (
    LLM_CALLS, LLM_CALL_DURATION, LLM_INPUT_TOKENS,
    LLM_OUTPUT_TOKENS, LLM_TOTAL_TOKENS, LLM_COST_USD, calculate_llm_cost
)

@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
    raw_response: Dict[str, Any]

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

class ObservableLLM:
    """
    Observable wrapper around LLM API clients using official provider SDKs.
    Automatically creates OpenTelemetry spans, measures latency, records token usage,
    logs structured events, and updates Prometheus metrics.
    """
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        self.provider = provider or settings.llm_provider
        self.model = model or settings.llm_model

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, simulate_failure: bool = False) -> LLMResponse:
        start_time = time.perf_counter()
        tracer = get_tracer("llm")

        with tracer.start_as_current_span("llm.call") as span:
            span.set_attribute("llm.provider", self.provider)
            span.set_attribute("llm.model", self.model)
            span.set_attribute("prompt.length", len(prompt))

            try:
                if simulate_failure or "simulate llm failure" in prompt.lower():
                    raise RuntimeError("Simulated LLM service error: Provider rate limit or timeout.")

                response = await self._call_provider(prompt, system_prompt)
                duration = time.perf_counter() - start_time
                duration_ms = round(duration * 1000, 2)
                cost = calculate_llm_cost(self.model, response.input_tokens, response.output_tokens)

                # Record Telemetry Attributes on Span
                span.set_attribute("llm.request_tokens", response.input_tokens)
                span.set_attribute("llm.response_tokens", response.output_tokens)
                span.set_attribute("llm.total_tokens", response.total_tokens)
                span.set_attribute("llm.cost_usd", cost)
                span.set_attribute("llm.latency_ms", duration_ms)
                span.set_attribute("llm.success", True)
                span.set_status(Status(StatusCode.OK))

                logger.info(
                    "LLM call completed successfully",
                    extra={
                        "llm_provider": self.provider,
                        "llm_model": self.model,
                        "duration_ms": duration_ms,
                        "input_tokens": response.input_tokens,
                        "output_tokens": response.output_tokens,
                        "total_tokens": response.total_tokens,
                        "cost_usd": cost,
                    }
                )

                # Update Prometheus Metrics
                LLM_CALLS.labels(provider=self.provider, model=self.model, status="success").inc()
                LLM_CALL_DURATION.labels(provider=self.provider, model=self.model).observe(duration)
                LLM_INPUT_TOKENS.labels(provider=self.provider, model=self.model).inc(response.input_tokens)
                LLM_OUTPUT_TOKENS.labels(provider=self.provider, model=self.model).inc(response.output_tokens)
                LLM_TOTAL_TOKENS.labels(provider=self.provider, model=self.model).inc(response.total_tokens)
                LLM_COST_USD.labels(provider=self.provider, model=self.model).inc(cost)

                return response

            except Exception as exc:
                duration = time.perf_counter() - start_time
                duration_ms = round(duration * 1000, 2)

                span.set_status(Status(StatusCode.ERROR, str(exc)))
                span.record_exception(exc)
                span.set_attribute("llm.success", False)

                logger.error(
                    f"LLM call failed: {str(exc)}",
                    extra={
                        "llm_provider": self.provider,
                        "llm_model": self.model,
                        "duration_ms": duration_ms,
                        "error": str(exc),
                    },
                    exc_info=True
                )

                LLM_CALLS.labels(provider=self.provider, model=self.model, status="error").inc()
                LLM_CALL_DURATION.labels(provider=self.provider, model=self.model).observe(duration)
                raise

    async def _call_provider(self, prompt: str, system_prompt: Optional[str]) -> LLMResponse:
        if self.provider == "openai" and settings.openai_api_key:
            return await self._call_openai(prompt, system_prompt)
        elif self.provider == "gemini" and settings.gemini_api_key:
            return await self._call_gemini(prompt, system_prompt)
        return await self._call_mock(prompt, system_prompt)

    async def _call_mock(self, prompt: str, system_prompt: Optional[str]) -> LLMResponse:
        await asyncio.sleep(0.05)
        prompt_lower = prompt.lower()

        if "calculate" in prompt_lower or "25 * 17" in prompt_lower or "math" in prompt_lower:
            if "plan" in (system_prompt or "").lower():
                content = json.dumps({
                    "action": "calculator",
                    "action_input": "25 * 17",
                    "thought": "Arithmetic request detected. Using calculator tool."
                })
            else:
                content = "The result of 25 * 17 is 425."
        elif "opentelemetry" in prompt_lower or "search" in prompt_lower:
            if "plan" in (system_prompt or "").lower():
                content = json.dumps({
                    "action": "search_knowledge",
                    "action_input": "OpenTelemetry",
                    "thought": "OpenTelemetry question detected. Searching knowledge base."
                })
            else:
                content = "OpenTelemetry provides standardized APIs, SDKs, and tools to generate and export telemetry data."
        else:
            content = f"Mock response for prompt: {prompt}"

        input_tokens = len(prompt.split()) + 10
        output_tokens = len(content.split()) + 5
        return LLMResponse(content=content, input_tokens=input_tokens, output_tokens=output_tokens, raw_response={"mock": True})

    async def _call_openai(self, prompt: str, system_prompt: Optional[str]) -> LLMResponse:
        """Invokes OpenAI API using the official AsyncOpenAI SDK client."""
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        res = await client.chat.completions.create(model=self.model, messages=messages)
        usage = res.usage

        return LLMResponse(
            content=res.choices[0].message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            raw_response=res.model_dump()
        )

    async def _call_gemini(self, prompt: str, system_prompt: Optional[str]) -> LLMResponse:
        """Invokes Gemini API using the official Google GenAI SDK client."""
        from google import genai

        client = genai.Client(api_key=settings.gemini_api_key)
        content_text = f"{system_prompt}\n{prompt}" if system_prompt else prompt
        res = await client.aio.models.generate_content(model=self.model, contents=content_text)

        usage = res.usage_metadata
        input_tokens = usage.prompt_token_count if usage else 0
        output_tokens = usage.candidates_token_count if usage else 0

        return LLMResponse(
            content=res.text or "",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            raw_response={"text": res.text}
        )
