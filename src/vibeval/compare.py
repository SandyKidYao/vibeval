"""Pairwise comparison — cross-run evaluation for LLM judge specs.

Compares the same test+item across two runs by asking an LLM
"which output is better?" twice with swapped order to eliminate
position bias.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

from .config import Config
from .dataset import Dataset, load_all_datasets
from .llm import _call_llm
from .result import load_run


def compare_runs(
    feature: str,
    run_a: str,
    run_b: str,
    config: Config,
) -> dict[str, Any]:
    """Compare two runs for a feature using pairwise LLM evaluation.

    Returns a ComparisonResult dict.
    """
    datasets = load_all_datasets(str(config.datasets_dir(feature)))
    results_a = load_run(str(config.results_dir(feature) / run_a))
    results_b = load_run(str(config.results_dir(feature) / run_b))
    output_language = config.output_language(feature)

    # Index by (test_name, item_id)
    index_a = {(r["test_name"], r.get("item_id", "")): r for r in results_a}
    index_b = {(r["test_name"], r.get("item_id", "")): r for r in results_b}

    # Find matching pairs
    common_keys = sorted(set(index_a.keys()) & set(index_b.keys()))

    pairs: list[dict[str, Any]] = []

    for test_name, item_id in common_keys:
        ra = index_a[(test_name, item_id)]
        rb = index_b[(test_name, item_id)]

        # Find the dataset and get LLM judge specs
        dataset_name = ra.get("dataset", "")
        dataset = datasets.get(dataset_name)
        if dataset is None:
            continue

        item = _find_item(dataset, item_id)
        specs = dataset.effective_specs(item) if item else dataset.judge_specs

        # Only compare LLM specs
        llm_specs = [s for s in specs if s.get("method") == "llm"]

        for spec in llm_specs:
            pair = _compare_pair(spec, ra, rb, config, output_language=output_language)
            pair["test_name"] = test_name
            pair["item_id"] = item_id
            pairs.append(pair)

    # Build summary
    a_wins = sum(1 for p in pairs if p["winner"] == "a")
    b_wins = sum(1 for p in pairs if p["winner"] == "b")
    ties = sum(1 for p in pairs if p["winner"] == "tie")
    inconclusive = sum(1 for p in pairs if p["winner"] == "inconclusive")

    comparison = {
        "run_a": run_a,
        "run_b": run_b,
        "timestamp": time.time(),
        "pairs": pairs,
        "summary": {
            "total_pairs": len(pairs),
            "a_wins": a_wins,
            "b_wins": b_wins,
            "ties": ties,
            "inconclusive": inconclusive,
        },
    }

    # Save
    _save_comparison(feature, comparison, config)

    return comparison


def _compare_pair(
    spec: dict[str, Any],
    result_a: dict[str, Any],
    result_b: dict[str, Any],
    config: Config,
    output_language: str = "English",
) -> dict[str, Any]:
    """Compare a single pair on a single criteria, with position swap."""
    criteria = spec.get("criteria", "")

    # Round 1: A=run_a, B=run_b
    prompt_ab = _build_comparison_prompt(spec, result_a, result_b, output_language)
    try:
        response_ab = _call_llm(prompt_ab, config.llm)
        verdict_ab = _parse_comparison(response_ab)
    except Exception as e:
        verdict_ab = {"winner": "error", "reason": str(e)}

    # Round 2: A=run_b, B=run_a (swapped)
    prompt_ba = _build_comparison_prompt(spec, result_b, result_a, output_language)
    try:
        response_ba = _call_llm(prompt_ba, config.llm)
        verdict_ba = _parse_comparison(response_ba)
    except Exception as e:
        verdict_ba = {"winner": "error", "reason": str(e)}

    # Reconcile: check consistency
    winner, confidence = _reconcile(verdict_ab, verdict_ba)

    return {
        "criteria": criteria,
        "winner": winner,
        "confidence": confidence,
        "reason": verdict_ab.get("reason", ""),
        "details": {
            "ab_order": verdict_ab,
            "ba_order": verdict_ba,
        },
    }


def _build_comparison_prompt(
    spec: dict[str, Any],
    result_a: dict[str, Any],
    result_b: dict[str, Any],
    output_language: str = "English",
) -> str:
    """Build a pairwise comparison prompt with full insider knowledge."""
    criteria = spec.get("criteria", "")

    parts = [
        "You are comparing two AI system outputs on the same task.",
        "Determine which output is better based on the given criteria.",
    ]
    if output_language and output_language.strip().lower() != "english":
        parts.append(
            f"All natural-language explanations you produce, including the JSON "
            f"`reason` field, MUST be written in {output_language}. The `winner` "
            f"field stays as the literal string \"a\", \"b\", or \"tie\"; quoted "
            f"excerpts from the outputs/trace stay in their original form."
        )

    # Insider knowledge — test design context
    test_intent = spec.get("test_intent", "")
    trap_design = spec.get("trap_design", "")
    if test_intent or trap_design:
        parts.append("\n## Test Design (Insider Knowledge)")
        if test_intent:
            parts.append(f"Test intent: {test_intent}")
        if trap_design:
            parts.append(f"Trap design: {trap_design}")
        parts.append("Use this context to make a more informed comparison.")

    parts.extend(["", f"## Criteria\n{criteria}"])

    # Anchors — what good/bad looks like
    anchors = spec.get("anchors", {})
    if anchors:
        parts.append("\n## Scoring Anchors")
        for score_val, desc in sorted(anchors.items()):
            parts.append(f"- Score {score_val}: {desc}")

    # Output A with trace
    parts.extend(["", "## Output A", json.dumps(result_a.get("outputs", {}), default=str, ensure_ascii=False)])
    _append_trace(parts, result_a, "A")

    # Output B with trace
    parts.extend(["", "## Output B", json.dumps(result_b.get("outputs", {}), default=str, ensure_ascii=False)])
    _append_trace(parts, result_b, "B")

    parts.extend([
        "",
        "## Instructions",
        'Respond in JSON: {"winner": "a" or "b" or "tie", "reason": "brief explanation"}',
        "Nothing else.",
    ])
    if output_language and output_language.strip().lower() != "english":
        parts.append(f'Reminder: write the `reason` value in {output_language}.')

    return "\n".join(parts)


def _append_trace(parts: list[str], result: dict[str, Any], label: str) -> None:
    """Append turn-based trace to prompt parts."""
    turns = result.get("trace", {}).get("turns", [])
    if not turns:
        return
    parts.append(f"\n### Process trace ({label})")
    for turn in turns:
        turn_num = turn.get("turn", "?")
        inp = json.dumps(turn.get("input", {}), default=str, ensure_ascii=False)[:500]
        parts.append(f"  Turn {turn_num} input: {inp}")
        for j, step in enumerate(turn.get("steps", [])):
            step_type = step.get("type", "?")
            step_data = json.dumps(step.get("data", {}), default=str, ensure_ascii=False)[:500]
            parts.append(f"    step {j+1} [{step_type}]: {step_data}")
        out = json.dumps(turn.get("output", {}), default=str, ensure_ascii=False)[:500]
        parts.append(f"  Turn {turn_num} output: {out}")


def _parse_comparison(response: str) -> dict[str, Any]:
    """Parse the LLM's comparison verdict."""
    json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            winner = str(data.get("winner", "")).lower().strip()
            if winner not in ("a", "b", "tie"):
                winner = "tie"
            return {"winner": winner, "reason": data.get("reason", "")}
        except (json.JSONDecodeError, ValueError):
            pass

    # Fallback
    lower = response.lower()
    if "output a" in lower and "better" in lower:
        return {"winner": "a", "reason": response[:200]}
    if "output b" in lower and "better" in lower:
        return {"winner": "b", "reason": response[:200]}
    return {"winner": "tie", "reason": f"Could not parse: {response[:200]}"}


