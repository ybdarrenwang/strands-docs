"""
API Tool Test Case: Weather Service

This file contains a test case specifically designed to trigger the weather_service API tool.
"""

from typing import Dict, Any
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
    Run the weather service API tool test.
    
    Args:
        function_prompt: Prompt template for function tools
        mcp_prompt: Prompt template for MCP tools
        api_prompt: Prompt template for API tools
    """
    # Setup telemetry and tool simulator upfront
    telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
    memory_exporter = telemetry.in_memory_exporter
    tool_simulator = ToolSimulator()

    # Weather data schema - represents the actual weather information (200 response body)
    class WeatherData(BaseModel):
        """Schema for successful weather API response data."""
        location: str = Field(description="City name or location identifier")
        temperature: float = Field(description="Current temperature")
        conditions: str = Field(description="Weather conditions description")
        humidity: float | None = Field(default=None, description="Humidity percentage (optional)")

    # Complete API response schema wrapping WeatherData in APIToolResponse
    class WeatherAPIResponse(APIToolResponse):
        """
        Complete OpenAPI response wrapper for weather service.
        
        Extends APIToolResponse to provide type safety for the data field.
        Represents the full HTTP response structure:
        - status: HTTP status code (200 for success, 404/500 for errors)
        - data: WeatherData for successful responses (200)
        - error: APIErrorDetail for error responses (4xx, 5xx)
        """
        data: WeatherData | None = Field(default=None, description="Weather data for successful requests (200)")

    # API tool: Weather service (Complexity Level 1 - Easiest: 1 required input, simple query)
    @tool_simulator.tool(output_schema=WeatherAPIResponse, tool_prompt=api_prompt)
    @tool
    def weather_service(location: str) -> Dict[str, Any]:
        """
        Get current weather information for a specific location.
        
        Simple single-parameter query that returns weather data wrapped in APIToolResponse.
        
        API Specification:
            Path: /weather/current
            Method: GET
            Parameters:
                - location (string, required): City name or location identifier
            
            Response (200 OK):
                {
                    "status": 200,
                    "data": {
                        "location": "Seattle",
                        "temperature": 55.3,
                        "conditions": "Partly cloudy",
                        "humidity": 72.0
                    },
                    "error": null
                }
            
            Response (404 Not Found):
                {
                    "status": 404,
                    "data": null,
                    "error": {
                        "type": "location_not_found",
                        "title": "Location Not Found",
                        "detail": "The specified location 'XYZ' could not be found",
                        "status": 404
                    }
                }
        """
        pass

    # Create test case
    test_case = Case(
        name="weather_query",
        input="What's the current weather in Seattle?",
        metadata={"expected_tool": "weather_service", "expected_tool_type": "api"}
    )

    # Define user task function
    def user_task_function(case: Case) -> dict:
        """Execute the agent with the given case input and return output with trajectory."""
        # Get tool
        tool = tool_simulator.get_tool("weather_service")
        
        # Create agent with trace attributes for session tracking
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a smart assistant that can help with weather information.",
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
        "name": report.cases[0].get("name", "weather_query"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }