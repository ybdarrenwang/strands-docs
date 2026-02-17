"""
Function Tool Test Case: Calendar Events

This file contains a test case specifically designed to trigger the get_calendar_events function tool.
"""

from typing import Dict, Any, List
from strands import Agent
from strands_evals import Case, Experiment, StrandsEvalsTelemetry
from strands_evals.evaluators import GoalSuccessRateEvaluator
from strands_evals.mappers import StrandsInMemorySessionMapper
from pydantic import BaseModel, Field
from strands.tools.decorator import tool

from strands_evals.simulation.tool_simulator import ToolSimulator


def run_test(function_prompt, mcp_prompt, api_prompt):
    """
    Run the calendar events function tool test.
    
    Args:
        function_prompt: Prompt template for function tools
        mcp_prompt: Prompt template for MCP tools
        api_prompt: Prompt template for API tools
    """
    # Setup telemetry and tool simulator upfront
    telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
    memory_exporter = telemetry.in_memory_exporter
    tool_simulator = ToolSimulator()

    # Output schema for calendar events
    class CalendarEventSchema(BaseModel):
        """Schema for calendar event data."""
        event_id: int = Field(description="Event ID")
        title: str = Field(description="Event title")
        start_time: str = Field(description="Event start time")
        end_time: str = Field(description="Event end time")
        location: str | None = Field(default=None, description="Event location")

    # Function tool: Calendar events (Complexity Level 1 - Easiest: 1 input, simple output)
    @tool_simulator.tool(
        output_schema=CalendarEventSchema,
        share_state_id="calendar",
        initial_state_description="Calendar: 3 events today, 2 events tomorrow, weekly meeting on Thursday",
        tool_prompt=function_prompt
    )
    @tool
    def get_calendar_events(day: str) -> Dict[str, Any]:
        """Get calendar events for a specific day. Simple function with single required input."""
        pass

    # Create test case
    test_case = Case(
        name="calendar_events_query",
        input="What events do I have scheduled for January 15th, 2024?",
        metadata={"expected_tool": "get_calendar_events", "expected_tool_type": "function"}
    )

    # Define user task function
    def user_task_function(case: Case) -> dict:
        """Execute the agent with the given case input and return output with trajectory."""
        # Get tool
        tool = tool_simulator.get_tool("get_calendar_events")
        
        # Create agent with trace attributes for session tracking
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a smart home assistant that can help with calendar events.",
            tools=[tool],
            callback_handler=None,
        )
        
        try:
            agent_response = agent(case.input)
        except Exception as e:
            agent_response = f"Agent execution error: {e}"
        
        # Get finished spans and map to session for trajectory
        finished_spans = memory_exporter.get_finished_spans()
        mapper = StrandsInMemorySessionMapper()
        session = mapper.map_to_session(finished_spans, session_id=case.session_id)
        
        return {"output": str(agent_response), "trajectory": session}

    # Setup evaluators
    evaluators = [GoalSuccessRateEvaluator()]

    # Create an experiment
    experiment = Experiment[str, str](cases=[test_case], evaluators=evaluators)

    # Run evaluations
    print(f"\n=== Running Evaluation: {test_case.name} ===")
    reports = experiment.run_evaluations(user_task_function)

    # Display results
    # reports[0].run_display()
    
    # Return simple results for driver script
    report = reports[0]
    return {
        "name": report.cases[0].get("name", "calendar_events_query"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }