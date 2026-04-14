# CLI Full Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `vibeval validate <feature>` to mechanically verify `analysis.yaml` and `design.yaml` — including the Rule 7 `tool_coverage[]` invariant — as a 1:1 translation of `plugin/protocol/references/07-agent-tools.md`.

**Architecture:** Add two new sibling modules (`src/vibeval/validate_analysis.py`, `src/vibeval/validate_design.py`) that produce typed dataclasses and share the existing `Issue` / `ValidationReport` in `src/vibeval/validate.py`. The existing `validate_feature()` gains two new calls at the top. Reuses `src/vibeval/dataset.py::load_all_datasets` (whose `Dataset.effective_specs(item)` already implements full-replacement precedence) for the filesystem manifest source of items.

**Tech Stack:** Python 3.11+, PyYAML, pytest, plain `@dataclass` (no Pydantic).

**Spec:** [docs/specs/2026-04-14-cli-full-validation.md](../specs/2026-04-14-cli-full-validation.md)

**Branch:** `feat/cli-full-validation` (already created, spec already committed at `e0fdbd3`)

---

## Runtime precondition checks (verified 2026-04-14 before writing this plan)

- `src/vibeval/dataset.py:40-42` `Dataset.effective_specs(item)` returns `item.judge_specs if item.judge_specs else self.judge_specs` — full-replacement precedence. **CLI Q7 decision matches runtime — no divergence.**
- `src/vibeval/dataset.py:131-140` `_parse_item` pops `_id`, `_tags`, `_judge_specs` from the raw dict; everything else goes into `DataItem.data`. **Filesystem dataset items carry no `mock_context_summary` field** — that is a design-phase artifact in `design.yaml:datasets[].items[]` only.
- `src/vibeval/validate.py:86-107` `validate_feature()` takes `feature_dir` (path-like), builds a `ValidationReport`, walks `datasets_dir` and `results_dir`. We insert new calls at the top, unchanged behavior below.
- `src/vibeval/validate.py:18-53` `Issue` + `ValidationReport` are plain dataclasses. The new modules import and populate them directly.
- `src/vibeval/cli.py:91-101` defines `p_validate` with a `description` string. We extend the description only; no new args.

---

## File Structure

New files:

- `src/vibeval/validate_analysis.py` — analysis.yaml loader + schema checks. Exports `validate_analysis(feature_dir, report) -> AnalysisModel | None`, `AnalysisModel`, `ToolModel`.
- `src/vibeval/validate_design.py` — design.yaml loader + Rule 7 mechanical check. Exports `validate_design(feature_dir, analysis, report) -> None`, `DesignModel`, `ItemModel`, `JudgeSpecModel`, `ToolCoverageModel`.
- `tests/test_validate_agent.py` — all unit + integration tests for the new modules.

Modified files:

- `src/vibeval/validate.py` — `validate_feature()` gains two new calls at the top. No other edits.
- `src/vibeval/cli.py` — `p_validate` description string extended. No new args.
- `CHANGELOG.md` — new `## [0.7.0] - 2026-04-14` entry (release task, last).
- `pyproject.toml`, `plugin/plugin.json`, `src/vibeval/__init__.py` — version bumped (release task, last).

---

## Task 1: Commit the plan itself

**Files:**
- Create: `docs/plans/2026-04-14-cli-full-validation.md` (this file)

- [ ] **Step 1: Verify the plan file exists and is staged-ready**

Run: `ls -la docs/plans/2026-04-14-cli-full-validation.md`
Expected: file exists, non-zero size.

- [ ] **Step 2: Commit the plan**

```bash
git add docs/plans/2026-04-14-cli-full-validation.md
git commit -m "$(cat <<'EOF'
docs: add implementation plan for CLI full validation (0.7.0)

8-task TDD plan mapping to the 8 commits in the approved spec.
Reuses src/vibeval/dataset.py::load_all_datasets for filesystem
manifest items (Q7 full-replacement precedence already matches).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

Expected: commit succeeds on `feat/cli-full-validation`.

---

## Task 2: `validate_analysis.py` — AnalysisModel + schema checks

**Files:**
- Create: `src/vibeval/validate_analysis.py`
- Create: `tests/test_validate_agent.py` (initial file with helpers + analysis tests)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_validate_agent.py` with:

```python
"""Tests for validate_analysis + validate_design (Agent features).

Fixtures are built in-memory under tmp_path, mirroring tests/test_validate.py.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from vibeval.validate import ValidationReport
from vibeval.validate_analysis import (
    AnalysisModel,
    ToolModel,
    validate_analysis,
)


# --- Helpers -----------------------------------------------------------------

def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


def make_feature(tmp_path: Path, analysis_yaml: str | None = None) -> Path:
    feature = tmp_path / "feat"
    feature.mkdir(parents=True, exist_ok=True)
    if analysis_yaml is not None:
        write(feature / "analysis" / "analysis.yaml", analysis_yaml)
    return feature


def error_messages(report: ValidationReport) -> list[str]:
    return [i.message for i in report.errors]


def warning_messages(report: ValidationReport) -> list[str]:
    return [i.message for i in report.warnings]


# --- validate_analysis: file presence ---------------------------------------

def test_analysis_missing_file_silent_when_absent(tmp_path: Path) -> None:
    feature = make_feature(tmp_path, analysis_yaml=None)
    report = ValidationReport()
    result = validate_analysis(feature, report)
    assert result is None
    assert report.issues == []


def test_analysis_invalid_yaml_errors(tmp_path: Path) -> None:
    feature = make_feature(tmp_path, analysis_yaml="project: [unclosed\n")
    report = ValidationReport()
    result = validate_analysis(feature, report)
    assert result is None
    assert any("Invalid YAML" in m or "YAML" in m for m in error_messages(report))


def test_analysis_top_level_not_dict_errors(tmp_path: Path) -> None:
    feature = make_feature(tmp_path, analysis_yaml="- just a list\n")
    report = ValidationReport()
    result = validate_analysis(feature, report)
    assert result is None
    assert any("must be a YAML mapping" in m for m in error_messages(report))


# --- execution_mode ----------------------------------------------------------

def test_analysis_missing_execution_mode_errors(tmp_path: Path) -> None:
    feature = make_feature(tmp_path, analysis_yaml="""
        project:
          name: foo
    """)
    report = ValidationReport()
    result = validate_analysis(feature, report)
    assert result is None
    assert any("project.execution_mode is required" in m for m in error_messages(report))


def test_analysis_unknown_execution_mode_errors(tmp_path: Path) -> None:
    feature = make_feature(tmp_path, analysis_yaml="""
        project:
          name: foo
          execution_mode: "hybrid"
    """)
    report = ValidationReport()
    result = validate_analysis(feature, report)
    assert result is None
    assert any("unknown execution_mode 'hybrid'" in m for m in error_messages(report))


# --- non_agent ---------------------------------------------------------------

def test_analysis_non_agent_mode_passes_with_no_tools(tmp_path: Path) -> None:
    feature = make_feature(tmp_path, analysis_yaml="""
        project:
          name: foo
          execution_mode: "non_agent"
    """)
    report = ValidationReport()
    result = validate_analysis(feature, report)
    assert result is not None
    assert result.execution_mode == "non_agent"
    assert result.tools == []
    assert error_messages(report) == []


def test_analysis_non_agent_mode_warns_if_tools_present(tmp_path: Path) -> None:
    feature = make_feature(tmp_path, analysis_yaml="""
        project:
          name: foo
          execution_mode: "non_agent"
        tools:
          - id: "stray"
            type: "custom_tool"
    """)
    report = ValidationReport()
    result = validate_analysis(feature, report)
    assert result is not None
    assert result.tools == []
    assert error_messages(report) == []
    assert any("non_agent" in m and "tools[]" in m for m in warning_messages(report))


# --- agent mode --------------------------------------------------------------

AGENT_HAPPY = """
    project:
      name: foo
      execution_mode: "agent"
    tools:
      - id: "search_documents"
        type: "custom_tool"
        source_location: "app/tools.py:42"
        mock_target: "app.tools.search_documents"
        surface:
          name: "search_documents"
          description: "Search internal documents by keyword"
          input_schema:
            query: "string, required"
          output_shape: "list of {doc_id, title}"
        responsibility: "Keyword retrieval over the corpus"
        design_risks: []
        siblings_to_watch: []
"""


def test_analysis_agent_mode_happy_path_passes(tmp_path: Path) -> None:
    feature = make_feature(tmp_path, analysis_yaml=AGENT_HAPPY)
    report = ValidationReport()
    result = validate_analysis(feature, report)
    assert result is not None
    assert result.execution_mode == "agent"
    assert len(result.tools) == 1
    tool = result.tools[0]
    assert tool.id == "search_documents"
    assert tool.type == "custom_tool"
    assert tool.mock_target == "app.tools.search_documents"
    assert tool.surface_name == "search_documents"
    assert error_messages(report) == []


def test_analysis_agent_mode_requires_non_empty_tools(tmp_path: Path) -> None:
    feature = make_feature(tmp_path, analysis_yaml="""
        project:
          name: foo
          execution_mode: "agent"
    """)
    report = ValidationReport()
    result = validate_analysis(feature, report)
    assert any("tools[] is required" in m for m in error_messages(report))


@pytest.mark.parametrize("removed_field,expected_fragment", [
    ("id", "missing required field 'id'"),
    ("type", "missing required field 'type'"),
    ("mock_target", "missing required field 'mock_target'"),
    ("source_location", "missing required field 'source_location'"),
    ("responsibility", "missing required field 'responsibility'"),
])
def test_analysis_agent_mode_tool_missing_required_field_errors(
    tmp_path: Path, removed_field: str, expected_fragment: str
) -> None:
    import yaml as _yaml
    data = _yaml.safe_load(textwrap.dedent(AGENT_HAPPY))
    del data["tools"][0][removed_field]
    feature = make_feature(tmp_path, analysis_yaml=_yaml.safe_dump(data))
    report = ValidationReport()
    validate_analysis(feature, report)
    assert any(expected_fragment in m for m in error_messages(report))


def test_analysis_agent_mode_missing_surface_name_errors(tmp_path: Path) -> None:
    import yaml as _yaml
    data = _yaml.safe_load(textwrap.dedent(AGENT_HAPPY))
    del data["tools"][0]["surface"]["name"]
    feature = make_feature(tmp_path, analysis_yaml=_yaml.safe_dump(data))
    report = ValidationReport()
    validate_analysis(feature, report)
    assert any("surface.name" in m for m in error_messages(report))


def test_analysis_agent_mode_invalid_tool_type_errors(tmp_path: Path) -> None:
    import yaml as _yaml
    data = _yaml.safe_load(textwrap.dedent(AGENT_HAPPY))
    data["tools"][0]["type"] = "weird"
    feature = make_feature(tmp_path, analysis_yaml=_yaml.safe_dump(data))
    report = ValidationReport()
    validate_analysis(feature, report)
    assert any("type invalid 'weird'" in m for m in error_messages(report))


def test_analysis_agent_mode_design_risks_must_be_list(tmp_path: Path) -> None:
    import yaml as _yaml
    data = _yaml.safe_load(textwrap.dedent(AGENT_HAPPY))
    data["tools"][0]["design_risks"] = "oops"
    feature = make_feature(tmp_path, analysis_yaml=_yaml.safe_dump(data))
    report = ValidationReport()
    validate_analysis(feature, report)
    assert any("design_risks must be a list" in m for m in error_messages(report))


def test_analysis_agent_mode_siblings_to_watch_must_be_list(tmp_path: Path) -> None:
    import yaml as _yaml
    data = _yaml.safe_load(textwrap.dedent(AGENT_HAPPY))
    data["tools"][0]["siblings_to_watch"] = "oops"
    feature = make_feature(tmp_path, analysis_yaml=_yaml.safe_dump(data))
    report = ValidationReport()
    validate_analysis(feature, report)
    assert any("siblings_to_watch must be a list" in m for m in error_messages(report))


def test_analysis_agent_mode_subagent_requires_prompt_summary(tmp_path: Path) -> None:
    feature = make_feature(tmp_path, analysis_yaml="""
        project:
          name: foo
          execution_mode: "agent"
        tools:
          - id: "research"
            type: "subagent"
            source_location: "plugin/agents/research.md"
            mock_target: "app.agents.research"
            surface:
              name: "research"
              description: "Research things"
              input_schema: {}
              output_shape: "brief"
            responsibility: "Research"
            design_risks: []
            siblings_to_watch: []
    """)
    report = ValidationReport()
    validate_analysis(feature, report)
    assert any("subagent_prompt_summary" in m for m in error_messages(report))


def test_analysis_agent_mode_duplicate_tool_ids_errors(tmp_path: Path) -> None:
    import yaml as _yaml
    data = _yaml.safe_load(textwrap.dedent(AGENT_HAPPY))
    data["tools"].append(dict(data["tools"][0]))  # shallow copy duplicates the id
    feature = make_feature(tmp_path, analysis_yaml=_yaml.safe_dump(data))
    report = ValidationReport()
    validate_analysis(feature, report)
    assert any("duplicate id 'search_documents'" in m for m in error_messages(report))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_validate_agent.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vibeval.validate_analysis'`

- [ ] **Step 3: Write the minimal implementation**

Create `src/vibeval/validate_analysis.py`:

```python
"""Analysis.yaml validator — schema checks and execution_mode gate.

Produces an AnalysisModel that validate_design consumes for cross-reference.
Errors are written to the shared ValidationReport.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .validate import ValidationReport


ALLOWED_EXECUTION_MODES = ("agent", "non_agent")
ALLOWED_TOOL_TYPES = ("custom_tool", "mcp_tool", "subagent")

# Required top-level fields on each tools[] entry
TOOL_REQUIRED_FIELDS = (
    "id",
    "type",
    "source_location",
    "mock_target",
    "responsibility",
)


@dataclass
class ToolModel:
    """Minimal, checked view of analysis.yaml:tools[i] for cross-reference.

    Only fields the Rule 7 mechanical check needs are stored. Everything
    else is schema-validated but discarded.
    """

    id: str
    type: str                # custom_tool | mcp_tool | subagent
    mock_target: str
    surface_name: str        # tool.surface.name


@dataclass
class AnalysisModel:
    execution_mode: str      # "agent" | "non_agent"
    tools: list[ToolModel] = field(default_factory=list)
    raw_path: str = ""


def validate_analysis(feature_dir: Path, report: ValidationReport) -> AnalysisModel | None:
    """Validate analysis/analysis.yaml and return a typed model.

    Q3 semantics:
    - File absent → return None silently (no issues).
    - File present but malformed / schema violations → errors added, return None.
    - File present and valid → return AnalysisModel.
    """
    feature_dir = Path(feature_dir)
    analysis_path = feature_dir / "analysis" / "analysis.yaml"
    if not analysis_path.exists():
        return None

    path_str = str(analysis_path)
    try:
        raw = yaml.safe_load(analysis_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        report.error(path_str, f"Invalid YAML: {e}")
        return None

    if raw is None:
        report.error(path_str, "analysis.yaml is empty")
        return None

    if not isinstance(raw, dict):
        report.error(path_str, "analysis.yaml must be a YAML mapping at the top level")
        return None

    project = raw.get("project")
    if not isinstance(project, dict):
        report.error(path_str, "project: is required and must be a mapping")
        return None

    execution_mode = project.get("execution_mode")
    if execution_mode is None:
        report.error(path_str, "project.execution_mode is required (0.6.0+)")
        return None
    if execution_mode not in ALLOWED_EXECUTION_MODES:
        report.error(
            path_str,
            f"unknown execution_mode '{execution_mode}' — must be one of {list(ALLOWED_EXECUTION_MODES)}",
        )
        return None

    tools_raw = raw.get("tools")

    if execution_mode == "non_agent":
        if isinstance(tools_raw, list) and len(tools_raw) > 0:
            report.warn(
                path_str,
                "execution_mode == 'non_agent' but tools[] is non-empty; ignoring",
            )
        return AnalysisModel(execution_mode="non_agent", tools=[], raw_path=path_str)

    # execution_mode == "agent"
    if not isinstance(tools_raw, list) or len(tools_raw) == 0:
        report.error(
            path_str,
            "tools[] is required when execution_mode == 'agent' and must be non-empty",
        )
        return None

    tools: list[ToolModel] = []
    seen_ids: set[str] = set()
    any_tool_failed = False

    for i, entry in enumerate(tools_raw):
        loc = f"{path_str} tools[{i}]"
        if not isinstance(entry, dict):
            report.error(loc, "tools[] entry must be a mapping")
            any_tool_failed = True
            continue

        missing_any = False
        for fname in TOOL_REQUIRED_FIELDS:
            if fname not in entry:
                report.error(loc, f"missing required field '{fname}'")
                missing_any = True

        ttype = entry.get("type")
        if ttype is not None and ttype not in ALLOWED_TOOL_TYPES:
            report.error(loc, f"type invalid '{ttype}' — must be one of {list(ALLOWED_TOOL_TYPES)}")
            missing_any = True

        surface = entry.get("surface")
        if not isinstance(surface, dict):
            report.error(loc, "missing required field 'surface' (must be a mapping)")
            missing_any = True
        else:
            for sf in ("name", "description", "input_schema", "output_shape"):
                if sf not in surface:
                    report.error(loc, f"missing required field 'surface.{sf}'")
                    missing_any = True

        # design_risks and siblings_to_watch must be lists (may be empty)
        for list_field in ("design_risks", "siblings_to_watch"):
            if list_field in entry and not isinstance(entry[list_field], list):
                report.error(loc, f"{list_field} must be a list")
                missing_any = True
        # Both are required (may be empty list)
        for list_field in ("design_risks", "siblings_to_watch"):
            if list_field not in entry:
                report.error(loc, f"missing required field '{list_field}' (empty list is OK)")
                missing_any = True

        # subagent extras
        if ttype == "subagent":
            if "subagent_prompt_summary" not in entry:
                report.error(loc, "subagent_prompt_summary required for type: subagent")
                missing_any = True

        if missing_any:
            any_tool_failed = True
            continue

        tool_id = entry["id"]
        if tool_id in seen_ids:
            report.error(loc, f"tools[] contains duplicate id '{tool_id}'")
            any_tool_failed = True
            continue
        seen_ids.add(tool_id)

        tools.append(ToolModel(
            id=tool_id,
            type=ttype,
            mock_target=entry["mock_target"],
            surface_name=surface["name"],
        ))

    if any_tool_failed:
        return None

    return AnalysisModel(execution_mode="agent", tools=tools, raw_path=path_str)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_validate_agent.py -v`
Expected: all tests PASS. If a test about missing `surface` fails because the happy-path uses `surface.name` but parametrized test deletes `id` — that's fine, those are independent branches. All tests green.

- [ ] **Step 5: Run the full Python test suite to verify no regression**

Run: `python -m pytest tests/ -v`
Expected: all existing tests continue to pass. New file adds ~13 tests.

- [ ] **Step 6: Commit**

