---
name: run
description: Run vibeval tests, execute judge evaluation, diagnose results, and suggest next steps. Use when entering the run phase of the /vibeval workflow.
---

# vibeval Run Phase

Execute the full test-evaluate cycle for a feature: run tests, judge results, diagnose failures.

**Before starting, read:**
- `tests/vibeval/{feature}/contract.yaml` — The negotiated contract. Diagnosis should reference contract requirements when analyzing failures.

## Output Language

Read `contract.yaml:output_language` (defaults to `English` if absent). The diagnosis you present to the user — failure summaries, pattern analysis, actionable recommendations, and the Checkpoint — MUST be written in that language. The `vibeval judge` and `vibeval compare` CLIs already inject `output_language` into the LLM judge/compare prompts (since v0.7.1), so the `reason` fields inside result and comparison files should already be in the target language; quote them as-is. Command names, file paths, framework error messages, and code snippets stay unchanged. See `${CLAUDE_PLUGIN_ROOT}/protocol/references/06-contract.md`.

## Steps

### 1. Detect Test Framework

Check `tests/vibeval/{feature}/tests/` for framework indicators:
- `conftest.py` or `test_*.py` → pytest
- `*.test.ts` or `*.spec.ts` → vitest/jest
- `*_test.go` → go test
- `pytest.ini` or `pyproject.toml` with pytest config → pytest

### 2. Run Tests

Execute the test suite using the detected framework. The tests will produce result files at `tests/vibeval/{feature}/results/{run_id}/`.

```bash
# Python/pytest
cd tests/vibeval/{feature}/tests && python -m pytest . -v

# TypeScript/vitest
npx vitest run tests/vibeval/{feature}/tests/

# Go
go test ./tests/vibeval/{feature}/tests/
```

If tests fail at the framework level (import errors, syntax errors, etc.), report the error and stop. Test assertion failures are fine — vibeval judge handles evaluation separately.

### 3. Run Judge

Execute vibeval judge to evaluate the results:

```bash
vibeval judge {feature} {run_id}
```

This reads judge_specs from datasets/ and evaluates each result file.

### 4. Show Results

Display the judge output (summary with binary pass rate and five-point distributions).

### 5. Diagnose Results

Read the result files from `tests/vibeval/{feature}/results/{run_id}/` and perform structured analysis:

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

## Checkpoint

Present diagnosis, then offer next steps:

- **Fix failures**: offer to help fix the application code based on the diagnosis above.
- **Compare runs**: if previous runs exist, suggest running `vibeval compare {feature} {previous_run} {run_id}` for deeper cross-version analysis.
- **Iterate**: edit datasets or test code, then re-run.
- **Visual review**: suggest `vibeval serve --open` to browse results, traces, trends, and manage datasets in the interactive dashboard.
- **Commit**: if results look good, suggest committing the test suite and datasets to version control.

## Error Handling

- **Test framework not found**: suggest installing it (e.g., `pip install pytest`)
- **No result files produced**: check that test code saves results to the correct path
- **vibeval CLI not found**: suggest installing with `pip install vibeval`
- **Judge errors**: show the error and suggest checking dataset manifest for valid judge_specs
