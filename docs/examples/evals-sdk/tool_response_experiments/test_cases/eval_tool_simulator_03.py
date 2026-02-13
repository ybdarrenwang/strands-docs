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

    # Function tool for door status
    @tool_simulator.tool(
        output_schema=None,
        tool_prompt=function_prompt,
        share_state_id="home_security",
        initial_state_description="Home security: front door (locked), back door (locked), garage door (closed), all windows (closed)"
    )
    @tool
    def get_door_status(date: str, time: str) -> Dict[str, Any]:
        """Get current status of all doors in the home.
        
        Args:
            date: Date to check status for
            time: Time to check status for
        
        Returns:
            Dict[str, Any]: Door status information
            
        Output Schema:
            {
                "doors": {
                    "front_door": {
                        "state": str,  # "locked" or "unlocked"
                        "last_activity": str  # Timestamp
                    },
                    "back_door": {
                        "state": str,
                        "last_activity": str
                    },
                    "garage_door": {
                        "state": str,  # "closed" or "open"
                        "last_activity": str
                    }
                },
                "windows": {
                    "status": str  # "all closed" or specific status
                }
            }
        """
        pass

    # MCP tool (shares state with home security)
    @tool_simulator.tool(
        output_schema=mcp_schema,
        tool_prompt=mcp_prompt,
        share_state_id="home_security"
    )
    @tool
    def smart_door_controller(door: str, action: str) -> Dict[str, Any]:
        """Control home smart door locks and garage door.
        
        Args:
            door: Door to control (front, back, garage)
            action: Action to perform (lock, unlock, open, close)
            
        Returns:
            Dict[str, Any]: MCP tool response
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "door": {
                        "type": "string",
                        "description": "Door to control (front, back, garage)"
                    },
                    "action": {
                        "type": "string",
                        "enum": ["lock", "unlock", "open", "close"],
                        "description": "Action to perform"
                    }
                },
                "required": ["door", "action"]
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
    def news_service(topic: str, region: str = "US") -> Dict[str, Any]:
        """Get latest news headlines by topic and region.
        
        Args:
            topic: News topic to search for
            region: Region for news (default: "US")
            
        Returns:
            Dict[str, Any]: News articles
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "News topic to search for"
                    },
                    "region": {
                        "type": "string",
                        "description": "Region for news",
                        "default": "US"
                    }
                },
                "required": ["topic"]
            }
            
        Output Schema:
            {
                "topic": str,
                "region": str,
                "articles": [
                    {
                        "title": str,
                        "source": str,
                        "published_date": str,
                        "summary": str,
                        "url": str,
                        "sentiment": str  # "positive", "neutral", "negative"
                    }
                ],
                "total_results": int
            }
        """
        pass

    # Create sub-agent (agent-as-tool) with simulated tools
    @tool
    def security_assistant(query: str) -> str:
        """Security assistant that uses door status and news data to control the door system based on user requests."""
        try:
            door_status_tool = tool_simulator.get_tool("get_door_status")
            door_tool = tool_simulator.get_tool("smart_door_controller")
            news_tool = tool_simulator.get_tool("news_service")
        
            control_agent = Agent(
                system_prompt="You are a home security assistant. Your job is to control the smart door system using the smart_door_controller tool based on information from door sensors and relevant news. Always check current door status first, consider news about local security incidents if relevant, then make appropriate door control adjustments to meet the user's request.",
                tools=[door_status_tool, door_tool, news_tool],
                callback_handler=None,
            )
            response = control_agent(f"Security control request: {query}")
            return str(response)

        except Exception as e:
            return f"Security assistant error: {str(e)}"

    # Define a task function
    def user_task_function(case: Case) -> dict:
        # Create agent with simulated tool and sub-agent
        door_status_tool = tool_simulator.get_tool("get_door_status")
    
        # Inspect initial shared state "home_security"
        initial_state = tool_simulator.get_state("home_security")
        print(f"[Home security state (before agent invocation)]:")
        print(f"  Initial state: {initial_state.get('initial_state')}")
        print(f"  Previous calls: {initial_state.get('previous_calls', [])}")
    
        # Showcase how user-agent interaction changes home security state
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a smart home assistant Alessa. You can check home door status. For door control, you must consult the security_assistant who has access to the smart door system.",
            tools=[
                door_status_tool,
                security_assistant,
            ],
            callback_handler=None,
        )

        try:
            agent_response = agent(case.input)
        except Exception as e:
            agent_response = f"Agent execution error: {e}"

        print(f"[User]: {case.input}")
        print(f"[Agent]: {agent_response}")

        # Inspect final shared state "home_security" after agent interaction
        final_state = tool_simulator.get_state("home_security")
        print(f"[Home security state (after agent invocation)]:")
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
            name="security_news_response", 
            input="I heard there might be break-ins in our neighborhood. Check the local crime news and make sure all our doors are locked.",
            metadata={"category": "security", "expected_tools": ["news_service", "smart_door_controller"]},
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
        "name": report.cases[0].get("name", "security_news_response"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }

