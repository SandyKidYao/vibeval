"""Dataset loader — reads protocol-format datasets."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class DataItem:
    """A single data item with its judge specs."""

    id: str
    tags: list[str]
    data: dict[str, Any]
    judge_specs: list[dict[str, Any]]  # item-level specs, or empty to use manifest default

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


@dataclass
class Dataset:
    """A loaded dataset with its manifest and items."""

    name: str
    description: str = ""
    version: str = "1"
    tags: list[str] = field(default_factory=list)
    judge_specs: list[dict[str, Any]] = field(default_factory=list)  # manifest-level defaults
    items: list[DataItem] = field(default_factory=list)

    def effective_specs(self, item: DataItem) -> list[dict[str, Any]]:
        """Get the effective judge specs for an item (item-level overrides manifest)."""
        return item.judge_specs if item.judge_specs else self.judge_specs


def load_dataset(path: str | Path) -> Dataset:
    """Load a dataset from a directory or single file."""
    path = Path(path)
    if path.is_dir():
        return _load_dir(path)
    if path.suffix in (".json", ".yaml", ".yml"):
        return _load_file(path)
    raise FileNotFoundError(f"Not a dataset: {path}")


def load_all_datasets(datasets_dir: str | Path) -> dict[str, Dataset]:
    """Load all datasets from the datasets directory."""
    base = Path(datasets_dir)
    if not base.exists():
        return {}

    result: dict[str, Dataset] = {}
    for p in sorted(base.iterdir()):
        if p.is_dir() and not p.name.startswith("."):
            result[p.name] = _load_dir(p)
        elif p.suffix in (".json", ".yaml", ".yml"):
            result[p.stem] = _load_file(p)
    return result


def _load_dir(dir_path: Path) -> Dataset:
    name = dir_path.name
    manifest: dict[str, Any] = {}

    for mname in ("manifest.yaml", "manifest.yml"):
        mpath = dir_path / mname
        if mpath.exists():
            manifest = yaml.safe_load(mpath.read_text(encoding="utf-8")) or {}
            break

    ds = Dataset(
        name=manifest.get("name", name),
        description=manifest.get("description", ""),
        version=str(manifest.get("version", "1")),
        tags=manifest.get("tags", []),
        judge_specs=manifest.get("judge_specs", []),
    )

    for f in sorted(dir_path.iterdir()):
        if f.name.startswith("manifest"):
            continue
        if f.suffix in (".json", ".yaml", ".yml"):
            ds.items.append(_parse_item(f))

    return ds


def _load_file(path: Path) -> Dataset:
    raw = _read(path)
    name = path.stem

    if isinstance(raw, list):
        items = [DataItem(id=str(i), tags=[], data=d if isinstance(d, dict) else {"value": d}, judge_specs=[]) for i, d in enumerate(raw)]
        return Dataset(name=name, items=items)

    if isinstance(raw, dict) and "items" in raw:
        ds = Dataset(
            name=raw.get("name", name),
            description=raw.get("description", ""),
            version=str(raw.get("version", "1")),
            tags=raw.get("tags", []),
            judge_specs=raw.get("judge_specs", []),
        )
        for i, d in enumerate(raw["items"]):
            if isinstance(d, dict):
                ds.items.append(DataItem(
                    id=d.pop("_id", str(i)),
                    tags=d.pop("_tags", []),
                    judge_specs=d.pop("_judge_specs", []),
                    data=d,
                ))
            else:
                ds.items.append(DataItem(id=str(i), tags=[], data={"value": d}, judge_specs=[]))
        return ds

    if isinstance(raw, dict):
        return Dataset(name=name, items=[DataItem(id="0", tags=[], data=raw, judge_specs=[])])

    return Dataset(name=name, items=[DataItem(id="0", tags=[], data={"value": raw}, judge_specs=[])])


def _parse_item(path: Path) -> DataItem:
    raw = _read(path)
    if isinstance(raw, dict):
        return DataItem(
            id=str(raw.pop("_id", path.stem)),
            tags=raw.pop("_tags", []),
            judge_specs=raw.pop("_judge_specs", []),
            data=raw,
        )
    return DataItem(id=path.stem, tags=[], data={"value": raw}, judge_specs=[])


def _read(path: Path) -> Any:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    return yaml.safe_load(text)
