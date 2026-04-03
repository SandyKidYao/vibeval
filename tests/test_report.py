"""Tests for vibeval report generation."""

import json
import tempfile
from pathlib import Path

import pytest

from vibeval.report import generate_report, _build_context, _serialize_datasets, _render
from vibeval.dataset import Dataset, DataItem
from vibeval.result import save_result, save_summary


@pytest.fixture
def sample_run(tmp_path):
    """Create a sample run directory with results and datasets."""
    # Create directory structure
    feature_dir = tmp_path / "tests" / "vibeval" / "test_feature"
    run_dir = feature_dir / "results" / "run_001"
    datasets_dir = feature_dir / "datasets"
    ds_dir = datasets_dir / "sample_ds"
    run_dir.mkdir(parents=True)
    ds_dir.mkdir(parents=True)

    # Write dataset manifest
    (ds_dir / "manifest.yaml").write_text(
        "name: sample_ds\n"
        "description: A sample dataset\n"
        "tags: [test]\n"
        "judge_specs:\n"
        "  - method: rule\n"
        "    rule: contains\n"
        "    args: {field: outputs.text, value: hello}\n"
        "    weight: gate\n",
        encoding="utf-8",
    )

    # Write dataset item
    (ds_dir / "item1.json").write_text(
        json.dumps({"_id": "item1", "_tags": ["greet"], "prompt": "say hello"}),
        encoding="utf-8",
    )

    # Write results
    result1 = {
        "test_name": "test_greet",
        "dataset": "sample_ds",
        "item_id": "item1",
        "judge_results": [
            {
                "spec": {"method": "rule", "rule": "contains", "args": {"field": "outputs.text", "value": "hello"}, "weight": "gate"},
                "score": 1,
                "reason": "'hello' found in outputs.text",
            }
        ],
        "trace": {
            "turns": [
                {
                    "turn": 1,
                    "input": {"content": "say hello"},
                    "steps": [
                        {"type": "llm_call", "data": {"prompt_preview": "say hello"}, "timestamp": 1000},
                        {"type": "llm_output", "data": {"content_preview": "hello world"}, "timestamp": 1001},
                    ],
                    "output": {"content": "hello world", "text": "hello world"},
                }
            ]
        },
        "inputs": {"prompt": "say hello"},
        "outputs": {"text": "hello world"},
        "timestamp": 1000,
        "duration": 0.5,
    }
    save_result(result1, str(run_dir))
    save_summary([result1], str(run_dir))

    return {
        "feature_dir": feature_dir,
        "run_dir": run_dir,
        "datasets_dir": datasets_dir,
    }


def test_generate_report_creates_html(sample_run):
    """generate_report should create a valid HTML file."""
    out = generate_report(
        "test_feature", "run_001",
        str(sample_run["run_dir"]),
        str(sample_run["datasets_dir"]),
    )
    assert out.exists()
    assert out.name == "report.html"
    html = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html
    assert "vibeval Report" in html
    assert "test_feature" in html
    assert "run_001" in html


def test_generate_report_custom_output(sample_run, tmp_path):
    """--output flag should write to custom path."""
    custom = tmp_path / "custom_report.html"
    out = generate_report(
        "test_feature", "run_001",
        str(sample_run["run_dir"]),
        str(sample_run["datasets_dir"]),
        output=str(custom),
    )
    assert out == custom
    assert custom.exists()


def test_report_contains_embedded_json(sample_run):
    """Report should contain embedded JSON data."""
    out = generate_report(
        "test_feature", "run_001",
        str(sample_run["run_dir"]),
        str(sample_run["datasets_dir"]),
    )
    html = out.read_text(encoding="utf-8")
    # Extract JSON between const DATA = and ;
    assert "const DATA = " in html
    # Check key data is present
    assert '"test_greet"' in html
    assert '"sample_ds"' in html
    assert '"item1"' in html


def test_build_context_structure(sample_run):
    """_build_context should produce expected keys."""
    from vibeval.result import load_summary, load_run
    from vibeval.dataset import load_all_datasets

    summary = load_summary(str(sample_run["run_dir"]))
    results = load_run(str(sample_run["run_dir"]))
    datasets = load_all_datasets(str(sample_run["datasets_dir"]))

    ctx = _build_context("feat", "run1", summary, results, datasets, [])
    assert ctx["feature"] == "feat"
    assert ctx["run_id"] == "run1"
    assert "generated_at" in ctx
    assert "summary" in ctx
    assert "results" in ctx
    assert "datasets" in ctx
    assert "comparisons" in ctx
    assert len(ctx["results"]) == 1
    assert len(ctx["datasets"]) == 1


def test_serialize_datasets():
    """_serialize_datasets should convert Dataset dataclasses to plain dicts."""
    ds = Dataset(
        name="ds1",
        description="test dataset",
        version="2",
        tags=["a", "b"],
        judge_specs=[{"method": "rule", "rule": "contains", "args": {"field": "x", "value": "y"}}],
        items=[
            DataItem(id="i1", tags=["t1"], data={"key": "val"}, judge_specs=[]),
            DataItem(id="i2", tags=[], data={"k2": "v2"}, judge_specs=[{"method": "rule", "rule": "equals"}]),
        ],
    )
    result = _serialize_datasets({"ds1": ds})
    assert len(result) == 1
    d = result[0]
    assert d["name"] == "ds1"
    assert d["description"] == "test dataset"
    assert d["version"] == "2"
    assert len(d["items"]) == 2
    assert d["items"][0]["id"] == "i1"
    assert d["items"][0]["data"] == {"key": "val"}
    assert d["items"][1]["judge_specs"][0]["rule"] == "equals"


def test_render_escapes_script_tag():
    """_render should escape </script> in embedded JSON."""
    ctx = {
        "feature": "test",
        "run_id": "1",
        "generated_at": "2026-01-01",
        "summary": {"run_id": "1", "total": 0, "duration": 0, "binary_stats": {}, "five_point_stats": {}},
        "results": [{"outputs": {"text": "</script><script>alert(1)</script>"}}],
        "datasets": [],
        "comparisons": [],
    }
    html = _render(ctx)
    assert "</script><script>" not in html
    assert "<\\/script>" in html


def test_report_with_no_judge_results(sample_run):
    """Report should handle results without judge_results gracefully."""
    run_dir = sample_run["run_dir"]
    result = {
        "test_name": "test_nojudge",
        "dataset": "sample_ds",
        "item_id": "item1",
        "judge_results": [],
        "trace": {"turns": []},
        "inputs": {},
        "outputs": {"text": "output"},
        "timestamp": 1000,
        "duration": 0.1,
    }
    save_result(result, str(run_dir))
    # Regenerate summary with both results
    from vibeval.result import load_run
    all_results = load_run(str(run_dir))
    save_summary(all_results, str(run_dir))

    out = generate_report(
        "test_feature", "run_001",
        str(run_dir),
        str(sample_run["datasets_dir"]),
    )
    assert out.exists()
    html = out.read_text(encoding="utf-8")
    assert "test_nojudge" in html
