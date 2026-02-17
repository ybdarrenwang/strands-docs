"""
API Tool Test Case: Payroll Information Service

This file contains a test case specifically designed to trigger the payroll_info_service API tool.
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
    Run the payroll information service API tool test.
    
    Args:
        function_prompt: Prompt template for function tools
        mcp_prompt: Prompt template for MCP tools
        api_prompt: Prompt template for API tools
    """
    # Setup telemetry and tool simulator upfront
    telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
    memory_exporter = telemetry.in_memory_exporter
    tool_simulator = ToolSimulator()

    # Nested schemas for optional breakdown data
    class TaxBreakdown(BaseModel):
        """Tax breakdown details."""
        federal: float = Field(description="Federal tax amount")
        state: float = Field(description="State tax amount")
        social_security: float = Field(description="Social Security tax amount")
        medicare: float = Field(description="Medicare tax amount")

    class DeductionItem(BaseModel):
        """Individual deduction item."""
        name: str = Field(description="Deduction name")
        amount: float = Field(description="Deduction amount")
        category: str = Field(description="Deduction category")

    class YTDTotals(BaseModel):
        """Year-to-date totals."""
        gross_pay: float = Field(description="YTD gross pay")
        net_pay: float = Field(description="YTD net pay")
        taxes: float = Field(description="YTD taxes")
        deductions: float = Field(description="YTD deductions")

    # Payroll info data schema - represents the actual payroll data (200 response body)
    class PayrollInfoData(BaseModel):
        """Schema for successful payroll info API response data."""
        employee_id: str = Field(description="Employee identifier")
        pay_period: str = Field(description="Pay period identifier")
        gross_pay: float = Field(description="Gross pay amount")
        net_pay: float = Field(description="Net pay amount")
        deductions: float = Field(description="Total deductions")
        next_payday: str = Field(description="Next payday date")
        tax_breakdown: TaxBreakdown | None = Field(default=None, description="Tax breakdown (if include_tax_breakdown=true)")
        deductions_detail: List[DeductionItem] | None = Field(default=None, description="Itemized deductions (if include_deductions=true)")
        ytd_totals: YTDTotals | None = Field(default=None, description="Year-to-date totals (if include_ytd=true)")

    # Complete API response schema wrapping PayrollInfoData in APIToolResponse
    class PayrollInfoAPIResponse(APIToolResponse):
        """
        Complete OpenAPI response wrapper for payroll info service.
        
        Extends APIToolResponse to provide type safety for the data field.
        Represents the full HTTP response structure:
        - status: HTTP status code (200 for success, 404/500 for errors)
        - data: PayrollInfoData for successful responses (200)
        - error: APIErrorDetail for error responses (4xx, 5xx)
        """
        data: PayrollInfoData | None = Field(default=None, description="Payroll info for successful requests (200)")

    # Complexity Level 4 - Hard: Detailed breakdowns with multiple boolean flags
    # Conditional Logic & Combinations:
    # - pay_period affects which data is retrieved ("current", "previous", "2024-01")
    # - include_tax_breakdown adds nested tax calculation details
    # - include_deductions adds itemized deduction list
    # - include_ytd adds year-to-date accumulations requiring aggregation
    # - Flags can be combined: all three flags together creates comprehensive report
    # - Different combinations create different response structures
    # Agent must determine: Which level of detail is needed? What combination of breakdowns?
    @tool_simulator.tool(output_schema=PayrollInfoAPIResponse, tool_prompt=api_prompt)
    @tool
    def payroll_info_service(
        employee_id: str,
        pay_period: str = "current",
        include_tax_breakdown: bool = False,
        include_deductions: bool = False,
        include_ytd: bool = False
    ) -> Dict[str, Any]:
        """
        Get payroll information for an employee with detailed tax breakdown, deductions, and year-to-date calculations.
        
        API Specification:
            Path: /payroll/info
            Method: GET
            Parameters:
                - employee_id (string, required): Employee identifier
                - pay_period (string, optional, default="current"): Pay period identifier
                - include_tax_breakdown (boolean, optional, default=false): Include detailed tax breakdown
                - include_deductions (boolean, optional, default=false): Include itemized deductions
                - include_ytd (boolean, optional, default=false): Include year-to-date totals
            
            Response (200 OK - Basic):
                {
                    "status": 200,
                    "data": {
                        "employee_id": "E12345",
                        "pay_period": "current",
                        "gross_pay": 5000.00,
                        "net_pay": 3750.00,
                        "deductions": 1250.00,
                        "next_payday": "2024-02-15"
                    },
                    "error": null
                }
            
            Response (200 OK - With All Breakdowns):
                {
                    "status": 200,
                    "data": {
                        "employee_id": "E12345",
                        "pay_period": "current",
                        "gross_pay": 5000.00,
                        "net_pay": 3750.00,
                        "deductions": 1250.00,
                        "next_payday": "2024-02-15",
                        "tax_breakdown": {
                            "federal": 750.00,
                            "state": 200.00,
                            "social_security": 310.00,
                            "medicare": 72.50
                        },
                        "deductions_detail": [
                            {"name": "401k", "amount": 500.00, "category": "retirement"},
                            {"name": "Health Insurance", "amount": 150.00, "category": "benefits"}
                        ],
                        "ytd_totals": {
                            "gross_pay": 30000.00,
                            "net_pay": 22500.00,
                            "taxes": 5000.00,
                            "deductions": 2500.00
                        }
                    },
                    "error": null
                }
            
            Response (404 Not Found):
                {
                    "status": 404,
                    "data": null,
                    "error": {
                        "type": "employee_not_found",
                        "title": "Employee Not Found",
                        "detail": "No payroll data found for employee 'E99999'",
                        "status": 404
                    }
                }
        """
        pass

    # Create test case
    test_case = Case(
        name="payroll_info_query",
        input="Show me current pay period information and next payday for employee E12345.",
        metadata={"expected_tool": "payroll_info_service", "expected_tool_type": "api"}
    )

    # Define user task function
    def user_task_function(case: Case) -> dict:
        """Execute the agent with the given case input and return output with trajectory."""
        # Get tool
        tool = tool_simulator.get_tool("payroll_info_service")
        
        # Create agent with trace attributes for session tracking
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a payroll assistant that can help with payroll information.",
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
        "name": report.cases[0].get("name", "payroll_info_query"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }