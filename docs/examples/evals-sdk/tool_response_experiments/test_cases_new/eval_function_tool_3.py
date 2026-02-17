"""
Function Tool Test Case: Banking Account Balance

This file contains a test case specifically designed to trigger the check_account_balance function tool.
"""

from typing import Dict, Any, List
from strands import Agent
from strands_evals import Case, Experiment, StrandsEvalsTelemetry
from strands_evals.evaluators import GoalSuccessRateEvaluator
from strands_evals.mappers import StrandsInMemorySessionMapper
from pydantic import BaseModel, Field
from strands.tools.decorator import tool

from strands_evals.simulation.tool_simulator import ToolSimulator


def run_test(function_prompt, mcp_prompt, api_prompt):
    """
    Run the banking account balance function tool test.
    
    Args:
        function_prompt: Prompt template for function tools
        mcp_prompt: Prompt template for MCP tools
        api_prompt: Prompt template for API tools
    """
    # Setup telemetry and tool simulator upfront
    telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
    memory_exporter = telemetry.in_memory_exporter
    tool_simulator = ToolSimulator()

    # Output schema for account balance
    class AccountBalanceSchema(BaseModel):
        """Schema for account balance data."""
        account_number: str = Field(description="Account number")
        account_type: str = Field(description="Type of account")
        balance: float = Field(description="Account balance")
        available_balance: float = Field(description="Available balance")
        currency: str = Field(description="Currency code")

    # Complexity Level 3 - Medium: Multiple parameters with conditional logic
    # Conditional Logic Examples:
    # - If include_pending=True, must include pending transactions in balance
    # - Currency parameter affects formatting of returned amounts
    # - Different account_type values may require different data sources
    # Agent must decide: Should pending transactions be included? Which currency format?
    @tool_simulator.tool(
        output_schema=AccountBalanceSchema,
        share_state_id="banking",
        initial_state_description="Banking: Checking account $5,432.10, Savings account $12,850.50, Credit card balance $1,234.56",
        tool_prompt=function_prompt
    )
    @tool
    def check_account_balance(account_type: str, include_pending: bool = False, currency: str = "USD") -> Dict[str, Any]:
        """Check the balance of a bank account with options for pending transactions and currency."""
        pass

    # Create test case
    test_case = Case(
        name="account_balance_query",
        input="What is my checking account balance?",
        metadata={"expected_tool": "check_account_balance", "expected_tool_type": "function"}
    )

    # Define user task function
    def user_task_function(case: Case) -> dict:
        """Execute the agent with the given case input and return output with trajectory."""
        # Get tool
        tool = tool_simulator.get_tool("check_account_balance")
        
        # Create agent with trace attributes for session tracking
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a banking assistant that can help with account information.",
            tools=[tool],
            callback_handler=None,
        )
        
        try:
            agent_response = agent(case.input)
        except Exception as e:
            agent_response = f"Agent execution error: {e}"
        
        # Get finished spans and map to session for trajectory
        finished_spans = memory_exporter.get_finished_spans()
        mapper = StrandsInMemorySessionMapper()
        session = mapper.map_to_session(finished_spans, session_id=case.session_id)
        
        return {"output": str(agent_response), "trajectory": session}

    # Setup evaluators
    evaluators = [GoalSuccessRateEvaluator()]

    # Create an experiment
    experiment = Experiment[str, str](cases=[test_case], evaluators=evaluators)

    # Run evaluations
    print(f"\n=== Running Evaluation: {test_case.name} ===")
    reports = experiment.run_evaluations(user_task_function)

    # Display results
    # reports[0].run_display()
    
    # Return simple results for driver script
    report = reports[0]
    return {
        "name": report.cases[0].get("name", "account_balance_query"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }