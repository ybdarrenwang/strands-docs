"""
MCP Tool Test Case: Mortgage Payment Scheduler

This file contains a test case specifically designed to trigger the mortgage_payment_scheduler MCP tool.
"""

from typing import Dict, Any
from strands import Agent
from strands_evals import Case, Experiment, StrandsEvalsTelemetry
from strands_evals.evaluators import GoalSuccessRateEvaluator
from strands_evals.mappers import StrandsInMemorySessionMapper
from pydantic import BaseModel, Field
from strands.tools.decorator import tool

from strands_evals.simulation.tool_simulator import ToolSimulator
from strands_evals.types.simulation.tool import MCPToolResponse, ContentBlock


def run_test(function_prompt, mcp_prompt, api_prompt):
    """
    Run the mortgage payment scheduler MCP tool test.
    
    Args:
        function_prompt: Prompt template for function tools
        mcp_prompt: Prompt template for MCP tools
        api_prompt: Prompt template for API tools
    """
    # Setup telemetry and tool simulator upfront
    telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
    memory_exporter = telemetry.in_memory_exporter
    tool_simulator = ToolSimulator()

    # Structured content schema for mortgage payment response
    class MortgagePaymentData(BaseModel):
        """Structured data for mortgage payment response."""
        payment_amount: float = Field(description="Payment amount")
        payment_date: str = Field(description="Payment date")
        confirmation_number: str = Field(description="Payment confirmation number")
        status: str = Field(description="Payment status")

    # Complete MCP response schema
    class MortgagePaymentResponse(MCPToolResponse):
        """
        Complete MCP response wrapper for mortgage payment scheduler.
        
        Extends MCPToolResponse to provide type safety for structured_content.
        Follows official MCP specification format:
        - tool_use_id: Unique identifier for this tool use
        - content: List of ContentBlock objects with text responses
        - structured_content: MortgagePaymentData for structured output
        - is_error: Whether an error occurred
        - meta: Additional metadata
        """
        structured_content: MortgagePaymentData | None = Field(default=None, description="Structured mortgage payment data")

    # Complexity Level 3 - Medium: Multiple required inputs with optional context
    # Conditional Logic:
    # - payment_type determines processing: "regular" vs "extra_principal" vs "full_payoff"
    # - Each type has different validation rules (e.g., full_payoff requires exact amount)
    # - memo is optional but may be required for certain payment types
    # Agent must understand: Which payment type applies? Is this a special payment?
    @tool_simulator.tool(
        output_schema=MortgagePaymentResponse,
        share_state_id="mortgage",
        tool_prompt=mcp_prompt
    )
    @tool
    def mortgage_payment_scheduler(amount: float, date: str, payment_type: str, memo: str = None) -> Dict[str, Any]:
        """
        Schedule a mortgage payment with amount, date, type, and optional memo.
        
        MCP Tool Specification:
            Name: mortgage_payment_scheduler
            Description: Schedule or make mortgage loan payments with type and optional memo
            
            Input Schema:
                {
                    "type": "object",
                    "properties": {
                        "amount": {
                            "type": "number",
                            "description": "Payment amount"
                        },
                        "date": {
                            "type": "string",
                            "description": "Payment date (YYYY-MM-DD)"
                        },
                        "payment_type": {
                            "type": "string",
                            "enum": ["regular", "extra_principal", "full_payoff"],
                            "description": "Type of payment"
                        },
                        "memo": {
                            "type": "string",
                            "description": "Optional payment memo"
                        }
                    },
                    "required": ["amount", "date", "payment_type"]
                }
            
            Response (Success):
                {
                    "tool_use_id": "call_127",
                    "content": [
                        {
                            "type": "text",
                            "text": "Regular mortgage payment of $1,280.00 scheduled for March 1st. Confirmation: MP-2024-001.",
                            "resource": null
                        }
                    ],
                    "structured_content": {
                        "payment_amount": 1280.00,
                        "payment_date": "2024-03-01",
                        "confirmation_number": "MP-2024-001",
                        "status": "scheduled"
                    },
                    "is_error": false,
                    "meta": {
                        "timestamp": "2024-02-17T22:00:00Z"
                    }
                }
            
            Response (Error):
                {
                    "tool_use_id": "call_128",
                    "content": [
                        {
                            "type": "text",
                            "text": "Error: Payment amount $500 is below the minimum regular payment of $1,280",
                            "resource": null
                        }
                    ],
                    "structured_content": null,
                    "is_error": true,
                    "meta": {
                        "error_code": "INSUFFICIENT_PAYMENT",
                        "minimum_required": 1280.00,
                        "timestamp": "2024-02-17T22:00:00Z"
                    }
                }
        """
        pass

    # Create test case
    test_case = Case(
        name="mortgage_payment_schedule",
        input="Schedule my regular mortgage payment of $1,280 for March 1st.",
        metadata={"expected_tool": "mortgage_payment_scheduler", "expected_tool_type": "mcp"}
    )

    # Define user task function
    def user_task_function(case: Case) -> dict:
        """Execute the agent with the given case input and return output with trajectory."""
        # Get tool
        tool = tool_simulator.get_tool("mortgage_payment_scheduler")
        
        # Create agent with trace attributes for session tracking
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a mortgage assistant that can help with scheduling loan payments.",
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
        "name": report.cases[0].get("name", "mortgage_payment_schedule"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }