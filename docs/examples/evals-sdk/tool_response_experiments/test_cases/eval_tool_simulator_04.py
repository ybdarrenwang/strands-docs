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

    # Function tool for thermostat status
    @tool_simulator.tool(
        output_schema=None,
        tool_prompt=function_prompt,
        share_state_id="home_temperature",
        initial_state_description="Home temperature: current 70°F, target 72°F, mode 'heat', schedule active"
    )
    @tool
    def get_thermostat_status() -> Dict[str, Any]:
        """Get current thermostat status and settings.
        
        Returns:
            Dict[str, Any]: Thermostat status
            
        Output Schema:
            {
                "current_temperature": float,  # Current temp in Fahrenheit
                "target_temperature": float,  # Target temp in Fahrenheit
                "mode": str,  # "heat", "cool", "auto", "off"
                "schedule_enabled": bool,
                "fan_state": str,  # "on", "auto", "circulate"
                "humidity": float  # Current humidity percentage
            }
        """
        pass

    # MCP tool (shares state with home temperature)
    @tool_simulator.tool(
        output_schema=mcp_schema,
        tool_prompt=mcp_prompt,
        share_state_id="home_temperature"
    )
    @tool
    def thermostat_controller(target_temp: float, mode: str, schedule_enabled: bool = True) -> Dict[str, Any]:
        """Control home smart thermostat with scheduling capabilities.
        
        Args:
            target_temp: Target temperature in Fahrenheit
            mode: Thermostat mode (heat, cool, auto, off)
            schedule_enabled: Whether to enable scheduled temperature changes
            
        Returns:
            Dict[str, Any]: MCP tool response
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "target_temp": {
                        "type": "number",
                        "description": "Target temperature in Fahrenheit"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["heat", "cool", "auto", "off"],
                        "description": "Thermostat mode"
                    },
                    "schedule_enabled": {
                        "type": "boolean",
                        "description": "Whether to enable scheduled temperature changes"
                    }
                },
                "required": ["target_temp", "mode"]
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
    def calendar_service(start_date: str, end_date: str, calendar_id: str = "primary") -> Dict[str, Any]:
        """Get calendar events for a specified date range.
        
        Args:
            start_date: Start date for events (ISO format)
            end_date: End date for events (ISO format)
            calendar_id: Calendar identifier (default: "primary")
            
        Returns:
            Dict[str, Any]: Calendar events
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "start_date": {
                        "type": "string",
                        "description": "Start date (ISO format)"
                    },
                    "end_date": {
                        "type": "string",
                        "description": "End date (ISO format)"
                    },
                    "calendar_id": {
                        "type": "string",
                        "description": "Calendar identifier",
                        "default": "primary"
                    }
                },
                "required": ["start_date", "end_date"]
            }
            
        Output Schema:
            {
                "calendar_id": str,
                "start_date": str,
                "end_date": str,
                "events": [
                    {
                        "id": str,
                        "title": str,
                        "start_time": str,
                        "end_time": str,
                        "location": str,
                        "description": str,
                        "attendees": [str]
                    }
                ],
                "total_events": int
            }
        """
        pass

    # Create sub-agent (agent-as-tool) with simulated tools
    @tool
    def temperature_scheduler(query: str) -> str:
        """Temperature scheduler that uses thermostat status and calendar data to control the thermostat based on user schedule and requests."""
        try:
            thermostat_status_tool = tool_simulator.get_tool("get_thermostat_status")
            thermostat_tool = tool_simulator.get_tool("thermostat_controller")
            calendar_tool = tool_simulator.get_tool("calendar_service")
        
            control_agent = Agent(
                system_prompt="You are a temperature scheduling assistant. Your job is to control the smart thermostat using the thermostat_controller tool based on information from thermostat status and calendar events. Always check current thermostat status first, consider calendar events to optimize temperature settings based on home occupancy, then make appropriate thermostat adjustments to meet the user's request.",
                tools=[thermostat_status_tool, thermostat_tool, calendar_tool],
                callback_handler=None,
            )
            response = control_agent(f"Temperature scheduling request: {query}")
            return str(response)

        except Exception as e:
            return f"Temperature scheduler error: {str(e)}"

    # Define a task function
    def user_task_function(case: Case) -> dict:
        # Create agent with simulated tool and sub-agent
        thermostat_status_tool = tool_simulator.get_tool("get_thermostat_status")
    
        # Inspect initial shared state "home_temperature"
        initial_state = tool_simulator.get_state("home_temperature")
        print(f"[Home temperature state (before agent invocation)]:")
        print(f"  Initial state: {initial_state.get('initial_state')}")
        print(f"  Previous calls: {initial_state.get('previous_calls', [])}")
    
        # Showcase how user-agent interaction changes home temperature state
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a smart home assistant Alessa. You can check thermostat status. For temperature scheduling, you must consult the temperature_scheduler who has access to the smart thermostat system.",
            tools=[
                thermostat_status_tool,
                temperature_scheduler,
            ],
            callback_handler=None,
        )

        try:
            agent_response = agent(case.input)
        except Exception as e:
            agent_response = f"Agent execution error: {e}"

        print(f"[User]: {case.input}")
        print(f"[Agent]: {agent_response}")

        # Inspect final shared state "home_temperature" after agent interaction
        final_state = tool_simulator.get_state("home_temperature")
        print(f"[Home temperature state (after agent invocation)]:")
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
            name="schedule_based_temperature", 
            input="I'm going on vacation next week. Check my calendar and adjust the thermostat schedule to save energy while I'm away.",
            metadata={"category": "temperature", "expected_tools": ["calendar_service", "thermostat_controller"]},
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
        "name": report.cases[0].get("name", "schedule_based_temperature"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }

