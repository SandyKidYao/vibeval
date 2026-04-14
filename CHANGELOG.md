# Changelog

## 0.7.0 (2026-04-14)

### New Features

- **CLI full validation for `analysis.yaml` and `design.yaml`.** `vibeval validate <feature>` now additionally validates the two Agent-feature authoring artifacts, turning the `vibeval-evaluator` agent's Rule 7 mechanical checks into a first-class CLI gate that runs outside the `/vibeval` workflow. The checks are a 1:1 mechanical translation of `plugin/protocol/references/07-agent-tools.md` — structural field comparison only, no semantic reasoning on prose fields, no contract.yaml coupling. `vibeval validate <feature>` returns exit 0 iff `analysis.yaml`, `design.yaml` (if present), datasets, and results all pass their respective validators.
  - **`analysis.yaml` schema checks.** `project.execution_mode` is required (`"agent"` or `"non_agent"`). When `"agent"`, every entry of `tools[]` is schema-validated: required scalar fields (`id`, `type`, `source_location`, `mock_target`, `responsibility`) are type-checked, `surface.{name,description,output_shape}` must be strings, `surface.input_schema` must be a mapping, `design_risks[]` and `siblings_to_watch[]` must be lists (may be empty), `type: subagent` additionally requires `subagent_prompt_summary` and `subagent_expected_context: list[str]`. Duplicate `tool.id` is rejected. Wrong-type fields produce clean errors instead of crashing the CLI.
  - **`design.yaml` schema + Rule 7 mechanical check.** `tool_coverage[]` entries are cross-referenced against `analysis.yaml:tools[]`: duplicate entries and orphan entries (whose `tool_id` matches no analysis tool) produce explicit errors. For every `(tool_id, dimension, item_id)` triple under `dimensions_covered`, the CLI verifies (a) item existence — the id must resolve to a real dataset item reachable from the design, (b) spec pattern match — the resolved item's effective `judge_specs` (item-level `_judge_specs` fully replace manifest `judge_specs` per the runtime's precedence rule) must contain at least one spec matching the dimension's Allowed Spec Pattern, and (c) for `output_handling`, the list must span ≥2 items whose `mock_context_summary[<tool.mock_target>]` string values are byte-unequal and non-empty.
  - **Allowed Spec Patterns per dimension, strict.** `positive_selection` / `negative_selection` require `rule: tool_called` / `tool_not_called` with `args.tool_name == tool.surface.name`. `disambiguation` requires `method: llm`, `target: {step_type: "tool_call"}` (dict form only), plus a non-empty `trap_design`. `argument_fidelity` accepts either the same llm tool-call form OR `method: rule, rule: equals|matches` with `args.field` present (strict whitelist — `contains` and other rules are rejected). `output_handling` requires `method: llm, target: "output"` (or `target` omitted) AND the item's `mock_context_summary` must have a key matching `tool.mock_target` (dict-form target is rejected). `sequence` requires `rule: tool_sequence` with `args.expected` containing `tool.surface.name`. `subagent_delegation` is mandatory iff `tool.type == "subagent"` and requires the same llm tool-call form.
  - **Partial workflow states are tolerated.** `analysis.yaml` absent → Agent checks skip silently. `analysis.yaml` present + `non_agent` → `tools[]` and `tool_coverage[]` checks skip silently. `analysis.yaml` present + `agent` + `design.yaml` absent → the design-missing warning fires. `design.yaml` present + `analysis.yaml` absent → schema checks run and a warning surfaces that cross-reference was skipped. The CLI is usable mid-workflow (after analyze but before design), in CI without a contract, and in pre-commit hooks.
  - **Hard gate, not exception path.** Malformed YAML in a dataset file no longer crashes `validate_feature` with `yaml.ParserError` — filesystem datasets are now loaded per-entry with per-dataset `try/except`, so one bad file does not poison cross-reference for unrelated valid datasets. The bad file is surfaced by the existing dataset-phase validator, and the rest of Rule 7 continues to run.

### Implementation Notes

- New modules: `src/vibeval/validate_analysis.py` and `src/vibeval/validate_design.py`. `src/vibeval/validate.py`'s `validate_feature()` gained 8 lines (two function calls); the existing 685 lines are untouched.
- CLI `--help` extended to describe the new analysis/design coverage per CLAUDE.md principle #3.
- No protocol, skill, agent, plugin, or dataset format changes. Pure additive Python + CHANGELOG + version bumps.
- 195 tests pass, including 149 new tests for the validator (happy path + per-dimension pattern match + all documented error categories + external-review regression tests).

### Breaking Changes

None. Features without `analysis/` or `design/` directories continue to validate as before. Features with `analysis/analysis.yaml` that predate 0.6.0 will now fail the validator with "project.execution_mode is required (0.6.0+)" — add the field or re-run the analyze skill.

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
