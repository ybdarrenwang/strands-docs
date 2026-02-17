"""
API Tool Test Case: Translation Service

This file contains a test case specifically designed to trigger the translation_service API tool.
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
    Run the translation service API tool test.
    
    Args:
        function_prompt: Prompt template for function tools
        mcp_prompt: Prompt template for MCP tools
        api_prompt: Prompt template for API tools
    """
    # Setup telemetry and tool simulator upfront
    telemetry = StrandsEvalsTelemetry().setup_in_memory_exporter()
    memory_exporter = telemetry.in_memory_exporter
    tool_simulator = ToolSimulator()

    # Alternative translation option schema
    class TranslationAlternative(BaseModel):
        """Alternative translation option."""
        text: str = Field(description="Alternative translated text")
        confidence: float = Field(description="Confidence score for alternative")

    # Translation data schema - represents the actual translation result (200 response body)
    class TranslationData(BaseModel):
        """Schema for successful translation API response data."""
        original_text: str = Field(description="Original input text")
        translated_text: str = Field(description="Translated text")
        source_language: str = Field(description="Detected or specified source language")
        target_language: str = Field(description="Target language")
        confidence: float | None = Field(default=None, description="Translation confidence score (0.0-1.0)")
        alternatives: List[TranslationAlternative] | None = Field(default=None, description="Alternative translations")

    # Complete API response schema wrapping TranslationData in APIToolResponse
    class TranslationAPIResponse(APIToolResponse):
        """
        Complete OpenAPI response wrapper for translation service.
        
        Extends APIToolResponse to provide type safety for the data field.
        Represents the full HTTP response structure:
        - status: HTTP status code (200 for success, 400/500 for errors)
        - data: TranslationData for successful responses (200)
        - error: APIErrorDetail for error responses (4xx, 5xx)
        """
        data: TranslationData | None = Field(default=None, description="Translation data for successful requests (200)")

    # Complexity Level 5 - Hardest: Context-aware translation with multiple modes
    # Complex Conditional Logic & Context Handling:
    # - source_language="auto" requires language detection preprocessing
    # - formality level affects word choices: "default" vs "formal" vs "informal"
    # - preserve_formatting=True requires parsing and maintaining structure (HTML, markdown)
    # - context provides semantic hints affecting translation choices
    # - glossary_id loads domain-specific term mappings (technical, legal, medical)
    # - model_version selection affects quality/speed tradeoffs
    # - Interdependencies: context + glossary + formality all influence same word choices
    # Agent must reason: What formality is appropriate? Is domain knowledge needed? 
    # Should formatting be preserved? How do all these factors combine to produce optimal translation?
    @tool_simulator.tool(output_schema=TranslationAPIResponse, tool_prompt=api_prompt)
    @tool
    def translation_service(
        text: str,
        target_language: str,
        source_language: str = "auto",
        formality: str = "default",
        preserve_formatting: bool = True,
        context: str = None,
        glossary_id: str = None,
        model_version: str = "latest"
    ) -> Dict[str, Any]:
        """
        Translate text with advanced options: auto-detect source, formality level, formatting preservation, context awareness, custom glossary, and model selection.
        
        API Specification:
            Path: /translate
            Method: POST
            Request Body:
                - text (string, required): Text to translate
                - target_language (string, required): Target language code (ISO 639-1)
                - source_language (string, optional, default="auto"): Source language code or 'auto' for auto-detection
                - formality (string, optional, default="default"): Formality level ["default", "formal", "informal"]
                - preserve_formatting (boolean, optional, default=true): Preserve original text formatting
                - context (string, optional): Additional context for better translation
                - glossary_id (string, optional): Custom glossary identifier for domain-specific terms
                - model_version (string, optional, default="latest"): Translation model version to use
            
            Response (200 OK - Basic):
                {
                    "status": 200,
                    "data": {
                        "original_text": "Hello, how are you?",
                        "translated_text": "Hola, ¿cómo estás?",
                        "source_language": "en",
                        "target_language": "es",
                        "confidence": 0.98
                    },
                    "error": null
                }
            
            Response (200 OK - With Alternatives):
                {
                    "status": 200,
                    "data": {
                        "original_text": "Hello, how are you?",
                        "translated_text": "Hola, ¿cómo estás?",
                        "source_language": "en",
                        "target_language": "es",
                        "confidence": 0.98,
                        "alternatives": [
                            {"text": "Hola, ¿cómo está usted?", "confidence": 0.95},
                            {"text": "Hola, ¿qué tal?", "confidence": 0.92}
                        ]
                    },
                    "error": null
                }
            
            Response (400 Bad Request):
                {
                    "status": 400,
                    "data": null,
                    "error": {
                        "type": "unsupported_language",
                        "title": "Unsupported Language",
                        "detail": "Language code 'xyz' is not supported",
                        "status": 400
                    }
                }
            
            Response (422 Unprocessable Entity):
                {
                    "status": 422,
                    "data": null,
                    "error": {
                        "type": "glossary_not_found",
                        "title": "Glossary Not Found",
                        "detail": "No glossary found with ID 'glossary-tech-001'",
                        "status": 422
                    }
                }
        """
        pass

    # Create test case
    test_case = Case(
        name="translation_query",
        input="Translate 'Hello, how are you?' to Spanish.",
        metadata={"expected_tool": "translation_service", "expected_tool_type": "api"}
    )

    # Define user task function
    def user_task_function(case: Case) -> dict:
        """Execute the agent with the given case input and return output with trajectory."""
        # Get tool
        tool = tool_simulator.get_tool("translation_service")
        
        # Create agent with trace attributes for session tracking
        agent = Agent(
            trace_attributes={"gen_ai.conversation.id": case.session_id, "session.id": case.session_id},
            system_prompt="You are a smart assistant that can help with translation.",
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
        "name": report.cases[0].get("name", "translation_query"),
        "score": report.scores[0],
        "test_pass": report.test_passes[0],
        "reason": report.reasons[0] if report.reasons else "",
        "input": report.cases[0].get("input", "")
    }