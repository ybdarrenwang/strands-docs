"""
Function Tool Test Case: Mortgage Loan Details

This file contains a test case specifically designed to trigger the get_mortgage_details function tool.
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
    Run the mortgage details function tool test.
    
    Args:
        function_prompt: Prompt template for function tools
        mcp_prompt: Prompt template for MCP tools
        api_prompt: Prompt template for API tools
    """
    # Setup telemetry and tool simulator upfront
    telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
    memory_exporter = telemetry.in_memory_exporter
    tool_simulator = ToolSimulator()

    # Output schema for mortgage details
    class MortgageDetailsSchema(BaseModel):
        """Schema for mortgage details data."""
        loan_number: str = Field(description="Loan number")
        principal_balance: float = Field(description="Principal balance")
        interest_rate: float = Field(description="Interest rate")
        monthly_payment: float = Field(description="Monthly payment amount")
        next_payment_due: str = Field(description="Next payment due date")

    # Complexity Level 4 - Hard: Multiple optional parameters with interdependencies
    # Conditional Logic & Dependencies:
    # - include_payment_history flag triggers retrieval of historical payment data
    # - include_amortization_schedule requires complex calculations based on loan terms
    # - calculation_date affects all computed values (interest, principal remaining)
    # - Combination of flags creates different response structures
    # Agent must understand: Which detailed breakdowns are needed? How do date calculations affect results?
    @tool_simulator.tool(
        output_schema=MortgageDetailsSchema,
        share_state_id="mortgage",
        initial_state_description="Mortgage: Loan #123456, Balance $285,000, Rate 3.5%, Monthly payment $1,280, Next due: March 1",
        tool_prompt=function_prompt
    )
    @tool
    def get_mortgage_details(
        loan_number: str = None,
        include_payment_history: bool = False,
        include_amortization_schedule: bool = False,
        calculation_date: str = None
    ) -> Dict[str, Any]:
        """Get current mortgage loan details with optional payment history, amortization schedule, and custom calculation date."""
        pass

    # Create test case
    test_case = Case(
        name="mortgage_details_query",
        input="What are my current mortgage loan details?",
        metadata={"expected_tool": "get_mortgage_details", "expected_tool_type": "function"}
    )

    # Define user task function
    def user_task_function(case: Case) -> dict:
        """Execute the agent with the given case input and return output with trajectory."""
        # Get tool
        tool = tool_simulator.get_tool("get_mortgage_details")
        
        # Create agent with trace attributes for session tracking
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a mortgage assistant that can help with loan information.",
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
        "name": report.cases[0].get("name", "mortgage_details_query"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }