"""LLM engine — calls LLM for evaluation, with Claude Code CLI as default."""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any

from .config import LLMConfig


def evaluate_llm(
    spec: dict[str, Any],
    result: dict[str, Any],
    dataset_item: dict[str, Any] | None,
    llm_config: LLMConfig,
    output_language: str = "English",
) -> dict[str, Any]:
    """Evaluate an LLM JudgeSpec against a TestResult.

    Returns a JudgeResult dict. `output_language` controls the natural
    language used for the judge's `reason` field — see contract.yaml's
    `output_language` field (plugin/protocol/references/06-contract.md).
    """
    scoring = spec.get("scoring", "binary")
    prompt = _build_prompt(spec, result, dataset_item, output_language)

    try:
        response = _call_llm(prompt, llm_config)
        parsed = _parse_response(response, scoring)
    except Exception as e:
        return {
            "spec": spec,
            "score": 0 if scoring == "binary" else 1,
            "reason": f"LLM evaluation error: {e}",
            "details": {"error": str(e)},
        }

    return {
        "spec": spec,
        "score": parsed["score"],
        "reason": parsed["reason"],
        "details": {"raw_response": response},
    }


def _build_prompt(
    spec: dict[str, Any],
    result: dict[str, Any],
    dataset_item: dict[str, Any] | None,
    output_language: str = "English",
) -> str:
    """Build the evaluation prompt from spec + result data (always full context)."""
    scoring = spec.get("scoring", "binary")
    criteria = spec.get("criteria", "")

    parts = ["You are an AI output evaluator. Evaluate the following test result.\n"]
    if output_language and output_language.strip().lower() != "english":
        parts.append(
            f"All natural-language explanations you produce, including the JSON "
            f"`reason` field, MUST be written in {output_language}. Numeric scores, "
            f"JSON keys, and any quoted excerpts from the inputs/outputs/trace "
            f"stay in their original form.\n"
        )

    # Test design context (insider knowledge — the tested AI never sees this)
    test_intent = spec.get("test_intent", "")
    trap_design = spec.get("trap_design", "")
    if test_intent or trap_design:
        parts.append("## Test Design (Insider Knowledge)")
        if test_intent:
            parts.append(f"Test intent: {test_intent}")
        if trap_design:
            parts.append(f"Trap design: {trap_design}")
        parts.append("Use this context to make a more informed judgment.\n")

    # Criteria
    parts.append(f"## Evaluation Criteria\n{criteria}\n")

    # Scoring instructions
    if scoring == "binary":
        parts.append("## Scoring\nYou must give a score of 0 or 1.\n")
        anchors = spec.get("anchors", {})
        if anchors:
            parts.append(f"- Score 0: {anchors.get('0', 'Does not meet criteria')}")
            parts.append(f"- Score 1: {anchors.get('1', 'Meets criteria')}\n")
    else:
        parts.append("## Scoring\nYou must give an integer score from 1 to 5.\n")
        anchors = spec.get("anchors", {})
        for i in range(1, 6):
            desc = anchors.get(str(i), "")
            if desc:
                parts.append(f"- Score {i}: {desc}")
        parts.append("")

    # Calibration examples
    calibrations = spec.get("calibrations", [])
    if calibrations:
        parts.append("## Calibration Examples")
        for cal in calibrations:
            parts.append(f"Output: {cal['output']}")
            parts.append(f"Score: {cal['score']}")
            parts.append(f"Reason: {cal['reason']}\n")

    # Ground truth reference
    reference_from = spec.get("reference_from", "")
    if reference_from and dataset_item:
        ref_value = dataset_item.get(reference_from)
        if ref_value is not None:
            parts.append(f"## Reference Answer (Ground Truth)\n{json.dumps(ref_value, default=str, ensure_ascii=False)}\n")

    # Context: filtered by target
    target = spec.get("target", "output")
    filtered_turns, filtered_steps_only = _filter_trace(result, target)

    inputs = result.get("inputs")
    if inputs:
        parts.append(f"## Test Inputs\n{json.dumps(inputs, default=str, ensure_ascii=False)}\n")

    if filtered_steps_only:
        # target is step_type filter — show only matching steps across turns
        parts.append(f"## Targeted Steps (type: {target.get('step_type', '?')})")
        for turn_num, steps in filtered_steps_only:
            for j, step in enumerate(steps):
                step_data = json.dumps(step.get("data", {}), default=str, ensure_ascii=False)[:500]
                parts.append(f"  Turn {turn_num} step {j+1} [{step.get('type', '?')}]: {step_data}")
        parts.append("")
    elif filtered_turns:
        # Show full turns (possibly a subset)
        parts.append("## Process Trace")
        for turn in filtered_turns:
            turn_num = turn.get("turn", "?")
            inp = json.dumps(turn.get("input", {}), default=str, ensure_ascii=False)[:500]
            parts.append(f"  Turn {turn_num} input: {inp}")
            for j, step in enumerate(turn.get("steps", [])):
                step_type = step.get("type", "?")
                step_data = json.dumps(step.get("data", {}), default=str, ensure_ascii=False)[:500]
                parts.append(f"    step {j+1} [{step_type}]: {step_data}")
            out = json.dumps(turn.get("output", {}), default=str, ensure_ascii=False)[:500]
            parts.append(f"  Turn {turn_num} output: {out}")
        parts.append("")

    outputs = result.get("outputs")
    if outputs:
        parts.append(f"## Test Outputs\n{json.dumps(outputs, default=str, ensure_ascii=False)}\n")

    # Response format
    parts.append('## Response Format\nRespond in JSON: {"score": <number>, "reason": "<brief explanation>"}\nNothing else.')
    if output_language and output_language.strip().lower() != "english":
        parts.append(f'Reminder: write the `reason` value in {output_language}.')

    return "\n".join(parts)


