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

    # Function tool for lock status
    @tool_simulator.tool(
        output_schema=None,
        tool_prompt=function_prompt,
        share_state_id="home_locks",
        initial_state_description="Home locks: front door (locked), back door (locked), garage door (locked), all windows (locked)"
    )
    @tool
    def get_lock_status() -> Dict[str, Any]:
        """Get current status of all smart locks in the home.
        
        Returns:
            Dict[str, Any]: Lock status information
            
        Output Schema:
            {
                "locks": {
                    "front_door": str,  # "locked" or "unlocked"
                    "back_door": str,
                    "garage_door": str
                },
                "windows": str,  # "all locked" or specific status
                "last_activity": str,  # Timestamp of last lock/unlock
                "battery_levels": {
                    "front_door": str,  # Battery percentage
                    "back_door": str,
                    "garage_door": str
                }
            }
        """
        pass

    # MCP tool (shares state with home locks)
    @tool_simulator.tool(
        output_schema=mcp_schema,
        tool_prompt=mcp_prompt,
        share_state_id="home_locks")
    @tool
    def smart_lock_controller(lock_id: str, action: str, duration: float = 5) -> Dict[str, Any]:
        """Control home smart locks.
        
        Args:
            lock_id: Lock identifier (front_door, back_door, garage_door)
            action: Action to perform (lock, unlock, temp_unlock)
            duration: Duration in minutes for temp_unlock
            
        Returns:
            Dict[str, Any]: MCP tool response
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "lock_id": {
                        "type": "string",
                        "description": "Lock identifier"
                    },
                    "action": {
                        "type": "string",
                        "enum": ["lock", "unlock", "temp_unlock"],
                        "description": "Action to perform"
                    },
                    "duration": {
                        "type": "number",
                        "description": "Duration in minutes for temp_unlock"
                    }
                },
                "required": ["lock_id", "action"]
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
    def sports_scores_service(sport: str, team: str = None, league: str = None) -> Dict[str, Any]:
        """Get sports scores for a specific sport, team, or league.
        
        Args:
            sport: Sport type (basketball, football, baseball, soccer, hockey)
            team: Optional team name filter
            league: Optional league name (NBA, NFL, MLB, MLS, NHL)
            
        Returns:
            Dict[str, Any]: Sports scores and game information
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "sport": {
                        "type": "string",
                        "description": "Sport type"
                    },
                    "team": {
                        "type": "string",
                        "description": "Optional team name"
                    },
                    "league": {
                        "type": "string",
                        "description": "Optional league name"
                    }
                },
                "required": ["sport"]
            }
            
        Output Schema:
            {
                "sport": str,
                "league": str,
                "games": [
                    {
                        "game_id": str,
                        "date": str,
                        "time": str,
                        "home_team": str,
                        "away_team": str,
                        "home_score": int,
                        "away_score": int,
                        "status": str,  # "live", "final", "scheduled"
                        "period": str  # Current period/quarter
                    }
                ],
                "standings": [
                    {
                        "team": str,
                        "wins": int,
                        "losses": int,
                        "ranking": int
                    }
                ]
            }
        """
        pass

    # Create sub-agent (agent-as-tool) with simulated tools
    @tool
    def sports_security_assistant(query: str) -> str:
        """Sports security assistant that uses lock status and sports scores data to control smart locks based on user requests and game schedules."""
        try:
            lock_status_tool = tool_simulator.get_tool("get_lock_status")
            lock_tool = tool_simulator.get_tool("smart_lock_controller")
            sports_tool = tool_simulator.get_tool("sports_scores_service")
        
            control_agent = Agent(
                system_prompt="You are a sports security assistant. Your job is to control the smart locks using the smart_lock_controller tool based on information from lock status and sports scores. Always check current lock status first, consider sports scores and game times if relevant to the user's schedule, then make appropriate lock control adjustments to meet the user's request.",
                tools=[lock_status_tool, lock_tool, sports_tool],
                callback_handler=None,
            )
            response = control_agent(f"Sports security request: {query}")
            return str(response)

        except Exception as e:
            return f"Sports security assistant error: {str(e)}"

    # Define a task function
    def user_task_function(case: Case) -> dict:
        # Create agent with simulated tool and sub-agent
        lock_status_tool = tool_simulator.get_tool("get_lock_status")
    
        # Inspect initial shared state "home_locks"
        initial_state = tool_simulator.get_state("home_locks")
        print(f"[Home locks state (before agent invocation)]:")
        print(f"  Initial state: {initial_state.get('initial_state')}")
        print(f"  Previous calls: {initial_state.get('previous_calls', [])}")
    
        # Showcase how user-agent interaction changes home locks state
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a smart home assistant Alessa. You can check lock status. For lock control, you must consult the sports_security_assistant who has access to the smart lock system.",
            tools=[
                lock_status_tool,
                sports_security_assistant,
            ],
            callback_handler=None,
        )

        try:
            agent_response = agent(case.input)
        except Exception as e:
            agent_response = f"Agent execution error: {e}"

        print(f"[User]: {case.input}")
        print(f"[Agent]: {agent_response}")

        # Inspect final shared state "home_locks" after agent interaction
        final_state = tool_simulator.get_state("home_locks")
        print(f"[Home locks state (after agent invocation)]:")
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
            name="sports_lock_control", 
            input="My friends are coming over to watch the Lakers game. What's the current score and unlock the front door for them to come in?",
            metadata={"category": "security", "expected_tools": ["sports_scores_service", "smart_lock_controller"]},
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
        "name": report.cases[0].get("name", "sports_lock_control"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }

