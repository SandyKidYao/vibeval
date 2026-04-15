"""Tests for vibeval serve REST API handlers.

These tests exercise the in-process router + handlers directly (no HTTP
layer) against a temporary feature tree laid out in the vibeval protocol
format. They cover the v0.7.2 serve-command improvements:

- contract endpoint (present + absent)
- compact overview endpoint (no full item payloads, counts + has_contract)
- run detail endpoint NOT joining against current datasets (historical
  accuracy — a past run must not be displayed against today's edited items)
- dedicated datasets listing endpoint (still full items)
- run-results filter-surface data shape
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from vibeval.config import Config
from vibeval.serve.api import register_routes
from vibeval.serve.router import Router


# ---------------------------------------------------------------------------
# Fixture: minimal feature tree on disk
# ---------------------------------------------------------------------------


@pytest.fixture()
def router() -> Router:
    r = Router()
    register_routes(r)
    return r


@pytest.fixture()
def feature_tree(tmp_path: Path) -> tuple[Config, str]:
    """Build a minimal but realistic feature tree and return (config, feature_name)."""
    vroot = tmp_path / "vibeval"
    feature = "demo"
    fdir = vroot / feature
    (fdir / "datasets" / "core").mkdir(parents=True)
    (fdir / "results" / "2026-04-15_001").mkdir(parents=True)

    # contract.yaml
    (fdir / "contract.yaml").write_text(
        yaml.safe_dump(
            {
                "feature": feature,
                "created": "2026-04-15",
                "updated": "2026-04-15",
                "rigor": "standard",
                "output_language": "English",
                "requirements": [
                    {"id": "req-1", "description": "Must greet user", "source": "user"},
                ],
                "known_gaps": [
                    {"requirement": "req-1", "gap": "No greeting in code"},
                ],
                "quality_criteria": {
                    "coverage": {"bar": "High"},
                },
                "feedback_log": [],
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    # datasets/core/manifest.yaml + one item
    (fdir / "datasets" / "core" / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "core",
                "description": "Core greeting tests",
                "version": "1",
                "tags": ["smoke"],
                "judge_specs": [
                    {"method": "rule", "rule": "contains", "args": {"field": "outputs.reply", "value": "hi"}},
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (fdir / "datasets" / "core" / "item1.json").write_text(
        json.dumps({"_id": "item1", "prompt": "original prompt for item1"}),
        encoding="utf-8",
    )

    # results/2026-04-15_001 — one result file + summary
    result_payload = {
        "test_name": "test_greet",
        "dataset": "core",
        "item_id": "item1",
        "judge_results": [
            {
                "spec": {"method": "rule", "rule": "contains"},
                "score": 1,
                "reason": "ok",
            }
        ],
        "trace": {"turns": []},
        # This is the historical snapshot of what was actually sent:
        "inputs": {"prompt": "HISTORICAL prompt at run time"},
        "outputs": {"reply": "hi there"},
        "duration": 0.5,
    }
    (fdir / "results" / "2026-04-15_001" / "test_greet__item1.result.json").write_text(
        json.dumps(result_payload), encoding="utf-8"
    )
    (fdir / "results" / "2026-04-15_001" / "summary.json").write_text(
        json.dumps(
            {
                "run_id": "2026-04-15_001",
                "timestamp": 0,
                "total": 1,
                "duration": 0.5,
                "binary_stats": {"total": 1, "passed": 1, "failed": 0, "pass_rate": 1.0},
                "five_point_stats": {},
                "metadata": {},
            }
        ),
        encoding="utf-8",
    )

    config = Config(vibeval_root=str(vroot))
    return config, feature


def _call(router: Router, config: Config, method: str, path: str, body=None):
    match = router.dispatch(method, path)
    assert match is not None, f"no route for {method} {path}"
    handler, params = match
    return handler(config, params, body)


# ---------------------------------------------------------------------------
# Contract endpoint
# ---------------------------------------------------------------------------


def test_get_contract_returns_parsed_yaml(router, feature_tree):
    config, feature = feature_tree
    status, data = _call(router, config, "GET", f"/api/features/{feature}/contract")
    assert status == 200
    assert data["feature"] == feature
    assert data["rigor"] == "standard"
    assert data["requirements"][0]["id"] == "req-1"
    assert data["known_gaps"][0]["requirement"] == "req-1"


def test_get_contract_returns_null_when_missing(router, feature_tree):
    config, feature = feature_tree
    (Path(config.vibeval_root) / feature / "contract.yaml").unlink()
    status, data = _call(router, config, "GET", f"/api/features/{feature}/contract")
    assert status == 200
    assert data is None


def test_get_contract_raises_value_error_on_malformed_yaml(router, feature_tree):
    config, feature = feature_tree
    (Path(config.vibeval_root) / feature / "contract.yaml").write_text(
        "feature: demo\n  bad_indent: [", encoding="utf-8"
    )
    with pytest.raises(ValueError):
        _call(router, config, "GET", f"/api/features/{feature}/contract")


# ---------------------------------------------------------------------------
# Compact overview endpoint
# ---------------------------------------------------------------------------


def test_get_feature_overview_is_compact(router, feature_tree):
    """The overview endpoint must return counts, not full items/specs.

    Even with many large datasets, loading the Overview tab must stay cheap.
    """
    config, feature = feature_tree
    status, data = _call(router, config, "GET", f"/api/features/{feature}")
    assert status == 200
    assert data["dataset_count"] == 1
    assert data["item_count"] == 1
    assert data["has_contract"] is True
    assert len(data["datasets"]) == 1
    ds = data["datasets"][0]
    # Compact shape — items and judge_specs must NOT be serialized here.
    assert "items" not in ds
    assert "judge_specs" not in ds
    assert ds["item_count"] == 1
    assert ds["spec_count"] == 1
    assert ds["name"] == "core"
    # Runs are still included as summaries.
    assert len(data["runs"]) == 1
    assert data["runs"][0]["run_id"] == "2026-04-15_001"


def test_get_feature_overview_has_contract_false_when_missing(router, feature_tree):
    config, feature = feature_tree
    (Path(config.vibeval_root) / feature / "contract.yaml").unlink()
    _, data = _call(router, config, "GET", f"/api/features/{feature}")
    assert data["has_contract"] is False


# ---------------------------------------------------------------------------
# Run detail endpoint — historical accuracy
# ---------------------------------------------------------------------------


def test_get_run_does_not_leak_current_datasets(router, feature_tree):
    """A past run must not be displayed against the *current* dataset.

    Regression test for the v0.7.2 review: if the endpoint joined results
    with `load_all_datasets()`, editing an item after the run would make
    the run detail page show today's item as the context for yesterday's
    verdict — actively misleading.
    """
    config, feature = feature_tree

    # Simulate the user editing the dataset item AFTER the run completed.
    (Path(config.vibeval_root) / feature / "datasets" / "core" / "item1.json").write_text(
        json.dumps({"_id": "item1", "prompt": "EDITED prompt after the run"}),
        encoding="utf-8",
    )

    status, data = _call(
        router, config, "GET", f"/api/features/{feature}/runs/2026-04-15_001"
    )
    assert status == 200
    # The run payload must NOT expose the current dataset state.
    assert "datasets" not in data
    # It must still provide summary + results.
    assert data["summary"]["run_id"] == "2026-04-15_001"
    assert len(data["results"]) == 1
    result = data["results"][0]
    # The historical snapshot travels inside the result file itself.
    assert result["inputs"] == {"prompt": "HISTORICAL prompt at run time"}
    # Ensure the edited current state is NOT anywhere in the response.
    blob = json.dumps(data)
    assert "EDITED prompt after the run" not in blob


def test_get_run_404_for_missing_run(router, feature_tree):
    config, feature = feature_tree
    with pytest.raises(FileNotFoundError):
        _call(router, config, "GET", f"/api/features/{feature}/runs/nope")


# ---------------------------------------------------------------------------
# Datasets listing endpoint — still full payload (used by the Datasets tab)
# ---------------------------------------------------------------------------


def test_datasets_list_includes_full_items(router, feature_tree):
    config, feature = feature_tree
    status, data = _call(router, config, "GET", f"/api/features/{feature}/datasets")
    assert status == 200
    assert len(data) == 1
    ds = data[0]
    assert ds["name"] == "core"
    assert len(ds["items"]) == 1
    assert ds["items"][0]["id"] == "item1"
    assert ds["items"][0]["data"]["prompt"] == "original prompt for item1"
    assert ds["judge_specs"][0]["rule"] == "contains"


# ---------------------------------------------------------------------------
# Features list — has_contract + latest run summary
# ---------------------------------------------------------------------------


def test_features_list_reports_has_contract_and_latest_run(router, feature_tree):
    config, _feature = feature_tree
    status, data = _call(router, config, "GET", "/api/features")
    assert status == 200
    assert len(data) == 1
    f = data[0]
    assert f["name"] == "demo"
    assert f["dataset_count"] == 1
    assert f["run_count"] == 1
    assert f["latest_run"] == "2026-04-15_001"
    assert f["latest_pass_rate"] == 1.0
    assert f["has_contract"] is True
