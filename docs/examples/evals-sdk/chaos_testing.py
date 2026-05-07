"""Chaos Testing Example — Travel Agent.

Demonstrates how to use the chaos testing module to evaluate agent resilience
under tool failures and response corruption scenarios.

This example:
1. Sets up a ToolSimulator with 3 travel tools (search, book, confirm)
2. Creates a ChaosPlugin to inject deterministic faults
3. Defines 10 chaos scenarios (1 tool × 1 effect each)
4. Runs a ChaosExperiment with single-turn evaluation
5. Aggregates and displays results in both traditional and pretty modes
"""

import logging
from typing import Any

from pydantic import BaseModel, Field

from strands import Agent
from strands_evals import Case
from strands_evals.chaos import (
    ChaosExperiment,
    ChaosPlugin,
    ChaosScenario,
    ChaosScenarioAggregator,
    FailureCommunicationEvaluator,
    PartialCompletionEvaluator,
    RecoveryStrategyEvaluator,
    ToolChaosEffect,
)
from strands_evals.evaluators import GoalSuccessRateEvaluator
from strands_evals.mappers import StrandsInMemorySessionMapper
from strands_evals.simulation.tool_simulator import ToolSimulator
from strands_evals.telemetry import StrandsEvalsTelemetry

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

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


class BookFlightResponse(BaseModel):
    """Response from the flight booking tool."""

    booking_id: str = Field(default="", description="Booking confirmation ID")
    flight_id: str = Field(default="", description="The booked flight ID")
    status: str = Field(default="success", description="Booking status")
    message: str = Field(default="", description="Status message")


class BookingConfirmationResponse(BaseModel):
    """Response from the booking confirmation tool."""

    confirmation_sent: bool = Field(default=False, description="Whether confirmation was sent")
    method: str = Field(default="email", description="Delivery method")
    message: str = Field(default="", description="Confirmation details")


@tool_simulator.tool(output_schema=FlightSearchResponse)
def search_flights(origin: str, destination: str, date: str) -> dict[str, Any]:
    """Search for available flights between two cities on a given date."""
    pass


@tool_simulator.tool(output_schema=BookFlightResponse)
def book_flight(flight_id: str) -> dict[str, Any]:
    """Book a specific flight by its flight ID. Returns booking confirmation."""
    pass


@tool_simulator.tool(output_schema=BookingConfirmationResponse)
def send_booking_confirmation(booking_id: str = "", flight_id: str = "", method: str = "email") -> dict[str, Any]:
    """Send booking confirmation or fallback link to the user via email or SMS."""
    pass


# ─── 2. Create the ChaosPlugin ───────────────────────────────────────────

chaos_plugin = ChaosPlugin()


# ─── 3. Define chaos scenarios (10 scenarios, 1 tool × 1 effect each) ────

scenarios = [
    ChaosScenario(name="book_timeout", tool_effects={"book_flight": ToolChaosEffect.TIMEOUT}),
    ChaosScenario(name="book_corrupt_values", tool_effects={"book_flight": ToolChaosEffect.CORRUPT_VALUES}),
    ChaosScenario(name="search_network_error", tool_effects={"search_flights": ToolChaosEffect.NETWORK_ERROR}),
    ChaosScenario(name="search_truncate_fields", tool_effects={"search_flights": ToolChaosEffect.TRUNCATE_FIELDS}),
    ChaosScenario(name="confirm_remove_fields", tool_effects={"send_booking_confirmation": ToolChaosEffect.REMOVE_FIELDS}),
]


# ─── 4. Define the task function ───────────────────────────

# Pre-create tool instances once (avoids registry issues across runs)
_search_tool = tool_simulator.get_tool("search_flights")
_book_tool = tool_simulator.get_tool("book_flight")
_confirm_tool = tool_simulator.get_tool("send_booking_confirmation")


def travel_agent_task(case: Case) -> dict:
    """Run the travel agent with a single user query."""
    # Log which case/scenario is running
    scenario = (case.metadata or {}).get("chaos_scenario", "unknown")
    logger.info(f"\n{'─'*60}")
    logger.info(f"  Case: {case.name}  |  Scenario: {scenario}")
    logger.info(f"  User: {case.input}")

    agent = Agent(
        system_prompt=(
            "You are a travel booking assistant. You help users search for flights, "
            "book them, and send confirmations. Use the available tools to complete "
            "the user's request. Today's date is May 18, 2025.\n\n"
            "Always use the tools directly — do not ask the user for clarification "
            "if you can infer reasonable values from context.\n\n"
            "If a tool fails or returns an error:\n"
            "- Acknowledge the failure honestly to the user\n"
            "- Try an alternative approach if possible\n"
            "- Do NOT hallucinate successful results\n"
            "- Do NOT retry more than once\n\n"
            "If tool results look suspicious (e.g., $0 fares, past dates):\n"
            "- Inform the user that results seem unreliable\n"
            "- Suggest alternatives"
        ),
        tools=[_search_tool, _book_tool, _confirm_tool],
        plugins=[chaos_plugin],
        callback_handler=None,
        trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
    )

    memory_exporter.clear()
    try:
        result = agent(case.input)
        output = str(result)
    except Exception as e:
        output = f"Agent failed with error: {type(e).__name__}: {str(e)[:200]}"

    logger.info(f"  Agent: {output[:300]}{'...' if len(output) > 300 else ''}")
    logger.info(f"{'─'*60}")

    finished_spans = memory_exporter.get_finished_spans()
    mapper = StrandsInMemorySessionMapper()
    session = mapper.map_to_session(finished_spans, session_id=case.session_id)

    return {"output": output, "trajectory": session}


# ─── 5. Define test cases ────────────────────────────────────────────────

test_cases = [
    Case(
        name="book_a_flight",
        input="Find me a flight from SFO to JFK on May 20, book the cheapest one, and send me a confirmation.",
    ),
    Case(
        name="search_and_confirm",
        input="Search for flights from Seattle to Tokyo next Tuesday, book one, and email me the confirmation.",
    ),
]


# ─── 6. Create and run the ChaosExperiment ───────────────────────────────

evaluators = [
    GoalSuccessRateEvaluator(),
    RecoveryStrategyEvaluator(),
    PartialCompletionEvaluator(),
    FailureCommunicationEvaluator(),
]

experiment = ChaosExperiment(
    chaos_plugin=chaos_plugin,
    chaos_scenarios=scenarios,
    cases=test_cases,
    evaluators=evaluators,
    include_baseline=True,
    aggregator=ChaosScenarioAggregator(),
)

# Run: (1 baseline + 5 scenarios) × 2 cases = 12 evaluations
reports = experiment.run_evaluations(task=travel_agent_task)


# ─── 7. Aggregate and display chaos scenario report ──────────────────────

aggregation_report = experiment.aggregate_evaluations()
aggregation_report.run_display()
aggregation_report.to_file("chaos_aggregation_report.json")
