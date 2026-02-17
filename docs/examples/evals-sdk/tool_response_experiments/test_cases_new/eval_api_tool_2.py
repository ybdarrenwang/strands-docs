"""
API Tool Test Case: Banking Transaction History

This file contains a test case specifically designed to trigger the transaction_history_service API tool.
"""

from typing import Dict, Any, List
from strands import Agent
from strands_evals import Case, Experiment, StrandsEvalsTelemetry
from strands_evals.evaluators import GoalSuccessRateEvaluator
from strands_evals.mappers import StrandsInMemorySessionMapper
from pydantic import BaseModel, Field
from strands.tools.decorator import tool

from strands_evals.simulation.tool_simulator import ToolSimulator
from strands_evals.types.simulation.tool import APIToolResponse, APIErrorDetail


def run_test(function_prompt, mcp_prompt, api_prompt):
    """
    Run the banking transaction history API tool test.
    
    Args:
        function_prompt: Prompt template for function tools
        mcp_prompt: Prompt template for MCP tools
        api_prompt: Prompt template for API tools
    """
    # Setup telemetry and tool simulator upfront
    telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
    memory_exporter = telemetry.in_memory_exporter
    tool_simulator = ToolSimulator()

    # Transaction schema - represents individual transaction
    class TransactionSchema(BaseModel):
        """Schema for individual transaction."""
        transaction_id: str = Field(description="Unique transaction identifier")
        date: str = Field(description="Transaction date")
        description: str = Field(description="Transaction description")
        amount: float = Field(description="Transaction amount")
        category: str = Field(description="Transaction category")

    # Transaction list data schema - represents the actual response data (200 response body)
    class TransactionListData(BaseModel):
        """Schema for successful transaction history API response data."""
        transactions: List[TransactionSchema] = Field(description="List of transactions")

    # Complete API response schema wrapping TransactionListData in APIToolResponse
    class TransactionAPIResponse(APIToolResponse):
        """
        Complete OpenAPI response wrapper for transaction history service.
        
        Extends APIToolResponse to provide type safety for the data field.
        Represents the full HTTP response structure:
        - status: HTTP status code (200 for success, 404/500 for errors)
        - data: TransactionListData for successful responses (200)
        - error: APIErrorDetail for error responses (4xx, 5xx)
        """
        data: TransactionListData | None = Field(default=None, description="Transaction list for successful requests (200)")

    # API tool: Transaction history service (Complexity Level 2 - Easy: 1 required input, 1 optional parameter)
    @tool_simulator.tool(output_schema=TransactionAPIResponse, tool_prompt=api_prompt)
    @tool
    def transaction_history_service(account_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get transaction history for a bank account with configurable time period.
        
        API Specification:
            Path: /banking/transactions
            Method: GET
            Parameters:
                - account_id (string, required): Bank account identifier
                - days (integer, optional, default=30): Number of days to retrieve transaction history
            
            Response (200 OK):
                {
                    "status": 200,
                    "data": {
                        "transactions": [
                            {
                                "transaction_id": "TXN-001",
                                "date": "2024-01-15",
                                "description": "Coffee Shop",
                                "amount": -4.50,
                                "category": "Food & Dining"
                            },
                            ...
                        ]
                    },
                    "error": null
                }
            
            Response (404 Not Found):
                {
                    "status": 404,
                    "data": null,
                    "error": {
                        "type": "account_not_found",
                        "title": "Account Not Found",
                        "detail": "The account 'ACC-999' does not exist",
                        "status": 404
                    }
                }
        """
        pass

    # Create test case
    test_case = Case(
        name="transaction_history_query",
        input="Show me recent bank transactions for account ACC-12345 from the last 30 days.",
        metadata={"expected_tool": "transaction_history_service", "expected_tool_type": "api"}
    )

    # Define user task function
    def user_task_function(case: Case) -> dict:
        """Execute the agent with the given case input and return output with trajectory."""
        # Get tool
        tool = tool_simulator.get_tool("transaction_history_service")
        
        # Create agent with trace attributes for session tracking
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a banking assistant that can help with transaction history.",
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
        "name": report.cases[0].get("name", "transaction_history_query"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }