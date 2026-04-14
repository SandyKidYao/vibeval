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
