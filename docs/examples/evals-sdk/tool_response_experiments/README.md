# Tool Response Generation Experiments

This directory contains experiments comparing different approaches to tool response generation in the Strands Evals framework. The experiments evaluate the effectiveness of combining MCP/API-specific prompts and structured output models for improved tool simulation accuracy.

## Overview

The experiments compare tool response generation across four configurations:

1. **Baseline**: Current implementation with function tools only
2. **Experiment 1**: Add MCP/API base models for validation (default prompts)
3. **Experiment 2**: Add MCP/API base models + tailored prompts (PROPOSED)
4. **Experiment 3**: Unified prompt for all tool types (STRETCH)

## Architecture

The experiment framework has been simplified:

- **Test Cases** (`test_cases/`): Individual test case scripts that accept command-line arguments
- **Driver Scripts**: Experiment scripts that run all test cases with specific configurations
- **No Intermediate Layers**: Removed `TestCaseConfig`, `test_case_runner.py`, and `run_all_test_cases.py`

### Test Case Arguments

Each test case accepts the following command-line arguments:

```bash
--function-prompt {function|unified}   # Prompt for function tools (default: function)
--mcp-prompt {mcp|unified}             # Prompt for MCP tools (default: mcp)
--api-prompt {api|unified}             # Prompt for API tools (default: api)
--use-mcp-schema                       # Enable MCPToolResponse validation
--use-api-schema                       # Enable APIToolResponse validation
```

**Examples**:
```bash
# Baseline configuration (all defaults)
python eval_tool_simulator_01.py

# Experiment 1 configuration (schemas only)
python eval_tool_simulator_01.py --use-mcp-schema --use-api-schema

# Experiment 2 configuration (specific prompts + schemas)
python eval_tool_simulator_01.py --function-prompt function --mcp-prompt mcp --api-prompt api --use-mcp-schema --use-api-schema

# Experiment 3 configuration (unified prompt + schemas)
python eval_tool_simulator_01.py --function-prompt unified --mcp-prompt unified --api-prompt unified --use-mcp-schema --use-api-schema
```

## Prerequisites

Before running the experiments:

1. Ensure `strands-evals` is installed with `pip install -e .`
2. Verify test cases in `test_cases/` directory are accessible
3. **Note**: Experiments 1-3 require updates to `tool_simulator.py` to support:
   - Custom prompt templates via `tool_prompt` parameter
   - MCP and API tool types with decorators
   - Structured output models for validation

## Experiment Details

### Baseline: Current Implementation

**File**: `baseline_experiment.py`

**Configuration**:
- Prompt: `FUNCTION_TOOL_RESPONSE_GENERATION_PROMPT` (default)
- Base Model: None (arbitrary LLM)
- Tool Types: Function only

**Test Case Arguments**: None (uses all defaults)

**Expected Behavior**:
- Works for function tools only
- No structured output validation
- Higher chance of schema violations without validation
- Users can use any LLM but may get erroneous results

**Run Command**:
```bash
python baseline_experiment.py
```

---

### Experiment 1: MCP/API Base Models

**File**: `experiment_1_base_models.py`

**Configuration**:
- Prompt: Default prompts (not MCP/API-specific)
- Base Models: `MCPToolResponse`, `APIToolResponse` for validation
- Tool Types: Function, MCP, API

**Test Case Arguments**:
```bash
--function-prompt function --mcp-prompt mcp --api-prompt api --use-mcp-schema --use-api-schema
```

**Expected Behavior**:
- Validation catches schema violations through structured output
- Without tailored prompts, LLM may generate incorrect formats initially
- Higher retry rate or validation failures expected
- Improvement over baseline but suboptimal

**Run Command**:
```bash
python experiment_1_base_models.py
```

---

### Experiment 2: MCP/API Base Models + Tailored Prompts (PROPOSED)

**File**: `experiment_2_base_models_prompts.py`

**Configuration**:
- Prompts: Tool-type-specific prompts
  - `FUNCTION_TOOL_RESPONSE_GENERATION_PROMPT`
  - `MCP_TOOL_RESPONSE_GENERATION_PROMPT`
  - `API_TOOL_RESPONSE_GENERATION_PROMPT`
- Base Models: `MCPToolResponse`, `APIToolResponse` for validation
- Tool Types: Function, MCP, API

**Test Case Arguments**:
```bash
--function-prompt function --mcp-prompt mcp --api-prompt api --use-mcp-schema --use-api-schema
```

**Expected Behavior**:
- **Highest accuracy expected**
- Prompts guide LLM to generate correct format from the start
- Structured output models validate schema compliance
- Optimal combination of guidance + validation
- **This is the PROPOSED production solution**

**Run Command**:
```bash
python experiment_2_base_models_prompts.py
```

---

### Experiment 3: Unified Prompt (STRETCH)

**File**: `experiment_3_unified_prompt.py`

**Configuration**:
- Prompt: `UNIFIED_TOOL_RESPONSE_GENERATION_PROMPT` (all tool types)
- Base Models: `MCPToolResponse`, `APIToolResponse` for validation
- Tool Types: Function, MCP, API

**Test Case Arguments**:
```bash
--function-prompt unified --mcp-prompt unified --api-prompt unified --use-mcp-schema --use-api-schema
```

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

## Running All Experiments

To run all experiments sequentially:

```bash
cd strands-docs/docs/examples/evals-sdk/tool_response_experiments/

# Baseline
python baseline_experiment.py > results_baseline.txt 2>&1

# Experiment 1
python experiment_1_base_models.py > results_exp1.txt 2>&1

# Experiment 2 (Proposed)
python experiment_2_base_models_prompts.py > results_exp2.txt 2>&1

# Experiment 3 (Stretch)
python experiment_3_unified_prompt.py > results_exp3.txt 2>&1
```

## Running Individual Test Cases

You can also run individual test cases with custom configurations:

```bash
cd test_cases/

# Run a single test case with baseline configuration
python eval_tool_simulator_01.py

# Run with custom configuration
python eval_tool_simulator_01.py --function-prompt unified --use-mcp-schema --use-api-schema

# Run multiple test cases with the same configuration
for test in eval_tool_simulator_*.py; do
    python "$test" --function-prompt function --mcp-prompt mcp --api-prompt api --use-mcp-schema --use-api-schema
done
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

The `test_cases/` directory contains 15 test scenarios:

- `eval_tool_simulator_01.py` - Morning coffee scheduling with calendar integration
- `eval_tool_simulator_02.py` - Commute lighting control with traffic data
- `eval_tool_simulator_03.py` - [Additional test scenarios...]
- ... (15 test cases total)

Each test case:
- Defines simulated tools (function, MCP, API)
- Creates agent with sub-agent architecture
- Tests tool interaction and state management
- Evaluates response quality

## Implementation Requirements

### Current Status

✅ **Completed**:
- Prompt templates in `strands-evals/src/strands_evals/simulation/prompt_templates/tool_response_generation.py`
- Tool types defined in `strands-evals/src/strands_evals/types/simulation/tool.py`
- Test cases accept command-line arguments
- Driver scripts simplified to use subprocess

⚠️ **Requires Implementation**:

The current `tool_simulator.py` needs updates to support:

1. **Custom Prompt Templates**:
   ```python
   @tool_simulator.tool(
       tool_prompt=CUSTOM_PROMPT  # Specify prompt per tool
   )
   ```

2. **Tool Type Detection**: Update simulation logic to:
   - Detect tool type (function/mcp/api) from decorator parameters
   - Use appropriate prompt template based on tool type
   - Pass correct parameters to prompt (e.g., `mcp_payload`, `api_payload`)

3. **Structured Output**: Support `output_schema` parameter for validation
   ```python
   @tool_simulator.tool(
       output_schema=MCPToolResponse,  # Validate against schema
       tool_prompt=MCP_TOOL_RESPONSE_GENERATION_PROMPT
   )
   ```

## Expected Results

### Success Criteria

**Baseline**:
- Establishes performance floor
- Function tools work reasonably well

**Experiment 1**:
- Some improvement through validation
- May show format errors caught by schema validation

**Experiment 2 (PROPOSED)**:
- **Target**: Highest accuracy across all tool types
- Minimal schema violations
- Clear guidance + validation = optimal results

**Experiment 3 (STRETCH)**:
- Performance between Exp 1 and Exp 2
- Acceptable for production if close to Exp 2
- Provides maintenance benefits

### Hypothesis Validation

The experiments test these hypotheses:

1. ✅ Structured output models reduce schema violations
2. ✅ Tailored prompts improve response format correctness
3. ✅ Combination of prompts + models yields best results
4. ❓ Unified prompt acceptable trade-off vs. specialized prompts

## Next Steps

1. **Run Baseline**: Verify current implementation works
2. **Run Experiments**: Execute all four experiment scripts
3. **Analyze Results**: Compare metrics across experiments
4. **Document Findings**: Record which approach performs best
5. **Production Decision**: Choose between Experiment 2 (optimal) or Experiment 3 (unified)

## Notes

- Scripts are designed to be run independently or sequentially
- Each script outputs clear headers and experiment configuration
- Results include evaluation metrics for comparison
- Test cases use simple scenarios to isolate tool response quality
- All test cases share the same argument interface for consistency

## Questions or Issues

If experiments fail to run:
1. Check that `strands-evals` is installed with `pip install -e .`
2. Verify test cases are in `test_cases/` directory
3. Ensure all prompts are accessible in `prompt_templates/tool_response_generation.py`
4. Check Python path includes necessary modules