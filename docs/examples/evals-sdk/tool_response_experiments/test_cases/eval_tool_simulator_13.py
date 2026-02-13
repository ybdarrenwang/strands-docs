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

    # Function tool for refrigerator status
    @tool_simulator.tool(
        output_schema=None,
        tool_prompt=function_prompt,
        share_state_id="kitchen_appliances",
        initial_state_description="Smart refrigerator: temperature (38°F), humidity (45%), contents (milk, eggs, vegetables, leftovers), inventory status (milk low, eggs ok)"
    )
    @tool
    def get_refrigerator_status() -> Dict[str, Any]:
        """Get current status of the smart refrigerator.
        
        Returns:
            Dict[str, Any]: Refrigerator status
            
        Output Schema:
            {
                "temperature": str,  # Temperature in Fahrenheit
                "humidity": str,  # Humidity percentage
                "contents": [str],  # List of items
                "inventory_status": {
                    "item_name": str  # Status (low, ok, full)
                },
                "shopping_list": [str],  # Items to purchase
                "energy_usage": str
            }
        """
        pass

    # MCP tool (shares state with kitchen appliances)
    @tool_simulator.tool(
        output_schema=mcp_schema,
        tool_prompt=mcp_prompt,
        share_state_id="kitchen_appliances")
    @tool
    def smart_fridge_controller(action: str, temperature: float = None, humidity: float = None, item: str = None) -> Dict[str, Any]:
        """Control smart refrigerator.
        
        Args:
            action: Action to perform (adjust_temp, adjust_humidity, check_inventory, add_to_shopping_list)
            temperature: Target temperature in Fahrenheit
            humidity: Target humidity percentage
            item: Item to add to shopping list
            
        Returns:
            Dict[str, Any]: MCP tool response with structured content
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["adjust_temp", "adjust_humidity", "check_inventory", "add_to_shopping_list"],
                        "description": "Action to perform"
                    },
                    "temperature": {
                        "type": "number",
                        "description": "Target temperature in Fahrenheit"
                    },
                    "humidity": {
                        "type": "number",
                        "description": "Target humidity percentage"
                    },
                    "item": {
                        "type": "string",
                        "description": "Item to add to shopping list"
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
                    "current_humidity": float,
                    "inventory_status": dict,
                    "shopping_list": [str]
                },
                "is_error": bool,
                "meta": {
                    "timestamp": str
                }
            }
        """
        # Initialize response data based on action
        inventory_status = {"milk": "low", "eggs": "ok", "vegetables": "ok", "leftovers": "ok"}
        shopping_list = ["milk"]
        current_temp = temperature if temperature is not None else 38
        current_humidity = humidity if humidity is not None else 45
    
        # Update data based on action
        if action == "add_to_shopping_list" and item:
            shopping_list.append(item)
    
        # Create structured content following the outputSchema
        structured_content = {
            "status": "success",
            "action": action,
            "current_temp": current_temp,
            "current_humidity": current_humidity,
            "inventory_status": inventory_status,
            "shopping_list": shopping_list
        }
    
        # Create response text based on action
        response_text = ""
        if action == "adjust_temp":
            response_text = f"Successfully adjusted refrigerator temperature to {temperature}°F"
        elif action == "adjust_humidity":
            response_text = f"Successfully adjusted refrigerator humidity to {humidity}%"
        elif action == "check_inventory":
            response_text = f"Current inventory status: milk (low), eggs (ok), vegetables (ok), leftovers (ok)"
        elif action == "add_to_shopping_list":
            response_text = f"Successfully added {item} to shopping list"
    
        # Create a proper MCP response as a dictionary
        return {
            "tool_use_id": "fridge_control_303",
            "content": [
                {
                    "type": "text",
                    "text": response_text,
                    "resource": None
                }
            ],
            "structured_content": structured_content,
            "is_error": False,
            "meta": {"timestamp": "2026-02-12T11:36:00Z"}
        }

    # API tool
    @tool_simulator.tool(
        output_schema=api_schema,
        tool_prompt=api_prompt,
    )
    @tool
    def music_service(query: str, type: str = "track", limit: int = 5) -> Dict[str, Any]:
        """Search for music by track, album, artist, or playlist.
        
        Args:
            query: Search query
            type: Search type (track, album, artist, playlist)
            limit: Maximum number of results
            
        Returns:
            Dict[str, Any]: Music search results
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "type": {
                        "type": "string",
                        "enum": ["track", "album", "artist", "playlist"],
                        "description": "Search type",
                        "default": "track"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
            
        Output Schema:
            {
                "query": str,
                "type": str,
                "results": [
                    {
                        "id": str,
                        "name": str,
                        "artist": str,
                        "album": str,
                        "duration": int,  # Seconds
                        "genre": str,
                        "year": int,
                        "preview_url": str
                    }
                ],
                "total_results": int
            }
        """
        pass

    # Create sub-agent (agent-as-tool) with simulated tools
    @tool
    def kitchen_entertainment_assistant(query: str) -> str:
        """Kitchen entertainment assistant that uses refrigerator status and music data to control the smart fridge based on user requests and entertainment preferences."""
        try:
            fridge_status_tool = tool_simulator.get_tool("get_refrigerator_status")
            fridge_tool = tool_simulator.get_tool("smart_fridge_controller")
            music_tool = tool_simulator.get_tool("music_service")
        
            control_agent = Agent(
                system_prompt="You are a kitchen entertainment assistant. Your job is to control the smart refrigerator using the smart_fridge_controller tool based on information from refrigerator status and music preferences. Always check current refrigerator status first, consider music preferences if relevant to the user's cooking or kitchen activities, then make appropriate refrigerator adjustments to meet the user's request.",
                tools=[fridge_status_tool, fridge_tool, music_tool],
                callback_handler=None,
            )
            response = control_agent(f"Kitchen entertainment request: {query}")
            return str(response)

        except Exception as e:
            return f"Kitchen entertainment assistant error: {str(e)}"

    # Define a task function
    def user_task_function(case: Case) -> dict:
        # Create agent with simulated tool and sub-agent
        fridge_status_tool = tool_simulator.get_tool("get_refrigerator_status")
    
        # Inspect initial shared state "kitchen_appliances"
        initial_state = tool_simulator.get_state("kitchen_appliances")
        print(f"[Kitchen appliances state (before agent invocation)]:")
        print(f"  Initial state: {initial_state.get('initial_state')}")
        print(f"  Previous calls: {initial_state.get('previous_calls', [])}")
    
        # Showcase how user-agent interaction changes kitchen appliances state
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a smart home assistant Alessa. You can check refrigerator status. For refrigerator control, you must consult the kitchen_entertainment_assistant who has access to the smart refrigerator system.",
            tools=[
                fridge_status_tool,
                kitchen_entertainment_assistant,
            ],
            callback_handler=None,
        )

        try:
            agent_response = agent(case.input)
        except Exception as e:
            agent_response = f"Agent execution error: {e}"

        print(f"[User]: {case.input}")
        print(f"[Agent]: {agent_response}")

        # Inspect final shared state "kitchen_appliances" after agent interaction
        final_state = tool_simulator.get_state("kitchen_appliances")
        print(f"[Kitchen appliances state (after agent invocation)]:")
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
            name="music_cooking_preparation", 
            input="I want to cook dinner with a playlist of Italian music. Check what ingredients I have in the fridge and add anything I'm missing for a pasta dish to my shopping list.",
            metadata={"category": "kitchen", "expected_tools": ["music_service", "smart_fridge_controller"]},
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
        "name": report.cases[0].get("name", "music_cooking_preparation"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }

