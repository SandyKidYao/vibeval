"""CLI entrypoint — vibeval judge / vibeval summary / vibeval diff / vibeval runs / vibeval features."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import json

from .compare import compare_runs
from .config import Config
from .conversation import simulate_user
from .judge import judge_run
from .result import load_summary, list_runs, load_run


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="vibeval",
        description="vibeval (Vibe Coding Eval) — AI application testing framework.\n\n"
                    "vibeval evaluates AI application outputs using rule-based and LLM-based judges.\n"
                    "Tests are organized by feature under tests/vibeval/{feature}/.\n"
                    "Configuration: .vibeval.yml at project root (optional, defaults work out of box).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--project", default=".", help="Project root directory (default: current directory)")
    sub = parser.add_subparsers(dest="command")

    # --- Evaluation ---
    p_judge = sub.add_parser("judge",
        help="Evaluate test results against judge_specs defined in datasets",
        description="Read judge_specs from datasets/, apply them to results/{run_id}/, "
                    "write judge_results back, and generate summary.json.")
    p_judge.add_argument("feature", help="Feature name (directory under tests/vibeval/)")
    p_judge.add_argument("run_id", help="Run ID (e.g. latest, 2026-03-31_001)")

    p_compare = sub.add_parser("compare",
        help="Pairwise LLM comparison of two runs (cross-version evaluation)",
        description="For each matching test+item across two runs, ask LLM which output is better. "
                    "Runs comparison twice with swapped order to eliminate position bias. "
                    "Results saved to {feature}/comparisons/.")
    p_compare.add_argument("feature", help="Feature name")
    p_compare.add_argument("run_a", help="First run ID")
    p_compare.add_argument("run_b", help="Second run ID")

    # --- Multi-turn helper ---
    p_sim = sub.add_parser("simulate",
        help="Generate next simulated user message for multi-turn testing",
        description="Given a persona (role, behavior rules) and conversation history, "
                    "generate the next user message using LLM. "
                    "Call this from test code via subprocess to drive multi-turn conversations. "
                    "Output: the generated message printed to stdout.")
    p_sim.add_argument("--persona", required=True, help="Path to persona JSON file (must have system_prompt)")
    p_sim.add_argument("--history", default=None,
        help="Path to conversation history JSON file: [{\"user\": \"...\", \"bot\": \"...\"}, ...]")

    # --- Reporting ---
    p_summary = sub.add_parser("summary", help="Show evaluation summary for a test run")
    p_summary.add_argument("feature", help="Feature name")
    p_summary.add_argument("run_id", help="Run ID")

    p_diff = sub.add_parser("diff",
        help="Compare summary statistics between two runs",
        description="Compare pass rates and five-point score distributions. "
                    "For deeper semantic comparison, use 'vibeval compare' instead.")
    p_diff.add_argument("feature", help="Feature name")
    p_diff.add_argument("run_a", help="First run ID")
    p_diff.add_argument("run_b", help="Second run ID")

    # --- Server ---
    p_serve = sub.add_parser("serve",
        help="Launch interactive web dashboard for browsing features, results, and datasets",
        description="Start a local web server with an interactive dashboard. "
                    "Browse features, view test results and traces, visualize trends across runs, "
                    "and manage datasets and judge specs. The server runs on localhost.")
    p_serve.add_argument("--port", type=int, default=8080,
        help="Port to listen on (default: 8080)")
    p_serve.add_argument("--host", default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)")
    p_serve.add_argument("--open", action="store_true",
        help="Open the dashboard in the default browser automatically")

    # --- Environment ---
    sub.add_parser("check",
        help="Verify that the LLM provider (Claude Code CLI) is installed, authenticated, and working",
        description="Send a test prompt to Claude Code CLI to verify the full chain: "
                    "installation, authentication, and API access. "
                    "If using a custom LLM command, verify that it is configured and executable.")

    # --- Discovery ---
    sub.add_parser("features", help="List all feature directories under tests/vibeval/")

    p_runs = sub.add_parser("runs", help="List all test runs for a feature")
    p_runs.add_argument("feature", help="Feature name")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    config = Config.load(args.project)

    if args.command == "serve":
        cmd_serve(config, args.host, args.port, getattr(args, 'open', False))
    elif args.command == "check":
        cmd_check(config)
    elif args.command == "simulate":
        cmd_simulate(args.persona, args.history, config)
    elif args.command == "judge":
        cmd_judge(args.feature, args.run_id, config)
    elif args.command == "summary":
        cmd_summary(args.feature, args.run_id, config)
    elif args.command == "diff":
        cmd_diff(args.feature, args.run_a, args.run_b, config)
    elif args.command == "compare":
        cmd_compare(args.feature, args.run_a, args.run_b, config)
    elif args.command == "runs":
        cmd_runs(args.feature, config)
    elif args.command == "features":
        cmd_features(config)


def cmd_serve(config: Config, host: str, port: int, open_browser: bool) -> None:
    """Launch the interactive web dashboard."""
    from .serve import start_server

    if open_browser:
        import webbrowser
        import threading
        threading.Timer(0.5, lambda: webbrowser.open(f"http://{host}:{port}/")).start()

    start_server(config, host, port)


def cmd_check(config: Config) -> None:
    """Verify that the configured LLM provider is working."""
    provider = config.llm.provider
    print(f"LLM provider: {provider}")

    if provider == "claude-code":
        from .llm import check_claude_code
        try:
            check_claude_code()
            print("Claude Code CLI is installed, authenticated, and working.")
        except RuntimeError as e:
            print(f"\n{e}")
            sys.exit(1)
    elif provider == "command":
        cmd = config.llm.command
        if not cmd:
            print("Error: provider is 'command' but no command is configured in .vibeval.yml")
            sys.exit(1)
        print(f"Custom command: {cmd}")
        from .llm import _call_custom_command
        try:
            resp = _call_custom_command("hello", config.llm)
            print(f"Custom LLM responded successfully ({len(resp)} chars).")
        except RuntimeError as e:
            print(f"\nCustom command failed: {e}")
            sys.exit(1)
    else:
        print(f"Error: unknown provider '{provider}'")
        sys.exit(1)


def cmd_simulate(persona_path: str, history_path: str | None, config: Config) -> None:
    """Generate next user message and print to stdout."""
    persona = json.loads(Path(persona_path).read_text(encoding="utf-8"))

    history: list[dict[str, str]] = []
    if history_path:
        history = json.loads(Path(history_path).read_text(encoding="utf-8"))

    message = simulate_user(persona, history, config.llm)
    print(message)


def cmd_judge(feature: str, run_id: str, config: Config) -> None:
    """Run judge on a test run."""
    print(f"Judging: {feature}/{run_id}")

    results = judge_run(feature, run_id, config)

    run_dir = config.results_dir(feature) / run_id
    summary = load_summary(str(run_dir))
    _print_summary(summary, feature)

    print(f"\nResults saved to {run_dir}/")


def cmd_summary(feature: str, run_id: str, config: Config) -> None:
    """Show summary for a run."""
    run_dir = config.results_dir(feature) / run_id
    try:
        summary = load_summary(str(run_dir))
    except FileNotFoundError:
        print(f"No summary found. Run 'vibeval judge {feature} {run_id}' first.")
        sys.exit(1)

    _print_summary(summary, feature)


def cmd_compare(feature: str, run_a: str, run_b: str, config: Config) -> None:
    """Pairwise LLM comparison of two runs."""
    print(f"[{feature}] Comparing {run_a} vs {run_b} (pairwise LLM evaluation)...\n")

    comparison = compare_runs(feature, run_a, run_b, config)
    s = comparison["summary"]

    print(f"Results: {s['total_pairs']} pairs evaluated")
    print(f"  {run_a} wins: {s['a_wins']}")
    print(f"  {run_b} wins: {s['b_wins']}")
    print(f"  Ties: {s['ties']}")
    print(f"  Inconclusive: {s['inconclusive']}")

    # Show details
    for pair in comparison["pairs"]:
        w = pair["winner"]
        c = pair["confidence"]
        icon = {"a": "<", "b": ">", "tie": "=", "inconclusive": "?"}[w]
        winner_label = run_a if w == "a" else run_b if w == "b" else w
        print(f"\n  {icon} {pair['test_name']}/{pair['item_id']}")
        print(f"    criteria: {pair['criteria'][:80]}")
        print(f"    winner: {winner_label} ({c})")
        if pair.get("reason"):
            print(f"    reason: {pair['reason'][:120]}")

    comp_dir = config.feature_dir(feature) / "comparisons"
    print(f"\nSaved to {comp_dir}/")


def cmd_diff(feature: str, run_a: str, run_b: str, config: Config) -> None:
    """Compare two runs."""
    results_dir = config.results_dir(feature)

    try:
        summary_a = load_summary(str(results_dir / run_a))
        summary_b = load_summary(str(results_dir / run_b))
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    print(f"[{feature}] Comparing {run_a} vs {run_b}\n")

    ba = summary_a.get("binary_stats", {})
    bb = summary_b.get("binary_stats", {})
    rate_a = ba.get("pass_rate", 0)
    rate_b = bb.get("pass_rate", 0)
    delta = rate_b - rate_a
    arrow = "+" if delta > 0 else ""
    print(f"Binary pass rate: {rate_a:.1%} -> {rate_b:.1%} ({arrow}{delta:.1%})")

    fa = summary_a.get("five_point_stats", {})
    fb = summary_b.get("five_point_stats", {})
    all_criteria = sorted(set(fa.keys()) | set(fb.keys()))
    if all_criteria:
        print(f"\nFive-point scores:")
        for c in all_criteria:
            avg_a = fa.get(c, {}).get("avg", "-")
            avg_b = fb.get(c, {}).get("avg", "-")
            if isinstance(avg_a, (int, float)) and isinstance(avg_b, (int, float)):
                d = avg_b - avg_a
                arr = "+" if d > 0 else ""
                print(f"  {c}: {avg_a:.1f} -> {avg_b:.1f} ({arr}{d:.1f})")
            else:
                print(f"  {c}: {avg_a} -> {avg_b}")


def cmd_runs(feature: str, config: Config) -> None:
    """List all runs for a feature."""
    runs = list_runs(str(config.results_dir(feature)))
    if not runs:
        print(f"No runs found for {feature}.")
        return
    print(f"Runs for {feature}:")
    for run_id in runs:
        try:
            summary = load_summary(str(config.results_dir(feature) / run_id))
            bs = summary.get("binary_stats", {})
            print(f"  {run_id}  tests={summary['total']}  pass_rate={bs.get('pass_rate', 0):.0%}")
        except FileNotFoundError:
            print(f"  {run_id}  (no summary)")


def cmd_features(config: Config) -> None:
    """List all feature directories."""
    features = config.list_features()
    if not features:
        print(f"No features found under {config.vibeval_root}/")
        return
    print(f"Features ({config.vibeval_root}/):")
    for f in features:
        parts = []
        ds_dir = config.datasets_dir(f)
        if ds_dir.exists():
            ds_count = sum(1 for d in ds_dir.iterdir() if d.is_dir())
            parts.append(f"{ds_count} datasets")
        runs = list_runs(str(config.results_dir(f)))
        if runs:
            parts.append(f"{len(runs)} runs")
        info = f"  ({', '.join(parts)})" if parts else ""
        print(f"  {f}{info}")


def _print_summary(summary: dict, feature: str) -> None:
    """Print a formatted summary."""
    print(f"\n[{feature}] Run: {summary['run_id']}")
    print(f"Tests: {summary['total']}  Duration: {summary.get('duration', 0):.1f}s")

    bs = summary.get("binary_stats", {})
    if bs.get("total", 0) > 0:
        print(f"\nBinary: {bs['passed']}/{bs['total']} passed ({bs['pass_rate']:.0%})")

    fs = summary.get("five_point_stats", {})
    if fs:
        print(f"\nFive-point:")
        for criteria, dist in fs.items():
            avg = dist.get("avg", 0)
            bar = "  ".join(f"{i}:{'#' * dist.get(str(i), 0)}{dist.get(str(i), 0)}" for i in range(1, 6))
            print(f"  {criteria}")
            print(f"    avg={avg:.1f}  {bar}")


if __name__ == "__main__":
    main()
