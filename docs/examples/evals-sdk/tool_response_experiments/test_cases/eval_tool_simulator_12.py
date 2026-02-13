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

    # Function tool for vacuum status
    @tool_simulator.tool(
        output_schema=None,
        tool_prompt=function_prompt,
        share_state_id="home_cleaning",
        initial_state_description="Home cleaning: robot vacuum (docked), battery (100%), last cleaned (2 days ago), cleaning schedule (daily at 10:00 AM)"
    )
    @tool
    def get_vacuum_status() -> Dict[str, Any]:
        """Get current status of the robot vacuum cleaner.
        
        Returns:
            Dict[str, Any]: Vacuum status information
            
        Output Schema:
            {
                "status": str,  # "docked", "cleaning", "idle", "charging"
                "battery": str,  # Battery percentage
                "last_cleaned": str,  # Time since last cleaning
                "cleaning_schedule": str,  # Scheduled cleaning times
                "current_room": str,  # Current room being cleaned (if active)
                "area_cleaned": str  # Area cleaned in last session
            }
        """
        pass

    # MCP tool (shares state with home cleaning)
    @tool_simulator.tool(
        output_schema=mcp_schema,
        tool_prompt=mcp_prompt,
        share_state_id="home_cleaning")
    @tool
    def robot_vacuum_controller(action: str, room: str = "all", mode: str = "auto", schedule_time: str = None) -> Dict[str, Any]:
        """Control robot vacuum cleaner.
        
        Args:
            action: Action to perform (start, stop, dock, schedule)
            room: Room to clean (all, living_room, kitchen, bedroom)
            mode: Cleaning mode (auto, spot, edge, max)
            schedule_time: Time to schedule cleaning (HH:MM format)
            
        Returns:
            Dict[str, Any]: MCP tool response
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["start", "stop", "dock", "schedule"],
                        "description": "Action to perform"
                    },
                    "room": {
                        "type": "string",
                        "description": "Room to clean"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["auto", "spot", "edge", "max"],
                        "description": "Cleaning mode"
                    },
                    "schedule_time": {
                        "type": "string",
                        "description": "Time to schedule (HH:MM)"
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
    def movie_database_service(query: str, year: int = None, genre: str = None) -> Dict[str, Any]:
        """Search for movies by title, year, or genre.
        
        Args:
            query: Movie title or search query
            year: Optional release year filter
            genre: Optional genre filter
            
        Returns:
            Dict[str, Any]: Movie search results
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Movie title or search query"
                    },
                    "year": {
                        "type": "integer",
                        "description": "Release year"
                    },
                    "genre": {
                        "type": "string",
                        "description": "Genre filter"
                    }
                },
                "required": ["query"]
            }
            
        Output Schema:
            {
                "query": str,
                "movies": [
                    {
                        "id": str,
                        "title": str,
                        "year": int,
                        "genre": [str],
                        "rating": float,  # IMDB rating
                        "director": str,
                        "cast": [str],
                        "runtime": int,  # Minutes
                        "plot": str,
                        "poster_url": str
                    }
                ],
                "total_results": int
            }
        """
        pass

    # Create sub-agent (agent-as-tool) with simulated tools
    @tool
    def entertainment_cleaning_assistant(query: str) -> str:
        """Entertainment cleaning assistant that uses vacuum status and movie data to control the robot vacuum based on user requests and movie viewing plans."""
        try:
            vacuum_status_tool = tool_simulator.get_tool("get_vacuum_status")
            vacuum_tool = tool_simulator.get_tool("robot_vacuum_controller")
            movie_tool = tool_simulator.get_tool("movie_database_service")
        
            control_agent = Agent(
                system_prompt="You are an entertainment cleaning assistant. Your job is to control the robot vacuum using the robot_vacuum_controller tool based on information from vacuum status and movie data. Always check current vacuum status first, consider movie viewing plans if relevant, then make appropriate vacuum control adjustments to meet the user's request.",
                tools=[vacuum_status_tool, vacuum_tool, movie_tool],
                callback_handler=None,
            )
            response = control_agent(f"Entertainment cleaning request: {query}")
            return str(response)

        except Exception as e:
            return f"Entertainment cleaning assistant error: {str(e)}"

    # Define a task function
    def user_task_function(case: Case) -> dict:
        # Create agent with simulated tool and sub-agent
        vacuum_status_tool = tool_simulator.get_tool("get_vacuum_status")
    
        # Inspect initial shared state "home_cleaning"
        initial_state = tool_simulator.get_state("home_cleaning")
        print(f"[Home cleaning state (before agent invocation)]:")
        print(f"  Initial state: {initial_state.get('initial_state')}")
        print(f"  Previous calls: {initial_state.get('previous_calls', [])}")
    
        # Showcase how user-agent interaction changes home cleaning state
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a smart home assistant Alessa. You can check vacuum status. For vacuum control, you must consult the entertainment_cleaning_assistant who has access to the robot vacuum system.",
            tools=[
                vacuum_status_tool,
                entertainment_cleaning_assistant,
            ],
            callback_handler=None,
        )

        try:
            agent_response = agent(case.input)
        except Exception as e:
            agent_response = f"Agent execution error: {e}"

        print(f"[User]: {case.input}")
        print(f"[Agent]: {agent_response}")

        # Inspect final shared state "home_cleaning" after agent interaction
        final_state = tool_simulator.get_state("home_cleaning")
        print(f"[Home cleaning state (after agent invocation)]:")
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
            name="movie_vacuum_coordination", 
            input="I want to watch the latest Marvel movie tonight. Find out what it is and make sure the living room is vacuumed before I start watching.",
            metadata={"category": "cleaning", "expected_tools": ["movie_database_service", "robot_vacuum_controller"]},
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
        "name": report.cases[0].get("name", "movie_vacuum_coordination"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }

