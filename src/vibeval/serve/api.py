"""REST API endpoint handlers for vibeval serve."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

import yaml

from ..config import Config
from ..dataset import Dataset, load_all_datasets, load_dataset
from ..result import list_runs, load_run, load_summary, load_result
from .router import Router


def register_routes(router: Router) -> None:
    """Register all API routes."""

    # ------------------------------------------------------------------
    # Validation helper
    # ------------------------------------------------------------------

    def _safe(name: str) -> str:
        """Validate a path segment against traversal attacks."""
        if not name or ".." in name or "/" in name or "\\" in name or "\x00" in name:
            raise ValueError(f"Invalid name: {name!r}")
        return name

    # ------------------------------------------------------------------
    # Features
    # ------------------------------------------------------------------

    @router.get("/api/features")
    def list_features(config: Config, params: dict, body: Any) -> tuple[int, Any]:
        features = []
        for f in config.list_features():
            ds_dir = config.datasets_dir(f)
            ds_count = sum(1 for d in ds_dir.iterdir() if d.is_dir()) if ds_dir.exists() else 0
            runs = list_runs(str(config.results_dir(f)))
            latest_summary = None
            if runs:
                try:
                    latest_summary = load_summary(str(config.results_dir(f) / runs[-1]))
                except FileNotFoundError:
                    pass
            features.append({
                "name": f,
                "dataset_count": ds_count,
                "run_count": len(runs),
                "latest_run": runs[-1] if runs else None,
                "latest_pass_rate": latest_summary.get("binary_stats", {}).get("pass_rate") if latest_summary else None,
            })
        return 200, features

    @router.get("/api/features/{feature}")
    def get_feature(config: Config, params: dict, body: Any) -> tuple[int, Any]:
        feature = _safe(params["feature"])
        fdir = config.feature_dir(feature)
        if not fdir.exists():
            raise FileNotFoundError(f"Feature not found: {feature}")

        datasets = load_all_datasets(str(config.datasets_dir(feature)))
        runs = list_runs(str(config.results_dir(feature)))
        run_summaries = []
        for r in runs:
            try:
                s = load_summary(str(config.results_dir(feature) / r))
                run_summaries.append(s)
            except FileNotFoundError:
                run_summaries.append({"run_id": r})

        return 200, {
            "name": feature,
            "datasets": _serialize_datasets(datasets),
            "runs": run_summaries,
        }

    # ------------------------------------------------------------------
    # Datasets
    # ------------------------------------------------------------------

    @router.get("/api/features/{feature}/datasets")
    def list_datasets(config: Config, params: dict, body: Any) -> tuple[int, Any]:
        feature = _safe(params["feature"])
        datasets = load_all_datasets(str(config.datasets_dir(feature)))
        return 200, _serialize_datasets(datasets)

    @router.get("/api/features/{feature}/datasets/{dataset}")
    def get_dataset(config: Config, params: dict, body: Any) -> tuple[int, Any]:
        feature = _safe(params["feature"])
        ds_name = _safe(params["dataset"])
        ds_path = config.datasets_dir(feature) / ds_name
        if not ds_path.exists():
            raise FileNotFoundError(f"Dataset not found: {ds_name}")
        ds = load_dataset(str(ds_path))
        return 200, _serialize_datasets({ds_name: ds})[0]

    @router.post("/api/features/{feature}/datasets")
    def create_dataset(config: Config, params: dict, body: Any) -> tuple[int, Any]:
        feature = _safe(params["feature"])
        name = _safe(body.get("name", ""))
        ds_dir = config.datasets_dir(feature) / name
        if ds_dir.exists():
            raise ValueError(f"Dataset already exists: {name}")

        ds_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "name": name,
            "description": body.get("description", ""),
            "version": str(body.get("version", "1")),
            "tags": body.get("tags", []),
            "judge_specs": body.get("judge_specs", []),
        }
        (ds_dir / "manifest.yaml").write_text(
            yaml.dump(manifest, allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )
        return 201, {"name": name, "path": str(ds_dir)}

    @router.put("/api/features/{feature}/datasets/{dataset}")
    def update_dataset(config: Config, params: dict, body: Any) -> tuple[int, Any]:
        feature = _safe(params["feature"])
        ds_name = _safe(params["dataset"])
        ds_dir = config.datasets_dir(feature) / ds_name
        if not ds_dir.exists():
            raise FileNotFoundError(f"Dataset not found: {ds_name}")

        manifest_path = ds_dir / "manifest.yaml"
        manifest: dict[str, Any] = {}
        if manifest_path.exists():
            manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}

        for key in ("name", "description", "version", "tags", "judge_specs"):
            if key in body:
                manifest[key] = body[key]

        manifest_path.write_text(
            yaml.dump(manifest, allow_unicode=True, default_flow_style=False),
            encoding="utf-8",
        )
        return 200, manifest

    @router.delete("/api/features/{feature}/datasets/{dataset}")
    def delete_dataset(config: Config, params: dict, body: Any) -> tuple[int, Any]:
        feature = _safe(params["feature"])
        ds_name = _safe(params["dataset"])
        ds_dir = config.datasets_dir(feature) / ds_name
        if not ds_dir.exists():
            raise FileNotFoundError(f"Dataset not found: {ds_name}")
        shutil.rmtree(ds_dir)
        return 204, None

    # ------------------------------------------------------------------
    # Dataset items
    # ------------------------------------------------------------------

    @router.get("/api/features/{feature}/datasets/{dataset}/items/{item_id}")
    def get_item(config: Config, params: dict, body: Any) -> tuple[int, Any]:
        feature = _safe(params["feature"])
        ds_name = _safe(params["dataset"])
        item_id = _safe(params["item_id"])
        ds = load_dataset(str(config.datasets_dir(feature) / ds_name))
        for item in ds.items:
            if item.id == item_id:
                return 200, {"id": item.id, "tags": item.tags, "data": item.data, "judge_specs": item.judge_specs}
        raise FileNotFoundError(f"Item not found: {item_id}")

    @router.post("/api/features/{feature}/datasets/{dataset}/items")
    def create_item(config: Config, params: dict, body: Any) -> tuple[int, Any]:
        feature = _safe(params["feature"])
        ds_name = _safe(params["dataset"])
        ds_dir = config.datasets_dir(feature) / ds_name
        if not ds_dir.exists():
            raise FileNotFoundError(f"Dataset not found: {ds_name}")

        item_id = _safe(body.get("id", body.get("_id", "")))
        if not item_id:
            raise ValueError("Item must have an 'id'")

        item_path = ds_dir / f"{item_id}.json"
        if item_path.exists():
            raise ValueError(f"Item already exists: {item_id}")

        item_data: dict[str, Any] = {"_id": item_id}
        if body.get("tags"):
            item_data["_tags"] = body["tags"]
        if body.get("judge_specs"):
            item_data["_judge_specs"] = body["judge_specs"]
        item_data.update(body.get("data", {}))

        item_path.write_text(
            json.dumps(item_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return 201, {"id": item_id, "path": str(item_path)}

    @router.put("/api/features/{feature}/datasets/{dataset}/items/{item_id}")
    def update_item(config: Config, params: dict, body: Any) -> tuple[int, Any]:
        feature = _safe(params["feature"])
        ds_name = _safe(params["dataset"])
        item_id = _safe(params["item_id"])
        ds_dir = config.datasets_dir(feature) / ds_name

        item_path = _find_item_file(ds_dir, item_id)
        if item_path is None:
            raise FileNotFoundError(f"Item not found: {item_id}")

        existing = json.loads(item_path.read_text(encoding="utf-8"))
        if "tags" in body:
            existing["_tags"] = body["tags"]
        if "judge_specs" in body:
            existing["_judge_specs"] = body["judge_specs"]
        if "data" in body:
            for k in list(existing.keys()):
                if not k.startswith("_"):
                    del existing[k]
            existing.update(body["data"])

        item_path.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return 200, {"id": item_id}

    @router.delete("/api/features/{feature}/datasets/{dataset}/items/{item_id}")
    def delete_item(config: Config, params: dict, body: Any) -> tuple[int, Any]:
        feature = _safe(params["feature"])
        ds_name = _safe(params["dataset"])
        item_id = _safe(params["item_id"])
        ds_dir = config.datasets_dir(feature) / ds_name

        item_path = _find_item_file(ds_dir, item_id)
        if item_path is None:
            raise FileNotFoundError(f"Item not found: {item_id}")
        item_path.unlink()
        return 204, None

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    @router.get("/api/features/{feature}/runs")
    def get_runs(config: Config, params: dict, body: Any) -> tuple[int, Any]:
        feature = _safe(params["feature"])
        runs = list_runs(str(config.results_dir(feature)))
        result = []
        for r in runs:
            try:
                s = load_summary(str(config.results_dir(feature) / r))
                result.append(s)
            except FileNotFoundError:
                result.append({"run_id": r})
        return 200, result

    @router.get("/api/features/{feature}/runs/{run_id}")
    def get_run(config: Config, params: dict, body: Any) -> tuple[int, Any]:
        feature = _safe(params["feature"])
        run_id = _safe(params["run_id"])
        run_dir = config.results_dir(feature) / run_id
        if not run_dir.exists():
            raise FileNotFoundError(f"Run not found: {run_id}")

        summary = load_summary(str(run_dir))
        results = load_run(str(run_dir))
        datasets = load_all_datasets(str(config.datasets_dir(feature)))

        return 200, {
            "summary": summary,
            "results": results,
            "datasets": _serialize_datasets(datasets),
        }

    @router.get("/api/features/{feature}/runs/{run_id}/results/{result_id}")
    def get_result(config: Config, params: dict, body: Any) -> tuple[int, Any]:
        feature = _safe(params["feature"])
        run_id = _safe(params["run_id"])
        result_id = params["result_id"]  # may contain -- separator
        run_dir = config.results_dir(feature) / run_id

        # Try to find the result file
        for f in run_dir.iterdir():
            if f.suffix == ".json" and f.stem == result_id:
                return 200, json.loads(f.read_text(encoding="utf-8"))
            if f.suffix == ".json" and f.name == f"{result_id}.result.json":
                return 200, json.loads(f.read_text(encoding="utf-8"))

        raise FileNotFoundError(f"Result not found: {result_id}")

    # ------------------------------------------------------------------
    # Comparisons
    # ------------------------------------------------------------------

    @router.get("/api/features/{feature}/comparisons")
    def get_comparisons(config: Config, params: dict, body: Any) -> tuple[int, Any]:
        feature = _safe(params["feature"])
        feature_dir = config.feature_dir(feature)
        comparisons = _load_comparisons(feature_dir)
        return 200, comparisons

    # ------------------------------------------------------------------
    # Analysis & Design
    # ------------------------------------------------------------------

    @router.get("/api/features/{feature}/analysis")
    def get_analysis(config: Config, params: dict, body: Any) -> tuple[int, Any]:
        feature = _safe(params["feature"])
        analysis_dir = config.analysis_dir(feature)
        if not analysis_dir.exists():
            return 200, None
        return 200, _load_yaml_dir(analysis_dir)

    @router.get("/api/features/{feature}/design")
    def get_design(config: Config, params: dict, body: Any) -> tuple[int, Any]:
        feature = _safe(params["feature"])
        design_dir = config.design_dir(feature)
        if not design_dir.exists():
            return 200, None
        return 200, _load_yaml_dir(design_dir)

    # ------------------------------------------------------------------
    # Trends
    # ------------------------------------------------------------------

    @router.get("/api/features/{feature}/trends")
    def get_trends(config: Config, params: dict, body: Any) -> tuple[int, Any]:
        feature = _safe(params["feature"])
        runs = list_runs(str(config.results_dir(feature)))
        points = []
        for r in runs:
            try:
                s = load_summary(str(config.results_dir(feature) / r))
                bs = s.get("binary_stats", {})
                fs = s.get("five_point_stats", {})
                points.append({
                    "run_id": r,
                    "timestamp": s.get("timestamp"),
                    "total": s.get("total", 0),
                    "pass_rate": bs.get("pass_rate"),
                    "passed": bs.get("passed", 0),
                    "failed": bs.get("failed", 0),
                    "five_point": {k: v.get("avg") for k, v in fs.items()} if fs else {},
                })
            except FileNotFoundError:
                continue
        return 200, points


def _load_yaml_dir(dir_path: Path) -> dict[str, Any]:
    """Load all YAML/JSON files in a directory into a combined dict."""
    result: dict[str, Any] = {}
    for f in sorted(dir_path.iterdir()):
        if f.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if data:
                result[f.stem] = data
        elif f.suffix == ".json":
            data = json.loads(f.read_text(encoding="utf-8"))
            result[f.stem] = data
    return result


def _serialize_datasets(datasets: dict[str, Dataset]) -> list[dict[str, Any]]:
    """Serialize Dataset objects to JSON-friendly dicts."""
    out = []
    for name, ds in datasets.items():
        items = []
        for item in ds.items:
            items.append({
                "id": item.id,
                "tags": item.tags,
                "data": item.data,
                "judge_specs": item.judge_specs,
            })
        out.append({
            "name": ds.name,
            "description": ds.description,
            "version": ds.version,
            "tags": ds.tags,
            "judge_specs": ds.judge_specs,
            "items": items,
        })
    return out


def _load_comparisons(feature_dir: Path) -> list[dict[str, Any]]:
    """Load all comparison JSON files from a feature's comparisons/ directory."""
    comp_dir = feature_dir / "comparisons"
    if not comp_dir.exists():
        return []
    result = []
    for f in sorted(comp_dir.iterdir()):
        if f.suffix == ".json":
            result.append(json.loads(f.read_text(encoding="utf-8")))
    return result


def _find_item_file(ds_dir: Path, item_id: str) -> Path | None:
    """Find the file for a given item ID by scanning the dataset directory."""
    for ext in (".json", ".yaml", ".yml"):
        candidate = ds_dir / f"{item_id}{ext}"
        if candidate.exists():
            return candidate
    # Fallback: scan files for matching _id
    for f in ds_dir.iterdir():
        if f.name.startswith("manifest") or f.suffix not in (".json", ".yaml", ".yml"):
            continue
        try:
            text = f.read_text(encoding="utf-8")
            data = json.loads(text) if f.suffix == ".json" else yaml.safe_load(text)
            if isinstance(data, dict) and data.get("_id") == item_id:
                return f
        except Exception:
            continue
    return None
