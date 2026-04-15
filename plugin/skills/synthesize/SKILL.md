---
name: synthesize
description: Synthesize vibeval test datasets by dispatching parallel Data Synthesizer agents — one per dataset. Use when entering the synthesize phase of the /vibeval workflow.
---

# vibeval Synthesize Phase

**Scope: Test data synthesis only.** This phase generates synthetic test data items (including user inputs, mock environment context, and traps) for all datasets defined in the design. Test code infrastructure is handled by the code phase and should already exist.

**Before starting, read:**
- `tests/vibeval/{feature}/contract.yaml` — The negotiated contract.
- `tests/vibeval/{feature}/design/design.yaml` — The test design specifying datasets, items, judge specs, and mock context summaries.
- `tests/vibeval/{feature}/analysis/analysis.yaml` — AI call points and mock targets.
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/00-philosophy.md` — Information asymmetry governs how data and mock context should be crafted.
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/02-dataset.md` — Dataset and data item format, including `_mock_context`.

## Output Language

Read `contract.yaml:output_language` (defaults to `English` if absent). When dispatching the `vibeval-data-synthesizer` agents, pass `output_language` in the dispatch context so each agent uses it for narrative fields — item `description`, `_mock_context.<target>.description`, dataset `description`, and the Checkpoint summary you present to the user. The actual user-facing input payloads (e.g., `user_message`, `query`, persona messages) and the mock response payloads themselves stay in whatever language the AI under test expects: a Chinese chatbot still receives Chinese inputs and Chinese mock context regardless of `output_language`. See `${CLAUDE_PLUGIN_ROOT}/protocol/references/06-contract.md` for the full scope.

## Steps

### 1. Plan Dataset Tasks

Read the design and enumerate all datasets to be generated. For each dataset, identify:
- Which contract requirements it covers
- Which mock targets it needs (from analysis)
- How many items to generate (design minimum + variants)
- What test dimensions to cover (from judge specs and item descriptions)

### 2. Dispatch Data Synthesizer Agents

For each dataset, spawn a **vibeval-data-synthesizer** agent with the following context:
- The dataset spec from design.yaml (items, judge_specs, schema, mock_context_summary)
- The relevant contract requirements and known gaps
- The mock targets from analysis.yaml
- The philosophy document path

**Spawn agents in parallel** — each dataset is independent. Example dispatch:

```
Agent 1: dataset "chat_persona" — 3 designed items, expand to 6-9 with variants
Agent 2: dataset "chat_injection" — 4 designed items, expand to 8-12 with variants
Agent 3: dataset "fishing_edge_cases" — 5 designed items, expand to 10-15 with variants
```

Each agent produces its complete dataset directory:
```
tests/vibeval/{feature}/datasets/{dataset_name}/
├── manifest.yaml
├── {item_id_1}.json
├── {item_id_2}.json
└── ...
```

### 3. Review and Cross-Validate

After all agents complete, review the generated datasets together to catch issues that are invisible when looking at datasets in isolation.

#### 3a. Design-Implementation Consistency

For each rule-type judge_spec, trace the `field` reference (e.g. `outputs.summary`) into the generated test code and the data items:

- **Type match**: does the value that will be assigned to that field match what the rule expects? For example, `length_between` expects a single string, not a concatenation of all turns.
- **Semantic match**: does the value represent what the designer intended? If the design says "single reply length <= 200 chars" but the test code assigns a multi-turn concatenation to `outputs.content`, the rule will evaluate the wrong thing.
- **Mock context completeness**: does every data item's `_mock_context` cover all mock targets that the test code will try to use? Missing mock targets will cause test failures.

#### 3b. Dataset-Level Spec Coverage Check

For each judge_spec defined at the **dataset level** (applies to all items):

- Enumerate every item in that dataset.
- For each item, determine whether the spec's expected behavior is correct. For example, a `tool_called: generate_image` spec is wrong for an item whose intent is to reject image requests.
- If a dataset-level spec conflicts with any item's expected behavior, move it to per-item `_judge_specs` with appropriate per-item values, or split into separate specs.

#### 3c. Iterate

If either check finds issues:

1. Fix the problem — modify datasets, items, or flag test code changes needed.
2. Re-run both checks on the updated artifacts.
3. Repeat until a full pass produces no new issues.

### 4. Validate Protocol Compliance via CLI

After all datasets are generated and cross-validated, run `vibeval validate` to validate all artifacts against the protocol:

```bash
vibeval validate {feature}
```

This validates manifest structure, judge_spec fields, data item format, `_mock_context` structure, trace format, and cross-references (e.g., `values_from` pointing to fields that exist in data items). If errors are reported, fix them before proceeding.

## Checkpoint

After data generation, present to the user:

1. Datasets created:
   - For each dataset: name, item count, test dimensions covered
   - Total items across all datasets

2. Mock context coverage:
   - Which mock targets are used across datasets
   - How mock scenarios vary across items (success/empty/error/edge-case)

3. Contract traceability:
   - Which requirements are covered by which datasets/items
   - Any requirements with thin coverage (flag for user attention)

4. Cross-validation results (Step 3) — any issues found and fixed

5. How to run:
   ```bash
   # Run tests to produce result files
   pytest tests/vibeval/{feature}/tests/
   # or: npx vitest tests/vibeval/{feature}/tests/
   # or: go test ./tests/vibeval/{feature}/tests/

   # Evaluate
   vibeval judge {feature} latest

   # View results
   vibeval summary {feature} latest
   ```

6. Ask: **"Datasets generated. Shall I run the tests and evaluate?"**

Wait for user confirmation before proceeding to the run phase.
