# Agent Tool Validation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce per-tool validation as a first-class testing unit in vibeval's analyze and design phases, so that custom tools, MCP tools, and sub-agents each get structured inventory entries, static design-risk findings, and a mechanically verifiable coverage matrix — without changing any downstream phase, CLI, or dataset format.

**Architecture:** Protocol-first. A new protocol file `07-agent-tools.md` becomes the source of truth for tool inventory structure, the static design-audit finding taxonomy, and the per-tool coverage matrix. Four existing protocol files get minimal cross-reference additions. Two skill files (`analyze`, `design`) add new steps that consume/produce the inventory. Two agent files (`consultant`, `evaluator`) learn about the new coverage dimension. No code, no CLI, no dataset format changes.

**Tech Stack:** Markdown (protocol, skill, agent files), YAML (example blocks inside those docs). No Python code.

**Spec:** `docs/specs/2026-04-13-agent-tool-validation-design.md`.

**Scope boundary:** Covers everything in the spec's "Protocol Changes" and "Skill and Agent Changes" sections. Does NOT cover: recursive sub-agent evaluation, new `judge_spec` rules, CLI changes, language-specific tool discovery hooks, or any Python code. The spec's "Verification Approach" item 3 (end-to-end dry run on a real Agent project) is a user-side validation and is not part of this plan's tasks — the final task only runs the existing Python test suite for regression safety.

**File Structure:**

Create:
- `plugin/protocol/references/07-agent-tools.md`

Modify:
- `plugin/protocol/references/00-philosophy.md`
- `plugin/protocol/references/01-overview.md`
- `plugin/protocol/references/03-judge-spec.md`
- `plugin/protocol/references/06-contract.md`
- `plugin/protocol/README.md`
- `plugin/skills/analyze/SKILL.md`
- `plugin/skills/design/SKILL.md`
- `plugin/agents/consultant.md`
- `plugin/agents/evaluator.md`

**Notes on this plan's cadence:**

- Since every file is markdown (not code), the standard TDD loop (failing test → impl → passing test) is not directly applicable. Each task uses the pattern: **edit → verify content via grep/read → commit**. A final task runs the existing Python test suite as a regression safety net.
- Tasks 1–6 MUST land before tasks 7–10 to honor the project's Protocol First principle. Tasks within phase A (1–6) are independent of each other and can be executed in any order within the phase; phase B (7–10) depends on phase A being complete.
- Commits are frequent (one per task) to keep the review surface small.

---

## Task 1: Create `07-agent-tools.md` protocol file

**Files:**
- Create: `plugin/protocol/references/07-agent-tools.md`

- [ ] **Step 1: Create the file with full content**

Write this exact content to `plugin/protocol/references/07-agent-tools.md`:

````markdown
# vibeval Protocol — Agent Tools

**Audience.** This file is the authoritative definition of how vibeval treats Agent tools — custom tools, MCP tools, and sub-agents — as independent testable units. It is read by:

- The `analyze` skill — to extract and audit the tool inventory
- The `design` skill — to plan per-tool test coverage
- The `vibeval-evaluator` agent — to verify that every tool has full coverage
- The `vibeval-consultant` agent — to produce tool-aware research briefs

For projects that are not Agent-style (no tool catalogue exposed to an LLM), the sections below are irrelevant and the analyze/design flow runs exactly as defined in `01-overview.md`.

## Scope: What Counts as a Tool

In vibeval's meaning, a **tool** is any entity the LLM sees as a selectable action surface during execution. Three subtypes are recognized:

| Subtype | Description | Distinguishing trait |
|---|---|---|
| `custom_tool` | A function registered with an LLM framework (OpenAI tools, Anthropic tool use, LangChain `@tool`, Vercel AI SDK tools, CrewAI tasks, etc.) | Defined in the project's source code; surface is the registered name + description + input schema |
| `mcp_tool` | A tool exposed by an MCP server that the agent connects to | Defined outside the project via the MCP protocol; surface is discovered from an MCP server manifest or connection config |
| `subagent` | A sub-agent invoked by the main agent as if it were a tool (delegation pattern) | Surface is a tool-like invocation handle; the sub-agent internally has its own system prompt and possibly its own tool catalogue |

Pure LLM calls with no tool surface (single-shot summarization, classification, extraction, etc.) are NOT tools under this definition; they are captured by the existing `ai_calls[]` section of `analysis.yaml` and tested holistically.

**Sub-agent boundary.** vibeval treats a sub-agent as a single invocation surface. It does NOT recursively test the sub-agent's own behavior under this protocol. If a feature owner wants to evaluate a sub-agent's internal behavior, they should run vibeval on the sub-agent as its own feature with its own contract.

## Tool Inventory Entry Structure

For Agent features, `tests/vibeval/{feature}/analysis/analysis.yaml` includes a `tools[]` top-level section. Each entry describes exactly one tool:

```yaml
tools:
  - id: "<stable snake_case identifier>"
    type: "custom_tool | mcp_tool | subagent"
    source_location: "<file:line, config path, or MCP server name>"

    # The surface the LLM actually sees when choosing this tool.
    # Captured verbatim from the registration site where possible;
    # free-form but MUST mirror what the LLM observes.
    surface:
      name: "<name exposed to LLM>"
      description: "<full description exposed to LLM>"
      input_schema:
        <param_name>: "<type, required/optional, brief>"
      output_shape: "<description of what the tool returns to the LLM>"

    responsibility: "<one-line statement of what this tool is for>"

    # Static audit findings. Populated by the analyze skill's
    # Audit Tool Design step. Empty list means the audit found
    # no issues at the recorded severity threshold.
    design_risks:
      - severity: "high | medium | low"
        category: "<one of the categories in Static Design Audit below>"
        finding: "<what the auditor observed>"
        suggested_fix: "<optional, one-line>"

    # Other tools with potential selection overlap.
    # Drives the disambiguation coverage dimension.
    siblings_to_watch:
      - id: "<other tool id>"
        overlap_reason: "<why these two could be confused>"

    # Only populated for type: subagent. null or absent otherwise.
    subagent_prompt_summary: "<abbreviated system prompt, 1-3 sentences>"
    subagent_expected_context: ["<context item>", "..."]
```

### Field definitions

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | Yes | Stable identifier, snake_case. Used as the key in `design.yaml:tool_coverage[]`. |
| `type` | enum | Yes | `custom_tool`, `mcp_tool`, or `subagent`. |
| `source_location` | string | Yes | For `custom_tool`: `file:line` of the registration site. For `mcp_tool`: MCP server name and tool name. For `subagent`: the sub-agent's definition path. |
| `surface.name` | string | Yes | Verbatim name exposed to the LLM. |
| `surface.description` | string | Yes | Verbatim description exposed to the LLM. |
| `surface.input_schema` | object | Yes | Parameter layout as the LLM sees it. Mirror the real schema; a free-form summary is acceptable if the real schema is complex. |
| `surface.output_shape` | string | Yes | What the tool returns. Describe the LLM-visible shape, not the internal Python/TS type. |
| `responsibility` | string | Yes | One-line statement of intent — why this tool exists. |
| `design_risks` | list | Yes (possibly empty) | Findings from the static audit. |
| `siblings_to_watch` | list | Yes (possibly empty) | Other tool ids with potential selection overlap. |
| `subagent_prompt_summary` | string or null | Only if `type: subagent` | Abbreviated system prompt. |
| `subagent_expected_context` | list of string | Only if `type: subagent` | Context items that the main agent should pass when delegating. |

## Static Design Audit

After extracting the inventory, the `analyze` skill runs a static audit LLM pass on each entry. The auditor inspects the `surface` block, the `responsibility`, and the relationship to sibling tools. It produces zero or more `design_risks` entries per tool, categorized as follows:

| Category | What triggers it |
|---|---|
| `description_ambiguity` | The name or description does not distinguish this tool from plausible alternatives. E.g., "retrieves documents" without specifying how. |
| `schema_gap` | A parameter the LLM would need to construct a correct call (based on the description) is missing from `input_schema`, or described without type/required info. |
| `overlap` | Two or more tools claim overlapping responsibility in their descriptions, producing selection ambiguity. Always recorded on both tools. |
| `output_opacity` | Output shape is unstructured or under-documented, making it hard for the LLM to parse results reliably. |
| `subagent_prompt_leak` | A sub-agent's description surfaces internal implementation details that could bias the main agent's delegation decision. Applies only to `type: subagent`. |
| `responsibility_drift` | The stated `responsibility` and the actual code behavior (as observed during analyze) diverge. |

Severity:

- `high` — the finding will likely cause failures the feature owner cares about; MUST have at least one dedicated test item in the design phase
- `medium` — the finding is worth surfacing but a dedicated item is optional
- `low` — informational only; the design phase may or may not act on it

## Per-Tool Coverage Matrix

Each tool in the inventory induces a fixed coverage matrix. Five dimensions are mandatory for every tool; two are conditional on tool characteristics.

| # | Dimension | Mandatory? | When it applies | Typical `judge_spec` pattern |
|---|---|---|---|---|
| 1 | Positive selection | Yes | All tools | `method: rule`, `rule: tool_called`, `args: {tool_name: <surface.name>}`. The containing data item describes a scenario where calling this tool is the correct action. |
| 2 | Negative selection | Yes | All tools | `method: rule`, `rule: tool_not_called`, `args: {tool_name: <surface.name>}`. The containing data item describes a scenario where this tool should NOT be called (no tool needed, or a different tool is appropriate). |
| 3 | Disambiguation | Yes | All tools | `method: llm`, `target: {step_type: "tool_call"}`, with `trap_design` describing the ambiguity. When `siblings_to_watch` is non-empty, the ambiguity should involve one of those siblings. When empty, the ambiguity can involve a plausible-but-wrong general-purpose alternative (e.g., answering from parametric memory). |
| 4 | Argument fidelity | Yes | All tools | `method: llm`, `target: {step_type: "tool_call"}`, evaluating whether the constructed arguments faithfully reflect the user's intent. When arguments are fully deterministic from the input, a `method: rule`, `rule: equals` spec on the relevant step-args field MAY be used instead. |
| 5 | Output handling | Yes | All tools | Varied `_mock_context` responses (success, empty, error, malformed) across different data items, evaluated by `method: llm`, `target: "output"` specs that check whether the downstream behavior is appropriate for each response variant. |
| 6 | Sequence / composition | Conditional | Only when this tool has a documented ordering dependency with another tool | `method: rule`, `rule: tool_sequence`, `args: {expected: [...]}`. |
| 7 | Sub-agent delegation | Conditional | Only when `type: subagent` | `method: llm`, `target: {step_type: "tool_call"}`, evaluating whether the main agent delegated at the right moment AND whether it passed all items listed in `subagent_expected_context`. |

**Gate rule.** For every tool entry, cells 1–5 MUST each map to at least one item in `design.yaml:tool_coverage[].dimensions_covered`. Cells 6 and 7 are required only when their applicability condition holds. The Evaluator agent treats missing mandatory cells as a blocking issue.

**Degradation rule for disambiguation.** When `siblings_to_watch` is empty, the disambiguation dimension is still mandatory. Satisfy it with a scenario that pits the tool against a plausible-but-wrong alternative that is not another registered tool (e.g., "answer from memory without calling the tool"), and describe the alternative in `trap_design`.

**No new judge_spec rules.** Every dimension in this matrix composes from existing `judge_spec` primitives defined in `03-judge-spec.md`. This protocol does not introduce new rules.

## Design Coverage Cross-Reference

`tests/vibeval/{feature}/design/design.yaml` gains a top-level `tool_coverage[]` section for Agent features. One entry per tool in the inventory:

```yaml
tool_coverage:
  - tool_id: "<matches analysis.yaml:tools[].id>"
    dimensions_covered:
      positive_selection: ["<item id>"]
      negative_selection: ["<item id>"]
      disambiguation: ["<item id>"]
      argument_fidelity: ["<item id>"]
      output_handling: ["<item id>", "<item id>"]
      sequence: ["<item id>"]            # only if applicable
      subagent_delegation: ["<item id>"] # only if applicable
    design_risks_addressed:
      - "<severity>/<category>: <item id> targets this risk directly"
```

**Invariant.** At the end of the design phase, for every `analysis.yaml:tools[i]`, there exists exactly one `design.yaml:tool_coverage[j]` where `j.tool_id == i.id`, and every mandatory dimension cell under `j.dimensions_covered` is non-empty. Any `high`-severity risk in `i.design_risks` must appear in `j.design_risks_addressed` with at least one referenced item.

The design skill enforces this invariant during its final checklist; the Evaluator agent re-verifies it when reviewing the design phase output.

## How to Record Tool-Related User Requirements

Tool-related behavioral requirements (e.g., "the agent must call the search tool before answering factual questions") are recorded in `contract.yaml:requirements[]` using the existing mechanism with `source: user` or `source: brainstorm`. The contract protocol is unchanged by this file. When the design phase maps contract requirements to `tool_coverage`, such requirements naturally surface as additional test points for the relevant tool's positive-selection or sequence dimensions.

## Examples

### Example 1: `custom_tool` inventory entry with a high-severity overlap risk

```yaml
tools:
  - id: "search_documents"
    type: "custom_tool"
    source_location: "app/tools/search.py:42"
    surface:
      name: "search_documents"
      description: "Search internal documents by keyword"
      input_schema:
        query: "string, required"
        top_k: "int, optional, default 5"
      output_shape: "list of {doc_id, title, snippet, score}"
    responsibility: "Keyword-based retrieval over the internal document corpus"
    design_risks:
      - severity: "high"
        category: "overlap"
        finding: "Both search_documents and list_recent_docs describe themselves as 'retrieving documents'. On a user query like 'get me the latest report', the LLM has no strong signal for which one to call."
        suggested_fix: "Rename search_documents.description to emphasize keyword-based search; rename list_recent_docs to emphasize recency-based listing."
    siblings_to_watch:
      - id: "list_recent_docs"
        overlap_reason: "Both surface a list of documents without a disambiguating verb"
```

### Example 2: `subagent` inventory entry

```yaml
tools:
  - id: "research_subagent"
    type: "subagent"
    source_location: "plugin/agents/research.md"
    surface:
      name: "dispatch_research"
      description: "Dispatch a research sub-agent to investigate a topic in depth"
      input_schema:
        topic: "string, required"
        scope: "string, optional — broad | narrow, default broad"
      output_shape: "structured research brief: findings[], sources[], open_questions[]"
    responsibility: "Multi-step topic research with web search and source verification"
    design_risks: []
    siblings_to_watch: []
    subagent_prompt_summary: "You are a research assistant. Given a topic, search the web, verify sources, and produce a structured brief."
    subagent_expected_context:
      - "topic (user's original question)"
      - "scope (broad or narrow)"
      - "any prior findings already in the main agent's context"
```

### Example 3: `tool_coverage` cross-reference matching Example 1

```yaml
tool_coverage:
  - tool_id: "search_documents"
    dimensions_covered:
      positive_selection: ["search_by_keyword_typical"]
      negative_selection: ["greeting_no_tool_needed"]
      disambiguation: ["keyword_vs_recency_ambiguous"]
      argument_fidelity: ["complex_multi_keyword_query"]
      output_handling: ["search_empty_result", "search_transport_error"]
    design_risks_addressed:
      - "high/overlap: keyword_vs_recency_ambiguous item directly exercises the search_documents vs list_recent_docs boundary"
```
````

- [ ] **Step 2: Verify the file exists and contains expected section headers**

Run a Grep for every top-level heading in the new file to confirm content was written correctly:

```bash
# Expected: each heading appears exactly once
```

Use the Grep tool with pattern `^## ` on the new file. Expected matches (in order):

1. `## Scope: What Counts as a Tool`
2. `## Tool Inventory Entry Structure`
3. `## Static Design Audit`
4. `## Per-Tool Coverage Matrix`
5. `## Design Coverage Cross-Reference`
6. `## How to Record Tool-Related User Requirements`
7. `## Examples`

Also Grep for `tool_coverage:` to confirm both YAML example blocks are present — expected: 2 matches.

- [ ] **Step 3: Commit**

```bash
git add plugin/protocol/references/07-agent-tools.md
git commit -m "$(cat <<'EOF'
protocol: add 07-agent-tools.md defining Agent tool validation

Introduces the authoritative protocol file for per-tool validation:
tool inventory entry structure, static design-audit finding taxonomy,
per-tool coverage matrix (5 mandatory + 2 conditional dimensions),
design coverage cross-reference, and end-to-end examples. No new
judge_spec rules — all dimensions compose from existing primitives.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Add Agent-tool sub-section to `00-philosophy.md`

**Files:**
- Modify: `plugin/protocol/references/00-philosophy.md`

- [ ] **Step 1: Insert a new sub-section between Principle 2 and Principle 3**

Use Edit to insert the new sub-section. The old_string is the transition from the last of Principle 2's design principles (rule #7, calibration examples) to the start of Principle 3. Open `plugin/protocol/references/00-philosophy.md` and find this block (around lines 118–126):

```
   - criteria: "In the first 3 turns of conversation, did the bot correctly understand the user's core request"
   - criteria: "When the user expressed negative emotions, did the bot avoid being dismissive or negating"
   - criteria: "Was the bot's tool call sequence reasonable"
   ```

## Principle 3: Negotiated Requirements — The Contract
```

Replace with:

```
   - criteria: "In the first 3 turns of conversation, did the bot correctly understand the user's core request"
   - criteria: "When the user expressed negative emotions, did the bot avoid being dismissive or negating"
   - criteria: "Was the bot's tool call sequence reasonable"
   ```

### Tools as Independent Test Units (Agent features)

Principle 2 reaches its fullest expression in Agent projects, where the LLM does not produce a single final output but makes a chain of tool-selection decisions. Each such decision is an independent review surface:

- **Did the agent choose the right tool for this scenario?** (selection)
- **Did it construct arguments faithfully from the user's intent?** (argument fidelity)
- **Did it handle the returned data appropriately, including empty and error cases?** (output handling)
- **When two tools overlap in description, did it pick the better one?** (disambiguation)
- **For tools implemented as sub-agents, did it delegate at the right moment and pass sufficient context?** (delegation)

A holistic "the final answer is good" evaluation collapses all of these into one signal. Per-tool evaluation preserves them as independent dimensions, and — crucially — makes "every tool has test coverage" a mechanically checkable property of the design.

See `07-agent-tools.md` for the tool inventory structure, the coverage matrix, and how each dimension maps onto existing `judge_spec` primitives.

## Principle 3: Negotiated Requirements — The Contract
```

- [ ] **Step 2: Verify**

Grep for the new section header — expected: exactly 1 match.

```
pattern: "### Tools as Independent Test Units"
file: plugin/protocol/references/00-philosophy.md
```

Also grep for `07-agent-tools.md` in the same file — expected: 1 match.

- [ ] **Step 3: Commit**

```bash
git add plugin/protocol/references/00-philosophy.md
git commit -m "$(cat <<'EOF'
protocol: extend Principle 2 with per-tool validation sub-section

Adds an Agent-features sub-section under Principle 2 making per-tool
evaluation an explicit application of global process visibility.
Cross-references 07-agent-tools.md for the operational protocol.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Add `Agent Features (tools[])` note to `01-overview.md`

**Files:**
- Modify: `plugin/protocol/references/01-overview.md`

- [ ] **Step 1: Append the new section at the end of the file**

Open `plugin/protocol/references/01-overview.md` and find the end of the file (the `Data Flow` code block that ends with `→ vibeval compare {feature} run_a run_b → comparison`). Use Edit to append after the closing code fence of Data Flow. The old_string:

```
           → vibeval compare {feature} run_a run_b → comparison
```

(Include the surrounding code fence context to make old_string unique if needed. Read the file first to confirm the exact lines, and use whatever surrounding context is needed to make the Edit unambiguous.)

Replace with:

```
           → vibeval compare {feature} run_a run_b → comparison
```
```

## Agent Features

For features where the AI under test is an Agent with a tool catalogue (custom tools, MCP tools, or sub-agents), `analysis.yaml` includes a top-level `tools[]` section that serves as the shared contract between the analyze and design phases. The design phase produces a corresponding `tool_coverage[]` section in `design.yaml`. See `07-agent-tools.md` for the full protocol — inventory entry structure, static design-audit finding taxonomy, and the per-tool coverage matrix.

For non-Agent features, `tools[]` is omitted and the analyze/design flow is unchanged.
```

Note: If the old_string as shown is not unique in the file, widen it to include the preceding code fence opener (` ```` `) or the `## Data Flow` heading — whatever it takes to make it unambiguous. Read the file first with the Read tool and copy the exact surrounding text.

- [ ] **Step 2: Verify**

Grep for `## Agent Features` in `plugin/protocol/references/01-overview.md` — expected: 1 match. Grep for `07-agent-tools.md` — expected: 1 match.

- [ ] **Step 3: Commit**

```bash
git add plugin/protocol/references/01-overview.md
git commit -m "$(cat <<'EOF'
protocol: mention tools[] as shared artifact between analyze and design

Adds an Agent Features note to 01-overview.md describing tools[] in
analysis.yaml and tool_coverage[] in design.yaml as the shared
contract for Agent-style features. Full protocol in 07-agent-tools.md.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Add cross-reference to `03-judge-spec.md`

**Files:**
- Modify: `plugin/protocol/references/03-judge-spec.md`

- [ ] **Step 1: Insert a `See also` note after the Trace Rules table**

Open `plugin/protocol/references/03-judge-spec.md` and find the Trace Rules table. The last row is:

```
| `max_steps` | Total steps count does not exceed limit | `max` |
```

After that row and before the next section heading `### Conversation Rules`, use Edit to insert this block. The old_string:

```
| `max_steps` | Total steps count does not exceed limit | `max` |

### Conversation Rules
```

Replace with:

```
| `max_steps` | Total steps count does not exceed limit | `max` |

**See also.** For Agent features, these trace rules combine with LLM specs using `target: {step_type: "tool_call"}` to form a per-tool coverage matrix. The combination is specified in `07-agent-tools.md`; this file does not introduce new trace rules for Agent features.

### Conversation Rules
```

- [ ] **Step 2: Verify**

Grep for `07-agent-tools.md` in `plugin/protocol/references/03-judge-spec.md` — expected: at least 1 match. Grep for `per-tool coverage matrix` — expected: 1 match.

- [ ] **Step 3: Commit**

```bash
git add plugin/protocol/references/03-judge-spec.md
git commit -m "$(cat <<'EOF'
protocol: cross-reference 07-agent-tools.md from Trace Rules

Adds a See also note under the Trace Rules table pointing to the
per-tool coverage matrix in 07-agent-tools.md. No new rules; existing
primitives are sufficient for per-tool validation.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Add tool-requirements note to `06-contract.md`

**Files:**
- Modify: `plugin/protocol/references/06-contract.md`

- [ ] **Step 1: Insert the note at the end of the `requirements` field definition**

Open `plugin/protocol/references/06-contract.md` and find the `### requirements` subsection. After its source table (ending with the `suggested` row) and before `### known_gaps`, find this block (around lines 110–116):

```
Requirements with `source: user` and `source: brainstorm` are the most valuable — they represent information that pure code analysis would miss entirely. The contract skill actively elicits these through Socratic dialogue, using a background brief from the Consultant Agent as seed questions.

### known_gaps
```

Replace with:

```
Requirements with `source: user` and `source: brainstorm` are the most valuable — they represent information that pure code analysis would miss entirely. The contract skill actively elicits these through Socratic dialogue, using a background brief from the Consultant Agent as seed questions.

**Agent features.** Tool-related behavioral requirements (e.g., "the agent must call the search tool before answering factual questions") are recorded here as ordinary requirements, typically with `source: user` or `source: brainstorm`. The contract format is unchanged by Agent-tool validation. When the design phase plans per-tool coverage, such requirements surface as additional test points for the relevant tool's positive-selection or sequence dimensions. See `07-agent-tools.md` for how contract requirements map to per-tool coverage.

### known_gaps
```

- [ ] **Step 2: Verify**

Grep for `**Agent features.**` in `plugin/protocol/references/06-contract.md` — expected: 1 match. Grep for `07-agent-tools.md` — expected: 1 match.

- [ ] **Step 3: Commit**

```bash
git add plugin/protocol/references/06-contract.md
git commit -m "$(cat <<'EOF'
protocol: note that tool requirements use existing contract mechanism

Adds a short Agent features note to the requirements field
definition clarifying that tool-related behavioral requirements
are recorded via source: user/brainstorm with no schema change.
Points to 07-agent-tools.md for the coverage mapping.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Update `plugin/protocol/README.md` Quick Reference

**Files:**
- Modify: `plugin/protocol/README.md`

- [ ] **Step 1: Add `07-agent-tools.md` to the Reference Files list**

Open `plugin/protocol/README.md` and find the `## Reference Files (Source of Truth)` section. The current last entry is:

```
- **`${CLAUDE_PLUGIN_ROOT}/protocol/references/06-contract.md`** — Contract format: requirements, known gaps, quality criteria, feedback log
```

Use Edit to append a new entry after it. old_string:

```
- **`${CLAUDE_PLUGIN_ROOT}/protocol/references/06-contract.md`** — Contract format: requirements, known gaps, quality criteria, feedback log
```

new_string:

```
- **`${CLAUDE_PLUGIN_ROOT}/protocol/references/06-contract.md`** — Contract format: requirements, known gaps, quality criteria, feedback log
- **`${CLAUDE_PLUGIN_ROOT}/protocol/references/07-agent-tools.md`** — Agent tools: inventory entry structure, static design-audit findings, per-tool coverage matrix (applies to features with a tool catalogue)
```

- [ ] **Step 2: Verify**

Grep for `07-agent-tools.md` in `plugin/protocol/README.md` — expected: 1 match.

- [ ] **Step 3: Commit**

```bash
git add plugin/protocol/README.md
git commit -m "$(cat <<'EOF'
protocol: add 07-agent-tools.md to Quick Reference index

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Update `analyze/SKILL.md` with Tool Inventory and Audit steps

**Files:**
- Modify: `plugin/skills/analyze/SKILL.md`

- [ ] **Step 1: Add `07-agent-tools.md` to the Before starting read-list**

Open `plugin/skills/analyze/SKILL.md` and find the "Before starting, read:" block (around lines 12–15). The old_string:

```
**Before starting, read:**
- `tests/vibeval/{feature}/contract.yaml` — **The negotiated contract.** All analysis must address the requirements and known gaps defined here.
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/00-philosophy.md` — Evaluation philosophy (information asymmetry + global perspective + contract)
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/01-overview.md` — Directory structure, unified turn model
```

Replace with:

```
**Before starting, read:**
- `tests/vibeval/{feature}/contract.yaml` — **The negotiated contract.** All analysis must address the requirements and known gaps defined here.
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/00-philosophy.md` — Evaluation philosophy (information asymmetry + global perspective + contract)
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/01-overview.md` — Directory structure, unified turn model
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/07-agent-tools.md` — **For Agent features only.** Tool inventory entry structure, static design-audit finding taxonomy. Consult before executing the Extract Tool Inventory and Audit Tool Design steps below.
```

- [ ] **Step 2: Insert new Steps 2 and 3 (Extract Tool Inventory, Audit Tool Design) and renumber existing steps**

Find Step 1 heading and the following Step 2 heading (around lines 27–41). The old_string:

```
### 1. Identify AI Call Points

Scan the codebase for:
- **LLM API calls**: OpenAI, Anthropic, Google, Azure, or other LLM SDK invocations
- **AI framework calls**: LangChain, LlamaIndex, CrewAI, Vercel AI SDK, or similar
- **Tool/function calling**: Functions registered as tools for LLM agents
- **External API calls**: REST/GraphQL calls that provide data to or consume data from AI pipelines

For each call point, record: file path, function name, purpose, input/output description, mock target path.

### 2. Determine Test Mode
```

Replace with:

```
### 1. Identify AI Call Points

Scan the codebase for:
- **LLM API calls**: OpenAI, Anthropic, Google, Azure, or other LLM SDK invocations
- **AI framework calls**: LangChain, LlamaIndex, CrewAI, Vercel AI SDK, or similar
- **Tool/function calling**: Functions registered as tools for LLM agents
- **External API calls**: REST/GraphQL calls that provide data to or consume data from AI pipelines

For each call point, record: file path, function name, purpose, input/output description, mock target path.

### 2. Extract Tool Inventory (Agent features only)

If the codebase exposes tools to the LLM (custom tool registration, MCP server connections, or sub-agents invoked via a tool-like interface), populate a `tools[]` section in `analysis.yaml`. For non-Agent features, skip this step and the next.

For each tool, identify:

- **`type`**: `custom_tool` (framework-registered function), `mcp_tool` (MCP-server-exposed), or `subagent` (sub-agent used as a tool).
- **`source_location`**: `file:line` for custom tools; MCP server + tool name for MCP tools; sub-agent definition path for sub-agents.
- **`surface`**: the name, description, `input_schema`, and `output_shape` as the LLM actually sees them. Read the registration site verbatim. For MCP tools, read the MCP manifest or connection config.
- **`responsibility`**: a one-line statement of intent.

For `type: subagent`, also capture `subagent_prompt_summary` and `subagent_expected_context`.

The full field definitions and YAML layout are in `07-agent-tools.md` — do not duplicate them here; follow that protocol.

### 3. Audit Tool Design (Agent features only)

For each entry produced in Step 2, run a static design audit and populate `design_risks[]` and `siblings_to_watch[]`. The finding taxonomy (`description_ambiguity`, `schema_gap`, `overlap`, `output_opacity`, `subagent_prompt_leak`, `responsibility_drift`) and severity semantics are defined in `07-agent-tools.md`.

Specific checks to perform:

1. **Description clarity**: Does the description distinguish this tool from plausible alternatives? Would a user query matching multiple plausible tools land correctly?
2. **Schema completeness**: Given the description, does the input schema expose every parameter the LLM would need to construct a correct call? Are types and required/optional flags present?
3. **Cross-tool overlap**: Compare every pair of tool descriptions. Record mutual `overlap` findings and populate `siblings_to_watch` on both entries.
4. **Output clarity**: Is the output shape specific enough for the LLM to reliably consume it (especially in downstream chaining)?
5. **Sub-agent prompt hygiene** (subagents only): Does the sub-agent's exposed description leak internal implementation details that could bias delegation?
6. **Responsibility drift**: Does the stated `responsibility` match the actual code behavior?

Record each finding with `severity` (high/medium/low), `category`, `finding`, and an optional `suggested_fix`. `high`-severity findings will be required test targets in the design phase.

### 4. Determine Test Mode
```

- [ ] **Step 3: Renumber the remaining steps**

Find the next three step headings and renumber them. Use three separate Edit calls (or a single Edit with `replace_all` if the old_strings are unique — they are, since step numbers appear only in headings):

Edit 1: `### 3. Map Data Flow` → `### 5. Map Data Flow`
Edit 2: `### 4. Identify Mock Points` → `### 6. Identify Mock Points`
Edit 3: `### 5. Filter Non-AI Pipelines` → `### 7. Filter Non-AI Pipelines`
Edit 4: `### 6. Evaluate Testability` → `### 8. Evaluate Testability`

Note: "### 2. Determine Test Mode" was replaced by the "### 4. Determine Test Mode" rename in Step 2 above (it was included in the new_string). Confirm with a Grep for `^### [0-9]\. ` — expected: exactly 8 matches, one per step.

- [ ] **Step 4: Extend the Output Format YAML example with a `tools:` section placeholder**

Find the end of the `suggestions:` block in the Output Format example (around lines 128–134). The old_string:

```
suggestions:
  - severity: "high|medium|low"
    category: "coupling|visibility|parsing|chat-interface|observability"
    location: "<file:line or module>"
    issue: "<what's wrong>"
    suggestion: "<what to do>"
```

Replace with:

```
suggestions:
  - severity: "high|medium|low"
    category: "coupling|visibility|parsing|chat-interface|observability"
    location: "<file:line or module>"
    issue: "<what's wrong>"
    suggestion: "<what to do>"

# Agent features only. Full field definitions in 07-agent-tools.md.
# Omit this section entirely for non-Agent features.
tools:
  - id: "<stable snake_case id>"
    type: "custom_tool | mcp_tool | subagent"
    source_location: "<file:line or MCP server/tool or subagent definition>"
    surface:
      name: "<LLM-facing name>"
      description: "<LLM-facing description>"
      input_schema: { <param>: "<type, required/optional, brief>" }
      output_shape: "<LLM-visible shape>"
    responsibility: "<one-line intent>"
    design_risks: []          # populated by Audit Tool Design
    siblings_to_watch: []     # populated by Audit Tool Design
    # subagent_prompt_summary / subagent_expected_context: only for type: subagent
```

- [ ] **Step 5: Add a Checkpoint bullet**

Find the Checkpoint block at the end of the file. The old_string:

```
Present to the user:
1. Summary: pipelines found, type (single-turn/multi-turn), AI calls, mock points
2. If any pipelines were excluded as non-AI deterministic logic, list them and briefly explain why (so the user knows they weren't overlooked)
3. Testability improvement suggestions ranked by severity
4. Ask: **"Analysis complete. Shall I proceed to design the test plan?"**
```

Replace with:

```
Present to the user:
1. Summary: pipelines found, type (single-turn/multi-turn), AI calls, mock points
2. If any pipelines were excluded as non-AI deterministic logic, list them and briefly explain why (so the user knows they weren't overlooked)
3. Testability improvement suggestions ranked by severity
4. **Agent features only.** Tool inventory: list of identified tools with their types, plus any high-severity design risks flagged during the audit.
5. Ask: **"Analysis complete. Shall I proceed to design the test plan?"**
```

- [ ] **Step 6: Verify**

Grep `^### [0-9]\. ` — expected: 8 matches in order 1..8. Grep for `Extract Tool Inventory` — expected: 1 match. Grep for `Audit Tool Design` — expected: 1 match. Grep for `07-agent-tools.md` — expected: at least 3 matches (Before-starting block, Step 2, Step 3, output format comment).

- [ ] **Step 7: Commit**

```bash
git add plugin/skills/analyze/SKILL.md
git commit -m "$(cat <<'EOF'
skills: analyze phase extracts and audits Agent tool inventory

Adds two new steps (Extract Tool Inventory, Audit Tool Design) after
Step 1, renumbering subsequent steps. Extends the analysis.yaml output
format with an Agent-features-only tools[] section, and adds a
checkpoint bullet for the tool inventory summary. Full protocol lives
in 07-agent-tools.md; this skill references but does not duplicate it.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Update `design/SKILL.md` with Tool Coverage Planning step

**Files:**
- Modify: `plugin/skills/design/SKILL.md`

- [ ] **Step 1: Add `07-agent-tools.md` to the Before starting read-list**

Open `plugin/skills/design/SKILL.md` and find the "Before starting, read:" block (around lines 13–17). The old_string:

```
**Before starting, read:**
- `tests/vibeval/{feature}/contract.yaml` — **The negotiated contract.** Every requirement must have corresponding test coverage. Quality criteria define the bar for this design.
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/00-philosophy.md` — **Must read first.** The three core principles (information asymmetry + global process visibility + contract) govern all design decisions.
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/02-dataset.md` — Dataset format, data items, persona format.
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/03-judge-spec.md` — Complete rule taxonomy, LLM scoring modes, target options, all field definitions.
```

Replace with:

```
**Before starting, read:**
- `tests/vibeval/{feature}/contract.yaml` — **The negotiated contract.** Every requirement must have corresponding test coverage. Quality criteria define the bar for this design.
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/00-philosophy.md` — **Must read first.** The three core principles (information asymmetry + global process visibility + contract) govern all design decisions.
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/02-dataset.md` — Dataset format, data items, persona format.
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/03-judge-spec.md` — Complete rule taxonomy, LLM scoring modes, target options, all field definitions.
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/07-agent-tools.md` — **For Agent features only.** Per-tool coverage matrix (5 mandatory + 2 conditional dimensions) and the `tool_coverage[]` invariant. Consult before executing the Tool Coverage Planning step below.
```

- [ ] **Step 2: Insert a new Step 1 (Tool Coverage Planning) and renumber subsequent steps**

Find the transition from `### 1. Design Datasets` and replace it. The old_string:

```
## Steps

### 1. Design Datasets

For each pipeline in the analysis, design one or more datasets.
```

Replace with:

```
## Steps

### 1. Tool Coverage Planning (Agent features only)

If `analysis.yaml` contains a `tools[]` section, enumerate the per-tool coverage matrix BEFORE designing datasets. For each tool in the inventory:

1. Instantiate the coverage matrix from `07-agent-tools.md` (5 mandatory dimensions + 2 conditional dimensions).
2. Plan one or more test items per mandatory dimension, and for applicable conditional dimensions. Items can be shared across dimensions when one scenario naturally exercises multiple dimensions.
3. For every `high`-severity entry in the tool's `design_risks`, plan at least one item that directly targets the risk and record it in `design_risks_addressed`.
4. Decide which dataset(s) the planned items will live in — the items themselves are written during Step 2 (Design Datasets); this step produces the plan and the cross-reference block `tool_coverage[]`.

The `tool_coverage[]` section is a top-level section in `design.yaml` whose structure and invariant are defined in `07-agent-tools.md`. The design is not complete until every tool in `analysis.yaml:tools[]` has a matching `tool_coverage[]` entry with every mandatory dimension cell non-empty.

Skip this step entirely when `analysis.yaml` has no `tools[]` section.

### 2. Design Datasets

For each pipeline in the analysis, design one or more datasets.
```

- [ ] **Step 3: Renumber subsequent steps**

Find and rename the remaining step headings with separate Edit calls:

Edit 1: `### 2. Design Judge Specs` → `### 3. Design Judge Specs`
Edit 2: `### 3. Design Test Structure` → `### 4. Design Test Structure`
Edit 3: `### 4. Design Mock Environment Context (single-turn only)` → `### 5. Design Mock Environment Context (single-turn only)`

After these three edits, verify with a Grep `^### [0-9]\. ` — expected: 5 matches in order 1..5.

- [ ] **Step 4: Extend Output Format YAML example with `tool_coverage`**

Find the `test_code:` block at the end of the YAML example (around lines 168–182). The old_string (include enough context to be unique — use the block just before `test_code:`):

```
test_code:
  framework: "<pytest|vitest|jest|go test>"
```

Replace with:

```
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
```

- [ ] **Step 5: Add a Checkpoint bullet**

Find the Checkpoint block. The old_string:

```
Present to the user:
1. Summary: datasets (single-turn/multi-turn), items count, judge specs count
2. Ask to review judge specs — anchors, calibrations, test_intent, and trap_design directly affect evaluation quality
3. Suggest `vibeval serve --open` to visually review and edit datasets, items, and judge specs in the interactive dashboard
4. Ask: **"Design complete. Shall I proceed to generate test code and datasets?"**
```

Replace with:

```
Present to the user:
1. Summary: datasets (single-turn/multi-turn), items count, judge specs count
2. Ask to review judge specs — anchors, calibrations, test_intent, and trap_design directly affect evaluation quality
3. **Agent features only.** Tool coverage status: for each tool in `analysis.yaml:tools[]`, list which dimensions are covered and by how many items. Flag any tool whose mandatory dimensions are incomplete.
4. Suggest `vibeval serve --open` to visually review and edit datasets, items, and judge specs in the interactive dashboard
5. Ask: **"Design complete. Shall I proceed to generate test code and datasets?"**
```

- [ ] **Step 6: Verify**

Grep `^### [0-9]\. ` — expected: 5 matches (1..5). Grep for `Tool Coverage Planning` — expected: 1 match. Grep for `tool_coverage:` in the file — expected: at least 1 match. Grep for `07-agent-tools.md` — expected: at least 3 matches.

- [ ] **Step 7: Commit**

```bash
git add plugin/skills/design/SKILL.md
git commit -m "$(cat <<'EOF'
skills: design phase plans per-tool coverage for Agent features

Adds a new Step 1 (Tool Coverage Planning) that consumes
analysis.yaml:tools[] and produces the tool_coverage[] cross-reference
section in design.yaml. Renumbers existing steps 1..4 to 2..5. Extends
the design.yaml output format example and the checkpoint with a tool
coverage status bullet. Full protocol in 07-agent-tools.md.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Update `consultant.md` with Agent Tool Failure Modes section

**Files:**
- Modify: `plugin/agents/consultant.md`

- [ ] **Step 1: Add the Agent Tool Failure Modes instruction to the design variant**

Open `plugin/agents/consultant.md` and find the design variant section describing section renames (around lines 74–78). The old_string:

```
- **Design variant** (dispatched from the `design` skill, Consultant Design Review). The caller already has a draft `design.yaml` and wants a coverage-focused brief. Use the same template structure but rename the sections as follows:
  - `## Identified AI Call Points` → `## Coverage Gaps` — list dataset/judge-spec gaps relative to the contract requirements and the feature's failure modes.
  - `## Hidden Contract (from prompts)` → `## Missing Test Dimensions` — adversarial inputs, mock-environment failures, multi-turn state issues, or other dimensions the current design doesn't exercise.
  - Keep the `## Seed Questions`, `## Same-Domain Failure Patterns (reference)`, and `## Notes for the Main Agent` sections with the same intent.
  - Change the top-line comment to `_Generated by vibeval-consultant for the design skill's coverage review. This file is temporary and will be deleted after the design is updated._`
```

Replace with:

```
- **Design variant** (dispatched from the `design` skill, Consultant Design Review). The caller already has a draft `design.yaml` and wants a coverage-focused brief. Use the same template structure but rename the sections as follows:
  - `## Identified AI Call Points` → `## Coverage Gaps` — list dataset/judge-spec gaps relative to the contract requirements and the feature's failure modes.
  - `## Hidden Contract (from prompts)` → `## Missing Test Dimensions` — adversarial inputs, mock-environment failures, multi-turn state issues, or other dimensions the current design doesn't exercise.
  - Keep the `## Seed Questions`, `## Same-Domain Failure Patterns (reference)`, and `## Notes for the Main Agent` sections with the same intent.
  - Change the top-line comment to `_Generated by vibeval-consultant for the design skill's coverage review. This file is temporary and will be deleted after the design is updated._`
  - **If `analysis.yaml` contains a non-empty `tools[]` section**, add a new section immediately after `## Missing Test Dimensions`:

        ## Agent Tool Failure Modes

        For each tool in `analysis.yaml:tools[]`, list concrete concerns the current draft `design.yaml:tool_coverage[]` does not adequately address. Reference specific `tool id`s and any `design_risks` entries (especially `high` severity). Focus on:

        - Selection ambiguity that is not yet exercised by disambiguation items
        - Argument-construction failure modes that are not yet exercised by argument-fidelity items
        - Output shapes (empty, error, malformed) whose handling is not yet exercised
        - Sub-agent delegation paths where context may not be passed correctly

        Append any resulting seed questions to `## Seed Questions` (High Priority for `high`-severity risks, Medium Priority otherwise). The main agent will use them to drive dialogue with the user. See `${CLAUDE_PLUGIN_ROOT}/protocol/references/07-agent-tools.md` for the inventory structure and coverage matrix.
```

- [ ] **Step 2: Add a line to the Integration Failures expertise block for cross-reference**

Find the Integration Failures block (around lines 47–51). The old_string:

```
### Integration Failures
- **Tool call errors**: calling the wrong tool, passing wrong arguments, misinterpreting results
- **Data pipeline issues**: upstream data missing fields, unexpected types, null values
- **Rate limiting / timeout**: external API calls failing under load
- **Partial failures**: one step in a multi-step pipeline fails, how does the system degrade?
```

Replace with:

```
### Integration Failures
- **Tool call errors**: calling the wrong tool, passing wrong arguments, misinterpreting results
- **Tool description ambiguity**: two tools describe overlapping responsibility, causing the LLM to guess; captured as `overlap` / `description_ambiguity` risks in the Agent tool inventory (see `07-agent-tools.md`)
- **Sub-agent delegation gaps**: main agent delegates without passing the context the sub-agent needs, or fails to delegate when appropriate
- **Data pipeline issues**: upstream data missing fields, unexpected types, null values
- **Rate limiting / timeout**: external API calls failing under load
- **Partial failures**: one step in a multi-step pipeline fails, how does the system degrade?
```

- [ ] **Step 3: Verify**

Grep for `Agent Tool Failure Modes` — expected: 1 match. Grep for `07-agent-tools.md` — expected: at least 2 matches. Grep for `Sub-agent delegation gaps` — expected: 1 match.

- [ ] **Step 4: Commit**

```bash
git add plugin/agents/consultant.md
git commit -m "$(cat <<'EOF'
agents: consultant design brief surfaces Agent tool failure modes

Extends the design variant's brief format with an Agent Tool Failure
Modes section (emitted only when analysis.yaml has a tools[] section)
and adds two tool-design failure patterns to the Integration Failures
expertise list. Main-agent dialogue now gets tool-aware seed questions.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Update `evaluator.md` with tool coverage verification

**Files:**
- Modify: `plugin/agents/evaluator.md`

- [ ] **Step 1: Add a `Tool coverage` row to the Design Phase Review table**

Open `plugin/agents/evaluator.md` and find the Design Phase Review dimensions table (around lines 42–51). The old_string:

```
### Design Phase Review

Review `tests/vibeval/{feature}/design/design.yaml`:

| Dimension | What to check |
|---|---|
| **Coverage** | Tests cover happy path, edge cases, and adversarial scenarios? All contract requirements have corresponding test items? |
| **Information asymmetry** | Judge specs have genuine insider knowledge in anchors and calibrations? Or are they generic ("output is good/bad")? |
| **Trap quality** | Traps are realistic failure modes the AI might actually exhibit? Not contrived scenarios that would never occur? |
| **Specificity** | Anchors describe what good/bad means for THIS specific test scenario? Calibrations use concrete examples from THIS data? |
| **Requirement depth** | Every `requirement` in the contract has at least one dataset item + judge spec that tests it? Trace each requirement. |
```

Replace with:

```
### Design Phase Review

Review `tests/vibeval/{feature}/design/design.yaml`:

| Dimension | What to check |
|---|---|
| **Coverage** | Tests cover happy path, edge cases, and adversarial scenarios? All contract requirements have corresponding test items? |
| **Information asymmetry** | Judge specs have genuine insider knowledge in anchors and calibrations? Or are they generic ("output is good/bad")? |
| **Trap quality** | Traps are realistic failure modes the AI might actually exhibit? Not contrived scenarios that would never occur? |
| **Specificity** | Anchors describe what good/bad means for THIS specific test scenario? Calibrations use concrete examples from THIS data? |
| **Requirement depth** | Every `requirement` in the contract has at least one dataset item + judge spec that tests it? Trace each requirement. |
| **Tool coverage** | (Agent features only — applies when `analysis.yaml` has a non-empty `tools[]` section.) For every tool in `tools[]`, does `design.yaml:tool_coverage[]` contain a matching entry? Are all mandatory dimension cells (positive_selection, negative_selection, disambiguation, argument_fidelity, output_handling) non-empty? Are conditional cells (sequence, subagent_delegation) present when applicable? Are all `high`-severity `design_risks` addressed by at least one referenced item? See `${CLAUDE_PLUGIN_ROOT}/protocol/references/07-agent-tools.md` for the invariant. |
```

- [ ] **Step 2: Add a behavior rule for mechanical tool-coverage check**

Find the Behavior Rules numbered list. The old_string is the last rule (currently rule 6):

```
6. **Prioritize by contract** — `known_gaps` and `user_emphasis` in quality criteria indicate where the user cares most. Weight your review toward these areas.
```

Replace with:

```
6. **Prioritize by contract** — `known_gaps` and `user_emphasis` in quality criteria indicate where the user cares most. Weight your review toward these areas.
7. **Mechanical checks come first for Agent features** — when `analysis.yaml` has a `tools[]` section, verify the `tool_coverage[]` invariant (every inventory tool has a matching entry; every mandatory dimension cell is non-empty) before scoring the other dimensions. A missing mandatory cell is always a blocking `tool_coverage: 0` finding with a specific suggestion to add the missing item.
```

- [ ] **Step 3: Verify**

Grep for `**Tool coverage**` in `plugin/agents/evaluator.md` — expected: 1 match. Grep for `07-agent-tools.md` — expected: 1 match. Grep for `Mechanical checks come first` — expected: 1 match.

- [ ] **Step 4: Commit**

```bash
git add plugin/agents/evaluator.md
git commit -m "$(cat <<'EOF'
agents: evaluator verifies tool_coverage invariant for Agent features

Adds a Tool coverage dimension to the Design Phase Review table and a
mechanical-check behavior rule: when analysis.yaml has tools[], the
evaluator verifies every tool has a matching tool_coverage[] entry
with all mandatory dimension cells non-empty before scoring other
dimensions. Missing cells are blocking.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Final verification and regression check

**Files:**
- (no modifications — verification only)

- [ ] **Step 1: Confirm every spec requirement has a corresponding committed task**

Open `docs/specs/2026-04-13-agent-tool-validation-design.md` side-by-side with this plan. Walk through each section and confirm:

- Spec section **P1** → Task 1 (create 07-agent-tools.md)
- Spec section **P2** → Task 2 (00-philosophy.md)
- Spec section **P3** → Task 4 (03-judge-spec.md)
- Spec section **P4** → Task 3 (01-overview.md)
- Spec section **P5** → Task 5 (06-contract.md)
- Spec section **P6** → Task 6 (protocol/README.md)
- Spec section **S1** → Task 7 (analyze SKILL.md)
- Spec section **S2** → Task 8 (design SKILL.md)
- Spec section **S3** → Task 9 (consultant.md)
- Spec section **S4** → Task 10 (evaluator.md)
- Spec section **S5** → explicit no-op (no CLI/Python changes)

If any spec section has no corresponding committed change, open a follow-up task before proceeding.

- [ ] **Step 2: Global grep sanity checks**

Run these four Grep checks across the repository and confirm expected counts:

1. Pattern `07-agent-tools.md` across `plugin/` — expected: at least 9 matches (the new file itself is excluded from this since grep will hit cross-references). Files expected to contain a reference: `00-philosophy.md`, `01-overview.md`, `03-judge-spec.md`, `06-contract.md`, `protocol/README.md`, `analyze/SKILL.md` (multiple), `design/SKILL.md` (multiple), `consultant.md` (multiple), `evaluator.md`.

2. Pattern `tool_coverage` across `plugin/` — expected: at least 6 matches, in `07-agent-tools.md`, `design/SKILL.md`, `evaluator.md`, and possibly others.

3. Pattern `tools[]` or `tools:` across `plugin/` — expected: at least 6 matches, in `07-agent-tools.md`, `analyze/SKILL.md`, `design/SKILL.md`, `evaluator.md`, `consultant.md`.

4. Pattern `### [0-9]\. ` in `plugin/skills/analyze/SKILL.md` — expected: 8 matches (renumbered 1..8).

5. Pattern `### [0-9]\. ` in `plugin/skills/design/SKILL.md` — expected: 5 matches (renumbered 1..5).

- [ ] **Step 3: Confirm no duplicate protocol content lives in skill files**

Grep `plugin/skills/` and `plugin/agents/` for protocol-level field definitions that should ONLY live in `07-agent-tools.md`:

- Pattern `description_ambiguity|schema_gap|responsibility_drift|output_opacity|subagent_prompt_leak` across `plugin/skills/` and `plugin/agents/` — expected: 0 or very few matches (only as references like "the finding taxonomy in 07-agent-tools.md"). The full enumeration of categories should NOT be duplicated outside `07-agent-tools.md`.

If a skill or agent file fully duplicates the finding taxonomy, that file should be simplified to reference `07-agent-tools.md` instead. Fix inline and amend the relevant commit (or create a follow-up commit).

- [ ] **Step 4: Run the existing Python test suite for regression safety**

```bash
cd /Users/yaoyupeng/workspace/vibeval
python -m pytest tests/ -v
```

Expected: all tests pass. This plan changes only markdown files under `plugin/`, so Python tests should be entirely unaffected. If any test fails, investigate the root cause before declaring the plan complete — do not amend or skip failing tests.

- [ ] **Step 5: Confirm final git state**

```bash
git status
git log --oneline -15
```

Expected:
- `git status` reports a clean tree (no uncommitted changes).
- `git log --oneline -15` shows the ten task commits from tasks 1–10 in order, plus any pre-existing commits.

- [ ] **Step 6: Final commit (if anything was added in Steps 1–3 as a fix)**

If any fix was needed during verification, commit it separately with a message starting `fix:`. If everything was clean, there is nothing to commit in this step — proceed to declaring the plan complete.

---

## Self-Review Summary

Ran against the spec (`docs/specs/2026-04-13-agent-tool-validation-design.md`):

**Spec coverage.** Every protocol change (P1–P6) and skill/agent change (S1–S4) in the spec maps to a numbered task. S5 (no CLI/Python changes) is honored by this plan — Task 11 Step 4 only runs existing tests for regression, and no Python or CLI files appear in any task's Files block.

**Placeholder scan.** No TBDs, TODOs, or "fill in details" phrases. Every edit step contains the literal old_string/new_string content. Every commit message is provided in full. Every verification step has an expected count or pattern.

**Type consistency.** Field names are consistent across all tasks:

- `tools[]`, `id`, `type`, `source_location`, `surface{name,description,input_schema,output_shape}`, `responsibility`, `design_risks[]`, `siblings_to_watch[]`, `subagent_prompt_summary`, `subagent_expected_context` — defined in Task 1, referenced identically in Tasks 7, 9, 10.
- `tool_coverage[]`, `tool_id`, `dimensions_covered{positive_selection, negative_selection, disambiguation, argument_fidelity, output_handling, sequence, subagent_delegation}`, `design_risks_addressed` — defined in Task 1, referenced identically in Tasks 8, 10.
- Finding categories (`description_ambiguity`, `schema_gap`, `overlap`, `output_opacity`, `subagent_prompt_leak`, `responsibility_drift`) — defined in Task 1, referenced as a list in Task 7 (with guidance to use 07-agent-tools.md as the source), never re-enumerated in skill/agent files.

**Ambiguity.** Task 3's `old_string` for appending to `01-overview.md` explicitly instructs the executor to widen the old_string if the minimum shown is not unique, and to Read the file first. This is the one place where the exact minimal old_string could be ambiguous in a short file.

**Scope.** Ten bite-sized tasks + one verification task. Each task is self-contained, produces one commit, and no task depends on a task later in the list. Tasks 1–6 (Phase A: protocol) must complete before Tasks 7–10 (Phase B: skills + agents), but within each phase tasks are independent.
