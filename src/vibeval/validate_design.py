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
from .validate_analysis import AnalysisModel


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
        # target key absent → treated as "output" (only meaningful for llm specs)
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
                # Check (b) — spec pattern match — added in Task 5

        # Check (c) — output_handling multi-item constraint — added in Task 6

        # Conditional: sequence dimension — Q8, never required by the CLI.
        # Only structurally checked when listed.
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
            # Check (b) for sequence — added in Task 5
