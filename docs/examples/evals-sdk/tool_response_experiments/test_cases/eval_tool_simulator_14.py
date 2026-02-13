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

    # Function tool for water heater status
    @tool_simulator.tool(
        output_schema=None,
        tool_prompt=function_prompt,
        share_state_id="home_water",
        initial_state_description="Water heater: temperature (120°F), mode (standard), energy usage (medium), last maintenance (3 months ago)"
    )
    @tool
    def get_water_heater_status() -> Dict[str, Any]:
        """Get current status of the smart water heater.
        
        Returns:
            Dict[str, Any]: Water heater status
            
        Output Schema:
            {
                "temperature": str,  # Temperature in Fahrenheit
                "mode": str,  # "standard", "eco", "high_demand", "vacation"
                "energy_usage": str,  # "low", "medium", "high"
                "last_maintenance": str,  # Time since last maintenance
                "estimated_savings": str  # Energy savings information
            }
        """
        pass

    # MCP tool (shares state with home water)
    @tool_simulator.tool(
        output_schema=mcp_schema,
        tool_prompt=mcp_prompt,
        share_state_id="home_water")
    @tool
    def water_heater_controller(action: str, temperature: float = None, mode: str = None, duration: float = None) -> Dict[str, Any]:
        """Control smart water heater.
        
        Args:
            action: Action to perform (adjust_temp, change_mode, schedule_maintenance, boost)
            temperature: Target temperature in Fahrenheit
            mode: Operation mode (standard, eco, high_demand, vacation)
            duration: Duration in hours for boost mode
            
        Returns:
            Dict[str, Any]: MCP tool response with structured content
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["adjust_temp", "change_mode", "schedule_maintenance", "boost"],
                        "description": "Action to perform"
                    },
                    "temperature": {
                        "type": "number",
                        "description": "Target temperature in Fahrenheit"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["standard", "eco", "high_demand", "vacation"],
                        "description": "Operation mode"
                    },
                    "duration": {
                        "type": "number",
                        "description": "Duration in hours for boost"
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
                    "current_temp": float,
                    "current_mode": str,
                    "energy_usage": str,
                    "estimated_savings": str
                },
                "is_error": bool,
                "meta": {
                    "timestamp": str
                }
            }
        """
        # Initialize default values
        current_temp = temperature if temperature is not None else 120
        current_mode = mode if mode is not None else "standard"
    
        # Determine energy usage and savings based on action and settings
        energy_usage = "low" if current_mode == "eco" or (current_temp < 120) else "medium" if current_mode == "standard" else "high"
        estimated_savings = "25% compared to standard mode" if current_mode == "eco" else "0%" if current_mode == "standard" else "-15% (higher usage)" if current_mode == "high_demand" else "40% (vacation mode)"
    
        # Create structured content following the outputSchema
        structured_content = {
            "status": "success",
            "action": action,
            "current_temp": current_temp,
            "current_mode": current_mode,
            "energy_usage": energy_usage,
            "estimated_savings": estimated_savings
        }
    
        # Create response text based on action
        response_text = ""
        if action == "adjust_temp":
            response_text = f"Successfully adjusted water heater temperature to {temperature}°F"
        elif action == "change_mode":
            response_text = f"Successfully changed water heater mode to {mode}"
        elif action == "schedule_maintenance":
            response_text = "Successfully scheduled water heater maintenance for next available appointment"
        elif action == "boost":
            boost_duration = duration if duration is not None else 1
            response_text = f"Successfully activated water heater boost mode for {boost_duration} hour(s)"
    
        # Create a proper MCP response as a dictionary
        return {
            "tool_use_id": "water_heater_control_404",
            "content": [
                {
                    "type": "text",
                    "text": response_text,
                    "resource": None
                }
            ],
            "structured_content": structured_content,
            "is_error": False,
            "meta": {"timestamp": "2026-02-12T11:37:00Z"}
        }

    # API tool
    @tool_simulator.tool(
        output_schema=api_schema,
        tool_prompt=api_prompt,
    )
    @tool
    def health_service(activity: str, age_group: str = "adult", duration: int = 30) -> Dict[str, Any]:
        """Get health recommendations for specific activities and age groups.
        
        Args:
            activity: Type of activity (workout, muscle_recovery, relaxation, sleep)
            age_group: Age group (child, teen, adult, senior)
            duration: Duration in minutes
            
        Returns:
            Dict[str, Any]: Health recommendations
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "activity": {
                        "type": "string",
                        "description": "Type of activity"
                    },
                    "age_group": {
                        "type": "string",
                        "enum": ["child", "teen", "adult", "senior"],
                        "description": "Age group",
                        "default": "adult"
                    },
                    "duration": {
                        "type": "integer",
                        "description": "Duration in minutes",
                        "default": 30
                    }
                },
                "required": ["activity"]
            }
            
        Output Schema:
            {
                "activity": str,
                "age_group": str,
                "recommendations": {
                    "temperature": str,  # Recommended temperature
                    "duration": str,  # Recommended duration
                    "frequency": str,  # How often
                    "benefits": [str],  # Health benefits
                    "precautions": [str],  # Safety precautions
                    "tips": [str]  # Additional tips
                }
            }
        """
        pass

    # Create sub-agent (agent-as-tool) with simulated tools
    @tool
    def wellness_assistant(query: str) -> str:
        """Wellness assistant that uses water heater status and health data to control the water heater based on user requests and wellness activities."""
        try:
            water_heater_status_tool = tool_simulator.get_tool("get_water_heater_status")
            water_heater_tool = tool_simulator.get_tool("water_heater_controller")
            health_tool = tool_simulator.get_tool("health_service")
        
            control_agent = Agent(
                system_prompt="You are a wellness assistant. Your job is to control the water heater using the water_heater_controller tool based on information from water heater status and health recommendations. Always check current water heater status first, consider health recommendations if relevant to the user's wellness activities, then make appropriate water heater adjustments to meet the user's request.",
                tools=[water_heater_status_tool, water_heater_tool, health_tool],
                callback_handler=None,
            )
            response = control_agent(f"Wellness request: {query}")
            return str(response)

        except Exception as e:
            return f"Wellness assistant error: {str(e)}"

    # Define a task function
    def user_task_function(case: Case) -> dict:
        # Create agent with simulated tool and sub-agent
        water_heater_status_tool = tool_simulator.get_tool("get_water_heater_status")
    
        # Inspect initial shared state "home_water"
        initial_state = tool_simulator.get_state("home_water")
        print(f"[Home water state (before agent invocation)]:")
        print(f"  Initial state: {initial_state.get('initial_state')}")
        print(f"  Previous calls: {initial_state.get('previous_calls', [])}")
    
        # Showcase how user-agent interaction changes home water state
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a smart home assistant Alessa. You can check water heater status. For water heater control, you must consult the wellness_assistant who has access to the smart water heater system.",
            tools=[
                water_heater_status_tool,
                wellness_assistant,
            ],
            callback_handler=None,
        )

        try:
            agent_response = agent(case.input)
        except Exception as e:
            agent_response = f"Agent execution error: {e}"

        print(f"[User]: {case.input}")
        print(f"[Agent]: {agent_response}")

        # Inspect final shared state "home_water" after agent interaction
        final_state = tool_simulator.get_state("home_water")
        print(f"[Home water state (after agent invocation)]:")
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
            name="health_water_temperature", 
            input="I'm planning to take a hot bath for muscle recovery after my workout. What temperature is recommended for muscle recovery and can you set the water heater accordingly?",
            metadata={"category": "wellness", "expected_tools": ["health_service", "water_heater_controller"]},
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
        "name": report.cases[0].get("name", "health_water_temperature"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }

