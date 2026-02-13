from typing import Dict, Any, List
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

    # Function tool for irrigation status
    @tool_simulator.tool(
        output_schema=None,
        tool_prompt=function_prompt,
        share_state_id="garden_irrigation",
        initial_state_description="Garden irrigation: system (off), last watered (yesterday), moisture level (medium), schedule (daily at 6:00 AM), zones (front yard, back yard, vegetable garden)"
    )
    @tool
    def get_irrigation_status() -> Dict[str, Any]:
        """Get current status of the smart irrigation system.
        
        Returns:
            Dict[str, Any]: Irrigation system status
            
        Output Schema:
            {
                "system_state": str,  # "on" or "off"
                "last_watered": str,  # Time since last watering
                "moisture_level": str,  # Soil moisture level
                "schedule": str,  # Watering schedule
                "zones": {
                    "front_yard": str,  # Status
                    "back_yard": str,
                    "vegetable_garden": str
                }
            }
        """
        pass

    # MCP tool (shares state with garden irrigation)
    @tool_simulator.tool(
        output_schema=mcp_schema,
        tool_prompt=mcp_prompt,
        share_state_id="garden_irrigation")
    @tool
    def irrigation_controller(action: str, zone: str = "all", duration: float = 15, moisture_threshold: str = "medium") -> Dict[str, Any]:
        """Control smart irrigation system.
        
        Args:
            action: Action to perform (start, stop, schedule, adjust_moisture)
            zone: Zone to control (all, front_yard, back_yard, vegetable_garden)
            duration: Duration in minutes for watering
            moisture_threshold: Moisture threshold (low, medium, high)
            
        Returns:
            Dict[str, Any]: MCP tool response with structured content
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["start", "stop", "schedule", "adjust_moisture"],
                        "description": "Action to perform"
                    },
                    "zone": {
                        "type": "string",
                        "description": "Zone to control"
                    },
                    "duration": {
                        "type": "number",
                        "description": "Duration in minutes"
                    },
                    "moisture_threshold": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "Moisture threshold"
                    }
                },
                "required": ["action"]
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
                "structured_content": {
                    "status": str,
                    "action": str,
                    "zone": str,
                    "water_usage": str,
                    "next_scheduled": str
                },
                "is_error": bool,
                "meta": {
                    "timestamp": str
                }
            }
        """
        # Calculate water usage based on zone and duration
        water_usage = "Low (2 gallons)" if zone != "all" and duration < 10 else "Medium (5 gallons)" if zone != "all" or duration < 20 else "High (10+ gallons)"
    
        # Determine next scheduled watering
        next_scheduled = "Tomorrow at 6:00 AM" if action != "schedule" else "Custom schedule applied"
    
        # Create structured content following the outputSchema
        structured_content = {
            "status": "success",
            "action": action,
            "zone": zone,
            "water_usage": water_usage,
            "next_scheduled": next_scheduled
        }
    
        # Create response text based on action
        response_text = ""
        if action == "start":
            response_text = f"Successfully started irrigation in {zone} zone for {duration} minutes"
        elif action == "stop":
            response_text = f"Successfully stopped irrigation in {zone} zone"
        elif action == "schedule":
            response_text = f"Successfully scheduled irrigation for {zone} zone with {moisture_threshold} moisture threshold"
        elif action == "adjust_moisture":
            response_text = f"Successfully adjusted moisture threshold to {moisture_threshold} for {zone} zone"
    
        # Create a proper MCP response as a dictionary
        return {
            "tool_use_id": "irrigation_control_505",
            "content": [
                {
                    "type": "text",
                    "text": response_text,
                    "resource": None
                }
            ],
            "structured_content": structured_content,
            "is_error": False,
            "meta": {"timestamp": "2026-02-12T11:38:00Z"}
        }

    # API tool
    @tool_simulator.tool(
        output_schema=api_schema,
        tool_prompt=api_prompt,
    )
    @tool
    def weather_forecast_service(location: str, days: int = 3, include_hourly: bool = False) -> Dict[str, Any]:
        """Get weather forecast for a specific location.
        
        Args:
            location: Location for forecast
            days: Number of days to forecast (1-7)
            include_hourly: Include hourly breakdown
            
        Returns:
            Dict[str, Any]: Weather forecast data
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Location for forecast"
                    },
                    "days": {
                        "type": "integer",
                        "description": "Number of days (1-7)",
                        "default": 3
                    },
                    "include_hourly": {
                        "type": "boolean",
                        "description": "Include hourly data",
                        "default": false
                    }
                },
                "required": ["location"]
            }
            
        Output Schema:
            {
                "location": str,
                "forecast": [
                    {
                        "date": str,
                        "high_temp": int,  # Fahrenheit
                        "low_temp": int,
                        "condition": str,  # "sunny", "cloudy", "rainy", "stormy"
                        "precipitation_chance": int,  # Percentage
                        "precipitation_amount": str,  # Inches
                        "humidity": int,  # Percentage
                        "wind_speed": int,  # mph
                        "hourly": [
                            {
                                "time": str,
                                "temp": int,
                                "condition": str,
                                "precipitation": int
                            }
                        ]
                    }
                ],
                "alerts": [str]  # Weather alerts
            }
        """
        pass

    # Create sub-agent (agent-as-tool) with simulated tools
    @tool
    def garden_assistant(query: str) -> str:
        """Garden assistant that uses irrigation status and weather data to control the irrigation system based on user requests and weather forecasts."""
        try:
            irrigation_status_tool = tool_simulator.get_tool("get_irrigation_status")
            irrigation_tool = tool_simulator.get_tool("irrigation_controller")
            weather_tool = tool_simulator.get_tool("weather_forecast_service")
        
            control_agent = Agent(
                system_prompt="You are a garden assistant. Your job is to control the irrigation system using the irrigation_controller tool based on information from irrigation status and weather forecasts. Always check current irrigation status first, consider weather forecasts if relevant to watering decisions, then make appropriate irrigation adjustments to meet the user's request.",
                tools=[irrigation_status_tool, irrigation_tool, weather_tool],
                callback_handler=None,
            )
            response = control_agent(f"Garden request: {query}")
            return str(response)

        except Exception as e:
            return f"Garden assistant error: {str(e)}"

    # Define a task function
    def user_task_function(case: Case) -> dict:
        # Create agent with simulated tool and sub-agent
        irrigation_status_tool = tool_simulator.get_tool("get_irrigation_status")
    
        # Inspect initial shared state "garden_irrigation"
        initial_state = tool_simulator.get_state("garden_irrigation")
        print(f"[Garden irrigation state (before agent invocation)]:")
        print(f"  Initial state: {initial_state.get('initial_state')}")
        print(f"  Previous calls: {initial_state.get('previous_calls', [])}")
    
        # Showcase how user-agent interaction changes garden irrigation state
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a smart home assistant Alessa. You can check irrigation status. For irrigation control, you must consult the garden_assistant who has access to the smart irrigation system.",
            tools=[
                irrigation_status_tool,
                garden_assistant,
            ],
            callback_handler=None,
        )

        try:
            agent_response = agent(case.input)
        except Exception as e:
            agent_response = f"Agent execution error: {e}"

        print(f"[User]: {case.input}")
        print(f"[Agent]: {agent_response}")

        # Inspect final shared state "garden_irrigation" after agent interaction
        final_state = tool_simulator.get_state("garden_irrigation")
        print(f"[Garden irrigation state (after agent invocation)]:")
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
            name="weather_garden_planning", 
            input="I'm planning to plant new flowers in my garden this weekend. What's the weather forecast and should I adjust the irrigation schedule for the vegetable garden?",
            metadata={"category": "gardening", "expected_tools": ["weather_forecast_service", "irrigation_controller"]},
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
        "name": report.cases[0].get("name", "weather_garden_planning"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }

