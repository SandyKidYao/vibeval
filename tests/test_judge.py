"""Tests for Judge (v0.2 turn-based trace format)."""

import json
import tempfile
from pathlib import Path

from vibeval.config import Config
from vibeval.judge import judge_run
from vibeval.result import save_result, load_summary


class TestJudgeWithRules:

    def _setup(self, tmpdir: Path):
        feature = "greeting_test"
        vibeval_root = tmpdir / "tests" / "vibeval"

        ds_dir = vibeval_root / feature / "datasets" / "greetings"
        ds_dir.mkdir(parents=True)

        (ds_dir / "manifest.yaml").write_text("""
name: greetings
judge_specs:
  - method: rule
    rule: contains
    args:
      field: "outputs.answer"
      value: "hello"
    weight: gate
  - method: rule
    rule: not_contains
    args:
      field: "outputs.answer"
      value: "ERROR"
""")

        (ds_dir / "item_001.json").write_text(json.dumps({
            "_id": "basic",
            "query": "hi there",
        }))

        results_dir = vibeval_root / feature / "results" / "run1"
        results_dir.mkdir(parents=True)

        result = {
            "test_name": "test_greeting",
            "dataset": "greetings",
            "item_id": "basic",
            "judge_results": [],
            "trace": {"turns": [
                {"turn": 1, "input": {"content": "hi there"},
                 "steps": [], "output": {"content": "hello world"}},
            ]},
            "inputs": {"query": "hi there"},
            "outputs": {"answer": "hello world"},
            "duration": 0.5,
        }
        save_result(result, str(results_dir))

        return Config(vibeval_root=str(vibeval_root)), feature

    def test_judge_run_pass(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config, feature = self._setup(Path(tmpdir))
            results = judge_run(feature, "run1", config)

            assert len(results) == 1
            jr = results[0]["judge_results"]
            assert jr[0]["score"] == 1
            assert jr[1]["score"] == 1

            summary = load_summary(str(config.results_dir(feature) / "run1"))
            assert summary["binary_stats"]["pass_rate"] == 1.0

    def test_judge_run_gate_fail(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config, feature = self._setup(Path(tmpdir))

            results_dir = config.results_dir(feature) / "run1"
            result = {
                "test_name": "test_greeting",
                "dataset": "greetings",
                "item_id": "basic",
                "judge_results": [],
                "outputs": {"answer": "goodbye ERROR"},
            }
            save_result(result, str(results_dir))

            results = judge_run(feature, "run1", config)
            jr = results[0]["judge_results"]
            assert jr[0]["score"] == 0
            assert "Skipped" in jr[1]["reason"]

    def test_trace_rules(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            feature = "agent_test"
            vibeval_root = Path(tmpdir) / "tests" / "vibeval"

            ds_dir = vibeval_root / feature / "datasets" / "traced"
            ds_dir.mkdir(parents=True)

            (ds_dir / "manifest.yaml").write_text("""
name: traced
judge_specs:
  - method: rule
    rule: tool_called
    args:
      tool_name: "search"
  - method: rule
    rule: max_steps
    args:
      max: 10
""")

            (ds_dir / "item_001.json").write_text(json.dumps({"_id": "q1"}))

            results_dir = vibeval_root / feature / "results" / "run1"
            results_dir.mkdir(parents=True)
            result = {
                "test_name": "test_agent",
                "dataset": "traced",
                "item_id": "q1",
                "judge_results": [],
                "trace": {"turns": [
                    {"turn": 1, "input": {"content": "weather"},
                     "steps": [
                         {"type": "tool_call", "data": {"name": "search", "args": {"q": "weather"}}},
                         {"type": "tool_result", "data": {"name": "search", "result": "sunny"}},
                         {"type": "llm_call", "data": {"prompt": "..."}},
                         {"type": "llm_output", "data": {"content": "It's sunny"}},
                     ],
                     "output": {"content": "It's sunny"}},
                ]},
                "outputs": {"answer": "It's sunny"},
            }
            save_result(result, str(results_dir))

            config = Config(vibeval_root=str(vibeval_root))
            results = judge_run(feature, "run1", config)
            jr = results[0]["judge_results"]
            assert jr[0]["score"] == 1  # tool_called
            assert jr[1]["score"] == 1  # max_steps


class TestJudgeItemOverride:

    def test_item_specs_override(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            feature = "override_test"
            vibeval_root = Path(tmpdir) / "tests" / "vibeval"

            ds_dir = vibeval_root / feature / "datasets" / "myds"
            ds_dir.mkdir(parents=True)

            (ds_dir / "manifest.yaml").write_text("""
name: myds
judge_specs:
  - method: rule
    rule: contains
    args:
      field: "outputs.answer"
      value: "default"
""")

            (ds_dir / "item_001.json").write_text(json.dumps({
                "_id": "special",
                "_judge_specs": [
                    {"method": "rule", "rule": "contains", "args": {"field": "outputs.answer", "value": "custom"}}
                ],
            }))

            results_dir = vibeval_root / feature / "results" / "run1"
            results_dir.mkdir(parents=True)
            save_result({
                "test_name": "test_special",
                "dataset": "myds",
                "item_id": "special",
                "judge_results": [],
                "outputs": {"answer": "custom response"},
            }, str(results_dir))

            config = Config(vibeval_root=str(vibeval_root))
            results = judge_run(feature, "run1", config)
            assert results[0]["judge_results"][0]["score"] == 1
