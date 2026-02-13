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

    # Function tool for appliance status
    @tool_simulator.tool(
        output_schema=None,
        tool_prompt=function_prompt,
        share_state_id="home_appliances",
        initial_state_description="Home appliances: refrigerator (on), oven (off), dishwasher (off), washing machine (off), dryer (off)"
    )
    @tool
    def get_appliance_status() -> Dict[str, Any]:
        """Get current status of all smart appliances in the home.
    
        Returns:
            Dict[str, Any]: Appliance status information
            
        Output Schema:
            {
                "appliances": {
                    "refrigerator": str,  # "on" or "off"
                    "oven": str,
                    "dishwasher": str,
                    "washing_machine": str,
                    "dryer": str
                },
                "power_consumption": str,  # Total power usage
                "estimated_monthly_cost": str
            }
        """
        pass

    # MCP tool (shares state with home appliances)
    @tool_simulator.tool(
        output_schema=mcp_schema,
        tool_prompt=mcp_prompt,
        share_state_id="home_appliances"
    )
    @tool
    def smart_appliance_controller(appliance: str, action: str, settings: Dict[str, Any] = None) -> Dict[str, Any]:
        """Control smart home appliances.
        
        Args:
            appliance: Appliance to control (refrigerator, oven, dishwasher, washing_machine, dryer)
            action: Action to perform (turn_on, turn_off, start_cycle, stop_cycle)
            settings: Optional settings specific to the appliance
            
        Returns:
            Dict with schema:
            {
                "name": "smart_appliance_controller",
                "description": "Control smart home appliances",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "appliance": {"type": "string", "description": "Appliance to control (refrigerator, oven, dishwasher, washing_machine, dryer)"},
                        "action": {"type": "string", "enum": ["turn_on", "turn_off", "start_cycle", "stop_cycle"], "description": "Action to perform"},
                        "settings": {"type": "object", "description": "Optional settings specific to the appliance"}
                    },
                    "required": ["appliance", "action"]
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
    def email_service(folder: str = "inbox", count: int = 5, unread_only: bool = True) -> Dict[str, Any]:
        """Get emails from the specified folder.
        
        Args:
            folder: Email folder to retrieve from (default: "inbox")
            count: Number of emails to retrieve (default: 5)
            unread_only: Only retrieve unread emails (default: True)
            
        Returns:
            Dict[str, Any]: Email messages
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "folder": {
                        "type": "string",
                        "description": "Email folder to retrieve from",
                        "default": "inbox"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of emails to retrieve",
                        "default": 5
                    },
                    "unread_only": {
                        "type": "boolean",
                        "description": "Only retrieve unread emails",
                        "default": true
                    }
                },
                "required": []
            }
            
        Output Schema:
            {
                "folder": str,
                "emails": [
                    {
                        "id": str,
                        "from": str,
                        "subject": str,
                        "date": str,
                        "preview": str,  # First 100 characters of body
                        "is_read": bool,
                        "has_attachments": bool
                    }
                ],
                "total_count": int,
                "unread_count": int
            }
        """
        pass

    # Create sub-agent (agent-as-tool) with simulated tools
    @tool
    def home_efficiency_assistant(query: str) -> str:
        """Home efficiency assistant that uses appliance status and email data to control appliances based on user requests and notifications."""
        try:
            appliance_status_tool = tool_simulator.get_tool("get_appliance_status")
            appliance_tool = tool_simulator.get_tool("smart_appliance_controller")
            email_tool = tool_simulator.get_tool("email_service")
        
            control_agent = Agent(
                system_prompt="You are a home efficiency assistant. Your job is to control smart appliances using the smart_appliance_controller tool based on information from appliance status and relevant emails. Always check current appliance status first, check emails for relevant notifications or utility company messages if needed, then make appropriate appliance control adjustments to meet the user's request.",
                tools=[appliance_status_tool, appliance_tool, email_tool],
                callback_handler=None,
            )
            response = control_agent(f"Home efficiency request: {query}")
            return str(response)

        except Exception as e:
            return f"Home efficiency assistant error: {str(e)}"

    # Define a task function
    def user_task_function(case: Case) -> dict:
        # Create agent with simulated tool and sub-agent
        appliance_status_tool = tool_simulator.get_tool("get_appliance_status")
    
        # Inspect initial shared state "home_appliances"
        initial_state = tool_simulator.get_state("home_appliances")
        print(f"[Home appliances state (before agent invocation)]:")
        print(f"  Initial state: {initial_state.get('initial_state')}")
        print(f"  Previous calls: {initial_state.get('previous_calls', [])}")
    
        # Showcase how user-agent interaction changes home appliances state
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a smart home assistant Alessa. You can check appliance status. For appliance control, you must consult the home_efficiency_assistant who has access to the smart appliance system.",
            tools=[
                appliance_status_tool,
                home_efficiency_assistant,
            ],
            callback_handler=None,
        )

        try:
            agent_response = agent(case.input)
        except Exception as e:
            agent_response = f"Agent execution error: {e}"

        print(f"[User]: {case.input}")
        print(f"[Agent]: {agent_response}")

        # Inspect final shared state "home_appliances" after agent interaction
        final_state = tool_simulator.get_state("home_appliances")
        print(f"[Home appliances state (after agent invocation)]:")
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
            name="email_appliance_control", 
            input="I think I got an email from the power company about peak hours. Can you check my inbox and turn off any non-essential appliances to save energy?",
            metadata={"category": "appliances", "expected_tools": ["email_service", "smart_appliance_controller"]},
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
        "name": report.cases[0].get("name", "email_appliance_control"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }

