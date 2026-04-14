# Changelog

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
