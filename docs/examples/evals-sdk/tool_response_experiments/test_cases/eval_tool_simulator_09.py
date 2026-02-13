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

    # Function tool for window blinds status
    @tool_simulator.tool(
        output_schema=None,
        tool_prompt=function_prompt,
        share_state_id="home_blinds",
        initial_state_description="Home window blinds: living room (closed), bedroom (open 50%), kitchen (open), office (closed)"
    )
    @tool
    def get_blinds_status() -> Dict[str, Any]:
        """Get current status of all window blinds in the home.
        
        Returns:
            Dict[str, Any]: Window blinds status
            
        Output Schema:
            {
                "rooms": {
                    "living_room": str,  # "closed", "open", or percentage
                    "bedroom": str,
                    "kitchen": str,
                    "office": str
                },
                "overall_status": str  # Human-readable summary
            }
        """
        pass

    # MCP tool (shares state with home blinds)
    @tool_simulator.tool(
        output_schema=mcp_schema,
        tool_prompt=mcp_prompt,
        share_state_id="home_blinds"
    )
    @tool
    def window_blinds_controller(room: str, action: str, position: float = None) -> Dict[str, Any]:
        """Control home window blinds.
        
        Args:
            room: Room to control blinds for
            action: Action to perform (open, close, adjust)
            position: Position percentage (0-100) for adjust action
            
        Returns:
            Dict[str, Any]: MCP tool response
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "room": {
                        "type": "string",
                        "description": "Room to control blinds for"
                    },
                    "action": {
                        "type": "string",
                        "enum": ["open", "close", "adjust"],
                        "description": "Action to perform"
                    },
                    "position": {
                        "type": "number",
                        "description": "Position percentage (0-100)"
                    }
                },
                "required": ["room", "action"]
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
    def restaurant_service(cuisine: str, location: str, price_range: str = "$$") -> Dict[str, Any]:
        """Search for restaurants by cuisine, location, and price range.
        
        Args:
            cuisine: Type of cuisine (italian, chinese, mexican, etc.)
            location: Location to search in
            price_range: Price range ($, $$, $$$, $$$$)
            
        Returns:
            Dict[str, Any]: Restaurant search results
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "cuisine": {
                        "type": "string",
                        "description": "Type of cuisine"
                    },
                    "location": {
                        "type": "string",
                        "description": "Location to search in"
                    },
                    "price_range": {
                        "type": "string",
                        "enum": ["$", "$$", "$$$", "$$$$"],
                        "description": "Price range",
                        "default": "$$"
                    }
                },
                "required": ["cuisine", "location"]
            }
            
        Output Schema:
            {
                "cuisine": str,
                "location": str,
                "restaurants": [
                    {
                        "name": str,
                        "address": str,
                        "rating": float,  # 1-5 stars
                        "price_range": str,
                        "ambiance": str,  # "casual", "romantic", "formal"
                        "hours": str,
                        "phone": str,
                        "reviews_count": int
                    }
                ],
                "total_results": int
            }
        """
        pass

    # Create sub-agent (agent-as-tool) with simulated tools
    @tool
    def ambiance_assistant(query: str) -> str:
        """Ambiance assistant that uses blinds status and restaurant data to control window blinds based on user requests and dining preferences."""
        try:
            blinds_status_tool = tool_simulator.get_tool("get_blinds_status")
            blinds_tool = tool_simulator.get_tool("window_blinds_controller")
            restaurant_tool = tool_simulator.get_tool("restaurant_service")
        
            control_agent = Agent(
                system_prompt="You are an ambiance assistant. Your job is to control the window blinds using the window_blinds_controller tool based on information from blinds status and restaurant preferences. Always check current blinds status first, consider restaurant ambiance preferences if relevant, then make appropriate blinds adjustments to meet the user's request.",
                tools=[blinds_status_tool, blinds_tool, restaurant_tool],
                callback_handler=None,
            )
            response = control_agent(f"Ambiance request: {query}")
            return str(response)

        except Exception as e:
            return f"Ambiance assistant error: {str(e)}"

    # Define a task function
    def user_task_function(case: Case) -> dict:
        # Create agent with simulated tool and sub-agent
        blinds_status_tool = tool_simulator.get_tool("get_blinds_status")
    
        # Inspect initial shared state "home_blinds"
        initial_state = tool_simulator.get_state("home_blinds")
        print(f"[Home blinds state (before agent invocation)]:")
        print(f"  Initial state: {initial_state.get('initial_state')}")
        print(f"  Previous calls: {initial_state.get('previous_calls', [])}")
    
        # Showcase how user-agent interaction changes home blinds state
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a smart home assistant Alessa. You can check window blinds status. For blinds control, you must consult the ambiance_assistant who has access to the smart blinds system.",
            tools=[
                blinds_status_tool,
                ambiance_assistant,
            ],
            callback_handler=None,
        )

        try:
            agent_response = agent(case.input)
        except Exception as e:
            agent_response = f"Agent execution error: {e}"

        print(f"[User]: {case.input}")
        print(f"[Agent]: {agent_response}")

        # Inspect final shared state "home_blinds" after agent interaction
        final_state = tool_simulator.get_state("home_blinds")
        print(f"[Home blinds state (after agent invocation)]:")
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
            name="restaurant_ambiance", 
            input="I'm planning a romantic Italian dinner at home tonight. Find a nice Italian restaurant for inspiration and adjust the blinds to create a similar ambiance.",
            metadata={"category": "ambiance", "expected_tools": ["restaurant_service", "window_blinds_controller"]},
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
        "name": report.cases[0].get("name", "restaurant_ambiance"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }

