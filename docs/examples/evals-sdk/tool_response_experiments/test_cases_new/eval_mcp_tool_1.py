"""
MCP Tool Test Case: HVAC Control

This file contains a test case specifically designed to trigger the hvac_controller MCP tool.
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
    Run the HVAC controller MCP tool test.
    
    Args:
        function_prompt: Prompt template for function tools
        mcp_prompt: Prompt template for MCP tools
        api_prompt: Prompt template for API tools
    """
    # Setup telemetry and tool simulator upfront
    telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
    memory_exporter = telemetry.in_memory_exporter
    tool_simulator = ToolSimulator()

    # Structured content schema for HVAC control response
    class HVACControlData(BaseModel):
        """Structured data for HVAC control response."""
        status: str = Field(description="HVAC status")
        temperature_set: float = Field(description="Temperature setpoint")
        mode: str = Field(description="HVAC mode")
        current_temperature: float | None = Field(default=None, description="Current temperature")

    # Complete MCP response schema
    class HVACControlResponse(MCPToolResponse):
        """
        Complete MCP response wrapper for HVAC controller.
        
        Extends MCPToolResponse to provide type safety for structured_content.
        Follows official MCP specification format:
        - tool_use_id: Unique identifier for this tool use
        - content: List of ContentBlock objects with text responses
        - structured_content: HVACControlData for structured output
        - is_error: Whether an error occurred
        - meta: Additional metadata
        """
        structured_content: HVACControlData | None = Field(default=None, description="Structured HVAC control data")

    # MCP tool: HVAC controller (Complexity Level 1 - Easiest: 1 required input, simple control)
    @tool_simulator.tool(
        output_schema=HVACControlResponse,
        share_state_id="room_environment",
        tool_prompt=mcp_prompt
    )
    @tool
    def hvac_controller(mode: str) -> Dict[str, Any]:
        """
        Control home HVAC system with simple on/off control.
        
        MCP Tool Specification:
            Name: hvac_controller
            Description: Control home heating/cooling system - simple mode control
            
            Input Schema:
                {
                    "type": "object",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["on", "off"],
                            "description": "HVAC mode - simple on/off"
                        }
                    },
                    "required": ["mode"]
                }
            
            Response (Success):
                {
                    "tool_use_id": "call_123",
                    "content": [
                        {
                            "type": "text",
                            "text": "HVAC system turned on. Temperature set to 72°F.",
                            "resource": null
                        }
                    ],
                    "structured_content": {
                        "status": "success",
                        "temperature_set": 72.0,
                        "mode": "on",
                        "current_temperature": 68.5
                    },
                    "is_error": false,
                    "meta": {
                        "timestamp": "2024-02-17T22:00:00Z"
                    }
                }
            
            Response (Error):
                {
                    "tool_use_id": "call_124",
                    "content": [
                        {
                            "type": "text",
                            "text": "Error: HVAC system is offline",
                            "resource": null
                        }
                    ],
                    "structured_content": null,
                    "is_error": true,
                    "meta": {
                        "error_code": "HVAC_OFFLINE",
                        "timestamp": "2024-02-17T22:00:00Z"
                    }
                }
        """
        pass

    # Create test case
    test_case = Case(
        name="hvac_control",
        input="Set the thermostat to heat mode at 72 degrees.",
        metadata={"expected_tool": "hvac_controller", "expected_tool_type": "mcp"}
    )

    # Define user task function
    def user_task_function(case: Case) -> dict:
        """Execute the agent with the given case input and return output with trajectory."""
        # Get tool
        tool = tool_simulator.get_tool("hvac_controller")
        
        # Create agent with trace attributes for session tracking
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a smart home assistant that can help with HVAC control.",
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
        "name": report.cases[0].get("name", "hvac_control"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }