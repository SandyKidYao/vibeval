---
description: Run vibeval tests, execute judge evaluation, and show results
argument-hint: [feature-name] [run-id]
---

Run the full test-evaluate cycle for feature `$1`: execute tests, run judge, show results.

Run ID: `$2` (default: `latest`).

If `$1` is not provided, list available features that have `tests/` directory and ask the user to choose.

## Prerequisites

The feature must have generated test code at `tests/vibeval/$1/tests/`. If not found, instruct the user to run the full workflow: `/vibeval-analyze $1` → `/vibeval-design $1` → `/vibeval-generate $1`.

## Execution Steps

### 1. Detect Test Framework

Check the test code directory for framework indicators:
- `conftest.py` or `test_*.py` → pytest
- `*.test.ts` or `*.spec.ts` → vitest/jest
- `*_test.go` → go test
- `pytest.ini` or `pyproject.toml` with pytest config → pytest

### 2. Run Tests

Execute the test suite using the detected framework. The tests will produce result files at `tests/vibeval/$1/results/{run_id}/`.

```bash
# Python/pytest
cd tests/vibeval/$1/tests && python -m pytest . -v

# TypeScript/vitest
npx vitest run tests/vibeval/$1/tests/

# Go
go test ./tests/vibeval/$1/tests/
```

If tests fail at the framework level (import errors, syntax errors, etc.), report the error and stop. Test assertion failures are fine — vibeval judge handles evaluation separately.

### 3. Run Judge

Execute vibeval judge to evaluate the results:

```bash
vibeval judge $1 $2
```

This reads judge_specs from datasets/ and evaluates each result file.

### 4. Show Results

Display the judge output (summary with binary pass rate and five-point distributions).

### 5. Diagnose Results

Read the result files from `tests/vibeval/$1/results/$2/` and perform structured analysis:

1. **Identify failures**: For each failed judge result (score=0 for binary, score<=2 for five-point), read the result file and analyze:
   - Which judge spec failed and why (the `reason` field)
   - Whether the failure is in the application output or the test design
   - Look at the trace to understand what the application did wrong (unnecessary tool calls, missing steps, wrong LLM outputs, etc.)

2. **Pattern analysis**: Look across all results for common patterns:
   - Are the same judge specs failing across multiple items? (systematic issue)
   - Are failures concentrated in specific datasets or items? (data-specific issue)
   - Are trace patterns abnormal? (extra turns, missing tool calls, etc.)

3. **Actionable recommendations**: Based on the diagnosis, suggest specific fixes:
   - If application logic is wrong → point to the relevant code and suggest changes
   - If test data is unreasonable → suggest adjusting dataset items or judge specs
   - If judge specs are too strict/loose → suggest tuning thresholds or criteria

Present the diagnosis as a concise summary: what passed, what failed, why, and what to do about it.

### 6. Suggest Next Steps

Based on the diagnosis:

- **If there are fixable failures**: offer to help fix the application code based on the diagnosis above.
- **If previous runs exist**: suggest running `vibeval compare $1 {previous_run} $2` for deeper cross-version analysis.
- **If results look good**: suggest committing the test suite and datasets to version control.
- **To iterate**: edit datasets or test code, then run `/vibeval-run $1` again.
- **To review visually**: suggest `vibeval serve --open` to browse results, traces, trends, and manage datasets in the interactive dashboard.

## Error Handling

- **Test framework not found**: suggest installing it (e.g., `pip install pytest`)
- **No result files produced**: check that test code saves results to the correct path
- **vibeval CLI not found**: suggest installing with `pip install vibeval`
- **Judge errors**: show the error and suggest checking dataset manifest for valid judge_specs
