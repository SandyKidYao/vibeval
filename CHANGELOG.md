# Changelog

## 0.6.1 (2026-04-14)

### Review Feedback Fixes

Closes 5 findings from an expert review of 0.6.0 covering the `feat/contract-phase-rewrite` and `feat/agent-tool-validation` merges. No CLI, Python, or dataset format changes; markdown-only updates to protocol, skill, and agent files.

- **Tool coverage mechanical verification is now real (F1-b).** The `tool_coverage[]` invariant previously checked only that dimension keys were non-empty — placeholder item ids silently passed. `07-agent-tools.md` now defines an "Allowed Spec Patterns Per Dimension" enumeration, and the Evaluator's Rule 7 runs three mechanical checks on every `(tool_id, dimension, item_id)` triple: (a) the item must resolve to a real dataset item, (b) the item's effective `judge_specs` must contain at least one spec whose structural fields match the dimension's allowed pattern (no semantic reasoning on `criteria` or `test_intent`), and (c) for `output_handling`, the dimension list must span ≥2 items whose `mock_context_summary` strings are not byte-equal. The design skill's Tool Coverage Planning step enforces the same rules on the generator side.
- **New required field `project.execution_mode` (F3-b).** `analysis.yaml:project` now carries an `execution_mode: "agent" | "non_agent"` field populated by the analyze skill during a single source scan. Design, evaluator, and consultant consume this field instead of re-detecting Agent features heuristically. The Evaluator's Analysis Phase Review gains a new "Tool inventory" dimension that triggers when `execution_mode == "agent"` and confirms `tools[]` plus its audit fields are present.
- **New required field `tools[].mock_target` (F1-b / F3-b).** The tool inventory gains a `mock_target` field as the stable join key between `analysis.yaml:tools[]` and each data item's `mock_context_summary` (design) / `_mock_context` (synthesize). This is the only reliable way to correlate a tool with its mocked responses across phases.
- **Consultant design-variant dispatch now includes `analysis.yaml` (F2).** The consultant's Agent Tool Failure Modes section depends on reading `project.execution_mode`, `tools[]`, and `design_risks[]` directly from analysis; previously the dispatch context only carried `design.yaml`, and the tool-aware review was not load-bearing.
- **Contract save is atomic (F4).** The contract skill absorbs `rigor` inference into Phase D before the single save. Previously the contract was saved once without `rigor`, `_research.md` was deleted, then rigor was inferred and the contract was re-saved — leaving a brief window with an incomplete contract on disk and the research brief already gone.
- **`/vibeval` evaluator iterations are rigor-aware (F5).** The orchestrator previously hardcoded max 3 evaluator iterations per phase. It now reads `contract.yaml:rigor` and applies the per-level cap: `light` → 1, `standard` → 3, `strict` → 5, with a `standard` fallback for missing/unparseable values. The stale "follow-up plan (P1)" note in `06-contract.md` is removed.

### Breaking Changes

None for existing datasets, results, or contracts. Two new required fields in `analysis.yaml` (`project.execution_mode`, `tools[].mock_target`) mean analyses created against 0.6.0 should be re-run before they can pass the strengthened Evaluator checks on 0.6.1 — but existing tests that don't touch the Agent-features flow are unaffected.

## 0.6.0 (2026-04-14)

### New Features

- **Per-tool validation for Agent features.** The analyze and design phases now treat every tool exposed to an LLM — custom function tools, MCP tools, and sub-agents — as an independent test unit. Analyze extracts a structured `tools[]` inventory and runs a static design audit producing `design_risks[]` findings. Design plans a `tool_coverage[]` cross-reference with 5 mandatory dimensions (positive selection, negative selection, disambiguation, argument fidelity, output handling) plus 2 conditional dimensions (sequence, sub-agent delegation). The Evaluator agent mechanically verifies the coverage invariant and honors `contract.yaml:rigor` severity filtering — under `light` rigor, missing coverage is blocking only for tools with high-severity design risks.
- **New protocol file `07-agent-tools.md`.** Authoritative definition of the tool inventory entry structure, static design-audit finding taxonomy (6 categories), per-tool coverage matrix, and `tool_coverage[]` invariant, with end-to-end examples for custom tools and sub-agents. Referenced by analyze, design, consultant, and evaluator without duplication — all definitions live in one place.
- **Consultant Agent Tool Failure Modes.** The design-phase research brief now includes an Agent Tool Failure Modes section when the analysis contains a tools inventory, seeding main-agent dialogue with tool-specific selection, argument construction, output handling, and delegation concerns.

### Breaking Changes

None. Existing features and datasets are unaffected; non-Agent features see no behavioral change. No CLI, Python, or dataset format changes. No new `judge_spec` rules — per-tool coverage composes from existing primitives (`tool_called`, `tool_not_called`, `tool_sequence`, and `llm` with `target.step_type: "tool_call"`).

## 0.5.0 (2026-04-09)

### New Features

- **Split generate into code + synthesize phases.** The monolithic generate phase is replaced by two focused phases: `code` (test infrastructure — conftest, collector, mock wiring, fixtures) and `synthesize` (dataset generation via parallel Data Synthesizer agents). This separates engineering work from creative data design, improving data quality.
- **`_mock_context` in dataset protocol.** Data items now support a `_mock_context` field for embedding mock responses from tools, APIs, and databases. Mock data is now first-class test data designed alongside user inputs, not an engineering afterthought hardcoded in test code.
- **`vibeval validate` command.** New CLI command to validate all datasets and results against the protocol format — manifests, judge specs, data items, `_mock_context`, traces, results, and cross-references (`values_from`/`expected_from`).
- **Data Synthesizer agent.** New subagent specialized in generating dataset items with full `_mock_context`. Spawned in parallel by the synthesize phase, one instance per dataset.
- **Consultant design review is now default.** The Consultant agent's design-stage coverage review runs by default after the initial design, catching blind spots before code and data generation.

### Breaking Changes

- The `generate` skill has been removed. `/vibeval` now routes through `code` then `synthesize`. The `generate` action is still accepted for backwards compatibility.
- Mock responses should now live in `_mock_context` within data items, not hardcoded in test code.

### Bug Fixes

- Removed stale `skills: protocol` reference from all agent definitions.
