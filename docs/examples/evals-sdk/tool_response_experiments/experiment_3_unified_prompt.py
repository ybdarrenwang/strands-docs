"""
Experiment 3: Unified Prompt for All Tool Types (Stretch Goal)

This experiment uses a single unified prompt (UNIFIED_TOOL_RESPONSE_GENERATION_PROMPT)
that handles Function, MCP, and API tools with comprehensive validation rules and
format guidance for all tool types.

Expected Behavior:
- Uses unified prompt with tool-type-specific guidance sections
- Uses structured output models for MCP/API validation
- May improve function tool responses with enhanced validation rules
- Could slightly reduce MCP/API performance vs dedicated prompts (Exp 2) but should be tolerable
- Simplifies maintenance with single prompt template

Trade-off Analysis:
- Pro: Single prompt easier to maintain and update
- Pro: May improve function tools with better validation guidance
- Con: May be slightly less optimized for MCP/API vs dedicated prompts
- Goal: Find acceptable middle ground that improves overall quality

Note: Requires updated tool_simulator.py to support custom prompts and MCP/API types.
"""

from strands_evals.simulation.prompt_templates.tool_response_generation import (
    UNIFIED_TOOL_RESPONSE_GENERATION_PROMPT,
)
from strands_evals.types.simulation.tool import MCPToolResponse, APIToolResponse

# Import all test cases
from test_cases.eval_tool_simulator_01 import run_test as test_01
from test_cases.eval_tool_simulator_02 import run_test as test_02
from test_cases.eval_tool_simulator_03 import run_test as test_03
from test_cases.eval_tool_simulator_04 import run_test as test_04
from test_cases.eval_tool_simulator_05 import run_test as test_05
from test_cases.eval_tool_simulator_06 import run_test as test_06
from test_cases.eval_tool_simulator_07 import run_test as test_07
from test_cases.eval_tool_simulator_08 import run_test as test_08
from test_cases.eval_tool_simulator_09 import run_test as test_09
from test_cases.eval_tool_simulator_10 import run_test as test_10
from test_cases.eval_tool_simulator_11 import run_test as test_11
from test_cases.eval_tool_simulator_12 import run_test as test_12
from test_cases.eval_tool_simulator_13 import run_test as test_13
from test_cases.eval_tool_simulator_14 import run_test as test_14
from test_cases.eval_tool_simulator_15 import run_test as test_15


def run_experiment_3():
    """Run experiment 3 with unified prompt for all tool types."""
    print("=" * 80)
    print("EXPERIMENT 3: Unified Prompt for All Tool Types (STRETCH)")
    print("=" * 80)
    print("Configuration:")
    print("  - Prompt: UNIFIED_TOOL_RESPONSE_GENERATION_PROMPT (all types)")
    print("  - Base Models: MCPToolResponse, APIToolResponse for validation")
    print("  - Tool Types: Function, MCP, API")
    print("Expectation: Simplified maintenance, may improve functions, tolerable MCP/API")
    print("=" * 80)
    print()

    # Test configurations (experiment 3: unified prompt for all tools WITH schema validation)
    function_prompt = UNIFIED_TOOL_RESPONSE_GENERATION_PROMPT
    mcp_prompt = UNIFIED_TOOL_RESPONSE_GENERATION_PROMPT
    api_prompt = UNIFIED_TOOL_RESPONSE_GENERATION_PROMPT
    mcp_schema = MCPToolResponse
    api_schema = APIToolResponse
    
    # List of all test functions
    test_cases = [
        ("eval_tool_simulator_01", test_01),
        ("eval_tool_simulator_02", test_02),
        ("eval_tool_simulator_03", test_03),
        ("eval_tool_simulator_04", test_04),
        ("eval_tool_simulator_05", test_05),
        ("eval_tool_simulator_06", test_06),
        ("eval_tool_simulator_07", test_07),
        ("eval_tool_simulator_08", test_08),
        ("eval_tool_simulator_09", test_09),
        ("eval_tool_simulator_10", test_10),
        ("eval_tool_simulator_11", test_11),
        ("eval_tool_simulator_12", test_12),
        ("eval_tool_simulator_13", test_13),
        ("eval_tool_simulator_14", test_14),
        ("eval_tool_simulator_15", test_15),
    ]
    
    print(f"Discovered {len(test_cases)} test cases\n")
    
    successful = 0
    failed = 0
    results = []
    
    for test_name, test_func in test_cases:
        print(f"\n{'='*80}")
        print(f"Running: {test_name}")
        print(f"{'='*80}\n")
        
        try:
            # Run test case with experiment 3 configuration
            result = test_func(function_prompt, mcp_prompt, api_prompt, mcp_schema, api_schema)
            
            print(f"\n✓ {test_name} completed successfully")
            print(f"  Name: {result['name']}")
            print(f"  Score: {result['score']}")
            print(f"  Pass: {result['test_pass']}")
            if result.get('reason'):
                print(f"  Reason: {result['reason']}")
            
            results.append(result)
            successful += 1
                
        except Exception as e:
            print(f"✗ {test_name} failed: {e}")
            failed += 1
    
    # Print summary
    print("\n" + "=" * 80)
    print("EXPERIMENT 3 RESULTS (UNIFIED PROMPT)")
    print("=" * 80)
    print(f"\nTotal test cases: {len(test_cases)}")
    print(f"Successfully completed: {successful}")
    print(f"Failed: {failed}")
    
    if results:
        avg_score = sum(r['score'] for r in results) / len(results)
        pass_rate = sum(1 for r in results if r['test_pass']) / len(results)
        print(f"\nAverage Score: {avg_score:.2f}")
        print(f"Pass Rate: {pass_rate:.1%}")
    
    return results


if __name__ == "__main__":
    run_experiment_3()
