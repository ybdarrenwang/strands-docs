"""
Experiment 1 (Baseline): Default Prompts for All Tool Types

This experiment establishes the baseline using default FUNCTION_TOOL_RESPONSE_GENERATION_PROMPT
for all tool types (function, MCP, API). Each test case now includes its own output schema
via the mandatory output_schema parameter in the tool decorator.

Expected Behavior:
- Uses default FUNCTION_TOOL_RESPONSE_GENERATION_PROMPT for all tools
- Output schemas are defined per-tool in test cases
- Works for function, MCP, and API tools
- Higher chance of format mismatches for MCP/API without tailored prompts
"""

from strands_evals.simulation.prompt_templates.tool_response_generation import (
    FUNCTION_TOOL_RESPONSE_GENERATION_PROMPT,
)

# Import all test cases from test_cases_new
from test_cases_new.eval_function_tool_1 import run_test as function_test_1
from test_cases_new.eval_function_tool_2 import run_test as function_test_2
from test_cases_new.eval_function_tool_3 import run_test as function_test_3
from test_cases_new.eval_function_tool_4 import run_test as function_test_4
from test_cases_new.eval_function_tool_5 import run_test as function_test_5
from test_cases_new.eval_mcp_tool_1 import run_test as mcp_test_1
from test_cases_new.eval_mcp_tool_2 import run_test as mcp_test_2
from test_cases_new.eval_mcp_tool_3 import run_test as mcp_test_3
from test_cases_new.eval_mcp_tool_4 import run_test as mcp_test_4
from test_cases_new.eval_mcp_tool_5 import run_test as mcp_test_5
from test_cases_new.eval_api_tool_1 import run_test as api_test_1
from test_cases_new.eval_api_tool_2 import run_test as api_test_2
from test_cases_new.eval_api_tool_3 import run_test as api_test_3
from test_cases_new.eval_api_tool_4 import run_test as api_test_4
from test_cases_new.eval_api_tool_5 import run_test as api_test_5


def run_experiment_1():
    """Run experiment 1 (baseline) with default prompts for all tool types."""
    print("=" * 80)
    print("EXPERIMENT 1 (BASELINE): Default Prompts for All Tool Types")
    print("=" * 80)
    print("Configuration:")
    print("  - Prompt: FUNCTION_TOOL_RESPONSE_GENERATION_PROMPT (default for all)")
    print("  - Output Schemas: Defined per-tool in test cases")
    print("  - Tool Types: Function, MCP, API")
    print("Expectation: Format mismatches for MCP/API without tailored prompts")
    print("=" * 80)
    print()

    # Test configurations (experiment 1: default prompt for all)
    function_prompt = FUNCTION_TOOL_RESPONSE_GENERATION_PROMPT
    mcp_prompt = FUNCTION_TOOL_RESPONSE_GENERATION_PROMPT
    api_prompt = FUNCTION_TOOL_RESPONSE_GENERATION_PROMPT
    
    # List of all test functions
    test_cases = [
        ("eval_function_tool_1", function_test_1),
        ("eval_function_tool_2", function_test_2),
        ("eval_function_tool_3", function_test_3),
        ("eval_function_tool_4", function_test_4),
        ("eval_function_tool_5", function_test_5),
        ("eval_mcp_tool_1", mcp_test_1),
        ("eval_mcp_tool_2", mcp_test_2),
        ("eval_mcp_tool_3", mcp_test_3),
        ("eval_mcp_tool_4", mcp_test_4),
        ("eval_mcp_tool_5", mcp_test_5),
        ("eval_api_tool_1", api_test_1),
        ("eval_api_tool_2", api_test_2),
        ("eval_api_tool_3", api_test_3),
        ("eval_api_tool_4", api_test_4),
        ("eval_api_tool_5", api_test_5),
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
            # Run test case with experiment 1 configuration
            result = test_func(function_prompt, mcp_prompt, api_prompt)
            
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
    print("EXPERIMENT 1 (BASELINE) RESULTS")
    print("=" * 80)
    print(f"\nTotal test cases: {len(test_cases)}")
    print(f"Successfully completed: {successful}")
    print(f"Failed: {failed}")
    
    if results:
        avg_score = sum(r['score'] for r in results) / len(results)
        pass_rate = sum(1 for r in results if r['test_pass']) / len(results)
        print(f"\nAverage Score: {avg_score:.2f}")
        print(f"Pass Rate: {pass_rate:.1%}")
        
        print(f"\nIndividual Test Scores:")
        print("-" * 80)
        for result in results:
            status = "✓ PASS" if result['test_pass'] else "✗ FAIL"
            print(f"  {result['name']:<30} Score: {result['score']:.2f}  {status}")
    
    return results


if __name__ == "__main__":
    run_experiment_1()