# Tool Response Generation Experiments

This directory contains experiments comparing different approaches to tool response generation in the Strands Evals framework. The experiments evaluate the effectiveness of combining MCP/API-specific prompts and structured output models for improved tool simulation accuracy.

## Overview

The experiments compare tool response generation across three configurations:

1. **Experiment 1 (Baseline)**: Default prompts for all tool types
2. **Experiment 2 (Proposed)**: MCP/API-specific prompts for each tool type
3. **Experiment 3 (Proposed)**: Unified prompt for all tool types

## Architecture

The experiment framework uses:

- **Test Cases** (`test_cases_new/`): Individual test modules with `run_test()` functions
- **Driver Scripts**: Experiment scripts that import and run all test cases with specific prompt configurations
- **Embedded Schemas**: Each test case defines its own output schema via the `output_schema` parameter in the tool decorator

### Test Case Structure

Each test case module exports a `run_test()` function that accepts three prompt parameters:

```python
def run_test(function_prompt: str, mcp_prompt: str, api_prompt: str) -> dict:
    """
    Run the test with the specified prompt templates.
    
    Args:
        function_prompt: Prompt template for function tools
        mcp_prompt: Prompt template for MCP tools  
        api_prompt: Prompt template for API tools
        
    Returns:
        dict: Test results with name, score, test_pass, reason
    """
```

**Key Changes**:
- Output schemas are now defined within each test case using the `@tool_simulator.tool(output_schema=MySchema)` decorator
- No need to pass `MCPToolResponse` or `APIToolResponse` as parameters
- Simpler API with only prompt parameters

## Prerequisites

Before running the experiments:

1. Ensure `strands-evals` is installed with `pip install -e .`
2. Verify test cases in `test_cases_new/` directory are accessible
3. **Important**: The ToolSimulator now requires:
   - Mandatory `output_schema` parameter in the `@tool_simulator.tool()` decorator
   - Custom prompt templates passed to ToolSimulator constructor
   - Support for function, MCP, and API tool types

## Experiment Details

### Experiment 1: Default Prompts (Baseline)

**File**: `experiment_1_baseline_prompt.py`

**Configuration**:
- Prompts: `FUNCTION_TOOL_RESPONSE_GENERATION_PROMPT` for all tool types
- Output Schemas: Defined per-tool in test cases
- Tool Types: Function, MCP, API

**Expected Behavior**:
- Function tools work well with default prompt
- MCP/API tools may have format mismatches without tailored guidance
- Output schemas validate structure but prompts don't guide format
- Establishes baseline for comparison

**Run Command**:
```bash
python experiment_1_baseline_prompt.py
```

---

### Experiment 2: MCP/API-Specific Prompts (PROPOSED)

**File**: `experiment_2_api_mcp_prompt.py`

**Configuration**:
- Prompts: Tool-type-specific prompts
  - `FUNCTION_TOOL_RESPONSE_GENERATION_PROMPT` for function tools
  - `MCP_TOOL_RESPONSE_GENERATION_PROMPT` for MCP tools
  - `API_TOOL_RESPONSE_GENERATION_PROMPT` for API tools
- Output Schemas: Defined per-tool in test cases
- Tool Types: Function, MCP, API

**Expected Behavior**:
- **Highest accuracy expected**
- Tailored prompts guide LLM to generate correct format for each tool type
- Output schemas validate structure
- Optimal combination of guidance + validation
- **This is the PROPOSED production solution**

**Run Command**:
```bash
python experiment_2_api_mcp_prompt.py
```

---

### Experiment 3: Unified Prompt (STRETCH)

**File**: `experiment_3_unified_prompt.py`

**Configuration**:
- Prompts: `UNIFIED_TOOL_RESPONSE_GENERATION_PROMPT` for all tool types
- Output Schemas: Defined per-tool in test cases
- Tool Types: Function, MCP, API

**Expected Behavior**:
- Single prompt simplifies maintenance
- May improve function tool validation with comprehensive rules
- Could slightly reduce MCP/API performance vs Experiment 2
- Trade-off: maintainability vs. optimization
- Should be "good enough" for all tool types

**Trade-off Analysis**:
- ✅ Easier to maintain single prompt
- ✅ May improve function tools with better validation
- ⚠️ May be slightly less optimized for MCP/API
- Goal: Find acceptable middle ground

**Run Command**:
```bash
python experiment_3_unified_prompt.py
```

---

## Running Experiments

To run all experiments sequentially:

```bash
cd strands-docs/docs/examples/evals-sdk/tool_response_experiments/

# Experiment 1 (Baseline)
python experiment_1_baseline_prompt.py > results_exp1.txt 2>&1

# Experiment 2 (Proposed)
python experiment_2_api_mcp_prompt.py > results_exp2.txt 2>&1

# Experiment 3 (Proposed)
python experiment_3_unified_prompt.py > results_exp3.txt 2>&1
```

## Evaluation Metrics

Each experiment uses `HelpfulnessEvaluator` to assess:
- Response quality
- Tool usage correctness
- Schema compliance
- Error rates

Compare results across experiments to identify:
1. Which approach yields most accurate tool responses
2. Whether unified prompt is acceptable vs. specialized prompts
3. Impact of structured output validation

## Test Cases

The `test_cases_new/` directory contains 15 test scenarios organized by tool type:

**Function Tools** (5 tests):
- `eval_function_tool_1.py` - Calendar events (1 input, simple)
- `eval_function_tool_2.py` - Room environment (1 input, multiple outputs)
- `eval_function_tool_3.py` - Account balance (multiple parameters, conditional logic)
- `eval_function_tool_4.py` - Mortgage details (multiple optional parameters)
- `eval_function_tool_5.py` - Order status (advanced filtering, complex queries)

**MCP Tools** (5 tests):
- `eval_mcp_tool_1.py` - HVAC control (1 input, simple)
- `eval_mcp_tool_2.py` - Lighting control (2 inputs, basic)
- `eval_mcp_tool_3.py` - Mortgage payment (multiple inputs, conditional)
- `eval_mcp_tool_4.py` - Order cancellation (multiple actions, dependencies)
- `eval_mcp_tool_5.py` - TV control (multi-mode, complex state)

**API Tools** (5 tests):
- `eval_api_tool_1.py` - Weather service (1 input, simple)
- `eval_api_tool_2.py` - Transaction history (2 inputs, time range)
- `eval_api_tool_3.py` - Employee info (access control)
- `eval_api_tool_4.py` - Payroll info (detailed breakdowns, multiple flags)
- `eval_api_tool_5.py` - Translation service (context-aware, multiple modes)

Each test case:
- Defines output schema using Pydantic BaseModel
- Creates simulated tools with `@tool_simulator.tool(output_schema=MySchema)`
- Tests tool interaction and response generation
- Returns evaluation metrics

## Implementation Requirements

### Current Status

✅ **Completed**:
- Prompt templates in `strands-evals/src/strands_evals/simulation/prompt_templates/tool_response_generation.py`
- Tool types defined in `strands-evals/src/strands_evals/types/simulation/tool.py`
- ToolSimulator updated to require mandatory `output_schema` parameter
- Test cases define output schemas per-tool
- Driver scripts import and run tests with prompt configurations

### Key Architecture Features

1. **Mandatory Output Schema**:
   ```python
   @tool_simulator.tool(
       output_schema=MyOutputSchema,  # Required first parameter
       share_state_id="my_state"      # Optional parameters follow
   )
   def my_tool(arg1: str) -> Dict[str, Any]:
       pass
   ```

2. **Per-Tool Schema Definition**: Each test case defines its own schema
   - Function tools: Simple BaseModel schemas
   - MCP tools: Schemas extending MCPToolResponse
   - API tools: Schemas extending APIToolResponse

3. **Prompt Configuration**: ToolSimulator accepts prompt templates in constructor
   ```python
   tool_simulator = ToolSimulator(
       function_tool_prompt=FUNCTION_TOOL_RESPONSE_GENERATION_PROMPT,
       mcp_tool_prompt=MCP_TOOL_RESPONSE_GENERATION_PROMPT,
       api_tool_prompt=API_TOOL_RESPONSE_GENERATION_PROMPT
   )
   ```

## Expected Results

### Success Criteria

**Experiment 1 (Baseline)**:
- Establishes performance baseline
- Function tools work well
- MCP/API tools may show format issues

**Experiment 2 (PROPOSED)**:
- **Target**: Highest accuracy across all tool types
- Minimal format mismatches
- Tailored prompts + schemas = optimal results
- **Goal for production**

**Experiment 3 (STRETCH)**:
- Performance between Exp 1 and Exp 2
- Acceptable for production if close to Exp 2
- Single prompt provides maintenance benefits

### Hypothesis Validation

The experiments test these hypotheses:

1. ✅ Output schemas enforce structure and validation
2. ✅ Tailored prompts improve response format correctness
3. ✅ Combination of tailored prompts + schemas yields best results
4. ❓ Unified prompt acceptable trade-off vs. specialized prompts

## Next Steps

1. **Run Experiment 1**: Establish baseline with default prompts
2. **Run Experiment 2**: Test proposed solution with tailored prompts
3. **Run Experiment 3**: Evaluate unified prompt alternative
4. **Analyze Results**: Compare metrics across experiments
5. **Document Findings**: Record which approach performs best
6. **Production Decision**: Choose between Experiment 2 (optimal) or Experiment 3 (unified)

## Notes

- Scripts are designed to be run independently or sequentially
- Each script outputs clear headers and experiment configuration
- Results include evaluation metrics for comparison
- Test cases use simple scenarios to isolate tool response quality
- All test cases share the same argument interface for consistency

## Questions or Issues

If experiments fail to run:
1. Check that `strands-evals` is installed with `pip install -e .`
2. Verify test cases are in `test_cases_new/` directory
3. Ensure all prompts are defined in `prompt_templates/tool_response_generation.py`
4. Verify ToolSimulator has been updated with mandatory `output_schema` parameter
5. Check Python path includes necessary modules
