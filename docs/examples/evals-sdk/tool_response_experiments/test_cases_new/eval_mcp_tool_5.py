"""
MCP Tool Test Case: TV Control

This file contains a test case specifically designed to trigger the tv_controller MCP tool.
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
    Run the TV controller MCP tool test.
    
    Args:
        function_prompt: Prompt template for function tools
        mcp_prompt: Prompt template for MCP tools
        api_prompt: Prompt template for API tools
    """
    # Setup telemetry and tool simulator upfront
    telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
    memory_exporter = telemetry.in_memory_exporter
    tool_simulator = ToolSimulator()

    # Structured content schema for TV control response
    class TVControlData(BaseModel):
        """Structured data for TV control response."""
        action: str = Field(description="Action performed")
        value: str = Field(description="Action value")
        status: str = Field(description="Operation status")

    # Complete MCP response schema
    class TVControlResponse(MCPToolResponse):
        """
        Complete MCP response wrapper for TV controller.
        
        Extends MCPToolResponse to provide type safety for structured_content.
        Follows official MCP specification format:
        - tool_use_id: Unique identifier for this tool use
        - content: List of ContentBlock objects with text responses
        - structured_content: TVControlData for structured output
        - is_error: Whether an error occurred
        - meta: Additional metadata
        """
        structured_content: TVControlData | None = Field(default=None, description="Structured TV control data")

    # Complexity Level 5 - Hardest: Multi-mode control with profiles and scheduling
    # Complex Conditional Logic & State Management:
    # - action type determines which other parameters are valid:
    #   * "power" → value ignored
    #   * "channel"/"volume" → value required
    #   * "profile" → profile parameter required, enables preset picture_mode/audio_mode
    #   * "schedule" → schedule_time and repeat required
    # - profile selection overrides individual picture/audio settings
    # - Custom modes (picture_mode/audio_mode) only valid when profile="custom"
    # - Scheduling creates time-based execution requiring validation of time format
    # - repeat flag adds daily recurrence logic
    # Agent must coordinate: Which action? Are timing constraints involved? Should presets or custom settings be used?
    # Requires understanding of hierarchical settings (profile > custom modes)
    @tool_simulator.tool(
        output_schema=TVControlResponse,
        share_state_id="smart_devices",
        tool_prompt=mcp_prompt
    )
    @tool
    def tv_controller(
        action: str,
        value: str = None,
        profile: str = None,
        schedule_time: str = None,
        repeat: bool = False,
        picture_mode: str = None,
        audio_mode: str = None
    ) -> Dict[str, Any]:
        """
        Control smart TV with advanced settings including profiles, scheduling, and custom audio/video modes.
        
        MCP Tool Specification:
            Name: tv_controller
            Description: Control smart TV with advanced settings, profiles, and scheduling
            
            Input Schema:
                {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["power", "channel", "volume", "input", "app", "profile", "schedule"],
                            "description": "Action to perform"
                        },
                        "value": {
                            "type": "string",
                            "description": "Value for the action (channel number, volume level, input source, app name)"
                        },
                        "profile": {
                            "type": "string",
                            "enum": ["movie", "sports", "gaming", "custom"],
                            "description": "Picture/sound profile"
                        },
                        "schedule_time": {
                            "type": "string",
                            "description": "Time to schedule action (HH:MM)"
                        },
                        "repeat": {
                            "type": "boolean",
                            "description": "Repeat scheduled action daily"
                        },
                        "picture_mode": {
                            "type": "string",
                            "description": "Custom picture mode settings"
                        },
                        "audio_mode": {
                            "type": "string",
                            "description": "Custom audio mode settings"
                        }
                    },
                    "required": ["action"]
                }
            
            Response (Success):
                {
                    "tool_use_id": "call_131",
                    "content": [
                        {
                            "type": "text",
                            "text": "TV powered on and switched to channel 5.",
                            "resource": null
                        }
                    ],
                    "structured_content": {
                        "action": "channel",
                        "value": "5",
                        "status": "success"
                    },
                    "is_error": false,
                    "meta": {
                        "timestamp": "2024-02-17T22:00:00Z"
                    }
                }
            
            Response (Error):
                {
                    "tool_use_id": "call_132",
                    "content": [
                        {
                            "type": "text",
                            "text": "Error: Channel 999 is not available in your subscription",
                            "resource": null
                        }
                    ],
                    "structured_content": null,
                    "is_error": true,
                    "meta": {
                        "error_code": "CHANNEL_UNAVAILABLE",
                        "timestamp": "2024-02-17T22:00:00Z"
                    }
                }
        """
        pass

    # Create test case
    test_case = Case(
        name="tv_control",
        input="Turn on the TV and switch to channel 5.",
        metadata={"expected_tool": "tv_controller", "expected_tool_type": "mcp"}
    )

    # Define user task function
    def user_task_function(case: Case) -> dict:
        """Execute the agent with the given case input and return output with trajectory."""
        # Get tool
        tool = tool_simulator.get_tool("tv_controller")
        
        # Create agent with trace attributes for session tracking
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a smart home assistant that can help with TV control.",
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
        "name": report.cases[0].get("name", "tv_control"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }