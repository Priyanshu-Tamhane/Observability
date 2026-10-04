import pytest
from app.agent import ObservableAgent

@pytest.mark.asyncio
async def test_agent_normal_execution():
    agent = ObservableAgent()
    res = await agent.run(user_request="What is OpenTelemetry?")
    assert res["status"] == "success"
    assert res["action"] == "search_knowledge"
    assert "OpenTelemetry" in res["response"]

@pytest.mark.asyncio
async def test_agent_math_execution():
    agent = ObservableAgent()
    res = await agent.run(user_request="Calculate 25 * 17")
    assert res["status"] == "success"
    assert res["action"] == "calculator"
    assert "425" in res["tool_output"]

@pytest.mark.asyncio
async def test_agent_llm_failure():
    agent = ObservableAgent()
    with pytest.raises(RuntimeError) as exc_info:
        await agent.run(user_request="Test prompt", simulate_llm_failure=True)
    assert "Simulated LLM service error" in str(exc_info.value)

@pytest.mark.asyncio
async def test_agent_tool_failure():
    agent = ObservableAgent()
    with pytest.raises(Exception):
        await agent.run(user_request="Calculate 25 * 17", simulate_tool_failure=True)
