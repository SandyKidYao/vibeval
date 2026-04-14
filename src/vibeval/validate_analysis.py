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
