# 0.6.0 Review Feedback Fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close five findings from an expert review of the 0.6.0 merges (`feat/contract-phase-rewrite` and `feat/agent-tool-validation`). Strengthen the `tool_coverage[]` mechanical invariant so placeholder item ids cannot satisfy it, wire missing protocol ↔ skill hand-offs, and realign orchestrator text with the `rigor` field.

**Architecture:** Protocol-first. The `07-agent-tools.md` Invariant is tightened and paired with a new **Allowed Spec Patterns per Dimension** enumeration so the Evaluator can cross-check item existence and per-dimension spec correspondence mechanically. A new `project.execution_mode: "agent" | "non_agent"` field on `analysis.yaml:project` gates the Agent-features dimensions. Contract, consultant, design, command, and evaluator files are aligned to the updated protocol.

**Tech Stack:** Markdown only (protocol, skill, agent, command files). No Python, no CLI changes.

**Branch:** `fix/0.6.0-review-feedback`, branched from `main` (at commit `a7073f4`, post-release v0.6.0).

---

## Findings and Fix Mapping

| Finding | Severity | Summary | Where | Fix location |
|---|---|---|---|---|
| F1 | High | `tool_coverage[]` invariant only checks non-empty keys; placeholder ids pass | 07-agent-tools:155, evaluator:51, design:73 | F1-b selected: Task 1 (protocol), Task 5 (design skill generator), Task 8 (evaluator) |
| F2 | High | Consultant design dispatch does not explicitly pass `analysis.yaml`; Agent Tool Failure Modes review not load-bearing | design:41, consultant:81 | Task 5 (design dispatch), Task 7 (consultant inputs) |
| F3 | Medium-High | Evaluator Analysis Phase Review has no dimension for `tools[]` / `design_risks` completeness | analyze:39, evaluator:31 | F3-b selected: Task 1 (protocol field), Task 4 (analyze writes), Task 8 (evaluator reads) |
| F4 | Medium | Contract skill saves contract before rigor inference, then re-saves; intermediate state is incomplete | contract:109, 06-contract:149 | Task 6 (contract skill reorder) |
| F5 | Medium | `/vibeval` command hardcodes max 3 evaluator iterations; `rigor` mapping is `light=1 / standard=3 / strict=5` | vibeval:108, vibeval:155, 06-contract:151 | Task 9 (command), Task 3 (06-contract cleanup) |

---

## Locked Design Decisions

### F1-b — Allowed Spec Patterns per Dimension (enumerable, no semantic judgment)

A new subsection of `07-agent-tools.md` enumerates, for each of the 7 coverage dimensions, the `judge_spec` patterns that satisfy the dimension. For every `(tool_id, dimension, item_id)` triple in `design.yaml:tool_coverage[]`, the evaluator cross-checks:

1. **Item existence.** `item_id` must resolve to an entry in a dataset's `items[]` reachable from the design.
2. **Spec pattern match.** The resolved item's effective `judge_specs` (item-level `_judge_specs` overriding the manifest's `judge_specs`) must contain at least one spec matching one of the dimension's allowed patterns.
3. **`output_handling` multi-item constraint.** The `dimensions_covered.output_handling` list must span ≥2 items whose `_mock_context` responses for this tool differ.

Allowed pattern table (verbatim text for Task 1):

| Dimension | Allowed pattern (at least one must match) |
|---|---|
| `positive_selection` | `method: rule`, `rule: tool_called`, `args.tool_name == <tool.surface.name>` |
| `negative_selection` | `method: rule`, `rule: tool_not_called`, `args.tool_name == <tool.surface.name>` |
| `disambiguation` | `method: llm`, `target: {step_type: "tool_call"}`, non-empty `trap_design` |
| `argument_fidelity` | EITHER `method: llm`, `target: {step_type: "tool_call"}`; OR `method: rule`, `rule: equals` or `matches`, `args.field` references a step-args path |
| `output_handling` | Item's `_mock_context` contains an entry keyed by the tool's mock target, AND item has `method: llm` with `target: "output"` (or `target` omitted). The multi-item constraint above also applies across the full `output_handling` list. |
| `sequence` | `method: rule`, `rule: tool_sequence`, `args.expected` contains `<tool.surface.name>` |
| `subagent_delegation` | Applies only to `type: subagent`. `method: llm`, `target: {step_type: "tool_call"}` |

**Principle:** No semantic reasoning on `criteria`, `test_intent`, or `trap_design` text. The evaluator matches only structural fields. The only "non-empty string" check is on `trap_design` for the disambiguation row.

### F3-b — `project.execution_mode` field

New required field at `analysis.yaml:project.execution_mode`. Enum: `"agent"` | `"non_agent"`. Chosen for:

- clarity (no overlap with the existing `pipelines:` concept),
- minimal schema change (one new field, two enum values).

Analyze skill populates the value by scanning source for tool registration sites (custom tool decorators, MCP server connections, sub-agent invocation patterns). Presence → `"agent"`. Ambiguous cases are surfaced at the checkpoint for user confirmation.

Every downstream consumer (design, evaluator, consultant) reads this field instead of re-scanning the code.

### F4 — Contract skill save ordering

Reorder Phase D/E so that:

1. Draft requirements / known_gaps / quality_criteria.
2. Infer `rigor` (currently Phase E).
3. Show the full draft (including `rigor`) to the user.
4. User confirms.
5. Save `contract.yaml` exactly once, fully populated.
6. Delete `_research.md`.

No re-save. No intermediate state.

### F5 — Rigor-aware iteration cap in `/vibeval` command

Replace `max 3 iterations per phase` in `plugin/commands/vibeval.md` with a lookup against `contract.yaml:rigor`:

- `light` → 1 iteration
- `standard` → 3 iterations
- `strict` → 5 iterations

Remove the "Phase skills that honor `rigor` will be updated in a follow-up plan (P1)" sentence from `06-contract.md` (this plan completes that promise for the `/vibeval` orchestrator; other phase-specific rigor wiring remains as deferred work but the orchestrator is no longer part of it).

---

## File Structure

**Create:** none

**Modify:**

- `plugin/protocol/references/07-agent-tools.md` — Invariant + Allowed Spec Patterns + execution_mode gate (Task 1)
- `plugin/protocol/references/01-overview.md` — short pointer to execution_mode (Task 2)
- `plugin/protocol/references/06-contract.md` — remove the P1 follow-up sentence (Task 3)
- `plugin/skills/analyze/SKILL.md` — write execution_mode in analysis.yaml (Task 4)
- `plugin/skills/design/SKILL.md` — Consultant dispatch + generator-side spec reminder (Task 5)
- `plugin/skills/contract/SKILL.md` — reorder Phase D/E (Task 6)
- `plugin/agents/consultant.md` — Design variant inputs include analysis.yaml (Task 7)
- `plugin/agents/evaluator.md` — strengthened Rule 7 + new Analysis Phase dimension (Task 8)
- `plugin/commands/vibeval.md` — rigor-based iteration cap (Task 9)

Nine files. One Python-free PR.

---

## Tasks

### Task 1 — `07-agent-tools.md`: strengthen Invariant, add Allowed Spec Patterns, add execution_mode

**Files:** Modify `plugin/protocol/references/07-agent-tools.md`

- [ ] **Step 1:** Add a new section `## Project Metadata: execution_mode` immediately after the `## Scope: What Counts as a Tool` section. Defines the field, its enum values, and how analyze determines the value. References 01-overview.md for the field's home in the analysis.yaml schema.

- [ ] **Step 2:** Add a new section `## Allowed Spec Patterns Per Dimension` immediately after `## Per-Tool Coverage Matrix` and before `## Design Coverage Cross-Reference`. Contents: the 7-row table from the Locked Design Decisions section above, the three-point mechanical check list (item existence / spec pattern match / multi-item output_handling), and a "No semantic reasoning" principle note.

- [ ] **Step 3:** Replace the Invariant paragraph (currently line 155) with the strengthened version:

> **Invariant.** At the end of the design phase, for every `analysis.yaml:tools[i]`, there exists exactly one `design.yaml:tool_coverage[j]` where `j.tool_id == i.id`, and every mandatory dimension key under `j.dimensions_covered` satisfies the mechanical check defined in "Allowed Spec Patterns Per Dimension" above — every referenced item must exist in a dataset reachable from the design and must carry at least one matching `judge_spec`. Any `high`-severity risk in `i.design_risks` must appear in `j.design_risks_addressed` with at least one referenced item that independently satisfies the check.

