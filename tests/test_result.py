"""Tests for result store and summary generation."""

import tempfile
from pathlib import Path

from vibeval.result import save_result, load_run, build_summary, save_summary, load_summary, list_runs


class TestResultStore:
    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir) / "run1"
            result = {
                "test_name": "test_a",
                "outputs": {"answer": "hello"},
                "judge_results": [],
            }
            save_result(result, str(run_dir))

            loaded = load_run(str(run_dir))
            assert len(loaded) == 1
            assert loaded[0]["test_name"] == "test_a"

    def test_list_runs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "run-001").mkdir()
            (Path(tmpdir) / "run-002").mkdir()
            runs = list_runs(tmpdir)
            assert runs == ["run-001", "run-002"]


class TestSummary:
    def test_binary_stats(self):
        results = [
            {
                "test_name": "t1",
                "judge_results": [
                    {"spec": {"method": "rule", "rule": "contains"}, "score": 1, "reason": "ok"},
                    {"spec": {"method": "llm", "scoring": "binary"}, "score": 0, "reason": "fail"},
                ],
                "duration": 1.0,
            },
            {
                "test_name": "t2",
                "judge_results": [
                    {"spec": {"method": "rule", "rule": "contains"}, "score": 1, "reason": "ok"},
                    {"spec": {"method": "llm", "scoring": "binary"}, "score": 1, "reason": "ok"},
                ],
                "duration": 2.0,
            },
        ]

        summary = build_summary(results, "test-run")
        assert summary["total"] == 2
        assert summary["duration"] == 3.0
        assert summary["binary_stats"]["total"] == 4
        assert summary["binary_stats"]["passed"] == 3
        assert summary["binary_stats"]["pass_rate"] == 0.75

    def test_five_point_stats(self):
        results = [
            {
                "test_name": "t1",
                "judge_results": [
                    {"spec": {"method": "llm", "scoring": "five-point", "criteria": "accuracy"}, "score": 4},
                    {"spec": {"method": "llm", "scoring": "five-point", "criteria": "completeness"}, "score": 3},
                ],
            },
            {
                "test_name": "t2",
                "judge_results": [
                    {"spec": {"method": "llm", "scoring": "five-point", "criteria": "accuracy"}, "score": 5},
                    {"spec": {"method": "llm", "scoring": "five-point", "criteria": "completeness"}, "score": 4},
                ],
            },
        ]

        summary = build_summary(results, "test-run")
        assert summary["five_point_stats"]["accuracy"]["avg"] == 4.5
        assert summary["five_point_stats"]["completeness"]["avg"] == 3.5
        assert summary["five_point_stats"]["accuracy"]["4"] == 1
        assert summary["five_point_stats"]["accuracy"]["5"] == 1

    def test_save_and_load_summary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            results = [{"test_name": "t1", "judge_results": [], "duration": 1.0}]
            save_summary(results, tmpdir, metadata={"git": "abc"})
            summary = load_summary(tmpdir)
            assert summary["total"] == 1
            assert summary["metadata"]["git"] == "abc"
