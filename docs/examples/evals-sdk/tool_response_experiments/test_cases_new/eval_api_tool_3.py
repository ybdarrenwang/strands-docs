"""
API Tool Test Case: Employee Information Service

This file contains a test case specifically designed to trigger the employee_info_service API tool.
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
    Run the employee information service API tool test.
    
    Args:
        function_prompt: Prompt template for function tools
        mcp_prompt: Prompt template for MCP tools
        api_prompt: Prompt template for API tools
    """
    # Setup telemetry and tool simulator upfront
    telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
    memory_exporter = telemetry.in_memory_exporter
    tool_simulator = ToolSimulator()

    # Employee info data schema - represents the actual employee data (200 response body)
    class EmployeeInfoData(BaseModel):
        """Schema for successful employee info API response data."""
        employee_id: str = Field(description="Employee identifier")
        name: str = Field(description="Employee full name")
        department: str = Field(description="Department name")
        position: str = Field(description="Job position/title")
        hire_date: str = Field(description="Hire date")
        manager: str = Field(description="Manager name")
        salary: float | None = Field(default=None, description="Salary (optional, if include_salary=true)")

    # Complete API response schema wrapping EmployeeInfoData in APIToolResponse
    class EmployeeInfoAPIResponse(APIToolResponse):
        """
        Complete OpenAPI response wrapper for employee info service.
        
        Extends APIToolResponse to provide type safety for the data field.
        Represents the full HTTP response structure:
        - status: HTTP status code (200 for success, 404/500 for errors)
        - data: EmployeeInfoData for successful responses (200)
        - error: APIErrorDetail for error responses (4xx, 5xx)
        """
        data: EmployeeInfoData | None = Field(default=None, description="Employee info for successful requests (200)")

    # Complexity Level 3 - Medium: Flexible query with multiple optional filters
    # Conditional Logic:
    # - employee_id OR department can be used (different query modes)
    # - include_salary flag adds sensitive data requiring authorization checks
    # - Zero parameters → return all employees (broad query)
    # - Both parameters → intersection query (employee in specific department)
    # Agent must decide: Search by ID or department? Is salary data needed and authorized?
    @tool_simulator.tool(output_schema=EmployeeInfoAPIResponse, tool_prompt=api_prompt)
    @tool
    def employee_info_service(
        employee_id: str = None,
        department: str = None,
        include_salary: bool = False
    ) -> Dict[str, Any]:
        """
        Get employee information from HR system with optional filters and salary data.
        
        API Specification:
            Path: /hr/employees
            Method: GET
            Parameters:
                - employee_id (string, optional): Employee identifier for specific lookup
                - department (string, optional): Filter by department name
                - include_salary (boolean, optional, default=false): Include salary information in response
            
            Response (200 OK):
                {
                    "status": 200,
                    "data": {
                        "employee_id": "E12345",
                        "name": "John Doe",
                        "department": "Engineering",
                        "position": "Senior Software Engineer",
                        "hire_date": "2020-03-15",
                        "manager": "Jane Smith",
                        "salary": 125000.00  // only if include_salary=true
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
                        "detail": "No employee found with ID 'E99999'",
                        "status": 404
                    }
                }
            
            Response (403 Forbidden):
                {
                    "status": 403,
                    "data": null,
                    "error": {
                        "type": "unauthorized_salary_access",
                        "title": "Unauthorized Salary Access",
                        "detail": "You do not have permission to view salary information",
                        "status": 403
                    }
                }
        """
        pass

    # Create test case
    test_case = Case(
        name="employee_info_query",
        input="Can you get me the information for employee ID E12345?",
        metadata={"expected_tool": "employee_info_service", "expected_tool_type": "api"}
    )

    # Define user task function
    def user_task_function(case: Case) -> dict:
        """Execute the agent with the given case input and return output with trajectory."""
        # Get tool
        tool = tool_simulator.get_tool("employee_info_service")
        
        # Create agent with trace attributes for session tracking
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are an HR assistant that can help with employee information lookup.",
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
        "name": report.cases[0].get("name", "employee_info_query"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }