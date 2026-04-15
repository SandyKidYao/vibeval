---
name: analyze
description: Analyze codebase to identify AI call points, data flow, mock points, and testability for vibeval testing. Use when entering the analyze phase of the /vibeval workflow.
---

# vibeval Analyze Phase

**Scope: AI capability evaluation only.** vibeval exists to evaluate the non-deterministic, AI-powered parts of an application — LLM calls, AI agent behaviors, prompt-driven pipelines. Deterministic logic (routing, validation, parsing, data transformation, CRUD operations) should be tested with standard unit/integration tests, NOT with vibeval. During analysis, identify only the AI-powered pipelines and exclude everything else.

Perform a thorough analysis of the codebase to prepare for test generation.

**Before starting, read:**
- `tests/vibeval/{feature}/contract.yaml` — **The negotiated contract.** All analysis must address the requirements and known gaps defined here.
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/00-philosophy.md` — Evaluation philosophy (information asymmetry + global perspective + contract)
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/01-overview.md` — Directory structure, unified turn model
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/07-agent-tools.md` — **For Agent features only.** Tool inventory entry structure, static design-audit finding taxonomy. Consult before executing the Extract Tool Inventory and Audit Tool Design steps below.

Produce analysis artifacts in `tests/vibeval/{feature}/analysis/`.

## Output Language

Read `contract.yaml:output_language` (defaults to `English` if absent). All narrative fields you write into `analysis.yaml` — `description`, `purpose`, `input_description`, `output_description`, `issue`, `suggestion`, `responsibility`, `design_risks[].finding`, `design_risks[].suggestion` — and the Checkpoint summary you present to the user MUST be written in that language. Code, file paths, identifiers, mock targets, rule names, YAML/JSON keys, and quoted excerpts from prompts or source code stay in their original form. See `${CLAUDE_PLUGIN_ROOT}/protocol/references/06-contract.md` for the full scope of `output_language`.

## Contract Alignment

The contract contains requirements that may not be visible in the code. During analysis:
- For each `requirement` in the contract, check whether the codebase supports it
- If a requirement has no code support, note it in `suggestions` as a gap (this informs the Evaluator)
- Ensure `known_gaps` from the contract are reflected in the analysis output

## Steps

### 1. Identify AI Call Points

Scan the codebase for:
- **LLM API calls**: OpenAI, Anthropic, Google, Azure, or other LLM SDK invocations
- **AI framework calls**: LangChain, LlamaIndex, CrewAI, Vercel AI SDK, or similar
- **Tool/function calling**: Functions registered as tools for LLM agents
- **External API calls**: REST/GraphQL calls that provide data to or consume data from AI pipelines

For each call point, record: file path, function name, purpose, input/output description, mock target path.

**Also determine `project.execution_mode` (required field).** Classify the project as `"agent"` or `"non_agent"` per the definition in `${CLAUDE_PLUGIN_ROOT}/protocol/references/07-agent-tools.md` (section "Project Metadata: `execution_mode`"). Operational procedure:

1. Scan for tool registration sites: custom tool decorators (framework-specific), SDK-level tool parameters passed to LLM calls (e.g., `tools=[...]` in OpenAI/Anthropic chat APIs), MCP server connection configs, and sub-agent invocation patterns where the main agent delegates to another agent via a tool-like handle.
2. If ANY such site is found → `execution_mode: "agent"`. Write the field with that value.
3. If NO such site is found → `execution_mode: "non_agent"`. Steps 2 and 3 below (Extract Tool Inventory, Audit Tool Design) are skipped.
4. If the classification is genuinely ambiguous (e.g., the project passes a tool list to one call but never the other; tool-like wrapper functions that don't actually use an LLM tool mechanism), do NOT silently default. Flag it in the Checkpoint output and ask the user to confirm before proceeding.

Every downstream consumer — design skill, evaluator agent, consultant agent — reads this field rather than re-scanning the code. Write it exactly once; do not infer from context in later steps.

### 2. Extract Tool Inventory (Agent features only)

If the codebase exposes tools to the LLM (custom tool registration, MCP server connections, or sub-agents invoked via a tool-like interface), populate a `tools[]` section in `analysis.yaml`. For non-Agent features, skip this step and the next.

For each tool, record all fields from the Tool Inventory Entry Structure in `${CLAUDE_PLUGIN_ROOT}/protocol/references/07-agent-tools.md` — the protocol defines the full schema and per-field semantics. The skill does not restate them.

Operational guidance for the extraction itself:

- **Capture `surface` verbatim.** `surface.name` and `surface.description` MUST match what the LLM actually sees at runtime, not how the tool is documented in comments, docstrings, or external docs. Read the registration site directly.
- **Record `mock_target`** for every tool. This is the dotted import path or identifier that the test mock framework will use to wrap the tool's underlying implementation. For `custom_tool`: derive from the registration site (e.g., registration at `app/tools/search.py:42` of a function `search_documents` → `mock_target: "app.tools.search_documents"`). For `mcp_tool`: use the MCP client call path that the agent framework will intercept. For `subagent`: use the sub-agent invocation handle (e.g., the function or method used to dispatch the sub-agent). The `mock_target` is the stable join key between `tools[]` and each data item's `mock_context_summary[...]` at design phase and `_mock_context[...]` at synthesize phase — it MUST be exactly the string that will appear as the key in both places.
- **For `mcp_tool` entries**, read the MCP server manifest or the connection config to discover the exposed surface — the registration is not in the project's source code.
- **For `subagent` entries**, the `source_location` is the sub-agent's definition file (not the registration site of the tool-like handle). Also capture `subagent_prompt_summary` and `subagent_expected_context`.
- **Leave `design_risks[]` and `siblings_to_watch[]` empty at this step.** They are populated in Step 3.

### 3. Audit Tool Design (Agent features only)

For each entry produced in Step 2, run a static design audit and populate `design_risks[]` and `siblings_to_watch[]`. The finding taxonomy, severity semantics, and category definitions live in `${CLAUDE_PLUGIN_ROOT}/protocol/references/07-agent-tools.md` — the skill does not restate them.

Operational checks to run per tool. Each check is an audit action; the criterion that determines whether a finding is recorded under the named category is defined in the protocol file. Consult `07-agent-tools.md` for the trigger conditions.

1. **Read the description in isolation.** Category: `description_ambiguity`.
2. **Walk every parameter the description implies against `input_schema`.** Category: `schema_gap`.
3. **Pairwise compare descriptions across the inventory.** When two tools could plausibly satisfy the same user query, record mutual findings under `overlap` on both entries and populate `siblings_to_watch` on both.
4. **Trace how the LLM would consume the tool's output shape end to end.** Category: `output_opacity`.
5. **(Sub-agents only) Inspect the exposed description against the sub-agent's internal prompt.** Category: `subagent_prompt_leak`.
6. **Compare the stated `responsibility` against the actual code behavior.** Category: `responsibility_drift`.

Record each finding using the fields defined in the protocol. High-severity findings become required test targets in the design phase.

### 4. Determine Test Mode

All vibeval tests are N-turn interactions; single-turn is N=1 (see `${CLAUDE_PLUGIN_ROOT}/protocol/references/01-overview.md` for the unified model).

Classify each pipeline:
- **Single-turn** (N=1): one input → one output (summarization, classification, extraction, etc.)
- **Multi-turn** (N>1): conversational system taking multiple rounds of user input. Must expose a `(str) -> str` chat entry point.

Record as `type: single-turn` or `type: multi-turn` in the analysis.
For multi-turn, also identify the chat entry point function signature.

### 5. Map Data Flow

Trace how data flows through the pipeline:
- Input source → transformations → context assembly → AI call → output parsing → final result
- For multi-turn: how conversation history is managed, what context accumulates across turns

### 6. Identify Mock Points

For each external dependency, record:
- The exact function/method to mock
- The mock target path (e.g., `myapp.services.llm_client.chat`)
- What synthetic data the mock should return

### 7. Filter Non-AI Pipelines

Exclude any pipeline that does not produce non-deterministic AI output. A pipeline is **out of vibeval scope** if:
- It has no AI calls (`ai_calls` is empty)
- Its outputs are fully determined by its inputs (routing, dispatching, parsing, validation, formatting)

Even if such a pipeline sits upstream of an AI pipeline (e.g., a message dispatcher that routes to an AI handler), it is deterministic logic and should be tested with standard unit tests, not vibeval. **Do not include it in the `pipelines` list.**

### 8. Evaluate Testability

Assess and suggest improvements ranked by impact:
- **Coupling**: LLM calls embedded in business logic → extract to separate functions
- **Context visibility**: prompt construction hidden → separate prompt building
- **Output parsing**: tightly coupled to LLM call → make parsing a separate function
- **Chat interface** (multi-turn): no clean `(str) -> str` entry point → suggest adding one
- **Observability**: no logging at pipeline stages → add logging for easier trace capture

## Output Format

Write the primary analysis to `tests/vibeval/{feature}/analysis/analysis.yaml`.
Additional artifacts (data flow diagrams, notes, etc.) can be placed alongside in the same directory.

```yaml
# vibeval Analysis
project:
  name: "<project name>"
  language: "<python|typescript|go|...>"
  test_framework: "<pytest|vitest|jest|go test|...>"
  execution_mode: "agent | non_agent"  # see 07-agent-tools.md Project Metadata section
  ai_frameworks:
    - "<openai|anthropic|langchain|...>"

pipelines:
  - name: "<descriptive pipeline name>"
    description: "<what this pipeline does>"
    entry_point: "<module.function>"
    type: "<single-turn|multi-turn>"

    # Multi-turn only:
    chat_entry: "<module.function>"  # (str) -> str interface
    manages_history: true            # whether bot manages its own conversation history

    ai_calls:
      - id: "<unique id>"
        file: "<file path>"
        function: "<function name>"
        mock_target: "<dotted.path.for.mock>"
        purpose: "<what this call does>"
        input_description: "<what goes in>"
        output_description: "<what comes out>"

    external_deps:
      - id: "<unique id>"
        file: "<file path>"
        function: "<function name>"
        mock_target: "<dotted.path.for.mock>"
        purpose: "<what this dependency provides>"

    data_flow:
      - stage: "input"
        source: "<where data comes from>"
        key_fields: ["<field1>", "<field2>"]
      - stage: "ai_call"
        call_id: "<references ai_calls.id>"
      - stage: "output"
        key_fields: ["<final output fields>"]

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
    mock_target: "<dotted import path used to mock this tool's implementation>"
    surface:
      name: "<LLM-facing name>"
      description: "<LLM-facing description>"
      input_schema:
        <param>: "<type, required/optional, brief>"
      output_shape: "<LLM-visible shape>"
    responsibility: "<one-line intent>"
    design_risks: []          # populated by Audit Tool Design (see 07-agent-tools.md for finding schema)
    siblings_to_watch: []     # populated by Audit Tool Design; when populated: [{id: "<tool_id>", overlap_reason: "<why>"}]
    # subagent_prompt_summary / subagent_expected_context: only for type: subagent
```

## Checkpoint

Present to the user:
1. Summary: pipelines found, type (single-turn/multi-turn), AI calls, mock points
2. **Project classification: `execution_mode`** — state whether the project is classified as `"agent"` or `"non_agent"`, and briefly name the signal(s) that drove the classification (e.g., "custom tool decorator at app/tools/search.py:42", "OpenAI chat API called with `tools=[...]` in app/bot.py:18", "no tool registrations found"). If the classification was ambiguous, explicitly ask the user to confirm the value before proceeding.
3. If any pipelines were excluded as non-AI deterministic logic, list them and briefly explain why (so the user knows they weren't overlooked)
4. Testability improvement suggestions ranked by severity
5. **Agent features only** (execution_mode == "agent"). Tool inventory: list of identified tools with their types, plus any high-severity design risks flagged during the audit.
6. Ask: **"Analysis complete. Shall I proceed to design the test plan?"**

Wait for user confirmation before proceeding to the design phase.
