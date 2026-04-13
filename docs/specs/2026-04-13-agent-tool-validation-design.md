# Agent Tool Validation — Design Spec

**Date:** 2026-04-13
**Status:** Approved by user, pending implementation plan
**Downstream:** an implementation plan will be produced separately via `writing-plans` and placed in `docs/plans/`.

## Goal

Introduce **per-tool validation** as a first-class testing unit for Agent projects in vibeval, so that custom tools, MCP tools, and sub-agents each get dedicated test coverage that validates both their *design* (static audit of name/description/schema/prompt) and their *behavior* (selection, argument fidelity, output handling, delegation). This closes the structural gap where the current `analyze → design` flow treats an Agent holistically and can silently miss per-tool test points.

## Motivation

Real-project feedback (see memory `feedback_real_project_eval.md`) and the user's own follow-up after end-to-end usage identified that Agent-style features have a testable surface — the tool catalogue — that the current framework does not model explicitly. Concretely:

- `analysis.yaml` today has `ai_calls[]` (LLM invocations) and `external_deps[]` (other external dependencies), but **no inventory of tools that are registered for the LLM to choose from**. Tools end up lumped into one of those two buckets depending on how the code is structured.
- Without an explicit tool inventory, the design phase has no mechanical way to enforce "every tool has test coverage" — it depends on the LLM's self-awareness during that one pass.
- Failure modes specific to tool design (description ambiguity, semantic overlap between two tools, opaque output schema, sub-agent delegation misrouting) get caught at most by accident in the current flow.

The fix is not a new phase. It is a structural augmentation of the two phases where the gap lives (`analyze` and `design`), with everything downstream (synthesize / code / run / judge) inheriting the improved coverage automatically.

## Non-Goals

- No new `judge_spec` rules. Existing primitives (`tool_called`, `tool_not_called`, `tool_sequence`, `llm` with `target.step_type: "tool_call"`, `_mock_context`) are sufficient to express every coverage dimension.
- No recursive evaluation of sub-agent internals. A sub-agent is tested only at the **delegation boundary** of its parent. If the user wants to evaluate a sub-agent's own behavior, they run vibeval on that sub-agent as its own feature.
- No language- or framework-specific tool discovery. Discovery is LLM-driven by reading source code, consistent with vibeval's language-agnostic principle.
- No changes to `synthesize`, `code`, `run`, `judge`, or `update` skills. No changes to dataset format, result format, or CLI commands.
- No changes to `contract.yaml` schema. Tool-related user requirements are recorded through the existing `requirements[]` + `source: user|brainstorm` mechanism.
- No new protocol fields on `analysis.yaml` or `design.yaml` beyond the specific additions listed below.

## Mental Model

For Agent projects, the unit of test coverage shifts from "the pipeline as a whole" to "each tool in the pipeline's catalogue, plus the pipeline's overall output".

A **Tool** is any entity the LLM sees as a selectable action surface. Three subtypes:

| Subtype | Examples | Distinguishing trait |
|---|---|---|
| `custom_tool` | A Python/TS function registered with an LLM framework (OpenAI tools, Anthropic tool use, LangChain `@tool`, etc.) | Defined in-repo; surface is code-level name + description + input schema |
| `mcp_tool` | A tool exposed by an MCP server the agent connects to | Defined out-of-repo via MCP protocol; surface is discovered from MCP config / manifest |
| `subagent` | A sub-agent that the main agent invokes as if it were a tool (delegation pattern) | Surface is a tool-like invocation handle; internals are a separate LLM system prompt + its own tool catalogue |

Each tool is an independent test unit with its own **coverage matrix** (see Coverage Matrix below). Sub-agents participate in the inventory with a dedicated "delegation" dimension; their internals are **explicitly out of scope** to avoid recursive complexity.

## Protocol Changes (Protocol First)

Per the project's Protocol First principle, protocol files are updated *before* any skill, agent, or CLI code is touched. The changes are:

### P1. New file: `plugin/protocol/references/07-agent-tools.md`

A standalone protocol document defining Agent tool validation. Contents:

1. **Scope** — What counts as a tool for vibeval's purposes. The three subtypes and their distinguishing traits.
2. **Tool Inventory Entry Structure** — Full YAML schema for entries under `analysis.yaml:tools[]`. See [Tool Inventory Data Model](#tool-inventory-data-model) below for the authoritative shape.
3. **Static Design Audit** — The audit that `analyze` runs against each entry. Defines the finding taxonomy:
   - `description_ambiguity` — name/description do not disambiguate the tool from plausible alternatives
   - `schema_gap` — input schema omits a parameter the LLM would need to construct a correct call from the description
   - `overlap` — two tools' descriptions claim overlapping responsibility, creating selection ambiguity
   - `output_opacity` — output shape is unstructured or under-documented, making it hard for the LLM to consume
   - `subagent_prompt_leak` — sub-agent description surfaces internals that could bias the main agent's delegation decision
   - `responsibility_drift` — stated responsibility and actual code behavior diverge
4. **Per-Tool Coverage Matrix** — The 5 mandatory + 2 conditional dimensions, their triggering conditions, and the typical `judge_spec` patterns that express each dimension. See [Coverage Matrix](#coverage-matrix) below.
5. **Design Coverage Cross-Reference** — The `tool_coverage[]` section that `design.yaml` must produce, and how it maps back to inventory entries to make "every tool covered" a mechanically verifiable property.
6. **Examples** — End-to-end examples for each subtype, including sample inventory entries and derived `judge_specs`.

A brief "who reads this file" section at the top: analyze skill, design skill, evaluator agent, consultant agent.

### P2. `plugin/protocol/references/00-philosophy.md` — Add a sub-principle

Under Principle 2 (Global Perspective) or as a new Principle 4, add a short section: **"For Agent features, each tool is an independent test unit."** The body explains that holistic-output testing verifies end results, while per-tool testing verifies each decision point in the process. One paragraph. Cross-reference `07-agent-tools.md`.

### P3. `plugin/protocol/references/03-judge-spec.md` — Add cross-reference

In the Trace Rules section (after `tool_sequence` / `tool_called` / `tool_not_called`) and in the `target.step_type` documentation, add a "See also" note pointing to `07-agent-tools.md` for how these primitives compose into a complete per-tool coverage matrix. **No new rules are added.**

### P4. `plugin/protocol/references/01-overview.md` — Mention shared artifact

In the Data Flow section or adjacent to the directory structure, add one line: for Agent-type features, `analysis.yaml` includes a `tools[]` inventory consumed by design as a shared contract. Link to `07-agent-tools.md`.

### P5. `plugin/protocol/references/06-contract.md` — No structural change

No field additions. Add a short note under the `requirements` field documentation clarifying that tool-related behavioral requirements (e.g., "must call search before answering factual questions") are recorded through the existing `requirements` mechanism with appropriate `source` attribution. Cross-reference `07-agent-tools.md` for downstream test coverage mapping.

### P6. Update `plugin/protocol/README.md`

Update the Quick Reference summary to include `07-agent-tools.md`.

## Tool Inventory Data Model

Added to `analysis.yaml` as a new top-level section `tools[]`. For Agent features, this section is populated; for non-Agent features (no tool surface), it is omitted or empty and the downstream flow behaves as today.

```yaml
tools:
  - id: "<stable identifier, snake_case>"
    type: "custom_tool | mcp_tool | subagent"
    source_location: "<file:line, config path, or MCP server name>"

    # What the LLM actually sees when choosing this tool.
    # Captured verbatim from the registration site where possible.
    surface:
      name: "<name exposed to LLM>"
      description: "<description exposed to LLM, full text>"
      input_schema:              # object or summary; free-form but SHOULD mirror the real schema
        <param>: "<type, required/optional, brief>"
      output_shape: "<description of what the tool returns to the LLM>"

    responsibility: "<one-line statement of what this tool is for>"

    # Static audit findings; one entry per finding.
    design_risks:
      - severity: "high | medium | low"
        category: "description_ambiguity | schema_gap | overlap | output_opacity | subagent_prompt_leak | responsibility_drift"
        finding: "<what the auditor saw>"
        suggested_fix: "<optional; a one-line suggestion>"

    # Other tools with potential selection overlap. Drives the disambiguation
    # coverage dimension. Empty list is allowed.
    siblings_to_watch:
      - id: "<other tool id>"
        overlap_reason: "<why these two could be confused>"

    # Only populated when type == "subagent".
    subagent_prompt_summary: "<abbreviated prompt, 1-3 sentences, or null>"
    subagent_expected_context: ["<context key>", "..."]  # or null
```

**Notes on the model:**

- `surface` captures the LLM-facing view (the only view that matters for selection behavior) and is the shared input of both static audit and behavioral test generation.
- `design_risks` is produced by the static audit pass and becomes a priority input for the design phase: `high` risks MUST have at least one test item specifically targeting them.
- `siblings_to_watch` is the trigger for the disambiguation coverage dimension. When empty, disambiguation degrades gracefully into "a general-purpose distractor scenario" rather than requiring a specific sibling.
- Sub-agent fields are nullable and only meaningful for `type: subagent` entries.

## Coverage Matrix

Each tool entry induces a fixed coverage matrix. The matrix is the design phase's mechanical checklist — every (tool, dimension) cell under "Mandatory" must map to at least one item in `tool_coverage`.

| # | Dimension | Mandatory | Applicability | Typical judge_spec pattern |
|---|---|---|---|---|
| 1 | Positive selection | Yes | All tools | `rule: tool_called` on a scenario where this tool is the correct choice |
| 2 | Negative selection | Yes | All tools | `rule: tool_not_called` on a scenario where no tool (or a different tool) is correct |
| 3 | Disambiguation | Yes | All tools; degraded when `siblings_to_watch` is empty | `llm` + `target: {step_type: "tool_call"}` + `trap_design` describing the ambiguity |
| 4 | Argument fidelity | Yes | All tools | `llm` + `target: {step_type: "tool_call"}` evaluating the constructed arguments; or `rule: equals` on step args when deterministic |
| 5 | Output handling | Yes | All tools | Varied `_mock_context` responses (success / empty / error / edge) + `llm` + `target: "output"` evaluating downstream behavior |
| 6 | Sequence / composition | Conditional | Only when this tool has a documented ordering dependency with another tool | `rule: tool_sequence` |
| 7 | Sub-agent delegation | Conditional | Only when `type: subagent` | `llm` + `target: {step_type: "tool_call"}` evaluating whether the main agent delegated at the right moment and passed sufficient context |

**Gate rule:** for every tool entry, cells 1–5 must each map to at least one item in `design.yaml:tool_coverage[]`. Cells 6 and 7 are required only when their applicability condition holds. The Evaluator agent treats missing mandatory cells as a blocking issue.

**Degradation rule for #3:** when `siblings_to_watch` is empty, disambiguation is still required, but it is satisfied by a scenario that pits this tool against a plausible-but-wrong general-purpose alternative (e.g., "answer from parametric memory"), not necessarily another registered tool.

## Design Coverage Cross-Reference

`design.yaml` gains a new top-level section `tool_coverage[]` produced during design. Its purpose is to make coverage mechanically verifiable without re-inspecting every item.

```yaml
tool_coverage:
  - tool_id: "<matches analysis.yaml:tools[].id>"
    dimensions_covered:
      positive_selection: ["<item id>", "..."]
      negative_selection: ["<item id>", "..."]
      disambiguation: ["<item id>", "..."]
      argument_fidelity: ["<item id>", "..."]
      output_handling: ["<item id>", "..."]
      sequence: ["<item id>", "..."]           # optional
      subagent_delegation: ["<item id>", "..."]  # optional
    design_risks_addressed:
      - "<severity>/<category>: <item id> targets this risk directly"
```

**Invariant:** at end of design, for every `analysis.yaml:tools[i]`, there exists exactly one `design.yaml:tool_coverage[j]` with `j.tool_id == i.id`, and all mandatory dimension cells under `j.dimensions_covered` are non-empty. The design skill enforces this during its final checklist; the Evaluator agent re-verifies it.

## Skill and Agent Changes

These changes land **after** the protocol changes above are merged. Each skill or agent file references the new protocol file rather than duplicating its content.

### S1. `plugin/skills/analyze/SKILL.md`

- **New step: Extract Tool Inventory.** Inserted between current Step 1 (Identify AI Call Points) and Step 2 (Determine Test Mode). Instructs the agent to identify custom tools, MCP tools, and sub-agents in the codebase via LLM-driven code read, and to populate `tools[]` with `type`, `source_location`, and the `surface` block.
- **New step: Audit Tool Design.** Inserted immediately after. Runs a static audit LLM pass over each entry using the finding taxonomy from `07-agent-tools.md` and populates `design_risks[]` and `siblings_to_watch[]`.
- **Output Format section:** extend the YAML example to show the `tools[]` block, with a pointer that full field definitions live in `07-agent-tools.md`.
- **Checkpoint:** add one bullet — "List of identified tools, their types, and any high-severity design risks."

### S2. `plugin/skills/design/SKILL.md`

- **New step: Tool Coverage Planning.** Inserted after "Contract-Driven Design" and before Step 1 (Design Datasets). Reads `analysis.yaml:tools[]`, enumerates the coverage matrix per tool, and plans items + judge_specs to populate each mandatory cell. High-severity `design_risks` entries require at least one item explicitly targeting them.
- **Output Format section:** extend the YAML example to show the `tool_coverage[]` block with a pointer to `07-agent-tools.md`.
- **Checkpoint:** add one bullet — "Tool coverage status: for each tool, list which dimensions are covered and by how many items."

### S3. `plugin/agents/consultant.md`

- **Design-phase research brief:** add a new section "Agent Tool Failure Modes". When the design phase dispatches the consultant with a draft `design.yaml` and `analysis.yaml` (including `tools[]`), the consultant produces seed questions specifically about tool design failure modes visible in the inventory:
  - Description ambiguity that might cause wrong selection
  - Missing output-handling scenarios (empty, error, malformed)
  - Sub-agent delegation paths that may not have been considered
- The consultant does not talk to the user directly — the main design-skill agent uses the brief as dialogue seeds, consistent with current consultant behavior.

### S4. `plugin/agents/evaluator.md`

- **New verification clause for design review:** for every `analysis.yaml:tools[]` entry, verify `design.yaml:tool_coverage[]` contains a matching entry with all mandatory dimension cells non-empty. Missing coverage is reported as a blocking issue. Matching and verification is mechanical (key lookup + non-empty check), not a judgment call.
- **Severity filtering** continues to apply per `contract.yaml:rigor` — under `light` rigor, only high-severity missing coverage is surfaced.

### S5. No changes to other skills

`synthesize`, `code`, `run`, `update`, and the CLI remain untouched. Datasets produced by synthesize already support everything this feature requires (`_mock_context`, arbitrary `judge_specs`), and `vibeval judge` / `vibeval run` consume them as usual.

## Verification Approach

How we will know the feature works end-to-end:

1. **Protocol self-consistency** — `07-agent-tools.md` is internally complete; every field it defines has a corresponding place in the example YAML blocks; `00-philosophy.md`, `01-overview.md`, `03-judge-spec.md`, `06-contract.md`, and `plugin/protocol/README.md` all cross-reference it correctly.
2. **Skill docs reference the protocol, not duplicate it** — per the project's CLI/plugin-doc-vs-protocol separation principle, skill docs must point to `07-agent-tools.md` for definitions.
3. **End-to-end dry run on a real Agent project** — take an existing agent-style feature (ideally the one that triggered this request) and run the updated `analyze` → `design` flow. Verify:
   - `analysis.yaml` contains a `tools[]` section with at least one entry per registered tool.
   - At least one design risk is surfaced for a tool whose description the user agrees is ambiguous.
   - `design.yaml:tool_coverage[]` covers every tool with the 5 mandatory dimensions.
   - Evaluator blocks the design if a tool is deliberately removed from `tool_coverage` as a test, and unblocks it once restored.
4. **Downstream pipeline unaffected** — the same Agent feature, after synthesize/code/run/judge, produces a normal results bundle with no protocol violations. Existing tests (`tests/`) continue to pass.

No new tests in `tests/vibeval/` are mandated by this spec — the feature is skill/protocol-level and has no Python surface. If implementation adds any CLI support later (e.g., a `vibeval validate` check for the `tool_coverage` invariant), that would earn its own tests under `tests/`.

## Backward Compatibility

- **Existing features (non-Agent):** the `tools[]` section is optional. Features that have no tool surface omit it and run unchanged.
- **Existing Agent features with prior analyses:** when `/vibeval` re-enters such a feature, the update skill treats the absence of `tools[]` as "not yet analyzed" and triggers the new steps in additive mode. Existing datasets and designs are preserved; the tool coverage is added alongside.
- **Contract format unchanged:** existing `contract.yaml` files need no migration.
- **Judge spec format unchanged:** existing datasets and their `judge_specs` continue to evaluate as before.

## Open Questions

None blocking implementation. Two minor points worth confirming during the implementation plan:

1. Whether the analyze skill should produce a *separate* `tool_audit.md` alongside `analysis.yaml` for human-readable findings, or keep everything inside `analysis.yaml`. Spec currently says "inside `analysis.yaml`" for simplicity.
2. Whether `subagent_expected_context` should be free-form strings or a structured schema. Spec currently says free-form strings; if later practice shows this is too loose, it can be tightened in a follow-up.

## Out of Scope (restated for clarity)

- New `judge_spec` rules
- Recursive evaluation of sub-agent internals
- Language- or framework-specific tool discovery hooks
- Changes to `synthesize`, `code`, `run`, `update`, CLI, dataset format, result format
- Changes to `contract.yaml` schema
- Migration tooling for existing features (they are handled by the additive-mode path in the update skill)
