"""Config loader — reads .vibeval.yml from project root."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class LLMConfig:
    provider: str = "claude-code"  # "claude-code" | "command"
    model: str = ""                # model hint (passed via --model to claude-code)
    command: str = ""              # custom command for "command" provider


@dataclass
class Config:
    vibeval_root: str = "tests/vibeval"    # root of all vibeval feature directories
    llm: LLMConfig = field(default_factory=LLMConfig)

    def feature_dir(self, feature: str) -> Path:
        """Get the path to a feature directory."""
        return Path(self.vibeval_root) / feature

    def datasets_dir(self, feature: str) -> Path:
        return self.feature_dir(feature) / "datasets"

    def results_dir(self, feature: str) -> Path:
        return self.feature_dir(feature) / "results"

    def baselines_dir(self, feature: str) -> Path:
        return self.feature_dir(feature) / "baselines"

    def list_features(self) -> list[str]:
        """List all feature directories under vibeval_root."""
        root = Path(self.vibeval_root)
        if not root.exists():
            return []
        return sorted(
            d.name for d in root.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )

    @staticmethod
    def load(project_root: str | Path = ".") -> Config:
        """Load config from .vibeval.yml, falling back to defaults."""
        root = Path(project_root)
        config = Config()

        for name in (".vibeval.yml", ".vibeval.yaml"):
            path = root / name
            if path.exists():
                raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                config.vibeval_root = raw.get("vibeval_root", config.vibeval_root)

                judge = raw.get("judge", {})
                llm = judge.get("llm", {})
                if llm:
                    config.llm.provider = llm.get("provider", config.llm.provider)
                    config.llm.model = llm.get("model", config.llm.model)
                    config.llm.command = llm.get("command", config.llm.command)
                break

        return config