- [ ] **Step 4:** Update the "## Scope: What Counts as a Tool" section's opening sentence to mention that Agent-tool validation activates only when `analysis.yaml:project.execution_mode == "agent"`, with a reference to the new Project Metadata section.

- [ ] **Step 5:** Verify with grep: `## Project Metadata: execution_mode` (1), `## Allowed Spec Patterns Per Dimension` (1), `every referenced item must exist in a dataset reachable from the design` (1), `non-empty key` (0 — the old wording should be gone). Also confirm all 7 dimension keys appear in the new table.

- [ ] **Step 6:** Commit with message `protocol: tighten tool_coverage invariant and add execution_mode field` (plus co-author footer per project convention).

### Task 2 — `01-overview.md`: execution_mode pointer

**Files:** Modify `plugin/protocol/references/01-overview.md`

- [ ] **Step 1:** Extend the existing `## Agent Features` section with a line noting that `analysis.yaml:project.execution_mode` is the authoritative classification field (values: `"agent"`, `"non_agent"`). Cross-reference `07-agent-tools.md` for the field definition.

- [ ] **Step 2:** Verify: grep for `execution_mode` — expected 1 match. Grep `07-agent-tools.md` — expected 1 match (existing, unchanged).

- [ ] **Step 3:** Commit: `protocol: cross-reference execution_mode field from 01-overview`.

### Task 3 — `06-contract.md`: remove P1 follow-up sentence

**Files:** Modify `plugin/protocol/references/06-contract.md`

- [ ] **Step 1:** Find the sentence at line 157 (end of the `### rigor` subsection): `The contract skill writes the inferred level into `rigor` and explains it to the user for confirmation. Phase skills that honor `rigor` will be updated in a follow-up plan (P1).`

- [ ] **Step 2:** Replace with a version that removes the stale P1 reference and reflects that the `/vibeval` orchestrator is now wired up:

> The contract skill writes the inferred level into `rigor` and explains it to the user for confirmation. The `/vibeval` orchestrator reads `rigor` to cap evaluator iterations per phase (see `plugin/commands/vibeval.md`). Individual phase skills may read `rigor` for additional behavior (e.g., light-rigor Consultant dispatch compression) as they are updated over time.

- [ ] **Step 3:** Verify: grep for `follow-up plan (P1)` — expected 0 matches. Grep for `orchestrator reads \`rigor\`` — expected 1 match.

- [ ] **Step 4:** Commit: `protocol: drop stale P1 follow-up note from 06-contract rigor section`.

### Task 4 — `analyze/SKILL.md`: populate `project.execution_mode`

**Files:** Modify `plugin/skills/analyze/SKILL.md`

- [ ] **Step 1:** In Step 1 "Identify AI Call Points", add a paragraph at the end instructing the skill to classify the project's execution mode. The text should:
  - Name `project.execution_mode` as the target field
  - Enumerate the two values `"agent"` and `"non_agent"`
  - List the signals for `"agent"`: any custom tool registration (framework decorators / SDKs), any MCP server connection, any sub-agent invocation pattern
  - Direct the skill to `07-agent-tools.md` for the authoritative definition
  - Say that when the classification is genuinely ambiguous, the skill surfaces the question at the checkpoint for user confirmation (not silent default)

- [ ] **Step 2:** In the `## Output Format` YAML block, add `execution_mode: "agent|non_agent"` as a new required field under `project:`. Keep the existing `name`, `language`, `test_framework`, `ai_frameworks` fields.

- [ ] **Step 3:** In the Checkpoint section, add a bullet (or extend an existing one) summarizing the execution_mode decision with its justification.

- [ ] **Step 4:** Verify: grep for `execution_mode` — expected at least 3 matches (step body, YAML example, checkpoint). Grep for `^### 1\. Identify AI Call Points` — expected 1 (unchanged).

- [ ] **Step 5:** Commit: `skills: analyze populates project.execution_mode for Agent classification`.

### Task 5 — `design/SKILL.md`: F2 Consultant dispatch + F1-b generator-side requirement

**Files:** Modify `plugin/skills/design/SKILL.md`

- [ ] **Step 1 (F2):** In the `## Consultant Design Review (default)` section, update the Dispatch context list:

  Old:
  ```
  Dispatch context:
  - Feature name and contract path
  - Current `design.yaml` (draft)
  - Target output path: `tests/vibeval/{feature}/_design_research.md`
  ```

  New:
  ```
  Dispatch context:
  - Feature name and contract path
  - `tests/vibeval/{feature}/analysis/analysis.yaml` — **required**; the Consultant's Agent Tool Failure Modes section depends on `project.execution_mode`, `tools[]`, and `design_risks[]` being directly in its context.
  - Current `design.yaml` (draft)
  - Target output path: `tests/vibeval/{feature}/_design_research.md`
  ```

- [ ] **Step 2 (F1-b generator side):** In `### 1. Tool Coverage Planning (Agent features only)`, after the 5 numbered sub-steps, append a new sub-step:

  > **6. Prove the coverage mechanically.** Every item id listed under `dimensions_covered.{dimension}` must correspond to a dataset item whose effective `judge_specs` carry at least one pattern matching the dimension's allowed set in `${CLAUDE_PLUGIN_ROOT}/protocol/references/07-agent-tools.md` ("Allowed Spec Patterns Per Dimension"). Do not register an item id under a dimension unless you have authored (or are authoring in Step 2/3) the matching `judge_spec`. The Evaluator cross-checks this after the design phase; placeholder ids will block the handoff.

- [ ] **Step 3:** Also update the final paragraph of Step 1 (currently: "The design is not complete until every tool in `analysis.yaml:tools[]` has a matching `tool_coverage[]` entry with every mandatory dimension cell non-empty. The Evaluator agent re-verifies this invariant.") to reflect the strengthened invariant — mention "mechanically verifiable by item existence + spec pattern match" instead of "non-empty".

- [ ] **Step 4:** Verify: grep for `analysis\.yaml` in the Dispatch context section — expected 1 match. Grep for `Prove the coverage mechanically` — expected 1. Grep for `Allowed Spec Patterns Per Dimension` — expected 1. Grep for `every mandatory dimension cell non-empty` — expected 0 (old wording removed).

- [ ] **Step 5:** Commit: `skills: design dispatches consultant with analysis and enforces spec-pattern coverage`.

### Task 6 — `contract/SKILL.md`: single-save ordering

**Files:** Modify `plugin/skills/contract/SKILL.md`

- [ ] **Step 1:** Read the file to understand the current Phase D (Finalize & Save) and Phase E (Rigor Inference) structure.

- [ ] **Step 2:** Reorder so the flow is:
  1. Phase D Step 1–3: Draft requirements / known_gaps / quality_criteria.
  2. **New placement:** Infer `rigor` (Phase E body, moved in).
  3. Phase D Step 4: Show the full draft (including `rigor`) to the user.
  4. Phase D Step 5: Loop until confirm.
  5. Phase D Step 6: Save `contract.yaml` once; delete `_research.md`.

  Concretely: move the body of "Phase E: Rigor Inference" into "Phase D" between the quality_criteria draft step and the "Show the draft to the user" step. Remove the standalone Phase E heading. Remove the final "Record rigor in contract.yaml and re-save" step because rigor is now included in the first (and only) save.

- [ ] **Step 3:** Update any cross-references within the file that mention Phase E as a separate phase (checkpoint section, any summary paragraphs at the top).

- [ ] **Step 4:** Verify: grep for `Phase E:` — expected 0 matches. Grep for `re-save` — expected 0 matches. Grep for `Save to \`tests/vibeval/{feature}/contract\.yaml\`` — expected 1 match (single save). Grep for `Record \`rigor\` in contract\.yaml` — expected 0 matches.

- [ ] **Step 5:** Commit: `skills: contract infers rigor before saving to eliminate intermediate state`.

### Task 7 — `consultant.md`: Design variant inputs include analysis.yaml

**Files:** Modify `plugin/agents/consultant.md`

