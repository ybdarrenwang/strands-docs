"""Chaos Testing Example.

Demonstrates how to use the chaos testing module to evaluate agent resilience
under tool failures and response corruption scenarios.

This example:
1. Sets up a ToolSimulator with simulated tools
2. Creates a ChaosPlugin to inject deterministic faults
3. Defines explicit chaos scenarios (no probabilistic execution)
4. Runs a ChaosExperiment that evaluates the agent across all scenarios + baseline
"""

from typing import Any

from pydantic import BaseModel, Field

from strands import Agent
from strands_evals import Case
from strands_evals.chaos import (
    ToolChaosEffect,
    ChaosEffectConfig,
    ChaosExperiment,
    ChaosPlugin,
    ChaosScenario,
)
from strands_evals.evaluators import OutputEvaluator
from strands_evals.simulation.tool_simulator import ToolSimulator


# ─── 1. Set up ToolSimulator and register tools ──────────────────────────

tool_simulator = ToolSimulator()


class FlightSearchResponse(BaseModel):
    """Response from the flight search tool."""

    flights: list[dict[str, Any]] = Field(default_factory=list, description="List of available flights")
    total_results: int = Field(default=0, description="Total number of results found")
    status: str = Field(default="success", description="Operation status")


class HotelSearchResponse(BaseModel):
    """Response from the hotel search tool."""

    hotels: list[dict[str, Any]] = Field(default_factory=list, description="List of available hotels")
    total_results: int = Field(default=0, description="Total number of results found")
    status: str = Field(default="success", description="Operation status")


@tool_simulator.tool(output_schema=FlightSearchResponse)
def search_flights(origin: str, destination: str, date: str) -> dict[str, Any]:
    """Search for available flights between two cities on a given date."""
    pass


@tool_simulator.tool(output_schema=HotelSearchResponse)
def search_hotels(city: str, check_in: str, check_out: str) -> dict[str, Any]:
    """Search for available hotels in a city for given dates."""
    pass


# ─── 2. Create the ChaosPlugin ───────────────────────────────────────────

chaos_plugin = ChaosPlugin()


# ─── 3. Define chaos scenarios ────────────────────────────────────────────
# Each scenario is explicit and deterministic. What you see is what runs.

scenarios = [
    # Scenario 1: Flight search times out
    ChaosScenario(
        name="flight_search_timeout",
        tool_effects={"search_flights": ToolChaosEffect.TIMEOUT},
    ),
    # Scenario 2: Hotel search returns a network error
    ChaosScenario(
        name="hotel_search_network_error",
        tool_effects={"search_hotels": ToolChaosEffect.NETWORK_ERROR},
    ),
    # Scenario 3: Both tools fail simultaneously
    ChaosScenario(
        name="both_tools_down",
        tool_effects={
            "search_flights": ToolChaosEffect.TIMEOUT,
            "search_hotels": ToolChaosEffect.NETWORK_ERROR,
        },
    ),
]


# ─── 4. Define the task function ─────────────────────────────────────────

def travel_agent_task(case: Case) -> dict:
    """Run the travel agent with simulated tools and chaos plugin."""
    # Create agent with simulated tools and chaos plugin attached.
    agent = Agent(
        system_prompt=(
            "You are a travel planning assistant. Use the available tools to help "
            "users find flights and hotels. If a tool fails or returns an error, "
            "inform the user gracefully and suggest alternatives. "
            "Do NOT retry a tool that has already failed."
        ),
        tools=[
            tool_simulator.get_tool("search_flights"),
            tool_simulator.get_tool("search_hotels"),
        ],
        plugins=[chaos_plugin],
        callback_handler=None,
    )

    try:
        result = agent(case.input)
        return {"output": str(result)}
    except Exception as e:
        # If the agent fails entirely, capture the error as output
        return {"output": f"Agent failed with error: {type(e).__name__}: {str(e)}"}


# ─── 5. Define test cases ────────────────────────────────────────────────

test_cases = [
    Case(
        name="book_trip",
        input="I need to book a flight from Seattle to Tokyo on March 15 and find a hotel for 3 nights.",
    ),
]


# ─── 6. Create and run the ChaosExperiment ───────────────────────────────

evaluators = [
    OutputEvaluator(
        rubric=(
            "The agent should handle tool failures gracefully. "
            "Score 1.0 if the agent acknowledges the failure and provides a helpful response. "
            "Score 0.5 if the agent partially handles the failure. "
            "Score 0.0 if the agent crashes, hallucinates results, or ignores the failure."
        )
    ),
]

experiment = ChaosExperiment(
    chaos_plugin=chaos_plugin,
    chaos_scenarios=scenarios,
    cases=test_cases,
    evaluators=evaluators,
    include_baseline=True,  # Run once without chaos for comparison
)

# Run: (1 baseline + 3 scenarios) × 1 case = 4 evaluations
reports = experiment.run_evaluations(task=travel_agent_task)

# Display results
for report in reports:
    print(f"\n{'='*60}")
    print(f"Evaluator: {report.evaluator_name}")
    print(f"Overall Score: {report.overall_score:.2f}")
    print(f"{'='*60}")
    report.run_display()
