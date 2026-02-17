"""
MCP Tool Test Case: Lighting Control

This file contains a test case specifically designed to trigger the lighting_controller MCP tool.
"""

from typing import Dict, Any
from strands import Agent
from strands_evals import Case, Experiment, StrandsEvalsTelemetry
from strands_evals.evaluators import GoalSuccessRateEvaluator
from strands_evals.mappers import StrandsInMemorySessionMapper
from pydantic import BaseModel, Field
from strands.tools.decorator import tool

from strands_evals.simulation.tool_simulator import ToolSimulator
from strands_evals.types.simulation.tool import MCPToolResponse, ContentBlock


def run_test(function_prompt, mcp_prompt, api_prompt):
    """
    Run the lighting controller MCP tool test.
    
    Args:
        function_prompt: Prompt template for function tools
        mcp_prompt: Prompt template for MCP tools
        api_prompt: Prompt template for API tools
    """
    # Setup telemetry and tool simulator upfront
    telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
    memory_exporter = telemetry.in_memory_exporter
    tool_simulator = ToolSimulator()

    # Structured content schema for lighting control response
    class LightingControlData(BaseModel):
        """Structured data for lighting control response."""
        room: str = Field(description="Room where lighting is controlled")
        state: str = Field(description="Light state (on/off)")
        brightness: float | None = Field(default=None, description="Brightness level (0-100)")
        color: str | None = Field(default=None, description="Light color")

    # Complete MCP response schema
    class LightingControlResponse(MCPToolResponse):
        """
        Complete MCP response wrapper for lighting controller.
        
        Extends MCPToolResponse to provide type safety for structured_content.
        Follows official MCP specification format:
        - tool_use_id: Unique identifier for this tool use
        - content: List of ContentBlock objects with text responses
        - structured_content: LightingControlData for structured output
        - is_error: Whether an error occurred
        - meta: Additional metadata
        """
        structured_content: LightingControlData | None = Field(default=None, description="Structured lighting control data")

    # MCP tool: Lighting controller (Complexity Level 2 - Easy: 2 required inputs, basic control)
    @tool_simulator.tool(
        output_schema=LightingControlResponse,
        share_state_id="smart_devices",
        tool_prompt=mcp_prompt
    )
    @tool
    def lighting_controller(room: str, state: str) -> Dict[str, Any]:
        """
        Control home smart lighting system with room and on/off state.
        
        MCP Tool Specification:
            Name: lighting_controller
            Description: Control home smart lighting system with room and state
            
            Input Schema:
                {
                    "type": "object",
                    "properties": {
                        "room": {
                            "type": "string",
                            "description": "Room to control lighting for"
                        },
                        "state": {
                            "type": "string",
                            "enum": ["on", "off"],
                            "description": "Light state"
                        }
                    },
                    "required": ["room", "state"]
                }
            
            Response (Success):
                {
                    "tool_use_id": "call_125",
                    "content": [
                        {
                            "type": "text",
                            "text": "Living room lights turned on at 80% brightness.",
                            "resource": null
                        }
                    ],
                    "structured_content": {
                        "room": "living room",
                        "state": "on",
                        "brightness": 80.0,
                        "color": "warm white"
                    },
                    "is_error": false,
                    "meta": {
                        "timestamp": "2024-02-17T22:00:00Z"
                    }
                }
            
            Response (Error):
                {
                    "tool_use_id": "call_126",
                    "content": [
                        {
                            "type": "text",
                            "text": "Error: Room 'garage' has no smart lights installed",
                            "resource": null
                        }
                    ],
                    "structured_content": null,
                    "is_error": true,
                    "meta": {
                        "error_code": "ROOM_NOT_FOUND",
                        "timestamp": "2024-02-17T22:00:00Z"
                    }
                }
        """
        pass

    # Create test case
    test_case = Case(
        name="lighting_control",
        input="Turn on the lights in the living room at 80% brightness.",
        metadata={"expected_tool": "lighting_controller", "expected_tool_type": "mcp"}
    )

    # Define user task function
    def user_task_function(case: Case) -> dict:
        """Execute the agent with the given case input and return output with trajectory."""
        # Get tool
        tool = tool_simulator.get_tool("lighting_controller")
        
        # Create agent with trace attributes for session tracking
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a smart home assistant that can help with lighting control.",
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
        "name": report.cases[0].get("name", "lighting_control"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }