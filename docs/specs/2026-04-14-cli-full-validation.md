# CLI Full Validation for analysis.yaml + design.yaml — Design Spec

**Date:** 2026-04-14
**Status:** Approved by user, pending implementation plan
**Target release:** vibeval 0.7.0
**Downstream:** an implementation plan will be produced separately via `writing-plans` and placed in `docs/plans/`.

## Goal

Extend `vibeval validate <feature>` to mechanically verify `analysis.yaml` and `design.yaml` — including the strengthened `tool_coverage[]` invariant introduced in 0.6.0/0.6.1 — so that the same checks the `vibeval-evaluator` agent runs inside the `/vibeval` workflow can also be run outside it (CI, pre-commit, manual scripts). No protocol changes; pure 1:1 Python translation of the authoritative spec in `plugin/protocol/references/07-agent-tools.md`.

## Motivation

0.6.0 introduced Agent tool validation and 0.6.1 closed review feedback by strengthening the mechanical invariant (`Allowed Spec Patterns Per Dimension` + item existence + `output_handling` multi-item constraint on `mock_context_summary`). These changes are currently enforced **only** by the Evaluator agent inside the `/vibeval` workflow. They are not reachable from:

- CI pipelines that run `vibeval validate <feature>` as a gate
- Pre-commit hooks
- Manual inspection (`vibeval validate` as a quick sanity check after editing a design by hand)
- Any automation that wants a reproducible pass/fail verdict on a feature's authored artifacts

`vibeval validate <feature>` currently covers only `datasets/` and `results/`. It has never touched `analysis/` or `design/`. As a result, a user can edit `design.yaml` incorrectly, run `vibeval validate`, get exit 0, and only discover the problem when they run the full `/vibeval` workflow.

0.7.0 closes this gap by porting the Evaluator agent's Rule 7 mechanical checks into CLI-level Python code.

## Non-Goals

- **No changes to `analysis.yaml` / `design.yaml` / protocol format.** Use the schema defined in 0.6.1. This spec is about reading the existing format, not extending it.
- **No re-running of `analyze` / `design` phases from Python.** The CLI validates existing artifacts; it does not produce them.
- **No rigor-aware severity downgrading.** The CLI is the hard mechanical gate; the Evaluator agent is the context-aware gate. The CLI does not read `contract.yaml`.
- **No semantic reasoning over prose fields** (`criteria`, `test_intent`, `description`). Structural field comparison only. `args.field` is a presence-only check. `trap_design` is presence + non-empty. `mock_context_summary` byte-equality is byte-level.
- **No parallelism, caching, or incremental validation.** Must run in well under 1s on real inputs. Implementation is straightforward serial Python.
- **No new CLI subcommands, new flags, or changes to existing subcommand names.** `vibeval validate <feature>` absorbs the new coverage.
- **No protocol changes**, no skill changes, no plugin changes except the CHANGELOG entry.
- **No touching the existing 685 lines of `src/vibeval/validate.py`** beyond extending `validate_feature()`'s orchestration. Existing checks, existing tests, existing behavior stay untouched.

## Scope (locked)

In scope:

1. Load `analysis.yaml` and `design.yaml` into typed Python dataclasses.
2. Schema checks: required fields, enum values, types, basic cross-references (e.g., `tool_coverage[].tool_id` must match some `tools[].id`).
3. Semantic invariant checks — a direct port of the `Mechanical Check` subsection in `plugin/protocol/references/07-agent-tools.md`:
   - **(a) Item existence.** Every `item_id` under `tool_coverage[].dimensions_covered.<dim>` must resolve to a real entry in some dataset reachable from the design.
   - **(b) Spec pattern match.** The resolved item's effective `judge_specs` (item-level `_judge_specs` replacing manifest-level per the priority rule in `02-dataset.md`) must contain at least one spec structurally matching the dimension's Allowed Spec Pattern. For `output_handling`, additionally verify the item has a `mock_context_summary` entry keyed by `analysis.yaml:tools[i].mock_target`.
   - **(c) `output_handling` multi-item constraint.** The full `dimensions_covered.output_handling` list must span ≥2 items whose `mock_context_summary[<mock_target>]` string values are byte-unequal. Empty strings do not count as distinct values.
4. `execution_mode` gate: Agent-specific checks run only when `project.execution_mode == "agent"`. When `"non_agent"`, Agent-specific checks are skipped (not reported as errors). When the field is missing or has an unknown value, that is an error.
5. TDD: every check gets a failing test first, then the implementation.
6. CHANGELOG entry + version bump to 0.7.0 in all three places (`pyproject.toml`, `plugin/plugin.json`, `src/vibeval/__init__.py`) + annotated tag `v0.7.0`.

## Design Decisions (locked)

These are the answers to the design questions resolved during brainstorming. Each is binding for the implementation.

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| Q1 | CLI interface shape | Extend `vibeval validate <feature>` in place (no new flag, no new subcommand). | Users expect one "is this feature's state correct" gate. Additive by construction — features without `analysis/` or `design/` stay passing. |
| Q2 | Rigor-aware severity | CLI ignores `contract.yaml:rigor`. Always reports errors; never downgrades. | Predictable CI behavior. Decouples the CLI from `contract.yaml` (which may not exist). Two clearly separated layers: CLI = hard gate, Evaluator = context-aware gate. |
| Q3 | Partial validation (refined) | `analysis.yaml` absent → skip all Agent checks silently. Present with `execution_mode` missing/unknown → error. Present + `non_agent` → skip `tools[]` and all `tool_coverage` checks. Present + `agent` + `design.yaml` absent → warn, validate `tools[]` schema, skip cross-reference. Present + `agent` + `design.yaml` present → full Rule 7 check. `design.yaml` present without `analysis.yaml` → validate `design.yaml` schema, warn, skip cross-reference. | Matches workflow ordering. `execution_mode` is the gate for every Agent check and lives in `analysis.yaml`. |
| Q4 | `argument_fidelity` rule whitelist | Strict: only `rule: equals` or `rule: matches` with `args.field` present. Nothing else. | Protocol says "(or matches)" literally. |
| Q5 | `disambiguation` / `subagent_delegation` target form | Strict dict: `target: {step_type: "tool_call"}`. String shorthand not accepted. | Protocol's Allowed Spec Pattern row shows only the dict form. |
| Q6 | `output_handling` target form | Strict: `target: "output"` string OR `target` key absent. Dict form not accepted. | Protocol verbatim. |
| Q7 | `_judge_specs` precedence | Full replacement: if item has `_judge_specs`, manifest-level `judge_specs` are ignored for that item. **Must match how `src/vibeval/judge.py` resolves specs at runtime.** Verified during implementation; if `judge.py` diverges, re-open this decision. | "Override" reading in `02-dataset.md:112`. CLI must not diverge from the runtime. |
| Q8 | `sequence` dimension applicability | CLI never requires `sequence`. Only structurally checked if the design voluntarily lists items under it. | No machine-readable field flags "has ordering dependency". CLI is the mechanical gate; requiring `sequence` would produce false positives. |
| Q9 | `subagent_delegation` dimension applicability | Required **iff** `tool.type == "subagent"`. Must have ≥1 item; each item must pattern-match. | Machine-readable via `tool.type`. |
| Q10 | `mock_context_summary` empty-string value | Treat empty string as a presence failure. Two empty strings do not satisfy the multi-item constraint. | Empty strings are placeholders and would trivially satisfy byte-equality. |
| Q11 | Item-id collision across datasets | Flatten all items from design-inline datasets + filesystem manifest datasets. First match wins; emit a warning on collision. | Simple, matches user intuition. Design-inline takes precedence per Q12. |
| Q12 | Dataset source resolution | Merge both sources (inline in `design.yaml:datasets[]` + filesystem under `tests/vibeval/{feature}/datasets/`). Design-inline items take precedence on collision; warn. | Protocol allows both sources. Merging matches `"reachable from the design"`. |

