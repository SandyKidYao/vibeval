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
| `surface.output_shape` | string | Yes | What the tool returns. Describe the LLM-visible shape, not the language-level type signature. |
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

**Gate rule.** For every tool entry, dimensions 1–5 MUST each map to at least one item in `design.yaml:tool_coverage[].dimensions_covered`. Dimensions 6 and 7 are required only when their applicability condition holds. The Evaluator agent treats missing mandatory dimensions as a blocking issue.

**Canonical YAML keys.** The `dimensions_covered` section of `tool_coverage[]` uses these keys (one per dimension):

- `positive_selection` (dimension 1)
- `negative_selection` (dimension 2)
- `disambiguation` (dimension 3)
- `argument_fidelity` (dimension 4)
- `output_handling` (dimension 5)
- `sequence` (dimension 6, conditional)
- `subagent_delegation` (dimension 7, conditional)

**Required `trap_design` for disambiguation.** The `trap_design` field is marked optional in the base `llm` spec schema defined in `03-judge-spec.md`, but the disambiguation dimension (3) requires it — the trap is the entire test point. Every `llm` spec that satisfies the disambiguation dimension MUST include a `trap_design` describing the ambiguity.

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

**Invariant.** At the end of the design phase, for every `analysis.yaml:tools[i]`, there exists exactly one `design.yaml:tool_coverage[j]` where `j.tool_id == i.id`, and every mandatory dimension key under `j.dimensions_covered` is non-empty. Any `high`-severity risk in `i.design_risks` must appear in `j.design_risks_addressed` with at least one referenced item.

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

### Example 4: Complete data item and `_judge_specs` for the disambiguation dimension

Illustrates what a complete `method: llm` judge_spec looks like for one of the mandatory dimensions. The abbreviated patterns in the Per-Tool Coverage Matrix table name only the diagnostic fields (`method`, `target`, etc.); the full `llm` spec shape (`scoring`, `criteria`, `test_intent`, `anchors`, `calibrations`) is defined in `03-judge-spec.md` and shown here in context.

```yaml
# The disambiguation dimension for search_documents lives inside a
# design.yaml dataset. Showing the full enclosing structure makes
# the example directly usable as a template.
datasets:
  - items:
      - id: "keyword_vs_recency_ambiguous"
        description: "User asks for 'the latest report'. Both search_documents and list_recent_docs plausibly apply. Correct choice: list_recent_docs (recency). Tests whether the agent reads search_documents's keyword-focused description carefully."
        data:
          user_message: "Can you pull up the latest report for me?"
        _judge_specs:
          - method: "llm"
            scoring: "binary"
            target: {step_type: "tool_call"}
            criteria: "The agent selects list_recent_docs rather than search_documents for a recency-based request."
            test_intent: "Verify that the agent distinguishes search_documents (keyword retrieval) from list_recent_docs (recency-based listing) when the user's phrasing leans on recency."
            trap_design: "The phrase 'pull up' can read as retrieval (→ search_documents), but 'latest report' is a recency signal (→ list_recent_docs). search_documents's description emphasizes keyword search; list_recent_docs's description emphasizes recency. The correct tool is list_recent_docs."
            anchors:
              "0": "Called search_documents, or called list_recent_docs with a keyword argument that pretends to search by content."
              "1": "Called list_recent_docs with no keyword argument (or an empty one), treating the request as recency-based."
            calibrations:
              - output: "Called search_documents with query='latest report'."
                score: 0
                reason: "Ignored the recency signal and treated the request as keyword search."
              - output: "Called list_recent_docs with no filter."
                score: 1
                reason: "Correctly read the recency signal and chose the recency-based tool."
```

### Example 5: `tool_coverage` cross-reference for `research_subagent` (Example 2)

Shows how a `subagent` tool populates the conditional `subagent_delegation` dimension. Note that `sequence` is absent (no ordering dependency with another tool) and `design_risks_addressed` is empty (the inventory entry had `design_risks: []`).

```yaml
tool_coverage:
  - tool_id: "research_subagent"
    dimensions_covered:
      positive_selection: ["research_topic_explicit"]
      negative_selection: ["casual_chat_no_research"]
      disambiguation: ["research_vs_direct_answer"]
      argument_fidelity: ["research_scope_narrow"]
      output_handling: ["research_returns_no_sources"]
      subagent_delegation: ["research_delegation_with_full_context"]
    design_risks_addressed: []
```