```bash
git add src/vibeval/validate_analysis.py tests/test_validate_agent.py
git commit -m "$(cat <<'EOF'
validate: add AnalysisModel and validate_analysis.py schema checks

New module validates analysis.yaml:
- project.execution_mode required, must be "agent" or "non_agent"
- When non_agent: tools[] ignored (warning if present)
- When agent: tools[] required non-empty; each entry schema-checked
  (id, type, source_location, mock_target, surface.{name,description,
  input_schema,output_shape}, responsibility, design_risks list,
  siblings_to_watch list); subagent type requires subagent_prompt_summary;
  duplicate ids rejected.

Returns a minimal AnalysisModel carrying only the fields the Rule 7
mechanical check needs (id, type, mock_target, surface.name).

Q3 file-absence: analysis.yaml missing → silent None, no issues.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `validate_design.py` — DesignModel + loader with item flattening

**Files:**
- Create: `src/vibeval/validate_design.py`
- Modify: `tests/test_validate_agent.py` — add design-loading tests

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_validate_agent.py`:

```python
# ========================================================================
# validate_design: loading and item flattening
# ========================================================================

from vibeval.validate_design import (
    DesignModel,
    ItemModel,
    JudgeSpecModel,
    ToolCoverageModel,
    validate_design,
    _build_judge_spec_model,
)


def add_design(feature: Path, design_yaml: str) -> None:
    write(feature / "design" / "design.yaml", design_yaml)


def make_agent_feature(tmp_path: Path, design_yaml: str | None = None) -> tuple[Path, AnalysisModel]:
    feature = make_feature(tmp_path, analysis_yaml=AGENT_HAPPY)
    report = ValidationReport()
    analysis = validate_analysis(feature, report)
    assert analysis is not None, error_messages(report)
    if design_yaml is not None:
        add_design(feature, design_yaml)
    return feature, analysis


# --- File presence ----------------------------------------------------------

def test_design_missing_file_silent_when_non_agent(tmp_path: Path) -> None:
    feature = make_feature(tmp_path, analysis_yaml="""
        project:
          name: foo
          execution_mode: "non_agent"
    """)
    report = ValidationReport()
    analysis = validate_analysis(feature, report)
    validate_design(feature, analysis, report)
    assert report.issues == []


def test_design_missing_file_warns_when_agent_mode(tmp_path: Path) -> None:
    feature, analysis = make_agent_feature(tmp_path, design_yaml=None)
    report = ValidationReport()
    validate_design(feature, analysis, report)
    assert any(
        "design.yaml missing" in m and "execution_mode: agent" in m
        for m in warning_messages(report)
    )
    assert error_messages(report) == []


# --- Inline dataset item flattening ----------------------------------------

FULL_COVERAGE_DESIGN = """
    datasets:
      - name: "search"
        judge_specs:
          - method: rule
            rule: "contains"
            args: {field: "outputs.summary", value: "ok"}
        items:
          - id: "pos_item"
            data: {user_message: "find docs about X"}
            _judge_specs:
              - method: rule
                rule: tool_called
                args: {tool_name: "search_documents"}
          - id: "neg_item"
            data: {user_message: "hello"}
            _judge_specs:
              - method: rule
                rule: tool_not_called
                args: {tool_name: "search_documents"}
          - id: "disambig_item"
            data: {user_message: "latest report"}
            _judge_specs:
              - method: llm
                scoring: binary
                target: {step_type: "tool_call"}
                criteria: "picks right tool"
                trap_design: "recency vs keyword"
          - id: "argfid_item"
            data: {user_message: "X and Y"}
            _judge_specs:
              - method: llm
                scoring: binary
                target: {step_type: "tool_call"}
                criteria: "args faithful"
          - id: "oh_empty"
            data: {user_message: "Z"}
            mock_context_summary:
              "app.tools.search_documents": "returns empty result list"
            _judge_specs:
              - method: llm
                scoring: binary
                target: "output"
                criteria: "handles empty gracefully"
          - id: "oh_error"
            data: {user_message: "W"}
            mock_context_summary:
              "app.tools.search_documents": "returns HTTP 429 error"
            _judge_specs:
              - method: llm
                scoring: binary
                target: "output"
                criteria: "handles error gracefully"

    tool_coverage:
      - tool_id: "search_documents"
        dimensions_covered:
          positive_selection: ["pos_item"]
          negative_selection: ["neg_item"]
          disambiguation: ["disambig_item"]
          argument_fidelity: ["argfid_item"]
          output_handling: ["oh_empty", "oh_error"]
"""


def test_design_inline_dataset_items_resolved(tmp_path: Path) -> None:
    feature, analysis = make_agent_feature(tmp_path, design_yaml=FULL_COVERAGE_DESIGN)
    report = ValidationReport()
    validate_design(feature, analysis, report)
    assert error_messages(report) == []


def test_design_judge_spec_model_extraction() -> None:
    raw = {
        "method": "rule",
        "rule": "tool_called",
        "args": {"tool_name": "search_documents", "field": "outputs.summary"},
    }
    m = _build_judge_spec_model(raw)
    assert m.method == "rule"
    assert m.rule == "tool_called"
    assert m.args_tool_name == "search_documents"
    assert m.args_field_present is True
    assert m.target_step_type is None
    assert m.target_output is True  # target key absent → True per Q6 refinement
    # Wait — target_output only applies when spec targets output; for a rule spec
    # it should still be True when target is absent, because the matcher only
    # reads target_output for llm specs. Keep it True for absent, we'll not
    # misuse it elsewhere.

    llm_raw = {
        "method": "llm",
        "scoring": "binary",
        "target": "output",
        "criteria": "x",
        "trap_design": "non-empty",
    }
    m2 = _build_judge_spec_model(llm_raw)
    assert m2.method == "llm"
    assert m2.target_output is True
    assert m2.trap_design_nonempty is True

    llm_tool_call = {
        "method": "llm",
        "scoring": "binary",
        "target": {"step_type": "tool_call"},
        "criteria": "x",
        "trap_design": "",
    }
    m3 = _build_judge_spec_model(llm_tool_call)
    assert m3.target_step_type == "tool_call"
    assert m3.target_output is False
    assert m3.trap_design_nonempty is False  # empty string → False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_validate_agent.py -v -k design`
Expected: FAIL with `ModuleNotFoundError: No module named 'vibeval.validate_design'`

- [ ] **Step 3: Write the minimal implementation**

Create `src/vibeval/validate_design.py`:

```python
"""Design.yaml validator — schema checks + Rule 7 mechanical check.

Ports the vibeval-evaluator agent's Rule 7 from
plugin/protocol/references/07-agent-tools.md into CLI Python code.

All checks are structural. No prose interpretation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .dataset import Dataset, load_all_datasets
from .validate import ValidationReport
from .validate_analysis import AnalysisModel, ToolModel


MANDATORY_DIMENSIONS = (
    "positive_selection",
    "negative_selection",
    "disambiguation",
    "argument_fidelity",
    "output_handling",
)


@dataclass
class JudgeSpecModel:
    """Structural view of a judge_spec used by the pattern matcher.

    Only the fields named by the Allowed Spec Patterns table are extracted;
    prose fields (criteria, test_intent, description) are deliberately NOT
    stored — the mechanical check does not look at them.
    """

    method: str | None
    rule: str | None
    target_step_type: str | None
    target_output: bool
    args_tool_name: str | None
    args_field_present: bool
    args_expected: Any
    trap_design_nonempty: bool


@dataclass
class ItemModel:
    id: str
    dataset_name: str
    source: str                                       # "design_inline" | "manifest"
    mock_context_summary: dict[str, str] = field(default_factory=dict)
    effective_specs: list[JudgeSpecModel] = field(default_factory=list)


@dataclass
class ToolCoverageModel:
    tool_id: str
    dimensions_covered: dict[str, list[str]]
    raw_path: str


@dataclass
class DesignModel:
    tool_coverage: list[ToolCoverageModel]
    items_by_id: dict[str, ItemModel]
    raw_path: str


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def validate_design(
    feature_dir: Path,
    analysis: AnalysisModel | None,
    report: ValidationReport,
) -> None:
    feature_dir = Path(feature_dir)
    design_path = feature_dir / "design" / "design.yaml"

    if not design_path.exists():
        if analysis is not None and analysis.execution_mode == "agent":
            report.warn(
                str(design_path),
                "design.yaml missing but analysis.yaml has execution_mode: agent",
            )
        return

    path_str = str(design_path)
    try:
        raw = yaml.safe_load(design_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        report.error(path_str, f"Invalid YAML: {e}")
        return

    if raw is None:
        report.error(path_str, "design.yaml is empty")
        return
    if not isinstance(raw, dict):
        report.error(path_str, "design.yaml must be a YAML mapping at the top level")
        return

    design = _build_design_model(raw, feature_dir, path_str, report)

    if analysis is None or analysis.execution_mode != "agent":
        return  # schema checks still ran; mechanical check skipped

    _run_rule_7(analysis, design, report)


# ---------------------------------------------------------------------------
# Model construction
# ---------------------------------------------------------------------------


def _build_design_model(
    raw: dict,
    feature_dir: Path,
    path_str: str,
    report: ValidationReport,
) -> DesignModel:
    items_by_id: dict[str, ItemModel] = {}

    # 1. Inline datasets from design.yaml itself
    datasets = raw.get("datasets", [])
    if datasets is not None and not isinstance(datasets, list):
        report.error(path_str, "datasets must be a list")
        datasets = []
    for di, ds in enumerate(datasets or []):
        if not isinstance(ds, dict):
            report.error(f"{path_str} datasets[{di}]", "dataset entry must be a mapping")
            continue
        ds_name = ds.get("name", f"<inline-{di}>")
        manifest_specs = _coerce_spec_list(ds.get("judge_specs", []))
        for ii, item_raw in enumerate(ds.get("items", []) or []):
            if not isinstance(item_raw, dict):
                report.error(
                    f"{path_str} datasets[{di}].items[{ii}]",
                    "item must be a mapping",
                )
                continue
            iid = item_raw.get("id")
            if not isinstance(iid, str) or not iid:
                report.error(
                    f"{path_str} datasets[{di}].items[{ii}]",
                    "item.id is required and must be a non-empty string",
                )
                continue
            item_model = _build_item_model(
                iid=iid,
                dataset_name=ds_name,
                source="design_inline",
                item_raw=item_raw,
                manifest_specs=manifest_specs,
            )
            if iid in items_by_id:
                report.warn(
                    path_str,
                    f"item '{iid}' defined in multiple datasets — using {items_by_id[iid].dataset_name}",
                )
                continue
            items_by_id[iid] = item_model

    # 2. Filesystem datasets (reuse existing loader for Q7 consistency)
    datasets_dir = feature_dir / "datasets"
    if datasets_dir.exists():
        fs_datasets: dict[str, Dataset] = load_all_datasets(str(datasets_dir))
        for ds_name, ds in fs_datasets.items():
            for item in ds.items:
                if item.id in items_by_id:
                    existing = items_by_id[item.id]
                    if existing.source != "design_inline":
                        report.warn(
                            path_str,
                            f"item '{item.id}' defined in multiple datasets — "
                            f"using {existing.dataset_name}",
                        )
                    # design-inline wins on collision per Q12 — skip
                    continue
                effective = ds.effective_specs(item)
                # mock_context_summary MAY exist in filesystem items as a leftover
                # data field, but synthesize-phase items use _mock_context instead.
                # Extract from data dict if present; otherwise empty.
                mcs_raw = item.data.get("mock_context_summary", {})
                mcs = _coerce_mock_context_summary(mcs_raw)
                items_by_id[item.id] = ItemModel(
                    id=item.id,
                    dataset_name=ds_name,
                    source="manifest",
                    mock_context_summary=mcs,
                    effective_specs=[_build_judge_spec_model(s) for s in effective],
                )

    # 3. tool_coverage[]
    tool_coverage: list[ToolCoverageModel] = []
    tc_raw = raw.get("tool_coverage", [])
    if tc_raw is not None and not isinstance(tc_raw, list):
        report.error(path_str, "tool_coverage must be a list")
        tc_raw = []
    for ci, entry in enumerate(tc_raw or []):
        loc = f"{path_str} tool_coverage[{ci}]"
        if not isinstance(entry, dict):
            report.error(loc, "tool_coverage entry must be a mapping")
            continue
        tool_id = entry.get("tool_id")
        if not isinstance(tool_id, str) or not tool_id:
            report.error(loc, "tool_id is required and must be a non-empty string")
            continue
        dims_raw = entry.get("dimensions_covered", {})
        if not isinstance(dims_raw, dict):
            report.error(loc, "dimensions_covered must be a mapping")
            continue
        dims_clean: dict[str, list[str]] = {}
        dims_ok = True
        for dname, dvalue in dims_raw.items():
            if not isinstance(dvalue, list) or not all(isinstance(x, str) for x in dvalue):
                report.error(loc, f"dimensions_covered.{dname} must be a list of strings")
                dims_ok = False
                continue
            dims_clean[dname] = list(dvalue)
        if not dims_ok:
            continue
        tool_coverage.append(ToolCoverageModel(
            tool_id=tool_id,
            dimensions_covered=dims_clean,
            raw_path=loc,
        ))

    return DesignModel(
        tool_coverage=tool_coverage,
        items_by_id=items_by_id,
        raw_path=path_str,
    )


def _build_item_model(
    iid: str,
    dataset_name: str,
    source: str,
    item_raw: dict,
    manifest_specs: list[dict],
) -> ItemModel:
    # Q7 full-replacement precedence: item _judge_specs (if non-empty) replace
    # manifest judge_specs entirely.
    item_specs = _coerce_spec_list(item_raw.get("_judge_specs", []))
    effective = item_specs if item_specs else manifest_specs
    mcs_raw = item_raw.get("mock_context_summary", {})
    mcs = _coerce_mock_context_summary(mcs_raw)
    return ItemModel(
        id=iid,
        dataset_name=dataset_name,
        source=source,
        mock_context_summary=mcs,
        effective_specs=[_build_judge_spec_model(s) for s in effective],
    )


def _coerce_spec_list(x: Any) -> list[dict]:
    if isinstance(x, list):
        return [s for s in x if isinstance(s, dict)]
    return []


def _coerce_mock_context_summary(x: Any) -> dict[str, str]:
    if not isinstance(x, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in x.items():
        if isinstance(k, str) and isinstance(v, str):
            out[k] = v
    return out


def _build_judge_spec_model(raw: dict) -> JudgeSpecModel:
    method = raw.get("method") if isinstance(raw.get("method"), str) else None
    rule = raw.get("rule") if isinstance(raw.get("rule"), str) else None

    target = raw.get("target")
    target_step_type: str | None = None
    target_output = False
    if isinstance(target, dict):
        st = target.get("step_type")
        if isinstance(st, str):
            target_step_type = st
    elif isinstance(target, str):
        if target == "output":
            target_output = True
    else:
        # target key absent → treated as "output" per Q6 (only meaningful for llm specs)
        target_output = True

    args = raw.get("args") if isinstance(raw.get("args"), dict) else {}
    args_tool_name = args.get("tool_name") if isinstance(args.get("tool_name"), str) else None
    args_field_present = "field" in args
    args_expected = args.get("expected")

    trap = raw.get("trap_design")
    trap_design_nonempty = isinstance(trap, str) and len(trap) > 0

    return JudgeSpecModel(
        method=method,
        rule=rule,
        target_step_type=target_step_type,
        target_output=target_output,
        args_tool_name=args_tool_name,
        args_field_present=args_field_present,
        args_expected=args_expected,
        trap_design_nonempty=trap_design_nonempty,
    )


# ---------------------------------------------------------------------------
# Rule 7 mechanical check — stub for Task 3; filled in Tasks 4-6
# ---------------------------------------------------------------------------


def _run_rule_7(
    analysis: AnalysisModel,
    design: DesignModel,
    report: ValidationReport,
) -> None:
    """Mechanical check ported from 07-agent-tools.md §Mechanical Check.

    Filled in incrementally across Tasks 4, 5, 6.
    """
    # Task 4 adds check (a) — item existence
    # Task 5 adds check (b) — spec pattern match
    # Task 6 adds check (c) — output_handling multi-item constraint
    pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_validate_agent.py -v`
Expected: PASS. `test_design_inline_dataset_items_resolved` passes because `_run_rule_7` is still a stub. The model extraction tests pass against `_build_judge_spec_model`.

- [ ] **Step 5: Run full suite**

Run: `python -m pytest tests/ -v`
Expected: all existing tests pass; no regressions.

- [ ] **Step 6: Commit**

```bash
git add src/vibeval/validate_design.py tests/test_validate_agent.py
git commit -m "$(cat <<'EOF'
validate: add DesignModel and load_design with item flattening

New module loads design.yaml, parses inline datasets and merges with
filesystem datasets from load_all_datasets(), and produces a typed
DesignModel with a flattened items_by_id map.

- Inline datasets win over filesystem on id collisions (Q12), with a
  warning emitted.
- Item-level _judge_specs replace manifest judge_specs (Q7 full
  replacement, matching src/vibeval/dataset.py:40-42 runtime).
- JudgeSpecModel extracts only the Allowed Spec Pattern fields:
  method, rule, target.step_type, target == "output" or absent,
  args.tool_name, args.field presence, args.expected, trap_design
  presence + non-empty.

Q3: design.yaml absent + execution_mode "agent" → warn; otherwise
silent. _run_rule_7() is a stub; Tasks 4-6 add the actual checks.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Rule 7 check (a) — item existence

**Files:**
- Modify: `src/vibeval/validate_design.py` — expand `_run_rule_7` to implement check (a)
- Modify: `tests/test_validate_agent.py` — add check-(a) tests

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_validate_agent.py`:

```python
# --- Rule 7 check (a) — item existence --------------------------------------

def test_design_missing_tool_coverage_entry_for_tool_errors(tmp_path: Path) -> None:
    feature, analysis = make_agent_feature(tmp_path, design_yaml="""
        datasets: []
        tool_coverage: []
    """)
    report = ValidationReport()
    validate_design(feature, analysis, report)
    assert any(
        "no tool_coverage entry for tool 'search_documents'" in m
        for m in error_messages(report)
    )


def test_design_mandatory_dim_empty_list_errors(tmp_path: Path) -> None:
    feature, analysis = make_agent_feature(tmp_path, design_yaml="""
        datasets: []
        tool_coverage:
          - tool_id: "search_documents"
            dimensions_covered:
              positive_selection: []
              negative_selection: []
              disambiguation: []
              argument_fidelity: []
              output_handling: []
    """)
    report = ValidationReport()
    validate_design(feature, analysis, report)
    msgs = error_messages(report)
    for dim in ("positive_selection", "negative_selection",
                "disambiguation", "argument_fidelity", "output_handling"):
        assert any(f"dimension '{dim}' has no items listed" in m for m in msgs), \
            f"missing error for {dim} in {msgs}"


def test_design_unknown_item_id_errors_check_a(tmp_path: Path) -> None:
    feature, analysis = make_agent_feature(tmp_path, design_yaml="""
        datasets: []
        tool_coverage:
          - tool_id: "search_documents"
            dimensions_covered:
              positive_selection: ["ghost"]
              negative_selection: ["ghost"]
              disambiguation: ["ghost"]
              argument_fidelity: ["ghost"]
              output_handling: ["ghost1", "ghost2"]
    """)
    report = ValidationReport()
    validate_design(feature, analysis, report)
    msgs = error_messages(report)
    # At least one "not found in any dataset" error per referenced id
    assert any("item 'ghost' not found in any dataset" in m for m in msgs)
    assert any("item 'ghost1' not found in any dataset" in m for m in msgs)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_validate_agent.py -v -k "rule_7 or not_found or empty_list or no_tool_coverage"`
Expected: FAIL — `_run_rule_7` stub produces no errors yet.

- [ ] **Step 3: Implement check (a)**

Replace the stub `_run_rule_7` in `src/vibeval/validate_design.py` with:

```python
def _run_rule_7(
    analysis: AnalysisModel,
    design: DesignModel,
    report: ValidationReport,
) -> None:
    """Mechanical check ported from 07-agent-tools.md §Mechanical Check."""
    coverage_by_id = {c.tool_id: c for c in design.tool_coverage}

    for tool in analysis.tools:
        coverage = coverage_by_id.get(tool.id)
        if coverage is None:
            report.error(
                design.raw_path,
                f"no tool_coverage entry for tool '{tool.id}'",
            )
            continue

        mandatory = list(MANDATORY_DIMENSIONS)
        if tool.type == "subagent":
            mandatory.append("subagent_delegation")

        for dim in mandatory:
            item_ids = coverage.dimensions_covered.get(dim, [])
            if not item_ids:
                report.error(
                    coverage.raw_path,
                    f"tool '{tool.id}' dimension '{dim}' has no items listed",
                )
                continue
            for item_id in item_ids:
                item = design.items_by_id.get(item_id)
                if item is None:
                    report.error(
                        coverage.raw_path,
                        f"tool '{tool.id}' dim '{dim}' item '{item_id}' "
                        f"not found in any dataset",
                    )
                    continue
                # Check (b) is added in Task 5
                # Check (c) is added in Task 6 as a post-loop

        # Conditional sequence dimension — Q8, never required; structurally
        # checked only when listed.
        seq_ids = coverage.dimensions_covered.get("sequence", [])
        for item_id in seq_ids:
            item = design.items_by_id.get(item_id)
            if item is None:
                report.error(
                    coverage.raw_path,
                    f"tool '{tool.id}' dim 'sequence' item '{item_id}' "
                    f"not found in any dataset",
                )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_validate_agent.py -v`
Expected: all check-(a) tests PASS. Existing happy-path test `test_design_inline_dataset_items_resolved` still passes because all referenced items exist.

- [ ] **Step 5: Commit**

```bash
git add src/vibeval/validate_design.py tests/test_validate_agent.py
git commit -m "$(cat <<'EOF'
validate: implement Rule 7 check (a) — item existence

For every (tool_id, dimension, item_id) triple in
tool_coverage[].dimensions_covered:
- missing tool_coverage entry → error
- empty dimension list (mandatory dim) → error
- unknown item_id → error ("not found in any dataset")
- sequence dimension (Q8): not required, but structurally checked when
  listed — unknown sequence item_ids still flagged

subagent_delegation is added to the mandatory set when tool.type ==
"subagent" (Q9). Check (b) stub remains — added in the next task.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Rule 7 check (b) — spec pattern match per dimension

**Files:**
- Modify: `src/vibeval/validate_design.py` — add `_any_spec_matches` + wire into `_run_rule_7`
- Modify: `tests/test_validate_agent.py` — add pattern-match tests (one per dimension, positive + negative)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_validate_agent.py`:

```python
# --- Rule 7 check (b) — spec pattern match ---------------------------------

def _design_with_item(item_yaml: str, dim: str, item_id: str) -> str:
    """Build a design.yaml that lists `item_id` under one dimension
    (filling the others with pass-through items) so a single-dimension
    pattern-match failure can be isolated."""
    return f"""
    datasets:
      - name: "ds"
        items:
{textwrap.indent(item_yaml, "          ")}
          - id: "filler_pos"
            data: {{}}
            _judge_specs:
              - method: rule
                rule: tool_called
                args: {{tool_name: "search_documents"}}
          - id: "filler_neg"
            data: {{}}
            _judge_specs:
              - method: rule
                rule: tool_not_called
                args: {{tool_name: "search_documents"}}
          - id: "filler_disambig"
            data: {{}}
            _judge_specs:
              - method: llm
                scoring: binary
                target: {{step_type: "tool_call"}}
                criteria: "x"
                trap_design: "t"
          - id: "filler_argfid"
            data: {{}}
            _judge_specs:
              - method: llm
                scoring: binary
                target: {{step_type: "tool_call"}}
                criteria: "x"
          - id: "filler_oh_a"
            data: {{}}
            mock_context_summary:
              "app.tools.search_documents": "returns empty"
            _judge_specs:
              - method: llm
                scoring: binary
                target: "output"
                criteria: "x"
          - id: "filler_oh_b"
            data: {{}}
            mock_context_summary:
              "app.tools.search_documents": "returns error"
            _judge_specs:
              - method: llm
                scoring: binary
                target: "output"
                criteria: "x"

    tool_coverage:
      - tool_id: "search_documents"
        dimensions_covered:
          positive_selection: ["{_pick(dim, item_id, 'filler_pos')}"]
          negative_selection: ["{_pick(dim, item_id, 'filler_neg')}"]
          disambiguation: ["{_pick(dim, item_id, 'filler_disambig')}"]
          argument_fidelity: ["{_pick(dim, item_id, 'filler_argfid')}"]
          output_handling: ["{_pick(dim, item_id, 'filler_oh_a')}", "filler_oh_b"]
    """


def _pick(dim: str, item_id: str, filler: str) -> str:
    """If `filler` belongs to the target dimension, return item_id; else filler."""
    mapping = {
        "filler_pos": "positive_selection",
        "filler_neg": "negative_selection",
        "filler_disambig": "disambiguation",
        "filler_argfid": "argument_fidelity",
        "filler_oh_a": "output_handling",
    }
    return item_id if mapping.get(filler) == dim else filler


# Positive selection — negative test

def test_design_positive_selection_spec_pattern_mismatch_errors(tmp_path: Path) -> None:
    item = """
    - id: "bad_pos"
      data: {}
      _judge_specs:
        - method: rule
          rule: tool_called
          args: {tool_name: "wrong_name"}
    """
    feature, analysis = make_agent_feature(
        tmp_path, design_yaml=_design_with_item(item, "positive_selection", "bad_pos")
    )
    report = ValidationReport()
    validate_design(feature, analysis, report)
    assert any(
        "item 'bad_pos' has no judge_spec matching the Allowed Pattern for 'positive_selection'" in m
        for m in error_messages(report)
    )


def test_design_negative_selection_pattern_mismatch_errors(tmp_path: Path) -> None:
    item = """
    - id: "bad_neg"
      data: {}
      _judge_specs:
        - method: rule
          rule: tool_called
          args: {tool_name: "search_documents"}
    """
    feature, analysis = make_agent_feature(
        tmp_path, design_yaml=_design_with_item(item, "negative_selection", "bad_neg")
    )
    report = ValidationReport()
    validate_design(feature, analysis, report)
    assert any(
        "'negative_selection'" in m for m in error_messages(report)
    )


def test_design_disambiguation_missing_trap_design_errors(tmp_path: Path) -> None:
    item = """
    - id: "bad_disambig"
      data: {}
      _judge_specs:
        - method: llm
          scoring: binary
          target: {step_type: "tool_call"}
          criteria: "x"
    """
    feature, analysis = make_agent_feature(
        tmp_path, design_yaml=_design_with_item(item, "disambiguation", "bad_disambig")
    )
    report = ValidationReport()
    validate_design(feature, analysis, report)
    assert any("'disambiguation'" in m for m in error_messages(report))


def test_design_disambiguation_wrong_target_step_type_errors(tmp_path: Path) -> None:
    item = """
    - id: "bad_disambig2"
      data: {}
      _judge_specs:
        - method: llm
          scoring: binary
          target: {step_type: "ai_call"}
          criteria: "x"
          trap_design: "t"
    """
    feature, analysis = make_agent_feature(
        tmp_path, design_yaml=_design_with_item(item, "disambiguation", "bad_disambig2")
    )
    report = ValidationReport()
    validate_design(feature, analysis, report)
    assert any("'disambiguation'" in m for m in error_messages(report))


def test_design_disambiguation_string_target_rejected(tmp_path: Path) -> None:
    item = """
    - id: "bad_disambig3"
      data: {}
      _judge_specs:
        - method: llm
          scoring: binary
          target: "tool_call"
          criteria: "x"
          trap_design: "t"
    """
    feature, analysis = make_agent_feature(
        tmp_path, design_yaml=_design_with_item(item, "disambiguation", "bad_disambig3")
    )
    report = ValidationReport()
    validate_design(feature, analysis, report)
    assert any("'disambiguation'" in m for m in error_messages(report))


def test_design_argument_fidelity_llm_form_passes(tmp_path: Path) -> None:
    feature, analysis = make_agent_feature(tmp_path, design_yaml=FULL_COVERAGE_DESIGN)
    report = ValidationReport()
    validate_design(feature, analysis, report)
    # FULL_COVERAGE_DESIGN uses llm target=tool_call for argfid_item — must pass
    assert not any("'argument_fidelity'" in m for m in error_messages(report))


def test_design_argument_fidelity_rule_equals_with_field_passes(tmp_path: Path) -> None:
    item = """
    - id: "eq_argfid"
      data: {}
      _judge_specs:
        - method: rule
          rule: equals
          args: {field: "outputs.query", expected: "X"}
    """
    feature, analysis = make_agent_feature(
        tmp_path, design_yaml=_design_with_item(item, "argument_fidelity", "eq_argfid")
    )
    report = ValidationReport()
    validate_design(feature, analysis, report)
    assert not any("'argument_fidelity'" in m for m in error_messages(report))


def test_design_argument_fidelity_rule_matches_with_field_passes(tmp_path: Path) -> None:
    item = """
    - id: "re_argfid"
      data: {}
      _judge_specs:
        - method: rule
          rule: matches
          args: {field: "outputs.query", pattern: "^X"}
    """
    feature, analysis = make_agent_feature(
        tmp_path, design_yaml=_design_with_item(item, "argument_fidelity", "re_argfid")
    )
    report = ValidationReport()
    validate_design(feature, analysis, report)
    assert not any("'argument_fidelity'" in m for m in error_messages(report))


def test_design_argument_fidelity_rule_contains_rejected(tmp_path: Path) -> None:
    # Q4: strict whitelist — contains does NOT count.
    item = """
    - id: "bad_argfid"
      data: {}
      _judge_specs:
        - method: rule
          rule: contains
          args: {field: "outputs.query", value: "X"}
    """
    feature, analysis = make_agent_feature(
        tmp_path, design_yaml=_design_with_item(item, "argument_fidelity", "bad_argfid")
    )
    report = ValidationReport()
    validate_design(feature, analysis, report)
    assert any("'argument_fidelity'" in m for m in error_messages(report))


def test_design_argument_fidelity_rule_equals_without_field_errors(tmp_path: Path) -> None:
    item = """
    - id: "bad_argfid2"
      data: {}
      _judge_specs:
        - method: rule
          rule: equals
          args: {expected: "X"}
    """
    feature, analysis = make_agent_feature(
        tmp_path, design_yaml=_design_with_item(item, "argument_fidelity", "bad_argfid2")
    )
    report = ValidationReport()
    validate_design(feature, analysis, report)
    assert any("'argument_fidelity'" in m for m in error_messages(report))


def test_design_output_handling_missing_mock_context_summary_key_errors(tmp_path: Path) -> None:
    item = """
    - id: "bad_oh"
      data: {}
      _judge_specs:
        - method: llm
          scoring: binary
          target: "output"
          criteria: "x"
    """
    feature, analysis = make_agent_feature(
        tmp_path, design_yaml=_design_with_item(item, "output_handling", "bad_oh")
    )
    report = ValidationReport()
    validate_design(feature, analysis, report)
    assert any("'output_handling'" in m for m in error_messages(report))


def test_design_output_handling_dict_target_rejected(tmp_path: Path) -> None:
    # Q6: strict string-or-absent; dict form not accepted.
    item = """
    - id: "dict_oh"
      data: {}
      mock_context_summary:
        "app.tools.search_documents": "returns something"
      _judge_specs:
        - method: llm
          scoring: binary
          target: {step_type: "output"}
          criteria: "x"
    """
    feature, analysis = make_agent_feature(
        tmp_path, design_yaml=_design_with_item(item, "output_handling", "dict_oh")
    )
    report = ValidationReport()
    validate_design(feature, analysis, report)
    assert any("'output_handling'" in m for m in error_messages(report))


def test_design_happy_path_all_dimensions_pass(tmp_path: Path) -> None:
    feature, analysis = make_agent_feature(tmp_path, design_yaml=FULL_COVERAGE_DESIGN)
    report = ValidationReport()
    validate_design(feature, analysis, report)
    assert error_messages(report) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_validate_agent.py -v`
Expected: the new pattern-match tests fail because `_run_rule_7` does not yet call `_any_spec_matches`.

- [ ] **Step 3: Implement check (b)**

In `src/vibeval/validate_design.py`, add `_any_spec_matches` above `_run_rule_7`:

```python
def _any_spec_matches(item: ItemModel, dim: str, tool: ToolModel) -> bool:
    """One row per dimension from 07-agent-tools.md §Allowed Spec Patterns."""
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
            # target: "output" (string) or target key absent, AND the item
            # must have a mock_context_summary entry keyed by tool.mock_target.
            if (spec.method == "llm" and spec.target_output
                    and spec.target_step_type is None
                    and tool.mock_target in item.mock_context_summary):
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

In `_run_rule_7`, inside the existing item loop, add the pattern-match call where Task 4 left a comment:

```python
            for item_id in item_ids:
                item = design.items_by_id.get(item_id)
                if item is None:
                    report.error(
                        coverage.raw_path,
                        f"tool '{tool.id}' dim '{dim}' item '{item_id}' "
                        f"not found in any dataset",
                    )
                    continue
                if not _any_spec_matches(item, dim, tool):
                    report.error(
                        coverage.raw_path,
                        f"tool '{tool.id}' dim '{dim}' item '{item_id}' "
                        f"has no judge_spec matching the Allowed Pattern for '{dim}'",
                    )
```

Also in the `sequence` conditional loop, add the same call for sequence:

```python
        seq_ids = coverage.dimensions_covered.get("sequence", [])
        for item_id in seq_ids:
            item = design.items_by_id.get(item_id)
            if item is None:
                report.error(
                    coverage.raw_path,
                    f"tool '{tool.id}' dim 'sequence' item '{item_id}' "
                    f"not found in any dataset",
                )
                continue
            if not _any_spec_matches(item, "sequence", tool):
                report.error(
                    coverage.raw_path,
                    f"tool '{tool.id}' dim 'sequence' item '{item_id}' "
                    f"has no judge_spec matching the Allowed Pattern for 'sequence'",
                )
```

**Important edge case in `_build_judge_spec_model`:** `target_output = True` when the target key is absent. For RULE specs (e.g., `rule: tool_called`), this is meaningless because the `output_handling` matcher also requires `method == "llm"`. So the defaults don't pollute rule specs. Verified during test writing.

**Also:** the `output_handling` matcher must reject `target: {step_type: "output"}` dict form per Q6. The extra guard `spec.target_step_type is None` ensures this — when target is a dict, `target_step_type` gets set (to "output" or whatever), and `target_output` is False, so the matcher will not return True on that case.

Wait — if target is `{step_type: "output"}`, `target_step_type` becomes `"output"` and `target_output` stays False. The output_handling guard `spec.target_output and spec.target_step_type is None` correctly rejects this.

If target is absent entirely, `target_step_type is None` and `target_output is True` — the guard accepts. Correct per Q6.

If target is `"output"` string, `target_step_type is None` and `target_output is True` — accepted. Correct.

If target is `{step_type: "tool_call"}`, `target_step_type is "tool_call"` and `target_output is False` — rejected for output_handling. Correct.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_validate_agent.py -v`
Expected: all tests pass, including the new pattern-match suite and the happy path.

- [ ] **Step 5: Run full suite**

Run: `python -m pytest tests/ -v`
Expected: all existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/vibeval/validate_design.py tests/test_validate_agent.py
git commit -m "$(cat <<'EOF'
validate: implement Rule 7 check (b) — spec pattern match per dimension

_any_spec_matches(item, dim, tool) encodes the Allowed Spec Patterns
table from 07-agent-tools.md. One case per dimension. Structural field
comparison only — no interpretation of criteria, test_intent, or any
prose field.

Dimension-by-dimension rules:
- positive_selection: method=rule, rule=tool_called, args.tool_name ==
  tool.surface.name
- negative_selection: same as positive but with rule=tool_not_called
- disambiguation: method=llm, target={step_type: tool_call},
  trap_design present + non-empty (Q5: dict form only)
- argument_fidelity: method=llm with tool_call target, OR method=rule
  with rule in {equals, matches} and args.field present (Q4 strict
  whitelist — contains rejected)
- output_handling: method=llm, target=="output" string OR target
  absent, AND item.mock_context_summary has key tool.mock_target
  (Q6 string-or-absent, dict form rejected)
- sequence: method=rule, rule=tool_sequence, args.expected is a list
  containing tool.surface.name
- subagent_delegation: method=llm, target={step_type: tool_call}

Each failure emits a distinct error with the exact (tool_id, dim,
item_id) triple so users can jump to the offending line.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Rule 7 check (c) — `output_handling` multi-item constraint

**Files:**
- Modify: `src/vibeval/validate_design.py` — add check (c) after the dimension loop
- Modify: `tests/test_validate_agent.py` — add check-(c) tests

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_validate_agent.py`:

```python
# --- Rule 7 check (c) — output_handling multi-item constraint --------------

def test_design_output_handling_single_item_errors_check_c(tmp_path: Path) -> None:
    feature, analysis = make_agent_feature(tmp_path, design_yaml="""
        datasets:
          - name: "ds"
            items:
              - id: "pos"
                data: {}
                _judge_specs:
                  - method: rule
                    rule: tool_called
                    args: {tool_name: "search_documents"}
              - id: "neg"
                data: {}
                _judge_specs:
                  - method: rule
                    rule: tool_not_called
                    args: {tool_name: "search_documents"}
              - id: "dis"
                data: {}
                _judge_specs:
                  - method: llm
                    scoring: binary
                    target: {step_type: "tool_call"}
                    criteria: "x"
                    trap_design: "t"
              - id: "arg"
                data: {}
                _judge_specs:
                  - method: llm
                    scoring: binary
                    target: {step_type: "tool_call"}
                    criteria: "x"
              - id: "oh_only"
                data: {}
                mock_context_summary:
                  "app.tools.search_documents": "returns empty"
                _judge_specs:
                  - method: llm
                    scoring: binary
                    target: "output"
                    criteria: "x"

        tool_coverage:
          - tool_id: "search_documents"
            dimensions_covered:
              positive_selection: ["pos"]
              negative_selection: ["neg"]
              disambiguation: ["dis"]
              argument_fidelity: ["arg"]
              output_handling: ["oh_only"]
    """)
    report = ValidationReport()
    validate_design(feature, analysis, report)
    assert any(
        "output_handling must span >=2 items, found 1" in m
        for m in error_messages(report)
    )


def test_design_output_handling_two_items_byte_equal_summaries_errors(tmp_path: Path) -> None:
    design = FULL_COVERAGE_DESIGN.replace(
        "returns HTTP 429 error",
        "returns empty result list",  # both items now have identical summaries
    )
    feature, analysis = make_agent_feature(tmp_path, design_yaml=design)
    report = ValidationReport()
    validate_design(feature, analysis, report)
    assert any(
        "mock_context_summary" in m and "byte-equal" in m
        for m in error_messages(report)
    )


def test_design_output_handling_two_items_all_empty_summaries_errors(tmp_path: Path) -> None:
    design = FULL_COVERAGE_DESIGN.replace(
        '"returns empty result list"', '""'
    ).replace(
        '"returns HTTP 429 error"', '""'
    )
    feature, analysis = make_agent_feature(tmp_path, design_yaml=design)
    report = ValidationReport()
    validate_design(feature, analysis, report)
    # Empty strings are excluded from the distinct-count (Q10), so effectively
    # zero distinct non-empty summaries → error.
    assert any(
        "byte-equal" in m or "empty" in m
        for m in error_messages(report)
    )


def test_design_output_handling_two_items_distinct_summaries_passes(tmp_path: Path) -> None:
    feature, analysis = make_agent_feature(tmp_path, design_yaml=FULL_COVERAGE_DESIGN)
    report = ValidationReport()
    validate_design(feature, analysis, report)
    assert error_messages(report) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_validate_agent.py -v -k "output_handling and (single_item or byte_equal or all_empty)"`
Expected: FAIL — check (c) not yet implemented.

- [ ] **Step 3: Implement check (c)**

In `src/vibeval/validate_design.py`, inside `_run_rule_7`, after the `mandatory` dimension loop and before the `sequence` loop, add:

```python
        # Check (c) — output_handling multi-item constraint
        oh_ids = coverage.dimensions_covered.get("output_handling", [])
        oh_items = [design.items_by_id[i] for i in oh_ids if i in design.items_by_id]
        if oh_ids and len(oh_items) < 2:
            report.error(
                coverage.raw_path,
                f"tool '{tool.id}' output_handling must span >=2 items, "
                f"found {len(oh_items)}",
            )
        elif len(oh_items) >= 2:
            summaries = [
                item.mock_context_summary.get(tool.mock_target, "")
                for item in oh_items
            ]
            distinct_nonempty = {s for s in summaries if s}
            if len(distinct_nonempty) < 2:
                report.error(
                    coverage.raw_path,
                    f"tool '{tool.id}' output_handling: "
                    f"mock_context_summary['{tool.mock_target}'] values "
                    f"are all empty or byte-equal; need >=2 distinct",
                )
```

Note: the check only triggers when at least one item_id is listed under `output_handling`. If the dimension list is empty, that's already flagged by check (a)'s "no items listed" error and we don't want a duplicate.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_validate_agent.py -v`
Expected: all tests pass. Happy path still green.

- [ ] **Step 5: Run full suite**

Run: `python -m pytest tests/ -v`
Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/vibeval/validate_design.py tests/test_validate_agent.py
git commit -m "$(cat <<'EOF'
validate: implement Rule 7 check (c) — output_handling multi-item

For every tool with a non-empty output_handling list:
- count resolved items; fewer than 2 → error
- collect mock_context_summary[<tool.mock_target>] values; count of
  distinct non-empty strings < 2 → error

Empty strings are excluded from the distinct set (Q10): two empty
strings do not satisfy the constraint. This catches copy-pasted mock
summaries ("same summary reused across items") without asking the
evaluator to judge whether two scenarios are "semantically different
enough" — the check is pure byte comparison.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Wire `validate_analysis` + `validate_design` into `validate_feature`

**Files:**
- Modify: `src/vibeval/validate.py` — add two calls at the top of `validate_feature()`
- Modify: `tests/test_validate_agent.py` — add integration tests through `validate_feature`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_validate_agent.py`:

```python
# ========================================================================
# Integration tests through validate_feature
# ========================================================================

from vibeval.validate import validate_feature


def test_validate_feature_non_agent_feature_runs_existing_checks_only(tmp_path: Path) -> None:
    feature = make_feature(tmp_path, analysis_yaml="""
        project:
          name: foo
          execution_mode: "non_agent"
    """)
    # No datasets, no design — should exit OK (with a warning about missing datasets/)
    report = validate_feature(str(feature))
    assert error_messages(report) == []


def test_validate_feature_agent_feature_with_full_coverage_exit_zero(tmp_path: Path) -> None:
    feature, _ = make_agent_feature(tmp_path, design_yaml=FULL_COVERAGE_DESIGN)
    report = validate_feature(str(feature))
    assert error_messages(report) == [], error_messages(report)


def test_validate_feature_agent_feature_with_broken_coverage_exit_nonzero(tmp_path: Path) -> None:
    broken = FULL_COVERAGE_DESIGN.replace('tool_name: "search_documents"', 'tool_name: "wrong"')
    feature, _ = make_agent_feature(tmp_path, design_yaml=broken)
    report = validate_feature(str(feature))
    assert len(report.errors) > 0
    assert any("'positive_selection'" in m for m in error_messages(report))


def test_validate_feature_missing_analysis_runs_existing_checks_silently(tmp_path: Path) -> None:
    # No analysis/, no design/, no datasets/, no results/ — legacy empty feature
    feature = tmp_path / "legacy"
    feature.mkdir()
    report = validate_feature(str(feature))
    # No errors; one warning about missing datasets/
    assert error_messages(report) == []
    assert any("No datasets/" in m for m in warning_messages(report))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_validate_agent.py::test_validate_feature_agent_feature_with_full_coverage_exit_zero -v`
Expected: FAIL — `validate_feature` doesn't yet call the new validators, so happy path may pass trivially but broken-coverage test will NOT produce errors because the Agent checks aren't wired.

- [ ] **Step 3: Wire the new validators into `validate_feature`**

In `src/vibeval/validate.py`, modify `validate_feature` (current lines 86-107):

```python
def validate_feature(feature_dir: str | Path) -> ValidationReport:
    """Validate all artifacts for a feature."""
    report = ValidationReport()
    feature_dir = Path(feature_dir)

    if not feature_dir.exists():
        report.error(str(feature_dir), "Feature directory does not exist")
        return report

    # Agent features: analysis.yaml and design.yaml
    # (Imports are local to avoid circular imports since validate_analysis and
    # validate_design import ValidationReport from this module.)
    from .validate_analysis import validate_analysis
    from .validate_design import validate_design
    analysis = validate_analysis(feature_dir, report)
    validate_design(feature_dir, analysis, report)

    # Datasets
    datasets_dir = feature_dir / "datasets"
    if datasets_dir.exists():
        _validate_datasets(datasets_dir, report)
    else:
        report.warn(str(feature_dir), "No datasets/ directory found")

    # Results
    results_dir = feature_dir / "results"
    if results_dir.exists():
        _validate_results(results_dir, report)

    return report
```

The only changes are the two new lines after the `if not feature_dir.exists()` guard.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_validate_agent.py -v`
Expected: all new integration tests pass.

- [ ] **Step 5: Run full suite — CRITICAL regression check**

Run: `python -m pytest tests/ -v`
Expected: all existing tests in `tests/test_validate.py` still pass. No regression on the datasets/results walks, the Issue/ValidationReport structure, or the CLI command wiring.

- [ ] **Step 6: Commit**

```bash
git add src/vibeval/validate.py tests/test_validate_agent.py
git commit -m "$(cat <<'EOF'
validate: wire validate_analysis + validate_design into validate_feature

validate_feature now calls validate_analysis (which may return None)
and then validate_design (passing the analysis through) BEFORE the
existing datasets/ and results/ walks. All four contribute to the
same ValidationReport. Exit code 0 iff every layer reports zero
errors.

Integration tests cover: non-agent features pass existing checks,
agent features with full coverage exit 0, agent features with broken
coverage exit non-zero, and legacy feature directories with no
analysis/ still validate cleanly (silent skip per Q3).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Extend `vibeval validate` `--help` description

**Files:**
- Modify: `src/vibeval/cli.py` — extend the `p_validate` description string

- [ ] **Step 1: Locate and update the description**

Open `src/vibeval/cli.py`, find the `p_validate = sub.add_parser(...)` block (around line 91). Replace the `description` string with the following (keep `help=` unchanged):

```python
    p_validate = sub.add_parser("validate",
        help="Validate analysis, design, datasets, and results against the vibeval protocol",
        description="Check all artifacts for a feature against the vibeval protocol format. "
                    "Catches structural issues that would cause judge/compare/summary to fail "
                    "at runtime and enforces the strengthened tool_coverage invariant from "
                    "plugin/protocol/references/07-agent-tools.md.\n\n"
                    "Validates:\n"
                    "  * analysis.yaml — project.execution_mode and tools[] schema (Agent features)\n"
                    "  * design.yaml — tool_coverage[] cross-reference + Rule 7 mechanical check:\n"
                    "    item existence, Allowed Spec Patterns per dimension, and the\n"
                    "    output_handling multi-item constraint on mock_context_summary\n"
                    "  * datasets — manifest structure, judge_spec fields (rule names, args, "
                    "scoring, anchors, calibrations), data item reserved fields "
                    "(_id, _tags, _judge_specs, _mock_context)\n"
                    "  * results — trace format (turns, steps), result files, and cross-references "
                    "(values_from/expected_from pointing to existing item fields)\n\n"
                    "Analysis and design checks are skipped silently when the respective files are "
                    "absent; the CLI is tolerant of mid-workflow states where the feature has only "
                    "been analyzed but not designed yet.\n\n"
                    "Exit code 0 if no errors, 1 if errors found.")
    p_validate.add_argument("feature", help="Feature name to validate")
```

- [ ] **Step 2: Verify the help output**

Run: `python -m vibeval validate --help`
Expected: the new description is printed. Should mention "analysis.yaml", "design.yaml", "Rule 7 mechanical check", and "output_handling multi-item constraint".

Run: `python -m vibeval validate --help | grep -c "analysis.yaml"`
Expected: ≥1.

- [ ] **Step 3: Run full suite**

Run: `python -m pytest tests/ -v`
Expected: all tests still green. This is a docs-only change but we run the suite as a sanity check.

- [ ] **Step 4: Commit**

```bash
git add src/vibeval/cli.py
git commit -m "$(cat <<'EOF'
cli: extend validate --help description to cover analysis + design

Per CLAUDE.md principle #3, CLI --help is the single source of truth
for command documentation. Describe the new analysis.yaml and design.yaml
coverage, the Rule 7 mechanical check, and the file-absence semantics
(mid-workflow features validate cleanly).

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Code review, merge, release (0.7.0)

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `pyproject.toml`
- Modify: `plugin/plugin.json`
- Modify: `src/vibeval/__init__.py`

- [ ] **Step 1: Request final holistic code review**

Run the `superpowers:code-reviewer` subagent over the full branch diff:

```
git diff main...feat/cli-full-validation --stat
git diff main...feat/cli-full-validation
```

Ask the reviewer to check:
- Every row of the `Allowed Spec Patterns` table in `plugin/protocol/references/07-agent-tools.md` has a corresponding case in `_any_spec_matches`.
- Every error message in the spec's Error Taxonomy (rows 1–18) is emitted by the code.
- Every test name in the spec's Test Plan exists in `tests/test_validate_agent.py`.
- `_run_rule_7` is a pure function of its inputs — no hidden globals.
- No prose interpretation anywhere (`criteria`, `test_intent`, `description` are never read).

Fix any findings as additional commits on the same branch, with "review:" prefix. Re-run `python -m pytest tests/ -v` after each fix.

- [ ] **Step 2: Ask the user for explicit merge authorization**

STOP here and ask the user: "All tasks complete, tests green, review addressed. Ready to merge `feat/cli-full-validation` into main with `--no-ff`?"

Wait for explicit approval. Do NOT proceed without it.

- [ ] **Step 3: Merge to main (only after explicit authorization)**

```bash
git checkout main
git merge --no-ff feat/cli-full-validation -m "$(cat <<'EOF'
Merge branch 'feat/cli-full-validation'

CLI full validation for analysis.yaml and design.yaml — 0.7.0.

Ports the vibeval-evaluator agent's Rule 7 mechanical checks for
tool_coverage into CLI Python code. vibeval validate <feature> now
validates analysis.yaml (execution_mode + tools[] schema), design.yaml
(tool_coverage[] cross-reference + Rule 7 item existence + Allowed
Spec Patterns + output_handling multi-item constraint), datasets, and
results. Exit 0 iff all layers pass.

No protocol, skill, or dataset format changes.
EOF
)"
```

- [ ] **Step 4: Bump version to 0.7.0 in all three places**

Edit `pyproject.toml` — change `version = "0.6.1"` to `version = "0.7.0"`.
Edit `plugin/plugin.json` — change `"version": "0.6.1"` to `"version": "0.7.0"`.
Edit `src/vibeval/__init__.py` — change `__version__ = "0.6.1"` to `__version__ = "0.7.0"`.

- [ ] **Step 5: Add 0.7.0 CHANGELOG entry**

Prepend to `CHANGELOG.md` (after any top header) a new entry:

```markdown
## [0.7.0] - 2026-04-14

### Added

- **CLI full validation for `analysis.yaml` and `design.yaml`.** `vibeval validate <feature>` now additionally validates analysis and design artifacts as a 1:1 port of the `vibeval-evaluator` agent's Rule 7 mechanical check from `plugin/protocol/references/07-agent-tools.md`. Concretely:
  - `analysis.yaml` — schema checks for `project.execution_mode` and the full `tools[]` entry structure (id, type, source_location, mock_target, surface.{name,description,input_schema,output_shape}, responsibility, design_risks, siblings_to_watch; subagent extras). Duplicate tool ids are rejected.
  - `design.yaml` — schema checks for `datasets[]` inline items and `tool_coverage[]`, plus the Rule 7 mechanical check: (a) every referenced `item_id` resolves to a real dataset item (inline or filesystem); (b) the resolved item carries at least one `judge_spec` structurally matching the dimension's Allowed Spec Pattern; (c) the full `output_handling` list spans ≥2 items with byte-unequal non-empty `mock_context_summary[<mock_target>]` values.
  - `execution_mode` gate: Agent checks run only when `project.execution_mode == "agent"`. `non_agent` features skip them silently.
  - Partial workflow states are tolerated: `analysis.yaml` absent skips all Agent checks; `design.yaml` absent on an agent feature warns (not errors).
- CLI is rigor-agnostic and does not read `contract.yaml`. The CLI is the hard mechanical gate; the Evaluator agent remains the context-aware gate inside `/vibeval`.

### Notes

- No protocol, skill, plugin, or dataset format changes. This release is purely a CLI/Python enhancement.
- Implementation mirrors the runtime's `Dataset.effective_specs(item)` precedence (item-level `_judge_specs` fully replace manifest-level `judge_specs`).
- Added `src/vibeval/validate_analysis.py`, `src/vibeval/validate_design.py`, and `tests/test_validate_agent.py`.

```

- [ ] **Step 6: Commit the release bump**

```bash
git add CHANGELOG.md pyproject.toml plugin/plugin.json src/vibeval/__init__.py
git commit -m "$(cat <<'EOF'
release: v0.7.0 — CLI full validation for analysis.yaml + design.yaml

Bumps version to 0.7.0 across pyproject.toml, plugin/plugin.json, and
src/vibeval/__init__.py. Adds a 0.7.0 CHANGELOG entry covering the
new CLI-level tool_coverage validation.

Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 7: Create the annotated tag**

```bash
git tag -a v0.7.0 -m "$(cat <<'EOF'
v0.7.0 — CLI full validation

Ports the vibeval-evaluator agent's Rule 7 mechanical checks for
tool_coverage into CLI Python code. vibeval validate <feature> now
covers analysis.yaml + design.yaml in addition to the existing
datasets/results walks.

- Schema checks for project.execution_mode and tools[] entry structure
- Rule 7 item existence + Allowed Spec Patterns per dimension
- output_handling multi-item constraint on mock_context_summary
- Partial workflow states tolerated (Q3 refinement)

Full Python test suite passes. No protocol, skill, or dataset format
changes.
EOF
)"
```

- [ ] **Step 8: Ask the user for explicit push authorization**

STOP and ask: "0.7.0 committed and tagged locally. Ready to push `main` + `v0.7.0` to origin?"

Wait for explicit approval.

- [ ] **Step 9: Push main + tag (only after explicit authorization)**

```bash
git push origin main
git push origin v0.7.0
```

- [ ] **Step 10: Delete the local feature branch**

```bash
git branch -d feat/cli-full-validation
```

(Use `-d`, not `-D`. If it refuses because the branch has unmerged commits, investigate rather than forcing.)

- [ ] **Step 11: Verify clean state**

```bash
git status
git log --oneline -5
```

Expected: clean working tree, `release: v0.7.0 ...` at HEAD, `v0.7.0` tag pointing at HEAD.

---

## Self-Review (write-phase)

Spec coverage check:

- [x] **Spec §Scope item 1** (load into typed dataclasses) → Task 2 (AnalysisModel), Task 3 (DesignModel)
- [x] **Spec §Scope item 2** (schema checks, cross-references) → Task 2 (analysis schema), Task 3 (design schema, item flattening)
- [x] **Spec §Scope item 3a** (item existence) → Task 4
- [x] **Spec §Scope item 3b** (spec pattern match + output_handling mock_context_summary key) → Task 5
- [x] **Spec §Scope item 3c** (output_handling multi-item constraint) → Task 6
- [x] **Spec §Scope item 4** (execution_mode gate) → Task 2 (parsing) + Task 3 (gate in validate_design) + Task 7 (orchestrator)
- [x] **Spec §Scope item 5** (TDD) → every task has failing test → impl → passing test → commit
- [x] **Spec §Scope item 6** (CHANGELOG + version bump + tag + push) → Task 9
- [x] **Spec §Error Taxonomy rows 1–18** → each has at least one negative test in Tasks 2/3/4/5/6
- [x] **Spec §CLI Integration** (description, no new flags) → Task 8
- [x] **Spec §Test Plan** — every named test exists in the plan. Verified by search.
- [x] **Spec §Design Decisions Q1-Q12** — locked in both spec and plan; code enforces each.
- [x] **Spec §Done Definition** — Task 9 covers every checkbox.

Placeholder scan: no "TBD", no "add appropriate error handling", no "similar to Task N". Each step contains the actual code or command.

Type consistency: `ToolModel` uses `surface_name` (not `surface.name`) throughout. `JudgeSpecModel` uses `target_output: bool` + `target_step_type: str | None` everywhere. `ItemModel` uses `mock_context_summary: dict[str, str]` everywhere. `ToolCoverageModel.dimensions_covered` is `dict[str, list[str]]` everywhere. Function signature `validate_analysis(feature_dir, report) -> AnalysisModel | None` and `validate_design(feature_dir, analysis, report) -> None` — consistent across tasks 2, 3, 7.

Task ordering: Task 2 defines `AnalysisModel`, Task 3 consumes it — good. Task 4 depends on Task 3's `_run_rule_7` stub — good. Task 5 adds `_any_spec_matches` and calls it from Task 4's loop — good. Task 6 adds check (c) after Task 4's mandatory loop — good. Task 7 wires everything into `validate_feature`, using symbols from Tasks 2 and 3 — good. Task 8 is CLI-only, independent — good. Task 9 is release, independent — good.

---

**Plan complete and saved to `docs/plans/2026-04-14-cli-full-validation.md`.**

Execution mode per the session handoff: **subagent-driven-development**. Each task dispatched as a fresh subagent with the full task text pasted inline (NOT by reading the plan file), two-stage review (spec compliance → code quality), Sonnet for implementation + reviews, Haiku permissible for Task 8's trivial CLI edit.