## Mental Model

The CLI becomes a **hard mechanical gate** with three layers of checks:

1. **Schema layer** — typed, required-field, enum checks on `analysis.yaml` and `design.yaml` themselves.
2. **Cross-reference layer** — `tool_coverage[].tool_id` resolves to some `tools[].id`; every referenced `item_id` resolves to a real dataset item.
3. **Pattern layer** — Rule 7 mechanical check: for every `(tool_id, dimension, item_id)` triple, the resolved item's effective `judge_specs` must contain at least one spec structurally matching the dimension's Allowed Spec Pattern.

No prose interpretation. No rigor-awareness. No retries. Exit 0 iff every layer passes and the existing `datasets/` + `results/` checks also pass.

## Module Layout

```
src/vibeval/
├── validate.py                 # unchanged except validate_feature() orchestration
├── validate_analysis.py        # NEW — analysis.yaml schema + execution_mode gate
└── validate_design.py          # NEW — design.yaml schema + Rule 7 mechanical check
```

**`validate.py`:**
- `Issue` and `ValidationReport` — unchanged, shared source of truth. Imported by the new modules.
- `validate_feature(feature_dir)` — extended: calls `validate_analysis(...)`, then `validate_design(...)` (threading the analysis model through for cross-reference), then the existing `_validate_datasets` + `_validate_results` walks, all into the same `ValidationReport`. Exit code is derived from `report.errors` as today.
- No other edits to the existing 685 lines.

**`validate_analysis.py`:**
- `validate_analysis(feature_dir: Path, report: ValidationReport) -> AnalysisModel | None`
- Reads `{feature_dir}/analysis/analysis.yaml`. Absent → returns `None` without writing to `report` (per Q3). Present but malformed → adds errors, returns `None`.
- Schema-validates `project.execution_mode`, and (when `agent`) every entry of `tools[]`.
- Returns a typed `AnalysisModel` (plain dataclass) that `validate_design` consumes.

**`validate_design.py`:**
- `validate_design(feature_dir: Path, analysis: AnalysisModel | None, report: ValidationReport) -> None`
- Reads `{feature_dir}/design/design.yaml`. Absent + `analysis.execution_mode == "agent"` → warn per Q3. Absent otherwise → silent. Present but malformed → errors.
- Builds a `DesignModel` containing the flattened `items_by_id` dict (merging design-inline datasets + filesystem manifest datasets) and the `tool_coverage[]` entries.
- Runs the Rule 7 mechanical check iff `analysis` is non-`None` and `analysis.execution_mode == "agent"` and the design loaded.

## Data Model

All dataclasses are plain Python — no Pydantic, no runtime validation framework. Parsing is a single pass per file; errors go into `ValidationReport`; successful parses yield a typed model.

### `validate_analysis.py`

```python
@dataclass
class ToolModel:
    id: str
    type: str                        # "custom_tool" | "mcp_tool" | "subagent"
    mock_target: str
    surface_name: str                # tool.surface.name — the string the pattern matcher compares
    # Other fields (source_location, surface.description, surface.input_schema,
    # surface.output_shape, responsibility, design_risks, siblings_to_watch,
    # subagent_*) are schema-validated but NOT stored on the model — the
    # mechanical check only needs id / type / mock_target / surface_name.

@dataclass
class AnalysisModel:
    execution_mode: str              # "agent" | "non_agent"
    tools: list[ToolModel]           # empty for non_agent; may not be empty for agent
    raw_path: str                    # absolute path to analysis.yaml, for error reporting
```

### `validate_design.py`

```python
@dataclass
class JudgeSpecModel:
    method: str                      # "rule" | "llm"
    rule: str | None                 # for method=rule
    target_step_type: str | None     # target.step_type if target is a dict
    target_output: bool              # True if target == "output" OR target key absent
    args_tool_name: str | None       # args.tool_name (for tool_called / tool_not_called)
    args_field_present: bool         # Q4: presence-only check
    args_expected: Any               # args.expected (for tool_sequence)
    trap_design_nonempty: bool       # trap_design is a present, non-empty string

@dataclass
class ItemModel:
    id: str
    dataset_name: str                # for error reporting and collision warnings
    source: str                      # "design_inline" | "manifest" (for Q12 precedence)
    mock_context_summary: dict[str, str]  # keyed by mock_target, empty dict if absent
    effective_specs: list[JudgeSpecModel] # Q7: item _judge_specs replace manifest specs if present

@dataclass
class ToolCoverageModel:
    tool_id: str
    dimensions_covered: dict[str, list[str]]  # dim_name -> item_ids
    raw_path: str                    # "design.yaml tool_coverage[<i>]"

@dataclass
class DesignModel:
    tool_coverage: list[ToolCoverageModel]
    items_by_id: dict[str, ItemModel]
    raw_path: str                    # absolute path to design.yaml
```

**Key points:**
- **`effective_specs` is pre-computed at load time**, applying Q7 precedence. Will be verified against `src/vibeval/judge.py`'s resolution logic before the implementation is finalized.
- **`target_output: bool`** collapses "target absent" and `target: "output"` into one flag — the `output_handling` matcher is a one-boolean read.
- **`items_by_id`** is the single item resolution point. Built once at parse time; collision warnings emitted during construction per Q11.
- **Typed at check time, raw dicts at parse time.** Follows the existing validator's pattern of "parse → validate fields → store".

## Check Algorithm

### Phase 1 — `analysis.yaml` schema (in `validate_analysis.py`)

```
1. Load analysis/analysis.yaml (absent → return None, silent per Q3).
   YAML parse error → report.error, return None.
   Top-level not a dict → report.error, return None.
2. project.execution_mode:
   - missing → error "project.execution_mode is required (0.6.0+)"
   - not in {"agent","non_agent"} → error "unknown execution_mode '<x>'"
3. if execution_mode == "non_agent":
     - tools[] absent or empty → OK
     - tools[] present and non-empty → warning (not error)
     - return AnalysisModel(execution_mode="non_agent", tools=[])
4. if execution_mode == "agent":
     - tools[] absent or empty → error
     - for each tool[i]:
         required fields: id, type, source_location, mock_target,
           surface.name, surface.description, surface.input_schema,
           surface.output_shape, responsibility
         type ∈ {custom_tool, mcp_tool, subagent}
         design_risks must be a list (empty OK)
         siblings_to_watch must be a list (empty OK)
         if type == "subagent": subagent_prompt_summary required
     - tool id uniqueness → error on duplicates
     - return AnalysisModel with populated tools list
```

### Phase 2 — `design.yaml` schema (in `validate_design.py`)

```
1. Load design/design.yaml (absent → handled per Q3).
2. Top-level must be a dict. datasets[] optional; tool_coverage[] optional.
3. For each design-inline dataset:
     - name required
     - items[]: each has id; collect into items_by_id as source="design_inline"
4. For each filesystem dataset under {feature}/datasets/:
     - load via the existing dataset loader's logic (not by calling _validate_dataset_dir,
       which writes to report — instead a minimal read-only loader that collects
       item ids + mock_context_summary + effective judge_specs from
       (manifest judge_specs) replaced by (item _judge_specs) per Q7)
     - collect into items_by_id as source="manifest", but only if the id is not
       already present from design-inline (Q11/Q12 precedence). If already
       present, emit a warning.
5. For each tool_coverage[j]:
     - tool_id required
     - dimensions_covered: must be a dict whose values are lists of strings
6. Return DesignModel.
```

### Phase 3 — Rule 7 mechanical check

Only runs iff `analysis` is non-`None`, `analysis.execution_mode == "agent"`, and design loaded.

```python
for analysis_tool in analysis.tools:
    coverage = next((c for c in design.tool_coverage if c.tool_id == analysis_tool.id), None)
    if coverage is None:
        report.error(design.raw_path,
            f"no tool_coverage entry for tool '{analysis_tool.id}'")
        continue

    mandatory_dims = ["positive_selection", "negative_selection",
                      "disambiguation", "argument_fidelity", "output_handling"]
    if analysis_tool.type == "subagent":
        mandatory_dims.append("subagent_delegation")  # Q9

    for dim in mandatory_dims:
        item_ids = coverage.dimensions_covered.get(dim, [])
        if not item_ids:
            report.error(coverage.raw_path,
                f"tool '{analysis_tool.id}' dimension '{dim}' has no items listed")
            continue
        for item_id in item_ids:
            item = design.items_by_id.get(item_id)
            if item is None:
                report.error(coverage.raw_path,
                    f"tool '{analysis_tool.id}' dim '{dim}' item '{item_id}' "
                    f"not found in any dataset")
                continue
            if not _any_spec_matches(item, dim, analysis_tool):
                report.error(coverage.raw_path,
                    f"tool '{analysis_tool.id}' dim '{dim}' item '{item_id}' "
                    f"has no judge_spec matching the Allowed Pattern for '{dim}'")

    # Check (c) — output_handling multi-item constraint
    oh_ids = coverage.dimensions_covered.get("output_handling", [])
    oh_items = [design.items_by_id[i] for i in oh_ids if i in design.items_by_id]
    if len(oh_items) < 2:
        report.error(coverage.raw_path,
            f"tool '{analysis_tool.id}' output_handling must span >=2 items, "
            f"found {len(oh_items)}")
    else:
        summaries = [
            item.mock_context_summary.get(analysis_tool.mock_target, "")
            for item in oh_items
        ]
        distinct_nonempty = {s for s in summaries if s}
        if len(distinct_nonempty) < 2:
            report.error(coverage.raw_path,
                f"tool '{analysis_tool.id}' output_handling: "
                f"mock_context_summary['{analysis_tool.mock_target}'] values "
                f"are all empty or byte-equal; need >=2 distinct (Q10)")

    # Conditional: sequence — Q8, never required by CLI
    seq_ids = coverage.dimensions_covered.get("sequence", [])
    if seq_ids:
        for item_id in seq_ids:
            item = design.items_by_id.get(item_id)
            if item is None:
                report.error(coverage.raw_path, f"... sequence ... not found ...")
                continue
            if not _any_spec_matches(item, "sequence", analysis_tool):
                report.error(coverage.raw_path, f"... sequence ... no match ...")
```

### `_any_spec_matches(item, dim, tool)` — the structural matcher

The heart of check (b). One function, one switch over dimension name. Each case is exactly one row of `plugin/protocol/references/07-agent-tools.md` §"Allowed Spec Patterns Per Dimension".

```python
def _any_spec_matches(item: ItemModel, dim: str, tool: ToolModel) -> bool:
    for spec in item.effective_specs:
        if dim == "positive_selection":
            if (spec.method == "rule" and spec.rule == "tool_called"
                    and spec.args_tool_name == tool.surface_name):
                return True

        elif dim == "negative_selection":
            if (spec.method == "rule" and spec.rule == "tool_not_called"
                    and spec.args_tool_name == tool.surface_name):
                return True

        elif dim == "disambiguation":
            if (spec.method == "llm" and spec.target_step_type == "tool_call"
                    and spec.trap_design_nonempty):
                return True

        elif dim == "argument_fidelity":
            if spec.method == "llm" and spec.target_step_type == "tool_call":
                return True
            if (spec.method == "rule" and spec.rule in ("equals", "matches")
                    and spec.args_field_present):
                return True

        elif dim == "output_handling":
            if spec.method == "llm" and spec.target_output:
                if tool.mock_target in item.mock_context_summary:
                    return True

        elif dim == "sequence":
            if spec.method == "rule" and spec.rule == "tool_sequence":
                expected = spec.args_expected
                if isinstance(expected, list) and tool.surface_name in expected:
                    return True

        elif dim == "subagent_delegation":
            if spec.method == "llm" and spec.target_step_type == "tool_call":
                return True

    return False
```

No interpretation of `criteria`, `test_intent`, `description`, or any other prose field. Structural equality and presence checks only.

## Error Taxonomy

All issues go through the existing `Issue(level, path, message)` shape. `level` is `"error"` or `"warning"`. `path` identifies a file or a logical locator.

| # | Phase | Level | Message template |
|---|-------|-------|------------------|
| 1 | analysis | error | `project.execution_mode is required (0.6.0+)` |
| 2 | analysis | error | `unknown execution_mode '<x>'` |
| 3 | analysis | error | `tools[] is required when execution_mode == 'agent'` |
| 4 | analysis | error | `tools[<i>] missing required field '<name>'` |
| 5 | analysis | error | `tools[<i>].type invalid '<x>'` (not in enum) |
| 6 | analysis | error | `tools[<i>].design_risks must be a list` |
| 7 | analysis | error | `tools[<i>].siblings_to_watch must be a list` |
| 8 | analysis | error | `tools[<i>] subagent_prompt_summary required for type: subagent` |
| 9 | analysis | error | `tools[] contains duplicate id '<id>'` |
| 10 | analysis | warning | `execution_mode == 'non_agent' but tools[] is non-empty; ignoring` |
| 11 | design | error | `no tool_coverage entry for tool '<tool_id>'` |
| 12 | design | error | `tool '<id>' dimension '<dim>' has no items listed` |
| 13 | design | error | `tool '<id>' dim '<dim>' item '<item_id>' not found in any dataset` (check a) |
| 14 | design | error | `tool '<id>' dim '<dim>' item '<item_id>' has no judge_spec matching the Allowed Pattern for '<dim>'` (check b) |
| 15 | design | error | `tool '<id>' output_handling must span >=2 items, found <n>` (check c count) |
| 16 | design | error | `tool '<id>' output_handling: mock_context_summary['<mock_target>'] values are all empty or byte-equal; need >=2 distinct` (check c value) |
| 17 | design | warning | `item '<id>' defined in multiple datasets — using <first>` (Q11 collision) |
| 18 | design | warning | `design.yaml missing but analysis.yaml has execution_mode: agent` (Q3) |

Each table row has at least one negative test in the test plan below.

## CLI Integration

[src/vibeval/cli.py](../../src/vibeval/cli.py) — the `p_validate` subparser's `description` is extended to name the new coverage. No new flags, no new arguments. The extended description reads:

```
Check all datasets, judge specs, data items, traces, and results for a
feature against the vibeval protocol format. Also validates analysis.yaml
(execution_mode + tools[] schema) and design.yaml (tool_coverage[]
cross-reference + Rule 7 mechanical check) when present. Catches
structural issues that would cause judge/compare/summary to fail at
runtime and enforces the strengthened tool_coverage invariant from
plugin/protocol/references/07-agent-tools.md.

Validates: analysis.yaml (execution_mode, tools[] schema), design.yaml
(tool_coverage[] Rule 7: item existence + Allowed Spec Patterns + the
output_handling multi-item constraint), manifest structure, judge_spec
fields (rule names, args, scoring, anchors, calibrations), data item
reserved fields, trace format, result files, and cross-references.

Exit code 0 if no errors, 1 if errors found.
```

The single entry point `validate_feature()` in `validate.py` becomes (new lines commented):

```python
def validate_feature(feature_dir):
    report = ValidationReport()
    feature_dir = Path(feature_dir)
    if not feature_dir.exists():
        report.error(str(feature_dir), "Feature directory does not exist")
        return report

    # NEW: analysis and design validation
    from .validate_analysis import validate_analysis
    from .validate_design import validate_design
    analysis = validate_analysis(feature_dir, report)     # may be None
    validate_design(feature_dir, analysis, report)        # uses analysis for cross-ref

    # UNCHANGED below this line
    datasets_dir = feature_dir / "datasets"
    if datasets_dir.exists():
        _validate_datasets(datasets_dir, report)
    else:
        report.warn(str(feature_dir), "No datasets/ directory found")
    results_dir = feature_dir / "results"
    if results_dir.exists():
        _validate_results(results_dir, report)
    return report
```

## Test Plan

New test file: `tests/test_validate_agent.py`. Mirrors the structure of the existing `tests/test_validate.py` — fixtures built in-memory (written to `tmp_path`), no network, no external state. TDD cadence: failing test → implementation → passing test → commit.

### analysis.yaml schema tests

- `test_analysis_missing_execution_mode_errors`
- `test_analysis_unknown_execution_mode_errors`
- `test_analysis_non_agent_mode_passes_with_no_tools`
- `test_analysis_non_agent_mode_warns_if_tools_present`
- `test_analysis_agent_mode_requires_non_empty_tools`
- `test_analysis_agent_mode_tool_missing_required_field_errors` (parameterized over each required field)
- `test_analysis_agent_mode_invalid_tool_type_errors`
- `test_analysis_agent_mode_design_risks_must_be_list`
- `test_analysis_agent_mode_siblings_to_watch_must_be_list`
- `test_analysis_agent_mode_subagent_requires_prompt_summary`
- `test_analysis_agent_mode_duplicate_tool_ids_errors`
- `test_analysis_agent_mode_happy_path_passes`
- `test_analysis_missing_file_silent_when_absent` (Q3)

### design.yaml schema + Rule 7 tests

- `test_design_missing_file_warns_when_agent_mode` (Q3)
- `test_design_missing_file_silent_when_non_agent_mode`
- `test_design_missing_tool_coverage_entry_for_tool_errors`
- `test_design_mandatory_dim_empty_list_errors` (×5 mandatory dims, one test each)
- `test_design_unknown_item_id_errors_check_a`
- `test_design_positive_selection_spec_pattern_mismatch_errors`
- `test_design_positive_selection_pattern_matches_passes`
- `test_design_negative_selection_pattern_mismatch_errors`
- `test_design_disambiguation_missing_trap_design_errors`
- `test_design_disambiguation_wrong_target_step_type_errors`
- `test_design_disambiguation_string_target_rejected` (Q5)
- `test_design_argument_fidelity_llm_form_passes`
- `test_design_argument_fidelity_rule_equals_with_field_passes`
- `test_design_argument_fidelity_rule_matches_with_field_passes`
- `test_design_argument_fidelity_rule_contains_rejected` (Q4 strict whitelist)
- `test_design_argument_fidelity_rule_equals_without_field_errors`
- `test_design_output_handling_missing_mock_context_summary_key_errors`
- `test_design_output_handling_single_item_errors_check_c`
- `test_design_output_handling_two_items_byte_equal_summaries_errors_check_c`
- `test_design_output_handling_two_items_all_empty_summaries_errors` (Q10)
- `test_design_output_handling_dict_target_rejected` (Q6)
- `test_design_output_handling_two_items_distinct_summaries_passes`
- `test_design_sequence_not_listed_is_not_required` (Q8)
- `test_design_sequence_listed_pattern_checked`
- `test_design_sequence_listed_unknown_item_errors`
- `test_design_subagent_delegation_required_for_subagent_type` (Q9)
- `test_design_subagent_delegation_not_required_for_custom_tool`
- `test_design_item_judge_specs_override_manifest` (Q7 — verifies CLI matches `judge.py` precedence)
- `test_design_inline_dataset_items_resolved`
- `test_design_manifest_dataset_items_resolved`
- `test_design_item_id_collision_warning` (Q11, inline takes precedence per Q12)
- `test_design_happy_path_all_dimensions_pass`

### Integration tests (`validate.py::validate_feature`)

- `test_validate_feature_non_agent_feature_runs_existing_checks_only`
- `test_validate_feature_agent_feature_with_full_coverage_exit_zero`
- `test_validate_feature_agent_feature_with_broken_coverage_exit_nonzero`
- `test_validate_feature_no_regression_on_existing_datasets_fixtures` (re-run existing validator test fixtures through the extended entry point; assert no new errors on features that previously passed)

### Coverage target

Every error taxonomy row (1–18) has at least one negative test. Every Allowed Spec Pattern row has at least one positive test. This guarantees the "1:1 protocol translation" invariant is testable and regressions are caught.

## Commit Cadence

The implementation plan will expand each of these into subagent-executable subtasks. Each commit must have passing tests before moving on.

1. `docs: add spec + plan for CLI full validation` — this spec + plan file, one commit.
2. `validate: add AnalysisModel and validate_analysis.py schema checks (+tests)`
3. `validate: add DesignModel and load_design with item flattening (+tests)`
4. `validate: implement Rule 7 check (a) item existence (+tests)`
5. `validate: implement Rule 7 check (b) spec pattern match per dimension (+tests)`
6. `validate: implement Rule 7 check (c) output_handling multi-item constraint (+tests)`
7. `validate: wire validate_analysis + validate_design into validate_feature (+integration tests)`
8. `cli: extend validate --help description to cover analysis + design`

## Release Plan (0.7.0)

Runs after the feature branch is merged to main with `--no-ff`:

- Bump version in all three places:
  - [pyproject.toml](../../pyproject.toml) `version`
  - [plugin/plugin.json](../../plugin/plugin.json) `version`
  - [src/vibeval/__init__.py](../../src/vibeval/__init__.py) `__version__`
- Add `## [0.7.0] - 2026-04-14` entry to [CHANGELOG.md](../../CHANGELOG.md) describing CLI-level tool_coverage validation:
  > **CLI full validation for analysis.yaml and design.yaml.** `vibeval validate <feature>` now additionally verifies `analysis.yaml` (execution_mode + `tools[]` schema) and `design.yaml` (`tool_coverage[]` cross-reference + strengthened Rule 7 mechanical check: item existence + Allowed Spec Patterns + the `output_handling` multi-item constraint on `mock_context_summary`). The checks are a 1:1 port of the Evaluator agent's Rule 7 from `plugin/protocol/references/07-agent-tools.md`, runnable outside the `/vibeval` workflow for CI, pre-commit, and manual use. No protocol, skill, or dataset format changes.
- Commit the release bump.
- Annotated tag `v0.7.0` with a summary of the CHANGELOG entry.
- Push `main` + tag (only after explicit user authorization).
- Delete local feature branch.

## Done Definition

- [ ] All 7 coverage dimensions have a Python check mirroring the row in `07-agent-tools.md`'s Allowed Spec Patterns table.
- [ ] Item existence, spec pattern match, and output_handling multi-item constraint all run mechanically from the CLI.
- [ ] `vibeval validate <feature>` returns exit 0 only when `analysis.yaml`, `design.yaml` (if present), datasets, and results all pass their respective validators.
- [ ] Every new check has at least one positive test (good input passes) and one negative test (each specific failure mode is caught).
- [ ] Existing Python tests continue to pass (no regression).
- [ ] `CHANGELOG.md` 0.7.0 entry describes the new CLI coverage.
- [ ] Branch merged to main, version bumped, tag `v0.7.0` pushed, local branches cleaned up.

## Protocol Source of Truth

Every check in this spec is a mechanical translation of:

- `plugin/protocol/references/07-agent-tools.md` §"Project Metadata: `execution_mode`"
- `plugin/protocol/references/07-agent-tools.md` §"Tool Inventory Entry Structure" + field definitions
- `plugin/protocol/references/07-agent-tools.md` §"Allowed Spec Patterns Per Dimension" + Mechanical Check subsection
- `plugin/protocol/references/07-agent-tools.md` §"Design Coverage Cross-Reference" → Invariant paragraph
- `plugin/protocol/references/02-dataset.md` §"Data Item" — specifically the `_judge_specs > judge_specs` priority rule (Q7)
- `plugin/agents/evaluator.md` Rule 7 (a/b/c) — secondary reference, cross-checks the Python interpretation

If any implementation question arises that is not answered by these files, the spec is ambiguous and the implementation MUST stop and escalate. Do not improvise.