- [ ] **Step 1:** In the `## Inputs` section (around lines 62–68), add a bullet making it explicit that the Design variant receives `analysis.yaml` via dispatch context. Text:

  > For the **Design variant**, the dispatch context also includes `tests/vibeval/{feature}/analysis/analysis.yaml`. Read its `project.execution_mode`, `tools[]`, and each tool's `design_risks[]` before producing the Agent Tool Failure Modes section. Do not re-scan the source code for tool registrations — the analyze phase has already done that and the result is authoritative.

- [ ] **Step 2:** In the Output Format section where the Design variant's Agent Tool Failure Modes instructions live (around line 81), add a one-line precondition: "Emit this section only when `analysis.yaml:project.execution_mode == "agent"` AND `analysis.yaml:tools[]` is non-empty. Otherwise omit the section entirely."

- [ ] **Step 3:** Verify: grep for `project\.execution_mode == "agent"` — expected 1. Grep for `Do not re-scan the source code` — expected 1. Grep for `## Inputs` — expected 1 (unchanged).

- [ ] **Step 4:** Commit: `agents: consultant design variant consumes analysis.yaml directly`.

### Task 8 — `evaluator.md`: F1-b Rule 7 strengthening + F3-b Analysis Phase dimension

**Files:** Modify `plugin/agents/evaluator.md`

- [ ] **Step 1 (F3-b):** In the `### Analysis Phase Review` dimensions table, add a new row after the existing 4 rows:

  ```
  | **Tool inventory** | (Agent features only — applies when `analysis.yaml:project.execution_mode == "agent"`.) Is `tools[]` non-empty? For every entry, is `design_risks[]` present (even if empty)? Is `siblings_to_watch[]` present? A missing `tools[]` section or missing audit fields indicates analyze skipped Steps 2 or 3. See `${CLAUDE_PLUGIN_ROOT}/protocol/references/07-agent-tools.md` for inventory semantics. |
  ```

- [ ] **Step 2 (F1-b Rule 7 rewrite):** Replace the current Rule 7 body with the strengthened version that references the Allowed Spec Patterns table and enumerates the three mechanical checks. New text:

  > 7. **Mechanical checks come first for Agent features** — when `analysis.yaml:project.execution_mode == "agent"`, verify the strengthened `tool_coverage[]` invariant defined in `${CLAUDE_PLUGIN_ROOT}/protocol/references/07-agent-tools.md` before scoring any other dimension. For every `(tool_id, dimension, item_id)` triple in `design.yaml:tool_coverage[]`:
  >
  >    a. **Item existence**: `item_id` MUST resolve to a dataset item reachable from the design. Unresolved ids → blocking `tool_coverage: 0` finding.
  >
  >    b. **Spec pattern match**: the resolved item's effective `judge_specs` MUST contain at least one spec matching the dimension's allowed pattern (see "Allowed Spec Patterns Per Dimension" in `07-agent-tools.md`). The check is structural, not semantic — compare fields, do not interpret `criteria` or `test_intent`. Non-matching → blocking `tool_coverage: 0` finding.
  >
  >    c. **`output_handling` multi-item constraint**: the full `dimensions_covered.output_handling` list MUST span ≥2 items with distinct `_mock_context` responses for the tool's mock target. Under-populated → blocking.
  >
  >    Under `light` rigor from `contract.yaml`, checks (a) and (b) remain blocking only for tools with at least one `high`-severity `design_risk`; failures on tools without high-severity risk become non-blocking `tool_coverage: 1` findings. Check (c) is always blocking when the dimension is declared as covered. This matches `06-contract.md`'s definition of `light`.

- [ ] **Step 3:** Verify: grep for `Tool inventory` in the analysis-review context — expected at least 1 match. Grep for `Allowed Spec Patterns Per Dimension` — expected 1 (Rule 7 reference). Grep for `Item existence` — expected 1. Grep for `Spec pattern match` — expected 1. Grep for `multi-item constraint` — expected 1. Grep for `A missing mandatory key is a blocking` — expected 0 (previous Rule 7 wording removed).

- [ ] **Step 4:** Commit: `agents: evaluator verifies item existence and spec patterns for tool coverage`.

### Task 9 — `commands/vibeval.md`: rigor-based iteration cap

**Files:** Modify `plugin/commands/vibeval.md`

- [ ] **Step 1:** Read the file and find both occurrences of the hardcoded "max 3 iterations" wording (approximately lines 108 and 155).

- [ ] **Step 2:** Replace the first occurrence (line 108, inside the ASCII flow diagram) to reference the rigor mapping instead of a fixed number. Suggested replacement:

  > `   (iterations capped per rigor — see below)`

- [ ] **Step 3:** Replace the second occurrence (in the Evaluator integration prose, currently "Maximum 3 evaluator iterations per phase to avoid infinite loops") with a rigor-aware rule:

  > - Maximum evaluator iterations per phase is determined by `contract.yaml:rigor`:
  >   - `light` → 1 iteration
  >   - `standard` → 3 iterations
  >   - `strict` → 5 iterations
  >
  >   See `${CLAUDE_PLUGIN_ROOT}/protocol/references/06-contract.md` for the `rigor` field definition.

- [ ] **Step 4:** Verify: grep for `max 3 iterations` — expected 0 matches. Grep for `Maximum 3 evaluator iterations` — expected 0 matches. Grep for `contract.yaml:rigor` in `vibeval.md` — expected at least 1 match. Grep for `light. → 1 iteration` (or equivalent loose pattern) — expected 1 match.

- [ ] **Step 5:** Commit: `commands: /vibeval evaluator iterations follow contract rigor`.

### Task 10 — Final verification and regression safety

**Files:** none

- [ ] **Step 1:** Confirm each finding F1–F5 has at least one corresponding commit on this branch. Run `git log --oneline main..HEAD` and walk the 9 task commits.

- [ ] **Step 2:** Cross-file grep sanity checks:
  - `07-agent-tools.md` referenced from each modified skill/agent file that touches Agent tool validation: expected matches in `01-overview.md`, `analyze/SKILL.md`, `design/SKILL.md`, `consultant.md`, `evaluator.md`.
  - `project.execution_mode` appears in `07-agent-tools.md`, `01-overview.md`, `analyze/SKILL.md`, `consultant.md`, `evaluator.md` — all 5 places.
  - `Allowed Spec Patterns Per Dimension` appears in `07-agent-tools.md` (definition) and `design/SKILL.md` + `evaluator.md` (references).

- [ ] **Step 3:** Run the existing Python test suite for regression safety: `python -m pytest tests/ -v`. All tests should pass (this plan changes only markdown).

- [ ] **Step 4:** Confirm clean working tree with `git status`.

- [ ] **Step 5 (optional commit):** If any fix was applied inline during verification, commit with `fix:` prefix. Otherwise no additional commit.

---

## Self-Review

**Spec coverage.** F1-b is split across Task 1 (protocol definition), Task 5 (generator reminder in design skill), and Task 8 (evaluator cross-check). F2 is split across Task 5 (dispatch context) and Task 7 (consultant inputs note). F3-b is split across Task 1 (field semantics), Task 2 (overview pointer), Task 4 (analyze writes), Task 8 (evaluator reads). F4 is fully in Task 6. F5 is fully in Task 9, with Task 3 cleaning the stale P1 note. All 5 findings are accounted for.

**Placeholder scan.** All task steps have concrete old_string / new_string text or explicit grep patterns with expected counts. No "TBD" or "figure out" language.

**Type/field consistency.** `project.execution_mode` is the single canonical field name across all 5 files that touch it. Enum values `"agent"` and `"non_agent"` are used verbatim. The 7 coverage dimension keys (`positive_selection`, `negative_selection`, `disambiguation`, `argument_fidelity`, `output_handling`, `sequence`, `subagent_delegation`) remain the same as in 0.6.0. The three mechanical checks (item existence / spec pattern match / multi-item output_handling) use the same names everywhere.

**Scope.** Nine files, protocol-first ordering, no Python / CLI / dataset format changes. The tasks are independent except for: Task 5 depending on Task 1 (needs Allowed Spec Patterns table defined), Task 8 depending on Tasks 1 and 4 (needs table + execution_mode field written), Task 7 depending on Task 4 (needs execution_mode in analysis.yaml schema). Sequential execution in task-number order satisfies all dependencies.
