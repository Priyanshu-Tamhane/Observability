import asyncio
import argparse
from typing import Dict, Any

from app.config import settings
from app.telemetry.logging import setup_logging
from app.telemetry.tracing import init_tracing
from app.agent import ObservableAgent

async def run_scenario(scenario: str) -> Dict[str, Any]:
    setup_logging(settings.log_level)
    init_tracing()

    agent = ObservableAgent()
    print(f"\n==================================================")
    print(f"  RUNNING OBSERVABILITY PLAYGROUND SCENARIO: [{scenario.upper()}]")
    print(f"==================================================\n")

    try:
        if scenario == "normal":
            res = await agent.run(user_request="What is OpenTelemetry?")
        elif scenario == "math":
            res = await agent.run(user_request="Calculate 25 * 17")
        elif scenario == "tool-error":
            res = await agent.run(user_request="Calculate 25 * 17", simulate_tool_failure=True)
        elif scenario == "llm-error":
            res = await agent.run(user_request="Explain tracing", simulate_llm_failure=True)
        elif scenario == "slow":
            res = await agent.run(user_request="Simulate slow agent", simulate_timeout=True)
        else:
            print(f"Unknown scenario '{scenario}'. Available: normal, math, tool-error, llm-error, slow")
            return {}
    except Exception as exc:
        res = {"status": "error", "error": str(exc), "scenario": scenario}

    print("\n--- Execution Result ---")
    print(res)
    print("------------------------\n")
    return res

def main():
    parser = argparse.ArgumentParser(description="Observability Playground CLI")
    parser.add_argument(
        "scenario",
        nargs="?",
        default="normal",
        choices=["normal", "math", "tool-error", "llm-error", "slow"],
        help="Scenario: normal | math | tool-error | llm-error | slow"
    )
    args = parser.parse_args()
    asyncio.run(run_scenario(args.scenario))

if __name__ == "__main__":
    main()
