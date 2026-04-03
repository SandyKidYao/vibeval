"""Tests for pairwise comparison."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from vibeval.config import Config
from vibeval.compare import compare_runs, _reconcile, _parse_comparison


class TestReconcile:
    """Test the position-bias reconciliation logic."""

    def test_consistent_a_wins(self):
        # ab: a wins, ba: b wins (b in ba = a in original) → a wins, consistent
        winner, confidence = _reconcile(
            {"winner": "a", "reason": ""},
            {"winner": "b", "reason": ""},
        )
        assert winner == "a"
        assert confidence == "consistent"

    def test_consistent_b_wins(self):
        # ab: b wins, ba: a wins (a in ba = b in original) → b wins, consistent
        winner, confidence = _reconcile(
            {"winner": "b", "reason": ""},
            {"winner": "a", "reason": ""},
        )
        assert winner == "b"
        assert confidence == "consistent"

    def test_consistent_tie(self):
        winner, confidence = _reconcile(
            {"winner": "tie", "reason": ""},
            {"winner": "tie", "reason": ""},
        )
        assert winner == "tie"
        assert confidence == "consistent"

    def test_contradictory(self):
        # ab: a wins, ba: also a wins → contradiction (both say position A is better)
        winner, confidence = _reconcile(
            {"winner": "a", "reason": ""},
            {"winner": "a", "reason": ""},
        )
        assert winner == "inconclusive"
        assert confidence == "inconsistent"

    def test_one_tie_one_winner(self):
        winner, confidence = _reconcile(
            {"winner": "a", "reason": ""},
            {"winner": "tie", "reason": ""},
        )
        assert winner == "a"
        assert confidence == "inconsistent"

    def test_error_handling(self):
        winner, confidence = _reconcile(
            {"winner": "error", "reason": "failed"},
            {"winner": "a", "reason": ""},
        )
        assert winner == "inconclusive"
        assert confidence == "error"


class TestParseComparison:
    def test_parse_json(self):
        result = _parse_comparison('{"winner": "a", "reason": "better coverage"}')
        assert result["winner"] == "a"
        assert result["reason"] == "better coverage"

    def test_parse_b(self):
        result = _parse_comparison('{"winner": "b", "reason": "more accurate"}')
        assert result["winner"] == "b"

    def test_parse_tie(self):
        result = _parse_comparison('{"winner": "tie", "reason": "equal quality"}')
        assert result["winner"] == "tie"

    def test_parse_invalid_defaults_tie(self):
        result = _parse_comparison("I can't decide")
        assert result["winner"] == "tie"


class TestCompareRuns:
    """End-to-end test with mocked LLM."""

    def _setup(self, tmpdir: Path):
        """Create two runs with different outputs."""
        feature = "test_feature"
        vibeval_root = tmpdir / "tests" / "vibeval"

        # Dataset with one LLM judge spec
        ds_dir = vibeval_root / feature / "datasets" / "myds"
        ds_dir.mkdir(parents=True)

        (ds_dir / "manifest.yaml").write_text("""
name: myds
judge_specs:
  - method: rule
    rule: contains
    args:
      field: "outputs.answer"
      value: "hello"
  - method: llm
    scoring: binary
    criteria: "answer is helpful and friendly"
    anchors:
      "0": "unhelpful or rude"
      "1": "helpful and friendly"
    calibrations:
      - output: "Go away"
        score: 0
        reason: "rude"
      - output: "Hello! How can I help?"
        score: 1
        reason: "friendly"
""")

        (ds_dir / "item_001.json").write_text(json.dumps({
            "_id": "q1",
            "query": "hi",
        }))

        # Run A — mediocre output
        run_a_dir = vibeval_root / feature / "results" / "run_a"
        run_a_dir.mkdir(parents=True)
        (run_a_dir / "test_greet__q1.result.json").write_text(json.dumps({
            "test_name": "test_greet",
            "dataset": "myds",
            "item_id": "q1",
            "judge_results": [],
            "outputs": {"answer": "hello"},
            "trace": {"snapshots": []},
        }))

        # Run B — better output
        run_b_dir = vibeval_root / feature / "results" / "run_b"
        run_b_dir.mkdir(parents=True)
        (run_b_dir / "test_greet__q1.result.json").write_text(json.dumps({
            "test_name": "test_greet",
            "dataset": "myds",
            "item_id": "q1",
            "judge_results": [],
            "outputs": {"answer": "hello! I'm happy to help you today."},
            "trace": {"snapshots": []},
        }))

        config = Config(vibeval_root=str(vibeval_root))
        return config, feature

    def test_compare_b_wins(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config, feature = self._setup(Path(tmpdir))

            # Mock LLM to consistently prefer B
            call_count = 0
            def mock_claude(prompt, llm_config=None):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    # AB order: B is better
                    return '{"winner": "b", "reason": "B is more enthusiastic and helpful"}'
                else:
                    # BA order (swapped): A is better (which is run_b in original)
                    return '{"winner": "a", "reason": "A is more enthusiastic and helpful"}'

            with patch("vibeval.compare._call_llm", side_effect=mock_claude):
                result = compare_runs(feature, "run_a", "run_b", config)

            assert result["summary"]["total_pairs"] == 1
            assert result["summary"]["b_wins"] == 1
            assert result["pairs"][0]["winner"] == "b"
            assert result["pairs"][0]["confidence"] == "consistent"

            # Check file was saved
            comp_file = config.feature_dir(feature) / "comparisons" / "run_a_vs_run_b.json"
            assert comp_file.exists()

    def test_compare_inconclusive(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config, feature = self._setup(Path(tmpdir))

            # Mock LLM to be inconsistent (position bias)
            def mock_claude(prompt, llm_config=None):
                # Always picks position A regardless of content
                return '{"winner": "a", "reason": "A is better"}'

            with patch("vibeval.compare._call_llm", side_effect=mock_claude):
                result = compare_runs(feature, "run_a", "run_b", config)

            assert result["pairs"][0]["winner"] == "inconclusive"
            assert result["pairs"][0]["confidence"] == "inconsistent"

    def test_compare_skips_rule_specs(self):
        """Only LLM specs are compared, rule specs are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config, feature = self._setup(Path(tmpdir))

            def mock_claude(prompt, llm_config=None):
                return '{"winner": "tie", "reason": "equal"}'

            with patch("vibeval.compare._call_llm", side_effect=mock_claude):
                result = compare_runs(feature, "run_a", "run_b", config)

            # Only 1 pair (the LLM spec), not 2 (rule spec skipped)
            assert result["summary"]["total_pairs"] == 1
