from typing import Dict, Any
import argparse
import json
from strands import Agent
from strands.tools.decorator import tool
from strands_evals import Case, Experiment
from strands_evals.evaluators import GoalSuccessRateEvaluator
from strands_evals.simulation.tool_simulator import ToolSimulator

from strands_evals.mappers import StrandsInMemorySessionMapper
from strands_evals.telemetry import StrandsEvalsTelemetry

def run_test(function_prompt, mcp_prompt, api_prompt, mcp_schema, api_schema):
    # Setup telemetry and tool simulator upfront
    telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
    memory_exporter = telemetry.in_memory_exporter
    tool_simulator = ToolSimulator()

    # Function tool for coffee maker status
    @tool_simulator.tool(
        tool_prompt=function_prompt,
        share_state_id="kitchen_coffee",
        initial_state_description="Coffee maker: status (off), water level (full), coffee beans (75%), last brew (8 hours ago)"
    )
    @tool
    def get_coffee_maker_status() -> Dict[str, Any]:
        """Get current status of the smart coffee maker.
        
        Returns:
            Dict[str, Any]: Coffee maker status information
            
        Output Schema:
            {
                "power_state": str,  # "on" or "off"
                "water_level": str,  # "empty", "low", "medium", "full"
                "coffee_beans_level": str,  # Percentage (e.g., "75%")
                "last_brew_time": str,  # Time since last brew (e.g., "8 hours ago")
                "current_status": str  # Human-readable status message
            }
        """
        pass

    # MCP tool (shares state with kitchen coffee)
    @tool_simulator.tool(
        output_schema=mcp_schema,
        tool_prompt=mcp_prompt,
        share_state_id="kitchen_coffee"
    )
    @tool
    def smart_coffee_maker_controller(action: str, brew_type: str = "regular", strength: str = "medium", schedule_time: str = None) -> Dict[str, Any]:
        """Control smart coffee maker with various brewing options.
        
        Args:
            action: Action to perform (brew, schedule, clean, stop)
            brew_type: Type of coffee to brew (espresso, americano, latte, cappuccino, regular)
            strength: Coffee strength (mild, medium, strong)
            schedule_time: Time to schedule brewing (HH:MM format)
            
        Returns:
            Dict[str, Any]: MCP tool response
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string", 
                        "enum": ["brew", "schedule", "clean", "stop"],
                        "description": "Action to perform"
                    },
                    "brew_type": {
                        "type": "string",
                        "enum": ["espresso", "americano", "latte", "cappuccino", "regular"],
                        "description": "Type of coffee to brew"
                    },
                    "strength": {
                        "type": "string",
                        "enum": ["mild", "medium", "strong"],
                        "description": "Coffee strength"
                    },
                    "schedule_time": {
                        "type": "string",
                        "description": "Time to schedule brewing (HH:MM format)"
                    }
                },
                "required": ["action"]
            }
            
        Output Schema:
            {
                "tool_use_id": str,  # Unique identifier for this tool use
                "content": [
                    {
                        "type": "text",
                        "text": str,  # Human-readable response message
                        "resource": null
                    }
                ],
                "is_error": bool,  # Whether an error occurred
                "meta": {
                    "timestamp": str  # ISO 8601 timestamp
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
    def calendar_reminder_service(date: str = "today", category: str = None) -> Dict[str, Any]:
        """Get calendar reminders for a specific date and optional category.
        
        Args:
            date: Date to get reminders for (default: "today")
            category: Optional category filter for reminders
            
        Returns:
            Dict[str, Any]: Calendar reminders data
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date to get reminders for",
                        "default": "today"
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional category filter"
                    }
                },
                "required": []
            }
            
        Output Schema:
            {
                "date": str,  # Date of the reminders
                "reminders": [
                    {
                        "time": str,  # Time of reminder (HH:MM format)
                        "title": str,  # Reminder title
                        "description": str,  # Detailed description
                        "category": str,  # Category (work, personal, meeting, etc.)
                        "priority": str  # Priority level (high, medium, low)
                    }
                ],
                "total_count": int  # Total number of reminders
            }
        """
        pass

    # Create sub-agent (agent-as-tool) with simulated tools
    @tool
    def morning_routine_assistant(query: str) -> str:
        """Morning routine assistant that uses coffee maker status and calendar reminders to control the coffee maker based on user requests and schedule."""
        try:
            coffee_status_tool = tool_simulator.get_tool("get_coffee_maker_status")
            coffee_maker_tool = tool_simulator.get_tool("smart_coffee_maker_controller")
            calendar_tool = tool_simulator.get_tool("calendar_reminder_service")
            
            control_agent = Agent(
                system_prompt="You are a morning routine assistant. Your job is to control the smart coffee maker using the smart_coffee_maker_controller tool based on information from coffee maker status and calendar reminders. Always check current coffee maker status first, consider calendar reminders if relevant to the user's schedule, then make appropriate coffee maker adjustments to meet the user's request.",
                tools=[coffee_status_tool, coffee_maker_tool, calendar_tool],
                callback_handler=None,
            )
            response = control_agent(f"Morning routine request: {query}")
            return str(response)

        except Exception as e:
            return f"Morning routine assistant error: {str(e)}"

    # Define a task function
    def user_task_function(case: Case) -> dict:
        # Create agent with simulated tool and sub-agent
        coffee_status_tool = tool_simulator.get_tool("get_coffee_maker_status")
        
        # Inspect initial shared state "kitchen_coffee"
        initial_state = tool_simulator.get_state("kitchen_coffee")
        print(f"[Kitchen coffee state (before agent invocation)]:")
        print(f"  Initial state: {initial_state.get('initial_state')}")
        print(f"  Previous calls: {initial_state.get('previous_calls', [])}")
        
        # Showcase how user-agent interaction changes kitchen coffee state
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a smart home assistant Alessa. You can check coffee maker status. For coffee maker control, you must consult the morning_routine_assistant who has access to the smart coffee maker system.",
            tools=[
                coffee_status_tool,
                morning_routine_assistant,
            ],
            callback_handler=None,
        )

        try:
            agent_response = agent(case.input)
        except Exception as e:
            agent_response = f"Agent execution error: {e}"

        print(f"[User]: {case.input}")
        print(f"[Agent]: {agent_response}")

        # Inspect final shared state "kitchen_coffee" after agent interaction
        final_state = tool_simulator.get_state("kitchen_coffee")
        print(f"[Kitchen coffee state (after agent invocation)]:")
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
            name="morning_coffee_schedule", 
            input="I have an early meeting tomorrow. Check my calendar and schedule the coffee maker to brew a strong coffee 30 minutes before my first appointment.",
            metadata={"category": "morning_routine", "expected_tools": ["calendar_reminder_service", "smart_coffee_maker_controller"]},
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
        "name": report.cases[0].get("name", "morning_coffee_schedule"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }

