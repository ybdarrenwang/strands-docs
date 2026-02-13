from typing import Dict, Any
import json

from strands import Agent
from strands.tools.decorator import tool
from strands_evals import Case, Experiment
from strands_evals.evaluators import GoalSuccessRateEvaluator
from strands_evals.simulation.tool_simulator import ToolSimulator
from strands_evals.mappers import StrandsInMemorySessionMapper
from strands_evals.telemetry import StrandsEvalsTelemetry
import argparse


def run_test(function_prompt, mcp_prompt, api_prompt, mcp_schema, api_schema):
    # Setup telemetry and tool simulator upfront
    telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
    memory_exporter = telemetry.in_memory_exporter
    tool_simulator = ToolSimulator()

    # Function tool for home lighting status
    @tool_simulator.tool(
        output_schema=None,
        tool_prompt=function_prompt,
        share_state_id="home_lighting",
        initial_state_description="Home lighting: living room (off), kitchen (off), bedroom (off), brightness 0%"
    )
    @tool
    def get_home_lighting_status() -> Dict[str, Any]:
        """Get current home lighting status.
        
        Returns:
            Dict[str, Any]: Lighting status for all rooms
            
        Output Schema:
            {
                "rooms": {
                    "living_room": {
                        "state": str,  # "on" or "off"
                        "brightness": int  # 0-100
                    },
                    "kitchen": {
                        "state": str,
                        "brightness": int
                    },
                    "bedroom": {
                        "state": str,
                        "brightness": int
                    }
                },
                "overall_status": str  # Human-readable summary
            }
        """
        pass

    # MCP tool (shares state with home lighting)
    @tool_simulator.tool(
        output_schema=mcp_schema,
        tool_prompt=mcp_prompt,
        share_state_id="home_lighting"
    )
    @tool
    def smart_lighting_controller(room: str, state: str, brightness: float = 100, color: str = "white") -> Dict[str, Any]:
        """Control home smart lighting system that affects room brightness and ambiance.
        
        Args:
            room: Room to control lighting for
            state: Light state (on, off)
            brightness: Brightness percentage (0-100)
            color: Light color (hex code or name)
            
        Returns:
            Dict[str, Any]: MCP tool response
            
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
                    },
                    "brightness": {
                        "type": "number",
                        "description": "Brightness percentage (0-100)"
                    },
                    "color": {
                        "type": "string",
                        "description": "Light color (hex code or name)"
                    }
                },
                "required": ["room", "state"]
            }
            
        Output Schema:
            {
                "tool_use_id": str,
                "content": [
                    {
                        "type": "text",
                        "text": str,
                        "resource": null
                    }
                ],
                "is_error": bool,
                "meta": {
                    "timestamp": str
                }
            }
        """
        pass

    # API tool
    @tool_simulator.tool(
        output_schema=api_schema,
        tool_prompt=api_prompt,
    )
    @tool
    def traffic_service(origin: str, destination: str) -> Dict[str, Any]:
        """Get current traffic information between two locations.
        
        Args:
            origin: Starting location
            destination: Destination location
            
        Returns:
            Dict[str, Any]: Traffic information
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "origin": {
                        "type": "string",
                        "description": "Starting location"
                    },
                    "destination": {
                        "type": "string",
                        "description": "Destination location"
                    }
                },
                "required": ["origin", "destination"]
            }
            
        Output Schema:
            {
                "origin": str,
                "destination": str,
                "distance": str,  # Distance with unit (e.g., "15.3 miles")
                "duration": str,  # Estimated travel time (e.g., "25 minutes")
                "duration_in_traffic": str,  # Current travel time with traffic
                "traffic_condition": str,  # "light", "moderate", "heavy", "severe"
                "routes": [
                    {
                        "name": str,  # Route name (e.g., "I-405 N")
                        "duration": str,
                        "distance": str,
                        "traffic_delays": str
                    }
                ]
            }
        """
        pass

    # Create sub-agent (agent-as-tool) with simulated tools
    @tool
    def lighting_assistant(query: str) -> str:
        """Lighting assistant that uses home lighting status and traffic data to control the lighting system based on user requests."""
        try:
            lighting_status_tool = tool_simulator.get_tool("get_home_lighting_status")
            lighting_tool = tool_simulator.get_tool("smart_lighting_controller")
            traffic_tool = tool_simulator.get_tool("traffic_service")
        
            control_agent = Agent(
                system_prompt="You are a smart lighting assistant. Your job is to control the home lighting system using the smart_lighting_controller tool based on information from lighting sensors and traffic conditions. Always check current lighting conditions first, consider traffic data (for estimating arrival times), then make appropriate lighting adjustments to meet the user's request.",
                tools=[lighting_status_tool, lighting_tool, traffic_tool],
                callback_handler=None,
            )
            response = control_agent(f"Lighting control request: {query}")
            return str(response)

        except Exception as e:
            return f"Lighting assistant error: {str(e)}"

    # Define a task function
    def user_task_function(case: Case) -> dict:
        # Create agent with simulated tool and sub-agent
        lighting_status_tool = tool_simulator.get_tool("get_home_lighting_status")
    
        # Inspect initial shared state "home_lighting"
        initial_state = tool_simulator.get_state("home_lighting")
        print(f"[Home lighting state (before agent invocation)]:")
        print(f"  Initial state: {initial_state.get('initial_state')}")
        print(f"  Previous calls: {initial_state.get('previous_calls', [])}")
    
        # Showcase how user-agent interaction changes home lighting state
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a smart home assistant Alessa. You can check home lighting conditions. For lighting adjustments, you must consult the lighting_assistant who has access to the smart lighting system.",
            tools=[
                lighting_status_tool,
                lighting_assistant,
            ],
            callback_handler=None,
        )

        try:
            agent_response = agent(case.input)
        except Exception as e:
            agent_response = f"Agent execution error: {e}"

        print(f"[User]: {case.input}")
        print(f"[Agent]: {agent_response}")

        # Inspect final shared state "home_lighting" after agent interaction
        final_state = tool_simulator.get_state("home_lighting")
        print(f"[Home lighting state (after agent invocation)]:")
        print(f"  Initial state: {final_state.get('initial_state')}")
        print(f"  Previous calls:")
        for i, call in enumerate(final_state.get('previous_calls', [])):
            print(f"    {i}. Tool: {call.get('tool_name')}")
            print(f"       Response: {str(call.get('response', {}))[:100]}...")

        finished_spans = memory_exporter.get_finished_spans()
        mapper = StrandsInMemorySessionMapper()
        session = mapper.map_to_session(finished_spans, session_id=case.session_id)

        return {"output": str(agent_response), "trajectory": session}

    # Create test cases
    test_cases = [
        Case(
            name="commute_lighting_control", 
            input="I'm leaving work now. Check the traffic from downtown to my home and turn on the living room lights for my arrival.",
            metadata={"category": "lighting", "expected_tools": ["traffic_service", "smart_lighting_controller"]},
        ),
    ]

    # Create evaluators
    evaluators = [GoalSuccessRateEvaluator()]

    # Create an experiment
    experiment = Experiment[str, str](cases=test_cases, evaluators=evaluators)

    # Run evaluations
    reports = experiment.run_evaluations(user_task_function)
    
    # Return simple results for driver script to display
    report = reports[0]
    return {
        "name": report.cases[0].get("name", "commute_lighting_control"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }

