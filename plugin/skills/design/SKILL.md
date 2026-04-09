---
name: design
description: Design vibeval test plan — define datasets, judge specs, and test structure based on analysis. Use when entering the design phase of the /vibeval workflow.
---

# vibeval Design Phase

**Scope: AI capability evaluation only.** All datasets, judge specs, and test structures designed in this phase must target the evaluation of AI behavior — how well the AI understands, reasons, and responds. Do NOT design tests for deterministic logic surrounding the AI calls (input validation, output parsing, routing, data formatting). Those belong in standard unit tests, not vibeval.

Read `tests/vibeval/{feature}/analysis/` and design a complete test plan.
Produce design artifacts in `tests/vibeval/{feature}/design/`.

**Before starting, read:**
- `tests/vibeval/{feature}/contract.yaml` — **The negotiated contract.** Every requirement must have corresponding test coverage. Quality criteria define the bar for this design.
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/00-philosophy.md` — **Must read first.** The three core principles (information asymmetry + global process visibility + contract) govern all design decisions.
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/02-dataset.md` — Dataset format, data items, persona format.
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/03-judge-spec.md` — Complete rule taxonomy, LLM scoring modes, target options, all field definitions.

## Contract-Driven Design

The contract is the primary driver for test design. Before designing datasets and judge specs:

1. **List all contract requirements** and plan which dataset(s) and judge spec(s) will cover each
2. **Prioritize `known_gaps`** — these represent the highest-risk areas and should have the most thorough test coverage
3. **Apply `quality_criteria`** from the contract — respect `user_emphasis` when deciding coverage depth
4. **Check `feedback_log`** — if past feedback exists, ensure it has been addressed in this design

Every requirement should be traceable: `contract requirement → dataset item(s) → judge spec(s)`.

## Mode Awareness

If entering this phase in **additive mode** (from a COMPLETE feature wanting to add tests), read existing `design/design.yaml` first and ADD to it rather than replacing it. Preserve all existing datasets and judge specs.

If entering in **edit mode** (modifying existing design), read existing design and make targeted changes as discussed with the user.

## Consultant Enrichment (optional)

After producing the initial design, if the coverage feels thin or only covers obvious happy-path scenarios, the `/vibeval` command may delegate to the `vibeval-consultant` agent to suggest additional test scenarios. The Consultant analyzes the feature context and current design, then proposes scenarios the design doesn't cover (adversarial inputs, failure modes, edge cases). User-confirmed suggestions are incorporated as additional dataset items or new datasets, and any new requirements are added to the contract with `source: suggested`.

## Steps

### 1. Design Datasets

For each pipeline in the analysis, design one or more datasets.

For data item format (single-turn items and multi-turn personas), consult `${CLAUDE_PLUGIN_ROOT}/protocol/references/02-dataset.md`.

Each data item should have a clear testing intent — what specific capability or failure mode is being tested. Apply the information asymmetry principle from `${CLAUDE_PLUGIN_ROOT}/protocol/references/00-philosophy.md`: embed deliberate traps and edge cases that will be visible only to the judge.

### 2. Design Judge Specs

Consult `${CLAUDE_PLUGIN_ROOT}/protocol/references/03-judge-spec.md` for the complete list of available rules, LLM scoring modes (binary/five-point), `target` options for process evaluation, and all required fields.

Key design guidance (from philosophy):

- `test_intent` and `trap_design` encode the designer's insider knowledge — what the test is designed to catch, what traps are embedded in the data. These are REQUIRED for LLM specs.
- `anchors` must describe what good/bad looks like **for this specific test scenario**, not generic quality statements.
- `calibrations` must show concrete examples from the test scenario that reveal the pitfalls the tested AI might fall into.
- Use `target` to decompose evaluation: one spec for final output, others for specific turns or step types. Consult `${CLAUDE_PLUGIN_ROOT}/protocol/references/03-judge-spec.md` for target syntax.
- One JudgeSpec per evaluation dimension. Do not combine multiple criteria.

### 3. Design Test Structure

**For single-turn tests:**
- Mock external deps using the test framework's mock mechanism
- Wrap mocks to capture trace steps (for trace format, consult `${CLAUDE_PLUGIN_ROOT}/protocol/references/04-result.md`)
- Each test: 1 turn with input → steps → output

**For multi-turn tests:**
- A for loop that drives N rounds of conversation
- Each round: send user message to bot → capture internal steps → record turn
- To generate subsequent user messages, run `vibeval simulate --help` for CLI syntax
- First round uses `opening_message` from persona (no simulate needed)
- Test code is responsible for managing bot state (conversation history, etc.)

### 4. Design Mock LLM Responses (single-turn only)

- Responses should be realistic and exercise the judge specs
- For rules with `values_from`, responses MUST include all expected values
- For multi-call pipelines, design sequential responses in order

Multi-turn tests do NOT mock LLM responses — they use the real bot with `vibeval simulate` providing user messages.

## Output Format

Write the primary design to `tests/vibeval/{feature}/design/design.yaml`.
Additional artifacts (notes, diagrams, etc.) can be placed alongside.

```yaml
# vibeval Test Design
source_analysis: "tests/vibeval/{feature}/analysis/"

datasets:
  - name: "<dataset_name>"
    description: "<what this dataset tests>"
    target_pipeline: "<pipeline name from analysis>"
    type: "<single-turn|multi-turn>"

    schema:
      field1: "<type and purpose>"

    items:
      - id: "<item_id>"
        tags: ["<tag>"]
        description: "<what this item tests — testing intent>"
        data: { ... }

    judge_specs:
      # See ${CLAUDE_PLUGIN_ROOT}/protocol/references/03-judge-spec.md for complete field definitions
      - method: rule
        rule: "<rule_name>"
        args: { ... }
        weight: "gate"
      - method: llm
        scoring: "<binary|five-point>"
        criteria: "<evaluation criteria>"
        test_intent: "<what this evaluates>"
        trap_design: "<traps embedded in the data>"
        target: "<output | {turns: [...]} | {step_type: '...'}>"
        anchors: { ... }
        calibrations: [ ... ]

test_code:
  framework: "<pytest|vitest|jest|go test>"

  tests:
    - name: "<test_function_name>"
      type: "<single-turn|multi-turn>"
      dataset: "<dataset_name>"
      pipeline_entry: "<module.function>"
      # Single-turn: define mocks
      mocks:
        - target: "<mock_target>"
          responses_per_item:
            "<item_id>": ["<response1>", "<response2>"]
      # Multi-turn: define chat entry
      chat_entry: "<module.function>"
      use_vibeval_simulate: true
```

## Checkpoint

Present to the user:
1. Summary: datasets (single-turn/multi-turn), items count, judge specs count
2. Ask to review judge specs — anchors, calibrations, test_intent, and trap_design directly affect evaluation quality
3. Suggest `vibeval serve --open` to visually review and edit datasets, items, and judge specs in the interactive dashboard
4. Ask: **"Design complete. Shall I proceed to generate test code and datasets?"**

Wait for user confirmation before proceeding to the generate phase.
