from typing import Dict, Any
import json
from pydantic import BaseModel, Field

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

    # Function tool for air quality status
    @tool_simulator.tool(
        output_schema=None,
        tool_prompt=function_prompt,
        share_state_id="home_air_quality",
        initial_state_description="Home air quality: PM2.5 (15 μg/m³), CO2 (650 ppm), VOCs (moderate), humidity (45%), all air purifiers off"
    )
    @tool
    def get_air_quality_status() -> Dict[str, Any]:
        """Get current air quality status in the home.
        
        Returns:
            Dict[str, Any]: Air quality measurements
            
        Output Schema:
            {
                "pm2_5": str,  # PM2.5 level (e.g., "15 μg/m³")
                "co2": str,  # CO2 level (e.g., "650 ppm")
                "vocs": str,  # VOC level (low, moderate, high)
                "humidity": str,  # Humidity percentage
                "air_purifiers": {
                    "living_room": str,  # "on" or "off"
                    "bedroom": str,
                    "kitchen": str
                },
                "overall_quality": str  # "good", "moderate", "poor"
            }
        """
        pass

    # MCP tool (shares state with home air quality)
    @tool_simulator.tool(
        output_schema=mcp_schema,
        tool_prompt=mcp_prompt,
        share_state_id="home_air_quality"
    )
    @tool
    def air_purifier_controller(room: str, power: str, fan_speed: str = "auto", mode: str = "auto") -> Dict[str, Any]:
        """Control home air purifiers.
        
        Args:
            room: Room to control air purifier for
            power: Power state (on, off)
            fan_speed: Fan speed (low, medium, high, auto)
            mode: Operation mode (auto, sleep, turbo)
            
        Returns:
            Dict[str, Any]: MCP tool response
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "room": {
                        "type": "string",
                        "description": "Room to control air purifier for"
                    },
                    "power": {
                        "type": "string",
                        "enum": ["on", "off"],
                        "description": "Power state"
                    },
                    "fan_speed": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "auto"],
                        "description": "Fan speed"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["auto", "sleep", "turbo"],
                        "description": "Operation mode"
                    }
                },
                "required": ["room", "power"]
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
    def flight_status_service(flight_number: str, date: str = None) -> Dict[str, Any]:
        """Get flight status information by flight number and optional date.
        
        Args:
            flight_number: Flight number (e.g., "AA123", "DL456")
            date: Optional date (ISO format, defaults to today)
            
        Returns:
            Dict[str, Any]: Flight status information
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "flight_number": {
                        "type": "string",
                        "description": "Flight number"
                    },
                    "date": {
                        "type": "string",
                        "description": "Date in ISO format"
                    }
                },
                "required": ["flight_number"]
            }
            
        Output Schema:
            {
                "flight_number": str,
                "airline": str,
                "date": str,
                "origin": str,
                "destination": str,
                "scheduled_departure": str,
                "actual_departure": str,
                "scheduled_arrival": str,
                "estimated_arrival": str,
                "status": str,  # "on-time", "delayed", "cancelled", "departed", "arrived"
                "delay_minutes": int,
                "gate": str,
                "terminal": str
            }
        """
        pass

    # Create sub-agent (agent-as-tool) with simulated tools
    @tool
    def air_quality_assistant(query: str) -> str:
        """Air quality assistant that uses air quality status and flight data to control air purifiers based on user requests and travel plans."""
        try:
            air_quality_status_tool = tool_simulator.get_tool("get_air_quality_status")
            air_purifier_tool = tool_simulator.get_tool("air_purifier_controller")
            flight_tool = tool_simulator.get_tool("flight_status_service")
        
            control_agent = Agent(
                system_prompt="You are an air quality assistant. Your job is to control the air purifiers using the air_purifier_controller tool based on information from air quality status and flight status. Always check current air quality first, consider flight status if relevant to the user's travel plans, then make appropriate air purifier adjustments to meet the user's request.",
                tools=[air_quality_status_tool, air_purifier_tool, flight_tool],
                callback_handler=None,
            )
            response = control_agent(f"Air quality request: {query}")
            return str(response)

        except Exception as e:
            return f"Air quality assistant error: {str(e)}"

    # Define a task function
    def user_task_function(case: Case) -> dict:
        # Create agent with simulated tool and sub-agent
        air_quality_status_tool = tool_simulator.get_tool("get_air_quality_status")
    
        # Inspect initial shared state "home_air_quality"
        initial_state = tool_simulator.get_state("home_air_quality")
        print(f"[Home air quality state (before agent invocation)]:")
        print(f"  Initial state: {initial_state.get('initial_state')}")
        print(f"  Previous calls: {initial_state.get('previous_calls', [])}")
    
        # Showcase how user-agent interaction changes home air quality state
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a smart home assistant Alessa. You can check air quality status. For air purifier control, you must consult the air_quality_assistant who has access to the smart air purifier system.",
            tools=[
                air_quality_status_tool,
                air_quality_assistant,
            ],
            callback_handler=None,
        )

        try:
            agent_response = agent(case.input)
        except Exception as e:
            agent_response = f"Agent execution error: {e}"

        print(f"[User]: {case.input}")
        print(f"[Agent]: {agent_response}")

        # Inspect final shared state "home_air_quality" after agent interaction
        final_state = tool_simulator.get_state("home_air_quality")
        print(f"[Home air quality state (after agent invocation)]:")
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
            name="flight_air_quality", 
            input="My flight AA123 is delayed by 3 hours. Check the status and turn on the air purifiers to make sure the house air is clean when I get home.",
            metadata={"category": "air_quality", "expected_tools": ["flight_status_service", "air_purifier_controller"]},
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
        "name": report.cases[0].get("name", "flight_air_quality"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }

