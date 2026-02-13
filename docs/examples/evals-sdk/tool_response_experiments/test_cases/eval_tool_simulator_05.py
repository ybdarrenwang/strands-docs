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

    # Function tool for security system status
    @tool_simulator.tool(
        output_schema=None,
        tool_prompt=function_prompt,
        share_state_id="home_security_system",
        initial_state_description="Home security system: armed (stay), motion sensors active, cameras on, last event: none"
    )
    @tool
    def get_security_system_status() -> Dict[str, Any]:
        """Get current status of the home security system.
        
        Returns:
            Dict[str, Any]: Security system status
            
        Output Schema:
            {
                "arm_state": str,  # "stay", "away", "disarm"
                "cameras": str,  # "on" or "off"
                "motion_sensors": str,  # "active" or "inactive"
                "last_event": str,  # Description of last event or "none"
                "last_event_time": str  # Timestamp of last event
            }
        """
        pass

    # MCP tool (shares state with home security system)
    @tool_simulator.tool(
        output_schema=mcp_schema,
        tool_prompt=mcp_prompt,
        share_state_id="home_security_system"
    )
    @tool
    def security_system_controller(arm_state: str, cameras: str = "on", motion_sensors: str = "active") -> Dict[str, Any]:
        """Control home security system including alarm, cameras, and sensors.
        
        Args:
            arm_state: Arm state of the security system (stay, away, disarm)
            cameras: Camera state (on, off)
            motion_sensors: Motion sensor state (active, inactive)
            
        Returns:
            Dict with schema:
            {
                "name": "security_system_controller",
                "description": "Control home security system including alarm, cameras, and sensors",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "arm_state": {"type": "string", "enum": ["stay", "away", "disarm"], "description": "Arm state of the security system"},
                        "cameras": {"type": "string", "enum": ["on", "off"], "description": "Camera state"},
                        "motion_sensors": {"type": "string", "enum": ["active", "inactive"], "description": "Motion sensor state"}
                    },
                    "required": ["arm_state"]
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
    def stock_service(symbol: str) -> Dict[str, Any]:
        """Get current stock quote information.
        
        Args:
            symbol: Stock ticker symbol (e.g., "AAPL", "GOOGL")
            
        Returns:
            Dict[str, Any]: Stock information
            
        Input Schema:
            {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Stock ticker symbol"
                    }
                },
                "required": ["symbol"]
            }
            
        Output Schema:
            {
                "symbol": str,
                "name": str,  # Company name
                "current_price": float,
                "change": float,  # Price change amount
                "change_percent": float,  # Percentage change
                "volume": int,
                "market_cap": str,
                "day_high": float,
                "day_low": float,
                "52_week_high": float,
                "52_week_low": float
            }
        """
        pass

    # Create sub-agent (agent-as-tool) with simulated tools
    @tool
    def financial_security_assistant(query: str) -> str:
        """Financial security assistant that uses security system status and stock data to manage home security based on financial triggers and user requests."""
        try:
            security_status_tool = tool_simulator.get_tool("get_security_system_status")
            security_tool = tool_simulator.get_tool("security_system_controller")
            stock_tool = tool_simulator.get_tool("stock_service")
        
            control_agent = Agent(
                system_prompt="You are a financial security assistant. Your job is to control the home security system using the security_system_controller tool based on information from security status and stock market data. Always check current security system status first, consider stock market data if relevant to the user's financial security concerns, then make appropriate security system adjustments to meet the user's request.",
                tools=[security_status_tool, security_tool, stock_tool],
                callback_handler=None,
            )
            response = control_agent(f"Financial security request: {query}")
            return str(response)

        except Exception as e:
            return f"Financial security assistant error: {str(e)}"

    # Define a task function
    def user_task_function(case: Case) -> dict:
        # Create agent with simulated tool and sub-agent
        security_status_tool = tool_simulator.get_tool("get_security_system_status")
    
        # Inspect initial shared state "home_security_system"
        initial_state = tool_simulator.get_state("home_security_system")
        print(f"[Home security system state (before agent invocation)]:")
        print(f"  Initial state: {initial_state.get('initial_state')}")
        print(f"  Previous calls: {initial_state.get('previous_calls', [])}")
    
        # Showcase how user-agent interaction changes home security system state
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a smart home assistant Alessa. You can check security system status. For security system control, you must consult the financial_security_assistant who has access to the security system.",
            tools=[
                security_status_tool,
                financial_security_assistant,
            ],
            callback_handler=None,
        )

        try:
            agent_response = agent(case.input)
        except Exception as e:
            agent_response = f"Agent execution error: {e}"

        print(f"[User]: {case.input}")
        print(f"[Agent]: {agent_response}")

        # Inspect final shared state "home_security_system" after agent interaction
        final_state = tool_simulator.get_state("home_security_system")
        print(f"[Home security system state (after agent invocation)]:")
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
            name="stock_security_response", 
            input="My Apple stock just went up 20%. Check the current price and set the security system to away mode since I'm going out to celebrate.",
            metadata={"category": "security", "expected_tools": ["stock_service", "security_system_controller"]},
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
        "name": report.cases[0].get("name", "stock_security_response"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }

