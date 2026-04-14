"""Tests for validate_analysis (Agent features).

Fixtures are built in-memory under tmp_path, mirroring tests/test_validate.py.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import yaml

import pytest

from vibeval.validate import ValidationReport
from vibeval.validate_analysis import (
    AnalysisModel,
    ToolModel,
    validate_analysis,
)
from vibeval.validate_design import (
    DesignModel,
    ItemModel,
    JudgeSpecModel,
    ToolCoverageModel,
    validate_design,
    _build_judge_spec_model,
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
    data = yaml.safe_load(textwrap.dedent(AGENT_HAPPY))
    del data["tools"][0][removed_field]
    feature = make_feature(tmp_path, analysis_yaml=yaml.safe_dump(data))
    report = ValidationReport()
    validate_analysis(feature, report)
    assert any(expected_fragment in m for m in error_messages(report))


def test_analysis_agent_mode_missing_surface_name_errors(tmp_path: Path) -> None:
    data = yaml.safe_load(textwrap.dedent(AGENT_HAPPY))
    del data["tools"][0]["surface"]["name"]
    feature = make_feature(tmp_path, analysis_yaml=yaml.safe_dump(data))
    report = ValidationReport()
    validate_analysis(feature, report)
    assert any("surface.name" in m for m in error_messages(report))


def test_analysis_agent_mode_invalid_tool_type_errors(tmp_path: Path) -> None:
    data = yaml.safe_load(textwrap.dedent(AGENT_HAPPY))
    data["tools"][0]["type"] = "weird"
    feature = make_feature(tmp_path, analysis_yaml=yaml.safe_dump(data))
    report = ValidationReport()
    validate_analysis(feature, report)
    assert any("type invalid 'weird'" in m for m in error_messages(report))


def test_analysis_agent_mode_design_risks_must_be_list(tmp_path: Path) -> None:
    data = yaml.safe_load(textwrap.dedent(AGENT_HAPPY))
    data["tools"][0]["design_risks"] = "oops"
    feature = make_feature(tmp_path, analysis_yaml=yaml.safe_dump(data))
    report = ValidationReport()
    validate_analysis(feature, report)
    assert any("design_risks must be a list" in m for m in error_messages(report))


def test_analysis_agent_mode_siblings_to_watch_must_be_list(tmp_path: Path) -> None:
    data = yaml.safe_load(textwrap.dedent(AGENT_HAPPY))
    data["tools"][0]["siblings_to_watch"] = "oops"
    feature = make_feature(tmp_path, analysis_yaml=yaml.safe_dump(data))
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
    data = yaml.safe_load(textwrap.dedent(AGENT_HAPPY))
    data["tools"].append(dict(data["tools"][0]))  # shallow copy duplicates the id
    feature = make_feature(tmp_path, analysis_yaml=yaml.safe_dump(data))
    report = ValidationReport()
    validate_analysis(feature, report)
    assert any("duplicate id 'search_documents'" in m for m in error_messages(report))


def test_analysis_agent_mode_subagent_requires_expected_context(tmp_path: Path) -> None:
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
            subagent_prompt_summary: "You are a research assistant."
    """)
    report = ValidationReport()
    validate_analysis(feature, report)
    assert any("subagent_expected_context required" in m for m in error_messages(report))


def test_analysis_agent_mode_subagent_expected_context_must_be_list_of_strings(tmp_path: Path) -> None:
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
            subagent_prompt_summary: "You are a research assistant."
            subagent_expected_context: [123, "ok"]
    """)
    report = ValidationReport()
    validate_analysis(feature, report)
    assert any("must be a list of strings" in m for m in error_messages(report))


# ========================================================================
# validate_design: loading and item flattening
# ========================================================================


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
    # _run_rule_7 is a stub in Task 3 — we only verify the model loads cleanly.
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
    # target key absent → target_output True (only meaningful for llm specs;
    # the pattern matcher reads this boolean only when method == "llm")
    assert m.target_output is True

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
    assert m2.target_step_type is None
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

    # Branch 3: target is a string but not "output" (e.g., "tool_call").
    # Neither flag should be set — this is a malformed/unrecognized target
    # that should NOT be interpreted as output_handling. Task 5's pattern
    # matcher depends on this.
    other_string = {
        "method": "llm",
        "scoring": "binary",
        "target": "tool_call",
        "criteria": "x",
    }
    m4 = _build_judge_spec_model(other_string)
    assert m4.method == "llm"
    assert m4.target_step_type is None
    assert m4.target_output is False


def test_design_filesystem_item_shadowed_by_design_inline_warns(tmp_path: Path) -> None:
    # design-inline defines 'pos_item'; filesystem dataset also defines 'pos_item'.
    # The design-inline copy wins per Q12, but a collision warning must fire.
    feature, analysis = make_agent_feature(tmp_path, design_yaml=FULL_COVERAGE_DESIGN)
    # Create a filesystem dataset under tests/vibeval/<feature>/datasets/ that
    # contains an item with the same id as one of the design-inline items.
    ds_dir = feature / "datasets" / "search"
    ds_dir.mkdir(parents=True)
    write(ds_dir / "manifest.yaml", """
        name: search
        judge_specs: []
    """)
    write(ds_dir / "pos_item.yaml", """
        _id: pos_item
        user_message: "shadowed"
    """)
    report = ValidationReport()
    validate_design(feature, analysis, report)
    assert any(
        "'pos_item' defined in multiple datasets" in m
        for m in warning_messages(report)
    )
