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

    # Function tool for irrigation system status
    @tool_simulator.tool(
        output_schema=None,
        tool_prompt=function_prompt,
        share_state_id="garden_irrigation",
        initial_state_description="Garden irrigation: all zones off, soil moisture 60%, last watered 2 days ago, schedule active"
    )
    @tool
    def get_irrigation_status() -> Dict[str, Any]:
        """Get current status of the garden irrigation system.
        
        Returns:
            Dict[str, Any]: Irrigation system status
            
        Output Schema:
            {
                "zones": {
                    "front": str,  # "on" or "off"
                    "back": str,
                    "side": str
                },
                "soil_moisture": str,  # Percentage (e.g., "60%")
                "last_watered": str,  # Time since last watering
                "schedule_active": bool,
                "next_scheduled": str  # Next scheduled watering time
            }
        """
        pass

    # MCP tool (shares state with garden irrigation)
    @tool_simulator.tool(
        output_schema=mcp_schema,
        tool_prompt=mcp_prompt,
        share_state_id="garden_irrigation"
    )
    @tool
    def irrigation_system_controller(zone: str, action: str, duration: float = 20, schedule_enabled: bool = True) -> Dict[str, Any]:
        """Control garden irrigation system with multiple zones and scheduling.
        
        Args:
            zone: Irrigation zone to control (front, back, side, all)
            action: Action to perform (start, stop)
            duration: Duration in minutes for watering
            schedule_enabled: Whether to enable scheduled watering
            
        Returns:
            Dict with schema:
            {
                "name": "irrigation_system_controller",
                "description": "Control garden irrigation system with multiple zones and scheduling",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "zone": {"type": "string", "description": "Irrigation zone to control (front, back, side, all)"},
                        "action": {"type": "string", "enum": ["start", "stop"], "description": "Action to perform"},
                        "duration": {"type": "number", "description": "Duration in minutes for watering"},
                        "schedule_enabled": {"type": "boolean", "description": "Whether to enable scheduled watering"}
                    },
                    "required": ["zone", "action"]
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
    def translation_service(text: str, source_language: str, target_language: str) -> Dict[str, Any]:
        """Translate text between languages.
        
        Args:
            text: Text to translate
            source_language: Source language code (e.g., "en", "es", "fr")
            target_language: Target language code
            
        Returns:
            Dict[str, Any]: Translation result
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to translate"
                    },
                    "source_language": {
                        "type": "string",
                        "description": "Source language code"
                    },
                    "target_language": {
                        "type": "string",
                        "description": "Target language code"
                    }
                },
                "required": ["text", "source_language", "target_language"]
            }
            
        Output Schema:
            {
                "original_text": str,
                "translated_text": str,
                "source_language": str,
                "target_language": str,
                "confidence": float  # Translation confidence score (0-1)
            }
        """
        pass

    # Create sub-agent (agent-as-tool) with simulated tools
    @tool
    def garden_assistant(query: str) -> str:
        """Garden assistant that uses irrigation status and translation services to control the irrigation system based on user requests in any language."""
        try:
            irrigation_status_tool = tool_simulator.get_tool("get_irrigation_status")
            irrigation_tool = tool_simulator.get_tool("irrigation_system_controller")
            translation_tool = tool_simulator.get_tool("translation_service")
        
            control_agent = Agent(
                system_prompt="You are a multilingual garden assistant. Your job is to control the irrigation system using the irrigation_system_controller tool based on information from irrigation status. You can understand and respond to requests in multiple languages using the translation service. Always check current irrigation status first, translate user requests if needed, then make appropriate irrigation system adjustments to meet the user's request.",
                tools=[irrigation_status_tool, irrigation_tool, translation_tool],
                callback_handler=None,
            )
            response = control_agent(f"Garden irrigation request: {query}")
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
            system_prompt="You are a smart home assistant Alessa. You can check irrigation system status. For irrigation control, you must consult the garden_assistant who has access to the irrigation system.",
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
            name="multilingual_irrigation_control", 
            input="'Regar el jardín por 15 minutos' - Can you translate this Spanish request and water the garden as requested?",
            metadata={"category": "irrigation", "expected_tools": ["translation_service", "irrigation_system_controller"]},
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
        "name": report.cases[0].get("name", "multilingual_irrigation_control"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }

