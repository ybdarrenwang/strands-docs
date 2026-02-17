"""
Function Tool Test Case: Online Order Status

This file contains a test case specifically designed to trigger the get_order_status function tool.
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
    Run the order status function tool test.
    
    Args:
        function_prompt: Prompt template for function tools
        mcp_prompt: Prompt template for MCP tools
        api_prompt: Prompt template for API tools
    """
    # Setup telemetry and tool simulator upfront
    telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
    memory_exporter = telemetry.in_memory_exporter
    tool_simulator = ToolSimulator()

    # Output schema for order status
    class OrderStatusSchema(BaseModel):
        """Schema for order status data."""
        order_id: str = Field(description="Order ID")
        status: str = Field(description="Order status")
        tracking_number: str | None = Field(default=None, description="Tracking number")
        estimated_delivery: str | None = Field(default=None, description="Estimated delivery date")
        items: List[str] = Field(description="Order items")

    # Complexity Level 5 - Hardest: Advanced filtering with lambda-like query combinations
    # Complex Filtering & Conditional Logic:
    # - status_filter: List of statuses to match (e.g., ["shipped", "processing"]) - OR logic
    # - date_from/date_to: Range filtering requiring date comparisons
    # - include_cancelled: Boolean affecting which orders are returned
    # - sort_by: Changes result ordering (date, status, amount)
    # - max_results: Limits output requiring prioritization
    # Multi-dimensional filtering: Agent must combine AND/OR logic across status, date ranges,
    # cancellation flags, apply sorting, and limit results - similar to database WHERE clauses
    @tool_simulator.tool(
        output_schema=OrderStatusSchema,
        share_state_id="orders",
        initial_state_description="Orders: Order #12345 (shipped, arrives tomorrow), Order #12346 (processing), Order #12344 (delivered)",
        tool_prompt=function_prompt
    )
    @tool
    def get_order_status(
        order_id: str = None,
        status_filter: List[str] = None,
        date_from: str = None,
        date_to: str = None,
        sort_by: str = "date",
        include_cancelled: bool = False,
        max_results: int = 10
    ) -> Dict[str, Any]:
        """Get status of online orders with advanced filtering, sorting, and conditional logic. Supports complex query combinations."""
        pass

    # Create test case
    test_case = Case(
        name="order_status_query",
        input="What's the status of my recent online orders?",
        metadata={"expected_tool": "get_order_status", "expected_tool_type": "function"}
    )

    # Define user task function
    def user_task_function(case: Case) -> dict:
        """Execute the agent with the given case input and return output with trajectory."""
        # Get tool
        tool = tool_simulator.get_tool("get_order_status")
        
        # Create agent with trace attributes for session tracking
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are an online shopping assistant that can help with order tracking.",
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
        "name": report.cases[0].get("name", "order_status_query"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }