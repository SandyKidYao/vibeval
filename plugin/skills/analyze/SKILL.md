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

### 2. Extract Tool Inventory (Agent features only)

If the codebase exposes tools to the LLM (custom tool registration, MCP server connections, or sub-agents invoked via a tool-like interface), populate a `tools[]` section in `analysis.yaml`. For non-Agent features, skip this step and the next.

For each tool, identify:

- **`type`**: `custom_tool` (framework-registered function), `mcp_tool` (MCP-server-exposed), or `subagent` (sub-agent used as a tool).
- **`source_location`**: `file:line` for custom tools; MCP server + tool name for MCP tools; sub-agent definition path for sub-agents.
- **`surface`**: the name, description, `input_schema`, and `output_shape` as the LLM actually sees them. Read the registration site verbatim. For MCP tools, read the MCP manifest or connection config.
- **`responsibility`**: a one-line statement of intent.

For `type: subagent`, also capture `subagent_prompt_summary` and `subagent_expected_context`.

The full field definitions and YAML layout are in `${CLAUDE_PLUGIN_ROOT}/protocol/references/07-agent-tools.md` — do not duplicate them here; follow that protocol.

### 3. Audit Tool Design (Agent features only)

For each entry produced in Step 2, run a static design audit and populate `design_risks[]` and `siblings_to_watch[]`. The finding taxonomy (`description_ambiguity`, `schema_gap`, `overlap`, `output_opacity`, `subagent_prompt_leak`, `responsibility_drift`) and severity semantics are defined in `${CLAUDE_PLUGIN_ROOT}/protocol/references/07-agent-tools.md`.

Specific checks to perform:

1. **Description clarity**: Does the description distinguish this tool from plausible alternatives? Would a user query matching multiple plausible tools land correctly?
2. **Schema completeness**: Given the description, does the input schema expose every parameter the LLM would need to construct a correct call? Are types and required/optional flags present?
3. **Cross-tool overlap**: Compare every pair of tool descriptions. Record mutual `overlap` findings and populate `siblings_to_watch` on both entries.
4. **Output clarity**: Is the output shape specific enough for the LLM to reliably consume it (especially in downstream chaining)?
5. **Sub-agent prompt hygiene** (subagents only): Does the sub-agent's exposed description leak internal implementation details that could bias delegation?
6. **Responsibility drift**: Does the stated `responsibility` match the actual code behavior?

Record each finding with `severity` (high/medium/low), `category`, `finding`, and an optional `suggested_fix`. `high`-severity findings will be required test targets in the design phase.

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

## Checkpoint

Present to the user:
1. Summary: pipelines found, type (single-turn/multi-turn), AI calls, mock points
2. If any pipelines were excluded as non-AI deterministic logic, list them and briefly explain why (so the user knows they weren't overlooked)
3. Testability improvement suggestions ranked by severity
4. **Agent features only.** Tool inventory: list of identified tools with their types, plus any high-severity design risks flagged during the audit.
5. Ask: **"Analysis complete. Shall I proceed to design the test plan?"**

Wait for user confirmation before proceeding to the design phase.
