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
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/07-agent-tools.md` — **For Agent features only.** Per-tool coverage matrix (5 mandatory + 2 conditional dimensions) and the `tool_coverage[]` invariant. Consult before executing the Tool Coverage Planning step below.

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

## Consultant Design Review (default)

After producing the initial design, dispatch the `vibeval-consultant` agent to produce a **coverage-focused research brief**. This is a **default step**, not optional — the Consultant's value is highest at this stage because it catches coverage gaps before code and data generation invest effort in the wrong direction.

Dispatch context:
- Feature name and contract path
- `tests/vibeval/{feature}/analysis/analysis.yaml` — **required**. The Consultant's Agent Tool Failure Modes section depends on `project.execution_mode`, `tools[]`, and each tool's `design_risks[]` being directly in its context. Do not expect the Consultant to re-scan the source code.
- Current `design.yaml` (draft)
- Target output path: `tests/vibeval/{feature}/_design_research.md`

The Consultant reads the design and the feature context, then writes a brief containing:
- Coverage gaps — requirements or failure modes not addressed by any dataset/judge spec
- Missing test dimensions — e.g., adversarial inputs, mock environment failures, multi-turn state issues
- Seed questions the main agent should ask the user to decide whether each gap matters

**Main agent behavior after receiving the brief:**

1. Read `_design_research.md`.
2. For each high-priority gap, ask the user a targeted question (one at a time, not a list):
   > "The design doesn't currently cover <X>. Is that intentional, or should I add a dataset/spec for it?"
3. For each gap the user confirms is important:
   - If it implies a new requirement, add it to the contract with `source: brainstorm`.
   - Add corresponding items to the relevant dataset or create a new dataset.
4. Delete `_design_research.md` when done.

The Consultant never talks to the user directly. The main agent owns the dialogue.

The user can skip this step by explicitly requesting it, but it runs by default.

## Steps

### 1. Tool Coverage Planning (Agent features only)

If `analysis.yaml` contains a non-empty `tools[]` section, enumerate the per-tool coverage matrix BEFORE designing datasets. The coverage matrix (5 mandatory + 2 conditional dimensions), the `tool_coverage[]` invariant, and all field definitions live in `${CLAUDE_PLUGIN_ROOT}/protocol/references/07-agent-tools.md` — consult that file for semantics.

Operational procedure:

1. **Iterate the inventory.** For every entry in `analysis.yaml:tools[]`, create a matching entry in `design.yaml:tool_coverage[]` keyed by `tool_id`. The matching is 1:1 — if a tool has no entry, the design is incomplete.
2. **Plan items per mandatory dimension.** For each of `positive_selection`, `negative_selection`, `disambiguation`, `argument_fidelity`, `output_handling`, plan at least one dataset item that exercises the dimension. One item may cover multiple dimensions if the scenario naturally exercises them. Record the item ids under `dimensions_covered`.
3. **Plan items for applicable conditional dimensions.** Include `sequence` only when the tool has a documented ordering dependency with another tool. Include `subagent_delegation` only when `type: subagent`.
4. **Address high-severity design risks.** For every `design_risks` entry with `severity: high`, plan at least one item that directly exercises that risk and record it in `design_risks_addressed`. Medium and low risks are optional targets.
5. **Assign items to datasets.** Decide which dataset(s) will host the planned items — the item bodies themselves are produced in Step 2 (Design Datasets), and their judge specs in Step 3 (Design Judge Specs). This step produces the plan and the `tool_coverage[]` cross-reference block.
6. **Prove the coverage mechanically.** Every item id you list under `dimensions_covered.<dimension>` must, by the end of Step 3, correspond to a dataset item whose effective `judge_specs` carry at least one spec matching that dimension's Allowed Spec Pattern from `${CLAUDE_PLUGIN_ROOT}/protocol/references/07-agent-tools.md` (section "Allowed Spec Patterns Per Dimension"). Do not register an item id under a dimension unless you have authored (or are authoring in Step 2 or Step 3) the matching `judge_spec`. The Evaluator cross-checks this after the design phase using structural field comparison on `method`, `rule`, `args.tool_name`, `args.expected`, `target.step_type`, `args.field` (presence), and `trap_design` (presence/non-empty) — placeholder ids or non-matching specs will block the handoff.

Skip this step entirely when `analysis.yaml` has no `tools[]` section (i.e., `project.execution_mode == "non_agent"`).

The design is not complete until every tool in `analysis.yaml:tools[]` has a matching `tool_coverage[]` entry satisfying the strengthened invariant defined in `${CLAUDE_PLUGIN_ROOT}/protocol/references/07-agent-tools.md` (section "Allowed Spec Patterns Per Dimension") — every referenced item id must resolve to a real dataset item, and every resolved item must carry at least one `judge_spec` matching the dimension's Allowed Spec Patterns Per Dimension. Non-empty keys alone are not enough; placeholder ids fail. The Evaluator agent re-verifies the invariant mechanically.

### 2. Design Datasets

For each pipeline in the analysis, design one or more datasets.

For data item format (single-turn items and multi-turn personas), consult `${CLAUDE_PLUGIN_ROOT}/protocol/references/02-dataset.md`.

Each data item should have a clear testing intent — what specific capability or failure mode is being tested. Apply the information asymmetry principle from `${CLAUDE_PLUGIN_ROOT}/protocol/references/00-philosophy.md`: embed deliberate traps and edge cases that will be visible only to the judge.

### 3. Design Judge Specs

Consult `${CLAUDE_PLUGIN_ROOT}/protocol/references/03-judge-spec.md` for the complete list of available rules, LLM scoring modes (binary/five-point), `target` options for process evaluation, and all required fields.

Key design guidance (from philosophy):

- `test_intent` and `trap_design` encode the designer's insider knowledge — what the test is designed to catch, what traps are embedded in the data. These are REQUIRED for LLM specs.
- `anchors` must describe what good/bad looks like **for this specific test scenario**, not generic quality statements.
- `calibrations` must show concrete examples from the test scenario that reveal the pitfalls the tested AI might fall into.
- Use `target` to decompose evaluation: one spec for final output, others for specific turns or step types. Consult `${CLAUDE_PLUGIN_ROOT}/protocol/references/03-judge-spec.md` for target syntax.
- One JudgeSpec per evaluation dimension. Do not combine multiple criteria.

### 4. Design Test Structure

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

### 5. Design Mock Environment Context (single-turn only)

The AI under test doesn't just receive user input — it also receives data from tools, APIs, and databases it calls during processing. These responses are **part of the test input** and must be designed with the same deliberation as user-facing data.

For each mock point identified in the analysis (`ai_calls` and `external_deps`), design what each dependency returns **per data item**. This mock data lives in `_mock_context` within each data item (see `${CLAUDE_PLUGIN_ROOT}/protocol/references/02-dataset.md` for format).

**Design principles:**

- **Mock responses shape AI behavior** — a search tool returning empty results, a database returning stale data, or an API returning an error are all distinct test scenarios. Design them deliberately.
- **Traps can live in mock context** — if testing whether the AI detects contradictions between user input and tool output, embed that contradiction in `_mock_context` and document the trap in `description`.
- **Per-item variation** — different items should exercise different environment conditions (success, empty, error, edge-case data, conflicting data).
- **LLM mock responses** must be realistic and exercise the judge specs. For rules with `values_from`, responses MUST include all expected values. For multi-call pipelines, design sequential responses in order.
- **Multi-call ordering** — for pipelines that call the same dependency multiple times, design the response sequence in order.

In the design output, mock context is specified per item under `mock_context_summary` (the full `_mock_context` data is generated in the data synthesis phase):

```yaml
items:
  - id: "search_empty"
    description: "Search returns no results — tests graceful degradation"
    data: { user_message: "Find info about quantum computing" }
    mock_context_summary:
      "myapp.services.search.query": "Returns empty results"
      "myapp.services.llm.chat": "Responds acknowledging no search results found"
```

Multi-turn tests do NOT mock LLM responses — they use the real bot with `vibeval simulate` providing user messages. However, if multi-turn tests mock **non-LLM** dependencies (databases, APIs, tools), those mock responses should still be designed here.

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
        mock_context_summary:  # What each mocked dependency returns for this item (design-level summary; full _mock_context generated in data synthesis)
          "<mock_target>": "<brief description of mock response and why>"

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

# Agent features only. One entry per tool in analysis.yaml:tools[].
# Full invariant and field definitions in 07-agent-tools.md.
# Omit this section entirely for non-Agent features.
tool_coverage:
  - tool_id: "<matches analysis.yaml:tools[].id>"
    dimensions_covered:
      positive_selection: ["<item id>"]
      negative_selection: ["<item id>"]
      disambiguation: ["<item id>"]
      argument_fidelity: ["<item id>"]
      output_handling: ["<item id>"]
      sequence: ["<item id>"]              # only if applicable
      subagent_delegation: ["<item id>"]   # only if applicable
    design_risks_addressed:
      - "<severity>/<category>: <item id> targets this risk directly"

test_code:
  framework: "<pytest|vitest|jest|go test>"

  tests:
    - name: "<test_function_name>"
      type: "<single-turn|multi-turn>"
      dataset: "<dataset_name>"
      pipeline_entry: "<module.function>"
      # Single-turn: mock targets (responses come from _mock_context in each data item)
      mock_targets:
        - "<mock_target_1>"
        - "<mock_target_2>"
      # Multi-turn: define chat entry
      chat_entry: "<module.function>"
      use_vibeval_simulate: true
```

## Checkpoint

Present to the user:
1. Summary: datasets (single-turn/multi-turn), items count, judge specs count
2. Ask to review judge specs — anchors, calibrations, test_intent, and trap_design directly affect evaluation quality
3. **Agent features only.** Tool coverage status: for each tool in `analysis.yaml:tools[]`, list which dimensions are covered and by how many items. Flag any tool whose mandatory dimensions are incomplete.
4. Suggest `vibeval serve --open` to visually review and edit datasets, items, and judge specs in the interactive dashboard
5. Ask: **"Design complete. Shall I proceed to generate test code and datasets?"**

Wait for user confirmation before proceeding to the generate phase.
