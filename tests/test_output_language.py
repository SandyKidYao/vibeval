"""Tests for output_language injection through judge and compare runtimes."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from vibeval.compare import _build_comparison_prompt, compare_runs
from vibeval.config import Config, LLMConfig
from vibeval.judge import judge_run
from vibeval.llm import _build_prompt, evaluate_llm
from vibeval.result import save_result


# ---------------------------------------------------------------------------
# Config.output_language reader
# ---------------------------------------------------------------------------


class TestConfigOutputLanguage:

    def _config_with_contract(self, tmpdir: Path, contract_yaml: str | None) -> tuple[Config, str]:
        feature = "demo"
        feature_dir = tmpdir / "tests" / "vibeval" / feature
        feature_dir.mkdir(parents=True)
        if contract_yaml is not None:
            (feature_dir / "contract.yaml").write_text(contract_yaml, encoding="utf-8")
        return Config(vibeval_root=str(tmpdir / "tests" / "vibeval")), feature

    def test_defaults_to_english_when_contract_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, feature = self._config_with_contract(Path(tmp), None)
            assert config.output_language(feature) == "English"

    def test_defaults_to_english_when_field_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, feature = self._config_with_contract(
                Path(tmp), "feature: demo\nrigor: standard\n"
            )
            assert config.output_language(feature) == "English"

    def test_returns_explicit_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, feature = self._config_with_contract(
                Path(tmp), "feature: demo\noutput_language: Chinese\n"
            )
            assert config.output_language(feature) == "Chinese"

    def test_strips_whitespace(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, feature = self._config_with_contract(
                Path(tmp), 'feature: demo\noutput_language: "  Japanese  "\n'
            )
            assert config.output_language(feature) == "Japanese"

    def test_blank_value_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, feature = self._config_with_contract(
                Path(tmp), 'feature: demo\noutput_language: "   "\n'
            )
            assert config.output_language(feature) == "English"

    def test_non_string_value_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, feature = self._config_with_contract(
                Path(tmp), "feature: demo\noutput_language: 42\n"
            )
            assert config.output_language(feature) == "English"

    def test_malformed_yaml_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, feature = self._config_with_contract(
                Path(tmp), "feature: demo\n  - this: is: broken\noutput_language: Chinese\n"
            )
            assert config.output_language(feature) == "English"


# ---------------------------------------------------------------------------
# _build_prompt language injection
# ---------------------------------------------------------------------------


class TestBuildPromptLanguage:

    SPEC = {
        "method": "llm",
        "scoring": "binary",
        "criteria": "Output should greet the user politely.",
    }
    RESULT = {"outputs": {"answer": "hello"}}

    def test_default_english_omits_directive(self):
        prompt = _build_prompt(self.SPEC, self.RESULT, None)
        assert "MUST be written in" not in prompt
        assert "Reminder: write the `reason` value" not in prompt

    def test_explicit_english_omits_directive(self):
        prompt = _build_prompt(self.SPEC, self.RESULT, None, output_language="English")
        assert "MUST be written in" not in prompt

    def test_english_case_insensitive(self):
        prompt = _build_prompt(self.SPEC, self.RESULT, None, output_language="english")
        assert "MUST be written in" not in prompt

    def test_chinese_injects_directive_at_top(self):
        prompt = _build_prompt(self.SPEC, self.RESULT, None, output_language="Chinese")
        assert "MUST be written in Chinese" in prompt
        first_directive = prompt.find("MUST be written in Chinese")
        criteria_pos = prompt.find("## Evaluation Criteria")
        assert first_directive < criteria_pos, "language directive must precede criteria"

    def test_chinese_injects_reminder_after_response_format(self):
        prompt = _build_prompt(self.SPEC, self.RESULT, None, output_language="Chinese")
        assert "Reminder: write the `reason` value in Chinese." in prompt
        reminder_pos = prompt.find("Reminder: write the `reason` value")
        format_pos = prompt.find("## Response Format")
        assert reminder_pos > format_pos

    def test_japanese_uses_provided_name(self):
        prompt = _build_prompt(self.SPEC, self.RESULT, None, output_language="Japanese")
        assert "Japanese" in prompt
        assert "Chinese" not in prompt

    def test_directive_does_not_alter_score_format(self):
        prompt = _build_prompt(self.SPEC, self.RESULT, None, output_language="Spanish")
        assert '{"score": <number>, "reason": "<brief explanation>"}' in prompt


# ---------------------------------------------------------------------------
# evaluate_llm passes language through
# ---------------------------------------------------------------------------


class TestEvaluateLLMLanguage:

    def test_passes_language_to_call_llm(self):
        spec = {"method": "llm", "scoring": "binary", "criteria": "ok"}
        result = {"outputs": {"answer": "hi"}}
        with patch("vibeval.llm._call_llm", return_value='{"score": 1, "reason": "你好，输出符合要求"}') as mock:
            evaluate_llm(spec, result, None, LLMConfig(), output_language="Chinese")
        prompt_arg = mock.call_args[0][0]
        assert "MUST be written in Chinese" in prompt_arg

    def test_default_language_does_not_inject(self):
        spec = {"method": "llm", "scoring": "binary", "criteria": "ok"}
        result = {"outputs": {"answer": "hi"}}
        with patch("vibeval.llm._call_llm", return_value='{"score": 1, "reason": "ok"}') as mock:
            evaluate_llm(spec, result, None, LLMConfig())
        prompt_arg = mock.call_args[0][0]
        assert "MUST be written in" not in prompt_arg


# ---------------------------------------------------------------------------
# judge_run reads contract.yaml and threads language through
# ---------------------------------------------------------------------------


class TestJudgeRunReadsContract:

    def _setup_feature(self, tmpdir: Path, contract_yaml: str | None) -> tuple[Config, str]:
        feature = "lang_test"
        vibeval_root = tmpdir / "tests" / "vibeval"
        feature_dir = vibeval_root / feature
        feature_dir.mkdir(parents=True)

        if contract_yaml is not None:
            (feature_dir / "contract.yaml").write_text(contract_yaml, encoding="utf-8")

        ds_dir = feature_dir / "datasets" / "qa"
        ds_dir.mkdir(parents=True)
        (ds_dir / "manifest.yaml").write_text(
            "name: qa\n"
            "judge_specs:\n"
            "  - method: llm\n"
            "    scoring: binary\n"
            '    criteria: "Output answers the question."\n'
        )
        (ds_dir / "item_001.json").write_text(json.dumps({"_id": "q1"}))

        results_dir = feature_dir / "results" / "run1"
        results_dir.mkdir(parents=True)
        save_result(
            {
                "test_name": "test_qa",
                "dataset": "qa",
                "item_id": "q1",
                "judge_results": [],
                "outputs": {"answer": "42"},
            },
            str(results_dir),
        )

        return Config(vibeval_root=str(vibeval_root)), feature

    def test_judge_run_uses_contract_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, feature = self._setup_feature(
                Path(tmp), "feature: lang_test\noutput_language: Chinese\n"
            )
            with patch(
                "vibeval.llm._call_llm",
                return_value='{"score": 1, "reason": "答案正确"}',
            ) as mock:
                judge_run(feature, "run1", config)
            prompt_arg = mock.call_args[0][0]
            assert "MUST be written in Chinese" in prompt_arg

    def test_judge_run_defaults_to_english_without_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, feature = self._setup_feature(Path(tmp), None)
            with patch(
                "vibeval.llm._call_llm",
                return_value='{"score": 1, "reason": "ok"}',
            ) as mock:
                judge_run(feature, "run1", config)
            prompt_arg = mock.call_args[0][0]
            assert "MUST be written in" not in prompt_arg


# ---------------------------------------------------------------------------
# Comparison prompt language injection
# ---------------------------------------------------------------------------


class TestComparisonPromptLanguage:

    SPEC = {"method": "llm", "criteria": "Which is more concise?"}
    RA = {"outputs": {"answer": "alpha"}}
    RB = {"outputs": {"answer": "beta"}}

    def test_default_english_omits_directive(self):
        prompt = _build_comparison_prompt(self.SPEC, self.RA, self.RB)
        assert "MUST be written in" not in prompt

    def test_chinese_injects_directive(self):
        prompt = _build_comparison_prompt(
            self.SPEC, self.RA, self.RB, output_language="Chinese"
        )
        assert "MUST be written in Chinese" in prompt
        assert "Reminder: write the `reason` value in Chinese." in prompt

    def test_winner_field_kept_literal(self):
        prompt = _build_comparison_prompt(
            self.SPEC, self.RA, self.RB, output_language="Chinese"
        )
        assert '"a", "b", or "tie"' in prompt


class TestCompareRunsReadsContract:

    def _setup(self, tmpdir: Path, contract_yaml: str) -> tuple[Config, str]:
        feature = "compare_lang"
        vibeval_root = tmpdir / "tests" / "vibeval"
        feature_dir = vibeval_root / feature
        feature_dir.mkdir(parents=True)
        (feature_dir / "contract.yaml").write_text(contract_yaml, encoding="utf-8")

        ds_dir = feature_dir / "datasets" / "qa"
        ds_dir.mkdir(parents=True)
        (ds_dir / "manifest.yaml").write_text(
            "name: qa\n"
            "judge_specs:\n"
            "  - method: llm\n"
            "    scoring: binary\n"
            '    criteria: "Which is better"\n'
        )
        (ds_dir / "item_001.json").write_text(json.dumps({"_id": "q1"}))

        for run in ("run_a", "run_b"):
            rdir = feature_dir / "results" / run
            rdir.mkdir(parents=True)
            save_result(
                {
                    "test_name": "test_qa",
                    "dataset": "qa",
                    "item_id": "q1",
                    "judge_results": [],
                    "outputs": {"answer": run},
                },
                str(rdir),
            )

        return Config(vibeval_root=str(vibeval_root)), feature

    def test_compare_runs_threads_language_to_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            config, feature = self._setup(
                Path(tmp), "feature: compare_lang\noutput_language: Japanese\n"
            )
            with patch(
                "vibeval.compare._call_llm",
                return_value='{"winner": "a", "reason": "Aの方が簡潔です"}',
            ) as mock:
                compare_runs(feature, "run_a", "run_b", config)
            assert mock.call_count >= 2
            for call in mock.call_args_list:
                prompt_arg = call[0][0]
                assert "MUST be written in Japanese" in prompt_arg
