"""Result loader/writer — reads and writes protocol-format results."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any


def load_result(path: str | Path) -> dict[str, Any]:
    """Load a single TestResult from a .result.json file."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_run(run_dir: str | Path) -> list[dict[str, Any]]:
    """Load all TestResults from a run directory."""
    run_dir = Path(run_dir)
    results = []
    for f in sorted(run_dir.iterdir()):
        if f.name == "summary.json" or not f.name.endswith(".result.json"):
            continue
        results.append(load_result(f))
    return results


def load_summary(run_dir: str | Path) -> dict[str, Any]:
    """Load the RunSummary from a run directory."""
    path = Path(run_dir) / "summary.json"
    if not path.exists():
        raise FileNotFoundError(f"No summary in {run_dir}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_result(result: dict[str, Any], run_dir: str | Path) -> Path:
    """Save a single TestResult to a run directory."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    test_name = _safe_name(result["test_name"])
    item_id = result.get("item_id", "")
    name = f"{test_name}__{_safe_name(item_id)}" if item_id else test_name
    path = run_dir / f"{name}.result.json"
    path.write_text(
        json.dumps(result, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def save_summary(results: list[dict[str, Any]], run_dir: str | Path, metadata: dict[str, Any] | None = None) -> Path:
    """Generate and save a RunSummary from a list of TestResults."""
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    summary = build_summary(results, run_dir.name, metadata)

    path = run_dir / "summary.json"
    path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def build_summary(results: list[dict[str, Any]], run_id: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build a RunSummary dict from a list of TestResults."""
    binary_total = 0
    binary_passed = 0

    five_point: dict[str, list[int]] = {}  # criteria -> list of scores

    total_duration = 0.0

    for r in results:
        total_duration += r.get("duration", 0)
        for jr in r.get("judge_results", []):
            spec = jr.get("spec", {})
            method = spec.get("method", "")
            scoring = spec.get("scoring", "")
            score = jr.get("score", 0)

            if method == "rule" or (method == "llm" and scoring == "binary"):
                binary_total += 1
                if score == 1:
                    binary_passed += 1
            elif method == "llm" and scoring == "five-point":
                criteria = spec.get("criteria", "unknown")
                five_point.setdefault(criteria, []).append(int(score))

    # Build five-point stats
    five_point_stats: dict[str, Any] = {}
    for criteria, scores in five_point.items():
        dist = {str(i): scores.count(i) for i in range(1, 6)}
        dist["avg"] = round(sum(scores) / len(scores), 2) if scores else 0
        five_point_stats[criteria] = dist

    return {
        "run_id": run_id,
        "timestamp": time.time(),
        "total": len(results),
        "duration": total_duration,
        "binary_stats": {
            "total": binary_total,
            "passed": binary_passed,
            "failed": binary_total - binary_passed,
            "pass_rate": round(binary_passed / binary_total, 4) if binary_total > 0 else 0,
        },
        "five_point_stats": five_point_stats,
        "metadata": metadata or {},
    }


def new_run_id(results_dir: str | Path) -> str:
    """Generate a new run ID."""
    results_dir = Path(results_dir)
    date_str = datetime.now().strftime("%Y-%m-%d")
    existing = [
        d.name for d in results_dir.iterdir()
        if d.is_dir() and d.name.startswith(date_str)
    ] if results_dir.exists() else []
    seq = len(existing) + 1
    return f"{date_str}_{seq:03d}"


def list_runs(results_dir: str | Path) -> list[str]:
    """List all run IDs."""
    results_dir = Path(results_dir)
    if not results_dir.exists():
        return []
    return sorted(d.name for d in results_dir.iterdir() if d.is_dir())


def _safe_name(name: str) -> str:
    return name.replace("/", "_").replace("\\", "_").replace(":", "_").replace(" ", "_")