def _reconcile(
    verdict_ab: dict[str, Any],
    verdict_ba: dict[str, Any],
) -> tuple[str, str]:
    """Reconcile two verdicts to determine winner and confidence.

    In ab_order: winner="a" means run_a is better
    In ba_order: winner="a" means run_b is better (because positions are swapped)
    """
    w_ab = verdict_ab.get("winner", "error")
    w_ba = verdict_ba.get("winner", "error")

    if w_ab == "error" or w_ba == "error":
        return "inconclusive", "error"

    # Normalize: translate both to "which run is better?"
    # ab_order: a=run_a, b=run_b → winner directly maps
    # ba_order: a=run_b, b=run_a → "a" means run_b wins, "b" means run_a wins
    run_winner_ab = w_ab  # "a" → run_a, "b" → run_b, "tie" → tie
    if w_ba == "a":
        run_winner_ba = "b"  # swapped: "a" in ba means run_b
    elif w_ba == "b":
        run_winner_ba = "a"  # swapped: "b" in ba means run_a
    else:
        run_winner_ba = "tie"

    if run_winner_ab == run_winner_ba:
        return run_winner_ab, "consistent"
    elif run_winner_ab == "tie" or run_winner_ba == "tie":
        # One says tie, other picks a winner — lean toward the winner
        actual = run_winner_ab if run_winner_ba == "tie" else run_winner_ba
        return actual, "inconsistent"
    else:
        # Contradictory results
        return "inconclusive", "inconsistent"


def _save_comparison(
    feature: str,
    comparison: dict[str, Any],
    config: Config,
) -> Path:
    """Save comparison result to the feature's comparisons/ directory."""
    comp_dir = config.feature_dir(feature) / "comparisons"
    comp_dir.mkdir(parents=True, exist_ok=True)

    run_a = comparison["run_a"]
    run_b = comparison["run_b"]
    filename = f"{run_a}_vs_{run_b}.json"
    path = comp_dir / filename

    path.write_text(
        json.dumps(comparison, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def _find_item(dataset: Dataset, item_id: str):
    """Find a data item by ID."""
    if not item_id:
        return dataset.items[0] if dataset.items else None
    for item in dataset.items:
        if item.id == item_id:
            return item
    return None
