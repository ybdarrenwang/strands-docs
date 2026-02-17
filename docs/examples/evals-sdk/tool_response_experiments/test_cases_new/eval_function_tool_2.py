"""
Function Tool Test Case: Room Temperature and Humidity

This file contains a test case specifically designed to trigger the get_room_temperature_humidity function tool.
"""

from typing import Dict, Any
from strands import Agent
from strands_evals import Case, Experiment, StrandsEvalsTelemetry
from strands_evals.evaluators import GoalSuccessRateEvaluator
from strands_evals.mappers import StrandsInMemorySessionMapper
from pydantic import BaseModel, Field
from strands.tools.decorator import tool

from strands_evals.simulation.tool_simulator import ToolSimulator


def run_test(function_prompt, mcp_prompt, api_prompt):
    """
    Run the room temperature and humidity function tool test.
    
    Args:
        function_prompt: Prompt template for function tools
        mcp_prompt: Prompt template for MCP tools
        api_prompt: Prompt template for API tools
    """
    # Setup telemetry and tool simulator upfront
    telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
    memory_exporter = telemetry.in_memory_exporter
    tool_simulator = ToolSimulator()

    # Output schema for room temperature and humidity
    class RoomEnvironmentSchema(BaseModel):
        """Schema for room environment data."""
        temperature: float = Field(description="Room temperature")
        humidity: float = Field(description="Room humidity percentage")
        unit: str = Field(description="Temperature unit (F or C)")

    # Function tool: Room temperature and humidity (Complexity Level 2 - Easy: 1 input, multiple outputs)
    @tool_simulator.tool(
        output_schema=RoomEnvironmentSchema,
        share_state_id="room_environment",
        initial_state_description="Room environment: temperature 68°F, humidity 45%, HVAC off",
        tool_prompt=function_prompt
    )
    @tool
    def get_room_temperature_humidity(room_name: str) -> Dict[str, Any]:
        """Get current room temperature and humidity levels for a specific room. Returns multiple environmental metrics."""
        pass

    # Create test case
    test_case = Case(
        name="room_temperature_query",
        input="What's the current temperature and humidity in the living room?",
        metadata={"expected_tool": "get_room_temperature_humidity", "expected_tool_type": "function"}
    )

    # Define user task function
    def user_task_function(case: Case) -> dict:
        """Execute the agent with the given case input and return output with trajectory."""
        # Get tool
        tool = tool_simulator.get_tool("get_room_temperature_humidity")
        
        # Create agent with trace attributes for session tracking
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a smart home assistant that can help with room temperature and humidity monitoring.",
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
        "name": report.cases[0].get("name", "room_temperature_query"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }