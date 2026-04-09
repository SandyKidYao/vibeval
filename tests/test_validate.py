"""Tests for data format validator."""

import json
import textwrap

import pytest

from vibeval.validate import (
    ValidationReport,
    validate_feature,
    _validate_judge_spec,
    _validate_mock_context,
    _validate_trace,
    _validate_result_file,
)


# --- Helpers ---

def write_yaml(path, content):
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def make_dataset(tmp_path, ds_name, manifest, items=None):
    """Create a dataset directory with manifest and optional items."""
    feature = tmp_path / "test_feature"
    ds_dir = feature / "datasets" / ds_name
    ds_dir.mkdir(parents=True)
    write_yaml(ds_dir / "manifest.yaml", manifest)
    if items:
        for item_id, item_data in items.items():
            write_json(ds_dir / f"{item_id}.json", item_data)
    return feature


# --- Test validate_feature ---

class TestValidateFeature:
    def test_missing_feature_dir(self, tmp_path):
        report = validate_feature(tmp_path / "nonexistent")
        assert not report.ok
        assert any("does not exist" in i.message for i in report.errors)

    def test_empty_feature(self, tmp_path):
        feature = tmp_path / "test_feature"
        feature.mkdir()
        report = validate_feature(feature)
        assert report.ok  # no errors, just warnings
        assert any("No datasets/" in i.message for i in report.warnings)

    def test_valid_dataset(self, tmp_path):
        feature = make_dataset(tmp_path, "my_ds", """
            name: my_ds
            tags:
              - test
            judge_specs:
              - method: rule
                rule: contains
                args:
                  field: outputs.summary
                  value: hello
        """, items={
            "item1": {"_id": "item1", "text": "hello world"},
        })
        report = validate_feature(feature)
        assert report.ok


# --- Test manifest validation ---

class TestManifestValidation:
    def test_missing_manifest(self, tmp_path):
        feature = tmp_path / "test_feature"
        ds_dir = feature / "datasets" / "bad_ds"
        ds_dir.mkdir(parents=True)
        write_json(ds_dir / "item1.json", {"_id": "item1"})
        report = validate_feature(feature)
        assert not report.ok
        assert any("Missing manifest.yaml" in i.message for i in report.errors)

    def test_invalid_yaml(self, tmp_path):
        feature = tmp_path / "test_feature"
        ds_dir = feature / "datasets" / "bad_ds"
        ds_dir.mkdir(parents=True)
        (ds_dir / "manifest.yaml").write_text(": [invalid yaml{{{", encoding="utf-8")
        report = validate_feature(feature)
        assert not report.ok
        assert any("Invalid YAML" in i.message for i in report.errors)

    def test_name_mismatch_warning(self, tmp_path):
        feature = make_dataset(tmp_path, "my_ds", """
            name: different_name
        """)
        report = validate_feature(feature)
        assert report.ok  # warning only
        assert any("does not match" in i.message for i in report.warnings)

    def test_tags_not_list(self, tmp_path):
        feature = make_dataset(tmp_path, "my_ds", """
            name: my_ds
            tags: not_a_list
        """)
        report = validate_feature(feature)
        assert not report.ok
        assert any("'tags' must be a list" in i.message for i in report.errors)


# --- Test judge_spec validation ---

class TestJudgeSpecValidation:
    def test_missing_method(self):
        report = ValidationReport()
        _validate_judge_spec({}, "test", report)
        assert not report.ok
        assert any("Missing required field 'method'" in i.message for i in report.errors)

    def test_invalid_method(self):
        report = ValidationReport()
        _validate_judge_spec({"method": "unknown"}, "test", report)
        assert not report.ok
        assert any("Invalid method" in i.message for i in report.errors)

    def test_valid_rule_spec(self):
        report = ValidationReport()
        _validate_judge_spec({
            "method": "rule",
            "rule": "contains",
            "args": {"field": "outputs.text", "value": "hello"},
        }, "test", report)
        assert report.ok

    def test_unknown_rule(self):
        report = ValidationReport()
        _validate_judge_spec({
            "method": "rule",
            "rule": "nonexistent_rule",
            "args": {},
        }, "test", report)
        assert not report.ok
        assert any("Unknown rule" in i.message for i in report.errors)

    def test_missing_rule_args(self):
        report = ValidationReport()
        _validate_judge_spec({
            "method": "rule",
            "rule": "contains",
            "args": {},  # missing field and value
        }, "test", report)
        assert not report.ok
        assert any("requires arg 'field'" in i.message for i in report.errors)
        assert any("requires arg 'value'" in i.message for i in report.errors)

    def test_invalid_regex(self):
        report = ValidationReport()
        _validate_judge_spec({
            "method": "rule",
            "rule": "matches",
            "args": {"field": "outputs.text", "pattern": "[invalid("},
        }, "test", report)
        assert not report.ok
        assert any("Invalid regex" in i.message for i in report.errors)

    def test_tool_sequence_not_list(self):
        report = ValidationReport()
        _validate_judge_spec({
            "method": "rule",
            "rule": "tool_sequence",
            "args": {"expected": "not_a_list"},
        }, "test", report)
        assert not report.ok
        assert any("must be a list" in i.message for i in report.errors)

    def test_valid_llm_binary(self):
        report = ValidationReport()
        _validate_judge_spec({
            "method": "llm",
            "scoring": "binary",
            "criteria": "output is accurate",
            "test_intent": "test accuracy",
            "anchors": {"0": "inaccurate", "1": "accurate"},
            "calibrations": [
                {"output": "wrong answer", "score": 0, "reason": "factually incorrect"},
                {"output": "correct answer", "score": 1, "reason": "matches facts"},
            ],
        }, "test", report)
        assert report.ok

    def test_valid_llm_five_point(self):
        report = ValidationReport()
        _validate_judge_spec({
            "method": "llm",
            "scoring": "five-point",
            "criteria": "completeness",
            "test_intent": "test coverage",
            "anchors": {
                "1": "very incomplete",
                "2": "mostly incomplete",
                "3": "partial",
                "4": "mostly complete",
                "5": "comprehensive",
            },
            "calibrations": [
                {"output": "They met.", "score": 1, "reason": "minimal"},
                {"output": "Detailed summary.", "score": 5, "reason": "thorough"},
            ],
        }, "test", report)
        assert report.ok

    def test_missing_scoring(self):
        report = ValidationReport()
        _validate_judge_spec({
            "method": "llm",
            "criteria": "test",
        }, "test", report)
        assert not report.ok
        assert any("Missing required field 'scoring'" in i.message for i in report.errors)

    def test_invalid_scoring(self):
        report = ValidationReport()
        _validate_judge_spec({
            "method": "llm",
            "scoring": "ten-point",
            "criteria": "test",
        }, "test", report)
        assert not report.ok
        assert any("Invalid scoring" in i.message for i in report.errors)

    def test_binary_wrong_anchor_keys(self):
        report = ValidationReport()
        _validate_judge_spec({
            "method": "llm",
            "scoring": "binary",
            "criteria": "test",
            "anchors": {"1": "good", "2": "better"},
        }, "test", report)
        assert not report.ok
        assert any("Binary anchors must have keys '0' and '1'" in i.message for i in report.errors)

    def test_five_point_wrong_anchor_keys(self):
        report = ValidationReport()
        _validate_judge_spec({
            "method": "llm",
            "scoring": "five-point",
            "criteria": "test",
            "anchors": {"0": "bad", "1": "ok"},
        }, "test", report)
        assert not report.ok
        assert any("Five-point anchors must have keys '1'-'5'" in i.message for i in report.errors)

    def test_calibration_wrong_score_binary(self):
        report = ValidationReport()
        _validate_judge_spec({
            "method": "llm",
            "scoring": "binary",
            "criteria": "test",
            "calibrations": [
                {"output": "test", "score": 3, "reason": "wrong range"},
            ],
        }, "test", report)
        assert not report.ok
        assert any("Binary calibration score must be 0 or 1" in i.message for i in report.errors)

    def test_calibration_wrong_score_five_point(self):
        report = ValidationReport()
        _validate_judge_spec({
            "method": "llm",
            "scoring": "five-point",
            "criteria": "test",
            "calibrations": [
                {"output": "test", "score": 0, "reason": "out of range"},
            ],
        }, "test", report)
        assert not report.ok
        assert any("Five-point calibration score must be 1-5" in i.message for i in report.errors)

    def test_calibration_missing_fields(self):
        report = ValidationReport()
        _validate_judge_spec({
            "method": "llm",
            "scoring": "binary",
            "criteria": "test",
            "calibrations": [{"score": 1}],  # missing output
        }, "test", report)
        assert not report.ok
        assert any("Missing required field 'output'" in i.message for i in report.errors)

    def test_weight_gate(self):
        report = ValidationReport()
        _validate_judge_spec({
            "method": "rule",
            "rule": "contains",
            "args": {"field": "outputs.text", "value": "hello"},
            "weight": "gate",
        }, "test", report)
        assert report.ok

    def test_weight_invalid(self):
        report = ValidationReport()
        _validate_judge_spec({
            "method": "rule",
            "rule": "contains",
            "args": {"field": "outputs.text", "value": "hello"},
            "weight": "invalid",
        }, "test", report)
        assert not report.ok

    def test_target_valid_dict(self):
        report = ValidationReport()
        _validate_judge_spec({
            "method": "llm",
            "scoring": "binary",
            "criteria": "test",
            "target": {"turns": [1, 3], "step_type": "tool_call"},
        }, "test", report)
        assert report.ok

    def test_target_invalid_turns(self):
        report = ValidationReport()
        _validate_judge_spec({
            "method": "llm",
            "scoring": "binary",
            "criteria": "test",
            "target": {"turns": [5, 2]},  # start > end
        }, "test", report)
        assert not report.ok
        assert any("start" in i.message and "end" in i.message for i in report.errors)

    def test_contains_all_values_from(self):
        report = ValidationReport()
        _validate_judge_spec({
            "method": "rule",
            "rule": "contains_all",
            "args": {"field": "outputs.text", "values_from": "expected_items"},
        }, "test", report)
        assert report.ok

    def test_equals_expected_from(self):
        report = ValidationReport()
        _validate_judge_spec({
            "method": "rule",
            "rule": "equals",
            "args": {"field": "outputs.answer", "expected_from": "expected"},
        }, "test", report)
        assert report.ok


# --- Test _mock_context validation ---

class TestMockContextValidation:
    def test_valid_mock_context(self):
        report = ValidationReport()
        _validate_mock_context({
            "myapp.services.search": {
                "responses": [{"results": []}],
                "description": "Empty search results",
            },
        }, "test", report)
        assert report.ok

    def test_not_a_dict(self):
        report = ValidationReport()
        _validate_mock_context("not a dict", "test", report)
        assert not report.ok

    def test_missing_responses(self):
        report = ValidationReport()
        _validate_mock_context({
            "myapp.search": {"description": "no responses field"},
        }, "test", report)
        assert not report.ok
        assert any("Missing required field 'responses'" in i.message for i in report.errors)

    def test_empty_responses(self):
        report = ValidationReport()
        _validate_mock_context({
            "myapp.search": {"responses": []},
        }, "test", report)
        assert not report.ok
        assert any("must not be empty" in i.message for i in report.errors)

    def test_responses_not_list(self):
        report = ValidationReport()
        _validate_mock_context({
            "myapp.search": {"responses": "not a list"},
        }, "test", report)
        assert not report.ok


# --- Test trace validation ---

class TestTraceValidation:
    def test_valid_trace(self):
        report = ValidationReport()
        _validate_trace({
            "turns": [
                {
                    "turn": 1,
                    "input": {"content": "hello"},
                    "steps": [
                        {"type": "llm_call", "data": {"prompt": "..."}},
                        {"type": "llm_output", "data": {"content": "..."}},
                    ],
                    "output": {"content": "world"},
                },
            ],
        }, "test", report)
        assert report.ok

    def test_missing_turns(self):
        report = ValidationReport()
        _validate_trace({}, "test", report)
        assert not report.ok
        assert any("missing required field 'turns'" in i.message for i in report.errors)

    def test_turn_missing_fields(self):
        report = ValidationReport()
        _validate_trace({
            "turns": [{"turn": 1}],  # missing input, output, steps
        }, "test", report)
        assert not report.ok
        assert any("'input'" in i.message for i in report.errors)
        assert any("'output'" in i.message for i in report.errors)
        assert any("'steps'" in i.message for i in report.errors)

    def test_non_sequential_turns_warning(self):
        report = ValidationReport()
        _validate_trace({
            "turns": [
                {"turn": 1, "input": {}, "steps": [], "output": {}},
                {"turn": 3, "input": {}, "steps": [], "output": {}},
            ],
        }, "test", report)
        assert report.ok  # warning, not error
        assert any("not sequential" in i.message for i in report.warnings)

    def test_step_missing_type(self):
        report = ValidationReport()
        _validate_trace({
            "turns": [
                {
                    "turn": 1,
                    "input": {"content": "hi"},
                    "steps": [{"data": {"foo": "bar"}}],  # missing type
                    "output": {"content": "bye"},
                },
            ],
        }, "test", report)
        assert not report.ok
        assert any("'type'" in i.message for i in report.errors)

    def test_step_missing_data(self):
        report = ValidationReport()
        _validate_trace({
            "turns": [
                {
                    "turn": 1,
                    "input": {"content": "hi"},
                    "steps": [{"type": "llm_call"}],  # missing data
                    "output": {"content": "bye"},
                },
            ],
        }, "test", report)
        assert not report.ok
        assert any("'data'" in i.message for i in report.errors)


# --- Test result validation ---

class TestResultValidation:
    def test_valid_result(self, tmp_path):
        path = tmp_path / "test__item.result.json"
        write_json(path, {
            "test_name": "test_summarize",
            "dataset": "meetings",
            "item_id": "standup",
            "outputs": {"summary": "Meeting summary"},
            "trace": {
                "turns": [
                    {
                        "turn": 1,
                        "input": {"content": "summarize"},
                        "steps": [],
                        "output": {"content": "summary"},
                    },
                ],
            },
            "duration": 1.5,
        })
        report = ValidationReport()
        _validate_result_file(path, report)
        assert report.ok

    def test_missing_test_name(self, tmp_path):
        path = tmp_path / "bad.result.json"
        write_json(path, {"dataset": "ds", "outputs": {}})
        report = ValidationReport()
        _validate_result_file(path, report)
        assert not report.ok
        assert any("'test_name'" in i.message for i in report.errors)

    def test_judge_results_wrong_score(self, tmp_path):
        path = tmp_path / "scored.result.json"
        write_json(path, {
            "test_name": "test_x",
            "outputs": {},
            "judge_results": [
                {
                    "spec": {"method": "rule", "rule": "contains"},
                    "score": 5,  # should be 0 or 1 for rule
                    "reason": "test",
                },
            ],
        })
        report = ValidationReport()
        _validate_result_file(path, report)
        assert not report.ok
        assert any("Binary/rule score must be 0 or 1" in i.message for i in report.errors)


# --- Test cross-validation (values_from against items) ---

class TestCrossValidation:
    def test_values_from_field_missing_in_item(self, tmp_path):
        feature = make_dataset(tmp_path, "ds", """
            name: ds
            judge_specs:
              - method: rule
                rule: contains_all
                args:
                  field: outputs.text
                  values_from: expected_values
        """, items={
            "item1": {"_id": "item1", "text": "hello"},
            "item2": {"_id": "item2", "text": "world", "expected_values": ["a"]},
        })
        report = validate_feature(feature)
        assert not report.ok
        assert any("values_from" in i.message and "item1" in i.message for i in report.errors)

    def test_values_from_field_present_in_all_items(self, tmp_path):
        feature = make_dataset(tmp_path, "ds", """
            name: ds
            judge_specs:
              - method: rule
                rule: contains_all
                args:
                  field: outputs.text
                  values_from: expected_values
        """, items={
            "item1": {"_id": "item1", "expected_values": ["a"]},
            "item2": {"_id": "item2", "expected_values": ["b"]},
        })
        report = validate_feature(feature)
        assert report.ok


# --- Test duplicate item IDs ---

class TestDuplicateIds:
    def test_duplicate_item_ids(self, tmp_path):
        feature = tmp_path / "test_feature"
        ds_dir = feature / "datasets" / "ds"
        ds_dir.mkdir(parents=True)
        write_yaml(ds_dir / "manifest.yaml", "name: ds")
        write_json(ds_dir / "a.json", {"_id": "same_id"})
        write_json(ds_dir / "b.json", {"_id": "same_id"})
        report = validate_feature(feature)
        assert not report.ok
        assert any("Duplicate item _id" in i.message for i in report.errors)
