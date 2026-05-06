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
    ChaosScenarioAggregator,
    display_chaos_aggregation,
)
from strands_evals.evaluators import GoalSuccessRateEvaluator
from strands_evals.mappers import StrandsInMemorySessionMapper
from strands_evals.simulation.tool_simulator import ToolSimulator
from strands_evals.telemetry import StrandsEvalsTelemetry

# Setup telemetry for session tracing (required by GoalSuccessRateEvaluator)
telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
memory_exporter = telemetry.in_memory_exporter


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
        trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
    )

    try:
        result = agent(case.input)
        finished_spans = memory_exporter.get_finished_spans()
        mapper = StrandsInMemorySessionMapper()
        session = mapper.map_to_session(finished_spans, session_id=case.session_id)
        return {"output": str(result), "trajectory": session}
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
    GoalSuccessRateEvaluator(),
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

# Display per-scenario results
#for report in reports:
#    print(f"\n{'='*60}")
#    print(f"Evaluator: {report.evaluator_name}")
#    print(f"Overall Score: {report.overall_score:.2f}")
#    print(f"{'='*60}")
#    report.run_display()


# ─── 7. Aggregate and display chaos scenario report ──────────────────────

aggregator = ChaosScenarioAggregator(
    known_tools=["search_flights", "search_hotels"],
    model="us.anthropic.claude-sonnet-4-20250514-v1:0",  # enables LLM-as-a-Judge summarization
)
aggregations = aggregator.aggregate(reports)

# Traditional mode: interactive table with expand/collapse
display_chaos_aggregation(aggregations, reports=reports, mode="traditional")

# Pretty mode: side-by-side panels (Stats | Coverage Matrix | Reason)
display_chaos_aggregation(aggregations, mode="pretty")
