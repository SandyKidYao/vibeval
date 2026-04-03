"""Judge — the core evaluation engine.

Reads datasets (with judge_specs) and results (with trace + outputs),
executes each judge_spec, and writes back judge_results.

Operates per-feature: vibeval judge {feature} {run_id}
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import Config
from .dataset import Dataset, DataItem, load_all_datasets
from .llm import evaluate_llm
from .result import load_run, save_result, save_summary
from .rules import evaluate_rule


def judge_run(feature: str, run_id: str, config: Config) -> list[dict[str, Any]]:
    """Judge all results in a feature's run against its dataset specs.

    Returns the list of updated TestResults with judge_results populated.
    """
    datasets_dir = config.datasets_dir(feature)
    run_dir = config.results_dir(feature) / run_id

    # Load datasets and results
    datasets = load_all_datasets(str(datasets_dir))
    results = load_run(str(run_dir))

    updated_results = []
    for result in results:
        updated = judge_single(result, datasets, config)
        updated_results.append(updated)
        save_result(updated, str(run_dir))

    # Generate summary
    save_summary(updated_results, str(run_dir))

    return updated_results


def judge_single(result: dict[str, Any], datasets: dict[str, Dataset], config: Config) -> dict[str, Any]:
    """Judge a single TestResult against its dataset's judge_specs."""
    dataset_name = result.get("dataset", "")
    item_id = result.get("item_id", "")

    dataset = datasets.get(dataset_name)
    if dataset is None:
        result["judge_results"] = [{
            "spec": {},
            "score": 0,
            "reason": f"Dataset '{dataset_name}' not found",
        }]
        return result

    # Find the specific data item
    item = _find_item(dataset, item_id)

    # Get effective judge specs
    specs = dataset.effective_specs(item) if item else dataset.judge_specs

    # Evaluate each spec
    judge_results = []
    gate_failed = False

    for spec in specs:
        if gate_failed:
            judge_results.append({
                "spec": spec,
                "score": 0,
                "reason": "Skipped due to gate failure",
            })
            continue

        jr = _evaluate_spec(spec, result, item, config)
        judge_results.append(jr)

        # Check gate
        if spec.get("weight") == "gate" and jr["score"] == 0:
            gate_failed = True

    result["judge_results"] = judge_results
    return result


def _evaluate_spec(spec: dict[str, Any], result: dict[str, Any], item: DataItem | None, config: Config) -> dict[str, Any]:
    """Evaluate a single JudgeSpec."""
    method = spec.get("method", "")
    item_data = item.data if item else None

    if method == "rule":
        return evaluate_rule(spec, result, item_data)
    elif method == "llm":
        return evaluate_llm(spec, result, item_data, config.llm)
    else:
        return {
            "spec": spec,
            "score": 0,
            "reason": f"Unknown method: {method}",
        }


def _find_item(dataset: Dataset, item_id: str) -> DataItem | None:
    """Find a data item by ID."""
    if not item_id:
        return dataset.items[0] if dataset.items else None
    for item in dataset.items:
        if item.id == item_id:
            return item
    return None