def _filter_trace(
    result: dict[str, Any],
    target: str | dict[str, Any],
) -> tuple[list[dict] | None, list[tuple[int, list[dict]]] | None]:
    """Filter trace data based on target spec.

    Returns:
        (filtered_turns, filtered_steps_only)
        - If target is "output" or no trace: (all_turns, None)
        - If target has "turns" range only: (subset_of_turns, None)
        - If target has "step_type": (None, [(turn_num, [matching_steps])])
        - If target has both: (None, [(turn_num, [matching_steps within range])])
    """
    trace = result.get("trace", {})
    all_turns = trace.get("turns", [])

    if not all_turns:
        return None, None

    if target == "output" or not target:
        return all_turns, None

    if isinstance(target, str):
        return all_turns, None

    # Parse target filters
    turn_range = target.get("turns")  # [start, end] inclusive, 1-based
    step_type = target.get("step_type")

    # Filter turns by range
    if turn_range:
        start, end = turn_range[0], turn_range[1]
        turns = [t for t in all_turns if start <= t.get("turn", 0) <= end]
    else:
        turns = all_turns

    # If no step_type filter, return filtered turns
    if not step_type:
        return turns, None

    # Filter steps by type within (possibly filtered) turns
    steps_only: list[tuple[int, list[dict]]] = []
    for turn in turns:
        turn_num = turn.get("turn", 0)
        matching = [s for s in turn.get("steps", []) if s.get("type") == step_type]
        if matching:
            steps_only.append((turn_num, matching))

    return None, steps_only


def check_claude_code() -> None:
    """Check that Claude Code CLI is installed, authenticated, and working.

    Sends a minimal prompt to verify the full chain: installation, auth, and API access.
    """
    try:
        result = subprocess.run(
            ["claude", "-p", "hello", "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(
                "Claude Code CLI is installed but failed to respond.\n"
                f"Error: {stderr}\n\n"
                "Possible causes:\n"
                "- Not logged in: run 'claude login' to authenticate\n"
                "- API key not configured: check your Claude Code settings\n"
                "- Network issue: verify your internet connection\n\n"
                "Alternatively, configure a custom LLM command in .vibeval.yml:\n"
                "  judge:\n"
                "    llm:\n"
                "      provider: command\n"
                "      command: \"your-llm-cli --prompt-stdin\""
            )
    except FileNotFoundError:
        raise RuntimeError(
            "Claude Code CLI ('claude') is not installed or not in PATH.\n"
            "vibeval requires Claude Code as the default LLM provider.\n"
            "Install: npm install -g @anthropic-ai/claude-code\n"
            "Docs: https://docs.anthropic.com/en/docs/claude-code\n\n"
            "Alternatively, configure a custom LLM command in .vibeval.yml:\n"
            "  judge:\n"
            "    llm:\n"
            "      provider: command\n"
            "      command: \"your-llm-cli --prompt-stdin\""
        )


def _call_llm(prompt: str, config: LLMConfig) -> str:
    """Call the LLM via the configured provider."""
    if config.provider == "claude-code":
        return _call_claude_code(prompt, config)
    elif config.provider == "command":
        return _call_custom_command(prompt, config)
    else:
        raise ValueError(
            f"Unknown LLM provider: '{config.provider}'. "
            f"Supported providers: 'claude-code', 'command'."
        )


def _call_claude_code(prompt: str, config: LLMConfig) -> str:
    """Call Claude Code CLI: claude -p '<prompt>' --output-format text"""
    check_claude_code()
    cmd = ["claude", "-p", prompt, "--output-format", "text"]
    if config.model:
        cmd.extend(["--model", config.model])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Claude Code CLI error: {result.stderr.strip()}")
    return result.stdout.strip()


def _call_custom_command(prompt: str, config: LLMConfig) -> str:
    """Call a user-defined command, passing the prompt via stdin.

    The command should read the prompt from stdin and write the
    LLM response to stdout.
    """
    if not config.command:
        raise ValueError(
            "Provider is 'command' but no command is configured.\n"
            "Set it in .vibeval.yml:\n"
            "  judge:\n"
            "    llm:\n"
            "      provider: command\n"
            "      command: \"your-llm-cli\""
        )
    result = subprocess.run(
        config.command,
        input=prompt,
        capture_output=True,
        text=True,
        shell=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Custom LLM command error: {result.stderr.strip()}")
    return result.stdout.strip()


def _parse_response(response: str, scoring: str) -> dict[str, Any]:
    """Parse the LLM's JSON response."""
    # Try to extract JSON from response
    json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
    if json_match:
        try:
            data = json.loads(json_match.group())
            score = data.get("score", 0)

            # Validate score range
            if scoring == "binary":
                score = 1 if score else 0
            else:
                score = max(1, min(5, int(score)))

            return {"score": score, "reason": data.get("reason", "")}
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    # Fallback: try to find a number
    numbers = re.findall(r"\b([0-5])\b", response)
    if numbers:
        score = int(numbers[0])
        if scoring == "binary":
            score = 1 if score else 0
        else:
            score = max(1, min(5, score))
        return {"score": score, "reason": response[:200]}

    return {"score": 0 if scoring == "binary" else 1, "reason": f"Could not parse LLM response: {response[:200]}"}
