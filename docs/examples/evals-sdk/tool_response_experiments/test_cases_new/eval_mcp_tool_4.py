"""
MCP Tool Test Case: Order Cancellation

This file contains a test case specifically designed to trigger the order_cancellation_controller MCP tool.
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
    Run the order cancellation controller MCP tool test.
    
    Args:
        function_prompt: Prompt template for function tools
        mcp_prompt: Prompt template for MCP tools
        api_prompt: Prompt template for API tools
    """
    # Setup telemetry and tool simulator upfront
    telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
    memory_exporter = telemetry.in_memory_exporter
    tool_simulator = ToolSimulator()

    # Structured content schema for order cancellation response
    class OrderCancellationData(BaseModel):
        """Structured data for order cancellation response."""
        order_id: str = Field(description="Order ID")
        status: str = Field(description="Order status")
        refund_amount: float | None = Field(default=None, description="Refund amount")
        message: str = Field(description="Status message")

    # Complete MCP response schema
    class OrderCancellationResponse(MCPToolResponse):
        """
        Complete MCP response wrapper for order cancellation controller.
        
        Extends MCPToolResponse to provide type safety for structured_content.
        Follows official MCP specification format:
        - tool_use_id: Unique identifier for this tool use
        - content: List of ContentBlock objects with text responses
        - structured_content: OrderCancellationData for structured output
        - is_error: Whether an error occurred
        - meta: Additional metadata
        """
        structured_content: OrderCancellationData | None = Field(default=None, description="Structured order cancellation data")

    # Complexity Level 4 - Hard: Multiple actions with dependent parameters
    # Conditional Logic & Dependencies:
    # - action="cancel" → refund_method becomes relevant
    # - action="modify" → different validation rules apply
    # - action="return" → refund_method AND reason both required
    # - refund_method choice affects processing time and customer account
    # - send_notification interacts with action type (urgent for cancellations)
    # Agent must reason: What action is appropriate? Which refund method? Should customer be notified immediately?
    @tool_simulator.tool(
        output_schema=OrderCancellationResponse,
        share_state_id="orders",
        tool_prompt=mcp_prompt
    )
    @tool
    def order_cancellation_controller(order_id: str, action: str, reason: str, refund_method: str = "original", send_notification: bool = True) -> Dict[str, Any]:
        """
        Cancel or modify an online order with refund options and notification settings.
        
        MCP Tool Specification:
            Name: order_cancellation_controller
            Description: Cancel or modify online orders with refund and notification options
            
            Input Schema:
                {
                    "type": "object",
                    "properties": {
                        "order_id": {
                            "type": "string",
                            "description": "Order ID to cancel or modify"
                        },
                        "action": {
                            "type": "string",
                            "enum": ["cancel", "modify", "return"],
                            "description": "Action to perform"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for cancellation or return"
                        },
                        "refund_method": {
                            "type": "string",
                            "enum": ["original", "store_credit", "gift_card"],
                            "description": "Refund method"
                        },
                        "send_notification": {
                            "type": "boolean",
                            "description": "Send email notification"
                        }
                    },
                    "required": ["order_id", "action", "reason"]
                }
            
            Response (Success):
                {
                    "tool_use_id": "call_129",
                    "content": [
                        {
                            "type": "text",
                            "text": "Order #12346 has been cancelled. Refund of $89.99 will be processed to your original payment method. You will receive an email confirmation shortly.",
                            "resource": null
                        }
                    ],
                    "structured_content": {
                        "order_id": "12346",
                        "status": "cancelled",
                        "refund_amount": 89.99,
                        "message": "Order cancelled successfully. Refund processing."
                    },
                    "is_error": false,
                    "meta": {
                        "timestamp": "2024-02-17T22:00:00Z",
                        "refund_method": "original",
                        "notification_sent": true
                    }
                }
            
            Response (Error):
                {
                    "tool_use_id": "call_130",
                    "content": [
                        {
                            "type": "text",
                            "text": "Error: Order #12346 cannot be cancelled as it has already shipped",
                            "resource": null
                        }
                    ],
                    "structured_content": null,
                    "is_error": true,
                    "meta": {
                        "error_code": "ORDER_ALREADY_SHIPPED",
                        "timestamp": "2024-02-17T22:00:00Z"
                    }
                }
        """
        pass

    # Create test case
    test_case = Case(
        name="order_cancellation",
        input="I need to cancel order #12346 because I ordered the wrong size.",
        metadata={"expected_tool": "order_cancellation_controller", "expected_tool_type": "mcp"}
    )

    # Define user task function
    def user_task_function(case: Case) -> dict:
        """Execute the agent with the given case input and return output with trajectory."""
        # Get tool
        tool = tool_simulator.get_tool("order_cancellation_controller")
        
        # Create agent with trace attributes for session tracking
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are an online shopping assistant that can help with order cancellations and modifications.",
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
        "name": report.cases[0].get("name", "order_cancellation"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }