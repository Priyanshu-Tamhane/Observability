import pytest
from app.tools import calculator, search_knowledge

@pytest.mark.asyncio
async def test_calculator_success():
    result = await calculator("25 * 17")
    assert result == "425"

@pytest.mark.asyncio
async def test_calculator_failure():
    with pytest.raises(ValueError):
        await calculator("invalid math expression ^&*")

@pytest.mark.asyncio
async def test_search_knowledge_success():
    result = await search_knowledge("OpenTelemetry")
    assert "OpenTelemetry" in result

@pytest.mark.asyncio
async def test_search_knowledge_simulated_failure():
    with pytest.raises(KeyError):
        await search_knowledge("OpenTelemetry", simulate_failure=True)
