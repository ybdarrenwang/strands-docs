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

    # Function tool for entertainment system status
    @tool_simulator.tool(
        output_schema=None,
        tool_prompt=function_prompt,
        share_state_id="home_entertainment",
        initial_state_description="Home entertainment: TV (off), sound system (off), streaming device (off), game console (off)"
    )
    @tool
    def get_entertainment_status() -> Dict[str, Any]:
        """Get current status of the home entertainment system.
        
        Returns:
            Dict[str, Any]: Entertainment system status
            
        Output Schema:
            {
                "devices": {
                    "tv": str,  # "on" or "off"
                    "sound_system": str,
                    "streaming_device": str,
                    "game_console": str
                },
                "current_source": str,  # Active input source
                "volume": int  # Volume level (0-100)
            }
        """
        pass

    # MCP tool (shares state with home entertainment)
    @tool_simulator.tool(
        output_schema=mcp_schema,
        tool_prompt=mcp_prompt,
        share_state_id="home_entertainment"
    )
    @tool
    def entertainment_system_controller(device: str, action: str, content: str = None) -> Dict[str, Any]:
        """Control home entertainment system.
        
        Args:
            device: Device to control (tv, sound_system, streaming_device, game_console)
            action: Action to perform (turn_on, turn_off, play, pause, volume_up, volume_down)
            content: Optional content to play
            
        Returns:
            Dict[str, Any]: MCP tool response
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "device": {
                        "type": "string",
                        "description": "Device to control"
                    },
                    "action": {
                        "type": "string",
                        "description": "Action to perform"
                    },
                    "content": {
                        "type": "string",
                        "description": "Optional content to play"
                    }
                },
                "required": ["device", "action"]
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
    def social_media_service(platform: str, count: int = 5) -> Dict[str, Any]:
        """Get recent posts from a social media platform.
        
        Args:
            platform: Social media platform (twitter, instagram, facebook)
            count: Number of posts to retrieve (default: 5)
            
        Returns:
            Dict[str, Any]: Social media posts
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "platform": {
                        "type": "string",
                        "description": "Social media platform"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of posts to retrieve",
                        "default": 5
                    }
                },
                "required": ["platform"]
            }
            
        Output Schema:
            {
                "platform": str,
                "posts": [
                    {
                        "id": str,
                        "author": str,
                        "text": str,
                        "timestamp": str,
                        "likes": int,
                        "shares": int,
                        "comments": int
                    }
                ],
                "trending_topics": [str]  # Current trending topics
            }
        """
        pass

    # Create sub-agent (agent-as-tool) with simulated tools
    @tool
    def entertainment_assistant(query: str) -> str:
        """Entertainment assistant that uses entertainment system status and social media data to control the entertainment system based on user requests and trending content."""
        try:
            entertainment_status_tool = tool_simulator.get_tool("get_entertainment_status")
            entertainment_tool = tool_simulator.get_tool("entertainment_system_controller")
            social_media_tool = tool_simulator.get_tool("social_media_service")
        
            control_agent = Agent(
                system_prompt="You are an entertainment assistant. Your job is to control the home entertainment system using the entertainment_system_controller tool based on information from entertainment status and social media trends. Always check current entertainment system status first, check social media for trending content if relevant, then make appropriate entertainment system adjustments to meet the user's request.",
                tools=[entertainment_status_tool, entertainment_tool, social_media_tool],
                callback_handler=None,
            )
            response = control_agent(f"Entertainment request: {query}")
            return str(response)

        except Exception as e:
            return f"Entertainment assistant error: {str(e)}"

    # Define a task function
    def user_task_function(case: Case) -> dict:
        # Create agent with simulated tool and sub-agent
        entertainment_status_tool = tool_simulator.get_tool("get_entertainment_status")
    
        # Inspect initial shared state "home_entertainment"
        initial_state = tool_simulator.get_state("home_entertainment")
        print(f"[Home entertainment state (before agent invocation)]:")
        print(f"  Initial state: {initial_state.get('initial_state')}")
        print(f"  Previous calls: {initial_state.get('previous_calls', [])}")
    
        # Showcase how user-agent interaction changes home entertainment state
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a smart home assistant Alessa. You can check entertainment system status. For entertainment control, you must consult the entertainment_assistant who has access to the entertainment system.",
            tools=[
                entertainment_status_tool,
                entertainment_assistant,
            ],
            callback_handler=None,
        )

        try:
            agent_response = agent(case.input)
        except Exception as e:
            agent_response = f"Agent execution error: {e}"

        print(f"[User]: {case.input}")
        print(f"[Agent]: {agent_response}")

        # Inspect final shared state "home_entertainment" after agent interaction
        final_state = tool_simulator.get_state("home_entertainment")
        print(f"[Home entertainment state (after agent invocation)]:")
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
            name="social_media_entertainment", 
            input="What's trending on Twitter right now? Turn on the TV and play something related to the top trending topic.",
            metadata={"category": "entertainment", "expected_tools": ["social_media_service", "entertainment_system_controller"]},
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
        "name": report.cases[0].get("name", "social_media_entertainment"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }

