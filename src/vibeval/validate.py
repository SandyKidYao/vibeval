"""Data format validator — checks datasets, results, and judge specs against protocol.

Validates structural correctness of all vibeval artifacts before runtime,
catching format issues that would cause judge/compare/summary to fail.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Issue:
    """A single validation issue."""

    level: str  # "error" or "warning"
    path: str  # file or location where the issue was found
    message: str

    def __str__(self) -> str:
        icon = "ERROR" if self.level == "error" else "WARN"
        return f"  [{icon}] {self.path}: {self.message}"


@dataclass
class ValidationReport:
    """Collected validation results."""

    issues: list[Issue] = field(default_factory=list)

    def error(self, path: str, message: str) -> None:
        self.issues.append(Issue("error", path, message))

    def warn(self, path: str, message: str) -> None:
        self.issues.append(Issue("warning", path, message))

    @property
    def errors(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def ok(self) -> bool:
        return len(self.errors) == 0


# Valid rule names from rules.py dispatch table
VALID_RULES = {
    "contains", "contains_all", "contains_any", "not_contains",
    "equals", "matches", "is_json", "length_between",
    "tool_sequence", "tool_called", "tool_not_called",
    "max_turns", "max_steps",
    "conversation_turns", "all_turns_responded", "no_role_violation",
}

# Required args per rule
RULE_REQUIRED_ARGS: dict[str, list[str]] = {
    "contains": ["field", "value"],
    "contains_all": ["field"],  # needs "values" or "values_from"
    "contains_any": ["field", "values"],
    "not_contains": ["field", "value"],
    "equals": ["field"],  # needs "expected" or "expected_from"
    "matches": ["field", "pattern"],
    "is_json": ["field"],
    "length_between": ["field"],  # min/max optional with defaults
    "tool_sequence": ["expected"],
    "tool_called": ["tool_name"],
    "tool_not_called": ["tool_name"],
    "max_turns": [],  # max optional with default
    "max_steps": [],  # max optional with default
    "conversation_turns": [],  # min/max optional with defaults
    "all_turns_responded": [],
    "no_role_violation": [],
}


def validate_feature(feature_dir: str | Path) -> ValidationReport:
    """Validate all artifacts for a feature."""
    report = ValidationReport()
    feature_dir = Path(feature_dir)

    if not feature_dir.exists():
        report.error(str(feature_dir), "Feature directory does not exist")
        return report

    # Agent features: analysis.yaml and design.yaml
    # Local imports to avoid circular dependency — the new modules import
    # ValidationReport from this file.
    from .validate_analysis import validate_analysis
    from .validate_design import validate_design
    analysis = validate_analysis(feature_dir, report)
    validate_design(feature_dir, analysis, report)

    # Validate datasets
    datasets_dir = feature_dir / "datasets"
    if datasets_dir.exists():
        _validate_datasets(datasets_dir, report)
    else:
        report.warn(str(feature_dir), "No datasets/ directory found")

    # Validate results
    results_dir = feature_dir / "results"
    if results_dir.exists():
        _validate_results(results_dir, report)

    return report


def _validate_datasets(datasets_dir: Path, report: ValidationReport) -> None:
    """Validate all datasets in the datasets directory."""
    found_any = False
    for p in sorted(datasets_dir.iterdir()):
        if p.is_dir() and not p.name.startswith("."):
            found_any = True
            _validate_dataset_dir(p, report)
        elif p.suffix in (".json", ".yaml", ".yml"):
            found_any = True
            _validate_single_file_dataset(p, report)

    if not found_any:
        report.warn(str(datasets_dir), "No datasets found")


def _validate_dataset_dir(dir_path: Path, report: ValidationReport) -> None:
    """Validate a directory-based dataset."""
    ds_name = dir_path.name

    # Check manifest exists
    manifest_path = None
    for mname in ("manifest.yaml", "manifest.yml"):
        p = dir_path / mname
        if p.exists():
            manifest_path = p
            break

    if manifest_path is None:
        report.error(str(dir_path), "Missing manifest.yaml")
        return

    # Parse manifest
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        report.error(str(manifest_path), f"Invalid YAML: {e}")
        return

    if not isinstance(manifest, dict):
        report.error(str(manifest_path), "Manifest must be a YAML mapping")
        return

    # Validate manifest fields
    _validate_manifest(manifest, str(manifest_path), ds_name, report)

    # Validate data items
    item_ids: list[str] = []
    items_data: list[dict[str, Any]] = []
    for f in sorted(dir_path.iterdir()):
        if f.name.startswith("manifest"):
            continue
        if f.suffix in (".json", ".yaml", ".yml"):
            item = _validate_data_item_file(f, report)
            if item is not None:
                item_id = item.get("_id", f.stem)
                if item_id in item_ids:
                    report.error(str(f), f"Duplicate item _id: '{item_id}'")
                item_ids.append(item_id)
                items_data.append(item)

    if not items_data:
        report.warn(str(dir_path), "Dataset has no data items")

    # Cross-validate judge_specs against items
    specs = manifest.get("judge_specs", [])
    _validate_specs_against_items(specs, items_data, str(manifest_path), report)


def _validate_manifest(manifest: dict, path: str, ds_name: str, report: ValidationReport) -> None:
    """Validate manifest fields."""
    # name field
    name = manifest.get("name")
    if name is not None and name != ds_name:
        report.warn(path, f"Manifest name '{name}' does not match directory name '{ds_name}'")

    # tags
    tags = manifest.get("tags")
    if tags is not None and not isinstance(tags, list):
        report.error(path, "Field 'tags' must be a list")
    elif isinstance(tags, list) and not all(isinstance(t, str) for t in tags):
        report.error(path, "All items in 'tags' must be strings")

    # judge_specs
    specs = manifest.get("judge_specs")
    if specs is not None:
        if not isinstance(specs, list):
            report.error(path, "Field 'judge_specs' must be a list")
        else:
            for i, spec in enumerate(specs):
                _validate_judge_spec(spec, f"{path} judge_specs[{i}]", report)


def _validate_data_item_file(path: Path, report: ValidationReport) -> dict[str, Any] | None:
    """Validate a single data item file. Returns parsed data or None on failure."""
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            raw = json.loads(text)
        else:
            raw = yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as e:
        report.error(str(path), f"Invalid {path.suffix} format: {e}")
        return None

    if not isinstance(raw, dict):
        report.warn(str(path), "Data item is not a dict — will be wrapped in {value: ...}")
        return None

    # Validate reserved fields
    _validate_reserved_fields(raw, str(path), report)

    return raw


def _validate_reserved_fields(item: dict, path: str, report: ValidationReport) -> None:
    """Validate reserved _ fields in a data item."""
    # _id
    _id = item.get("_id")
    if _id is not None and not isinstance(_id, str):
        report.error(path, "_id must be a string")

    # _tags
    _tags = item.get("_tags")
    if _tags is not None:
        if not isinstance(_tags, list):
            report.error(path, "_tags must be a list")
        elif not all(isinstance(t, str) for t in _tags):
            report.error(path, "All items in _tags must be strings")

    # _judge_specs
    _specs = item.get("_judge_specs")
    if _specs is not None:
        if not isinstance(_specs, list):
            report.error(path, "_judge_specs must be a list")
        else:
            for i, spec in enumerate(_specs):
                _validate_judge_spec(spec, f"{path} _judge_specs[{i}]", report)

    # _mock_context
    _mock = item.get("_mock_context")
    if _mock is not None:
        _validate_mock_context(_mock, path, report)


def _validate_mock_context(mock_context: Any, path: str, report: ValidationReport) -> None:
    """Validate _mock_context structure."""
    if not isinstance(mock_context, dict):
        report.error(path, "_mock_context must be a dict")
        return

    for target, config in mock_context.items():
        loc = f"{path} _mock_context[{target}]"
        if not isinstance(config, dict):
            report.error(loc, "Mock target config must be a dict")
            continue

        responses = config.get("responses")
        if responses is None:
            report.error(loc, "Missing required field 'responses'")
        elif not isinstance(responses, list):
            report.error(loc, "'responses' must be a list")
        elif len(responses) == 0:
            report.error(loc, "'responses' must not be empty")

        desc = config.get("description")
        if desc is not None and not isinstance(desc, str):
            report.warn(loc, "'description' should be a string")


def _validate_judge_spec(spec: Any, path: str, report: ValidationReport) -> None:
    """Validate a single judge spec."""
    if not isinstance(spec, dict):
        report.error(path, "Judge spec must be a dict")
        return

    method = spec.get("method")
    if method is None:
        report.error(path, "Missing required field 'method'")
        return

    if method not in ("rule", "llm"):
        report.error(path, f"Invalid method '{method}' — must be 'rule' or 'llm'")
        return

    # Validate weight
    weight = spec.get("weight")
    if weight is not None:
        if weight != "gate" and not isinstance(weight, (int, float)):
            report.error(path, f"Invalid weight '{weight}' — must be a number or 'gate'")
        elif isinstance(weight, (int, float)) and weight <= 0:
            report.warn(path, f"Weight {weight} is non-positive")

    if method == "rule":
        _validate_rule_spec(spec, path, report)
    else:
        _validate_llm_spec(spec, path, report)


def _validate_rule_spec(spec: dict, path: str, report: ValidationReport) -> None:
    """Validate a rule-type judge spec."""
    rule_name = spec.get("rule")
    if rule_name is None:
        report.error(path, "Missing required field 'rule'")
        return

    if rule_name not in VALID_RULES:
        report.error(path, f"Unknown rule '{rule_name}' — valid rules: {sorted(VALID_RULES)}")
        return

    args = spec.get("args", {})
    if not isinstance(args, dict):
        report.error(path, "'args' must be a dict")
        return

    # Check required args
    required = RULE_REQUIRED_ARGS.get(rule_name, [])
    for arg in required:
        if arg not in args:
            # Special cases: contains_all accepts values OR values_from
            if rule_name == "contains_all" and arg == "field":
                report.error(path, f"Rule '{rule_name}' requires arg '{arg}'")
            elif rule_name == "contains_all" and "values" not in args and "values_from" not in args:
                report.error(path, f"Rule '{rule_name}' requires 'values' or 'values_from'")
            elif rule_name == "equals" and arg == "field":
                report.error(path, f"Rule '{rule_name}' requires arg '{arg}'")
            elif rule_name == "equals" and "expected" not in args and "expected_from" not in args:
                report.error(path, f"Rule '{rule_name}' requires 'expected' or 'expected_from'")
            else:
                report.error(path, f"Rule '{rule_name}' requires arg '{arg}'")

    # Validate regex pattern for matches rule
    if rule_name == "matches" and "pattern" in args:
        try:
            re.compile(args["pattern"])
        except re.error as e:
            report.error(path, f"Invalid regex pattern: {e}")

    # Validate tool_sequence expects list
    if rule_name == "tool_sequence" and "expected" in args:
        if not isinstance(args["expected"], list):
            report.error(path, "Rule 'tool_sequence' arg 'expected' must be a list")

    # Validate min/max are numbers where applicable
    for num_arg in ("min", "max"):
        if num_arg in args and not isinstance(args[num_arg], (int, float)):
            report.error(path, f"Arg '{num_arg}' must be a number")


def _validate_llm_spec(spec: dict, path: str, report: ValidationReport) -> None:
    """Validate an LLM-type judge spec."""
    # scoring
    scoring = spec.get("scoring")
    if scoring is None:
        report.error(path, "Missing required field 'scoring'")
        return
    if scoring not in ("binary", "five-point"):
        report.error(path, f"Invalid scoring '{scoring}' — must be 'binary' or 'five-point'")
        return

    # criteria
    criteria = spec.get("criteria")
    if criteria is None:
        report.error(path, "Missing required field 'criteria'")
    elif not isinstance(criteria, str) or not criteria.strip():
        report.error(path, "'criteria' must be a non-empty string")

    # test_intent
    test_intent = spec.get("test_intent")
    if test_intent is None:
        report.warn(path, "Missing 'test_intent' — recommended for information asymmetry")
    elif not isinstance(test_intent, str):
        report.error(path, "'test_intent' must be a string")

    # anchors
    anchors = spec.get("anchors")
    if anchors is None:
        report.warn(path, "Missing 'anchors' — recommended for evaluation quality")
    elif not isinstance(anchors, dict):
        report.error(path, "'anchors' must be a dict")
    else:
        if scoring == "binary":
            expected_keys = {"0", "1"}
            actual_keys = set(str(k) for k in anchors.keys())
            if actual_keys != expected_keys:
                report.error(path, f"Binary anchors must have keys '0' and '1', got {actual_keys}")
        elif scoring == "five-point":
            expected_keys = {"1", "2", "3", "4", "5"}
            actual_keys = set(str(k) for k in anchors.keys())
            if actual_keys != expected_keys:
                report.error(path, f"Five-point anchors must have keys '1'-'5', got {actual_keys}")
        # All anchor values should be strings
        for k, v in anchors.items():
            if not isinstance(v, str):
                report.warn(path, f"Anchor '{k}' value should be a string")

    # calibrations
    calibrations = spec.get("calibrations")
    if calibrations is None:
        report.warn(path, "Missing 'calibrations' — recommended for evaluation quality")
    elif not isinstance(calibrations, list):
        report.error(path, "'calibrations' must be a list")
    elif len(calibrations) == 0:
        report.warn(path, "'calibrations' is empty")
    else:
        for i, cal in enumerate(calibrations):
            cal_path = f"{path} calibrations[{i}]"
            if not isinstance(cal, dict):
                report.error(cal_path, "Calibration must be a dict")
                continue
            if "output" not in cal:
                report.error(cal_path, "Missing required field 'output'")
            if "score" not in cal:
                report.error(cal_path, "Missing required field 'score'")
            else:
                score = cal["score"]
                if scoring == "binary" and score not in (0, 1):
                    report.error(cal_path, f"Binary calibration score must be 0 or 1, got {score}")
                elif scoring == "five-point" and score not in (1, 2, 3, 4, 5):
                    report.error(cal_path, f"Five-point calibration score must be 1-5, got {score}")
            if "reason" not in cal:
                report.warn(cal_path, "Missing 'reason' — recommended for calibration quality")

    # target
    target = spec.get("target")
    if target is not None and not isinstance(target, str):
        if isinstance(target, dict):
            turns = target.get("turns")
            if turns is not None:
                if not isinstance(turns, list) or len(turns) != 2:
                    report.error(path, "'target.turns' must be a list of [start, end]")
                elif not all(isinstance(t, int) for t in turns):
                    report.error(path, "'target.turns' values must be integers")
                elif turns[0] > turns[1]:
                    report.error(path, f"'target.turns' start ({turns[0]}) must be <= end ({turns[1]})")
            step_type = target.get("step_type")
            if step_type is not None and not isinstance(step_type, str):
                report.error(path, "'target.step_type' must be a string")
        else:
            report.error(path, "'target' must be a string or dict")


def _validate_specs_against_items(
    specs: list, items: list[dict], path: str, report: ValidationReport
) -> None:
    """Cross-validate dataset-level specs against data items."""
    for i, spec in enumerate(specs):
        if not isinstance(spec, dict):
            continue
        method = spec.get("method")
        if method == "rule":
            args = spec.get("args", {})
            # Check values_from / expected_from references
            for ref_key in ("values_from", "expected_from"):
                ref_field = args.get(ref_key)
                if ref_field is not None and items:
                    missing_in = []
                    for item in items:
                        item_id = item.get("_id", "?")
                        if ref_field not in item:
                            missing_in.append(item_id)
                    if missing_in:
                        report.error(
                            f"{path} judge_specs[{i}]",
                            f"'{ref_key}: {ref_field}' not found in items: {missing_in[:5]}"
                        )

            # Check reference_from for LLM specs
        elif method == "llm":
            ref = spec.get("reference_from")
            if ref is not None and items:
                missing_in = []
                for item in items:
                    item_id = item.get("_id", "?")
                    if ref not in item:
                        missing_in.append(item_id)
                if missing_in:
                    report.warn(
                        f"{path} judge_specs[{i}]",
                        f"'reference_from: {ref}' not found in items: {missing_in[:5]}"
                    )


def _validate_single_file_dataset(path: Path, report: ValidationReport) -> None:
    """Validate a single-file dataset."""
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".json":
            raw = json.loads(text)
        else:
            raw = yaml.safe_load(text)
    except (json.JSONDecodeError, yaml.YAMLError) as e:
        report.error(str(path), f"Invalid format: {e}")
        return

    if isinstance(raw, dict) and "items" in raw:
        # Named single-file dataset
        if "name" not in raw:
            report.warn(str(path), "Missing 'name' field")
        items = raw.get("items")
        if not isinstance(items, list):
            report.error(str(path), "'items' must be a list")
        elif len(items) == 0:
            report.warn(str(path), "'items' is empty")

        specs = raw.get("judge_specs")
        if specs is not None:
            if not isinstance(specs, list):
                report.error(str(path), "'judge_specs' must be a list")
            else:
                for i, spec in enumerate(specs):
                    _validate_judge_spec(spec, f"{path} judge_specs[{i}]", report)


def _validate_results(results_dir: Path, report: ValidationReport) -> None:
    """Validate all result files across all runs."""
    for run_dir in sorted(results_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        for f in sorted(run_dir.iterdir()):
            if f.name.endswith(".result.json"):
                _validate_result_file(f, report)


def _validate_result_file(path: Path, report: ValidationReport) -> None:
    """Validate a single .result.json file."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        report.error(str(path), f"Invalid JSON: {e}")
        return

    if not isinstance(raw, dict):
        report.error(str(path), "Result must be a JSON object")
        return

    # Required fields
    test_name = raw.get("test_name")
    if test_name is None:
        report.error(str(path), "Missing required field 'test_name'")
    elif not isinstance(test_name, str) or not test_name.strip():
        report.error(str(path), "'test_name' must be a non-empty string")

    dataset = raw.get("dataset")
    if dataset is not None and not isinstance(dataset, str):
        report.error(str(path), "'dataset' must be a string")

    item_id = raw.get("item_id")
    if item_id is not None and not isinstance(item_id, str):
        report.error(str(path), "'item_id' must be a string")

    # outputs
    outputs = raw.get("outputs")
    if outputs is not None and not isinstance(outputs, dict):
        report.error(str(path), "'outputs' must be a dict")

    # trace
    trace = raw.get("trace")
    if trace is not None:
        _validate_trace(trace, str(path), report)

    # judge_results
    judge_results = raw.get("judge_results")
    if judge_results is not None:
        if not isinstance(judge_results, list):
            report.error(str(path), "'judge_results' must be a list")
        else:
            for i, jr in enumerate(judge_results):
                _validate_judge_result(jr, f"{path} judge_results[{i}]", report)

    # duration
    duration = raw.get("duration")
    if duration is not None and not isinstance(duration, (int, float)):
        report.error(str(path), "'duration' must be a number")

    # timestamp
    timestamp = raw.get("timestamp")
    if timestamp is not None and not isinstance(timestamp, (int, float)):
        report.error(str(path), "'timestamp' must be a number")


def _validate_trace(trace: Any, path: str, report: ValidationReport) -> None:
    """Validate trace structure."""
    if not isinstance(trace, dict):
        report.error(path, "'trace' must be a dict")
        return

    turns = trace.get("turns")
    if turns is None:
        report.error(path, "trace missing required field 'turns'")
        return

    if not isinstance(turns, list):
        report.error(path, "'trace.turns' must be a list")
        return

    prev_turn_num = 0
    for i, turn in enumerate(turns):
        turn_path = f"{path} trace.turns[{i}]"

        if not isinstance(turn, dict):
            report.error(turn_path, "Turn must be a dict")
            continue

        # turn number
        turn_num = turn.get("turn")
        if turn_num is None:
            report.error(turn_path, "Missing required field 'turn'")
        elif not isinstance(turn_num, int) or turn_num < 1:
            report.error(turn_path, f"'turn' must be a positive integer, got {turn_num}")
        elif turn_num != prev_turn_num + 1:
            report.warn(turn_path, f"Turn numbers not sequential: expected {prev_turn_num + 1}, got {turn_num}")
        if isinstance(turn_num, int):
            prev_turn_num = turn_num

        # input
        if "input" not in turn:
            report.error(turn_path, "Missing required field 'input'")
        elif not isinstance(turn["input"], dict):
            report.error(turn_path, "'input' must be a dict")

        # output
        if "output" not in turn:
            report.error(turn_path, "Missing required field 'output'")
        elif not isinstance(turn["output"], dict):
            report.error(turn_path, "'output' must be a dict")

        # steps
        steps = turn.get("steps")
        if steps is None:
            report.error(turn_path, "Missing required field 'steps'")
        elif not isinstance(steps, list):
            report.error(turn_path, "'steps' must be a list")
        else:
            for j, step in enumerate(steps):
                step_path = f"{turn_path} steps[{j}]"
                if not isinstance(step, dict):
                    report.error(step_path, "Step must be a dict")
                    continue
                if "type" not in step:
                    report.error(step_path, "Missing required field 'type'")
                elif not isinstance(step["type"], str) or not step["type"].strip():
                    report.error(step_path, "'type' must be a non-empty string")
                if "data" not in step:
                    report.error(step_path, "Missing required field 'data'")
                elif not isinstance(step["data"], dict):
                    report.error(step_path, "'data' must be a dict")


def _validate_judge_result(jr: Any, path: str, report: ValidationReport) -> None:
    """Validate a single judge result entry."""
    if not isinstance(jr, dict):
        report.error(path, "Judge result must be a dict")
        return

    spec = jr.get("spec")
    if spec is None:
        report.error(path, "Missing required field 'spec'")
    elif not isinstance(spec, dict):
        report.error(path, "'spec' must be a dict")

    score = jr.get("score")
    if score is None:
        report.error(path, "Missing required field 'score'")
    elif not isinstance(score, (int, float)):
        report.error(path, f"'score' must be a number, got {type(score).__name__}")
    else:
        # Validate score range based on spec
        if isinstance(spec, dict):
            method = spec.get("method", "")
            scoring = spec.get("scoring", "")
            if method == "rule" or scoring == "binary":
                if score not in (0, 1):
                    report.error(path, f"Binary/rule score must be 0 or 1, got {score}")
            elif scoring == "five-point":
                if score not in (1, 2, 3, 4, 5):
                    report.error(path, f"Five-point score must be 1-5, got {score}")
