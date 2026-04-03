"""Rule engine — built-in deterministic rules for output and trace checking.

Trace format (v0.2): turns-based
  trace.turns[].input / steps[] / output
"""

from __future__ import annotations

import json
import re
from typing import Any


def evaluate_rule(spec: dict[str, Any], result: dict[str, Any], dataset_item: dict[str, Any] | None = None) -> dict[str, Any]:
    """Evaluate a rule JudgeSpec against a TestResult."""
    rule_name = spec.get("rule", "")
    args = _resolve_refs(spec.get("args", {}), dataset_item)

    try:
        passed, reason = _dispatch_rule(rule_name, args, result)
    except Exception as e:
        passed, reason = False, f"Rule error: {e}"

    return {"spec": spec, "score": 1 if passed else 0, "reason": reason}


def _dispatch_rule(name: str, args: dict[str, Any], result: dict[str, Any]) -> tuple[bool, str]:
    rules = {
        # Output rules
        "contains": _rule_contains,
        "contains_all": _rule_contains_all,
        "contains_any": _rule_contains_any,
        "not_contains": _rule_not_contains,
        "equals": _rule_equals,
        "matches": _rule_matches,
        "is_json": _rule_is_json,
        "length_between": _rule_length_between,
        # Trace rules
        "tool_sequence": _rule_tool_sequence,
        "tool_called": _rule_tool_called,
        "tool_not_called": _rule_tool_not_called,
        "max_turns": _rule_max_turns,
        "max_steps": _rule_max_steps,
        # Conversation rules
        "conversation_turns": _rule_conversation_turns,
        "all_turns_responded": _rule_all_turns_responded,
        "no_role_violation": _rule_no_role_violation,
    }
    fn = rules.get(name)
    if fn is None:
        return False, f"Unknown rule: {name}"
    return fn(args, result)


# --- Output rules ---

def _resolve_field(field: str, result: dict) -> Any:
    parts = field.split(".")
    current: Any = result
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _rule_contains(args: dict, result: dict) -> tuple[bool, str]:
    value = str(_resolve_field(args["field"], result))
    target = args["value"]
    found = target in value
    return found, f"'{target}' {'found' if found else 'not found'} in {args['field']}"


def _rule_contains_all(args: dict, result: dict) -> tuple[bool, str]:
    value = str(_resolve_field(args["field"], result))
    values = args["values"]
    missing = [v for v in values if v not in value]
    if not missing:
        return True, f"{len(values)}/{len(values)} values found in {args['field']}"
    return False, f"{len(values) - len(missing)}/{len(values)} found, missing: {missing[:5]}"


def _rule_contains_any(args: dict, result: dict) -> tuple[bool, str]:
    value = str(_resolve_field(args["field"], result))
    values = args["values"]
    found = [v for v in values if v in value]
    if found:
        return True, f"Found {found[0]} in {args['field']}"
    return False, f"None of {len(values)} values found"


def _rule_not_contains(args: dict, result: dict) -> tuple[bool, str]:
    value = str(_resolve_field(args["field"], result))
    target = args["value"]
    found = target in value
    return not found, f"'{target}' {'unexpectedly found' if found else 'correctly absent'}"


def _rule_equals(args: dict, result: dict) -> tuple[bool, str]:
    value = _resolve_field(args["field"], result)
    expected = args["expected"]
    return value == expected, f"{args['field']} {'equals' if value == expected else 'does not equal'} expected"


def _rule_matches(args: dict, result: dict) -> tuple[bool, str]:
    value = str(_resolve_field(args["field"], result))
    pattern = args["pattern"]
    matched = bool(re.search(pattern, value))
    return matched, f"Pattern /{pattern}/ {'matched' if matched else 'not matched'}"


def _rule_is_json(args: dict, result: dict) -> tuple[bool, str]:
    value = str(_resolve_field(args["field"], result))
    try:
        json.loads(value)
        return True, f"{args['field']} is valid JSON"
    except (json.JSONDecodeError, ValueError):
        return False, f"{args['field']} is not valid JSON"


def _rule_length_between(args: dict, result: dict) -> tuple[bool, str]:
    value = str(_resolve_field(args["field"], result))
    length = len(value)
    min_len = args.get("min", 0)
    max_len = args.get("max", float("inf"))
    ok = min_len <= length <= max_len
    return ok, f"length {length} {'within' if ok else 'outside'} [{min_len}, {max_len}]"


# --- Trace rules (v0.2 turns-based) ---

def _get_turns(result: dict) -> list[dict]:
    return result.get("trace", {}).get("turns", [])


def _get_all_steps(result: dict) -> list[dict]:
    steps = []
    for turn in _get_turns(result):
        steps.extend(turn.get("steps", []))
    return steps


def _rule_tool_sequence(args: dict, result: dict) -> tuple[bool, str]:
    expected = args.get("expected", [])
    actual = [
        s.get("data", {}).get("name", "unknown")
        for s in _get_all_steps(result)
        if s.get("type") == "tool_call"
    ]
    if actual == expected:
        return True, f"Tool sequence matches: {actual}"
    return False, f"Expected {expected}, got {actual}"


def _rule_tool_called(args: dict, result: dict) -> tuple[bool, str]:
    tool_name = args.get("tool_name", "")
    called = any(
        s.get("data", {}).get("name") == tool_name
        for s in _get_all_steps(result)
        if s.get("type") == "tool_call"
    )
    return called, f"Tool '{tool_name}' {'was' if called else 'was not'} called"


def _rule_tool_not_called(args: dict, result: dict) -> tuple[bool, str]:
    tool_name = args.get("tool_name", "")
    called = any(
        s.get("data", {}).get("name") == tool_name
        for s in _get_all_steps(result)
        if s.get("type") == "tool_call"
    )
    return not called, f"Tool '{tool_name}' {'unexpectedly called' if called else 'correctly not called'}"


def _rule_max_turns(args: dict, result: dict) -> tuple[bool, str]:
    turns = _get_turns(result)
    max_val = args.get("max", 10)
    ok = len(turns) <= max_val
    return ok, f"{len(turns)} turns {'<=' if ok else '>'} max {max_val}"


def _rule_max_steps(args: dict, result: dict) -> tuple[bool, str]:
    steps = _get_all_steps(result)
    max_val = args.get("max", 20)
    ok = len(steps) <= max_val
    return ok, f"{len(steps)} steps {'<=' if ok else '>'} max {max_val}"


# --- Conversation rules ---

def _get_conversation(result: dict) -> list[dict]:
    """Extract conversation from outputs or trace turns."""
    conv = _resolve_field("outputs.conversation", result)
    if isinstance(conv, list):
        return conv
    # Fallback: build from trace turns
    turns = _get_turns(result)
    msgs = []
    for t in turns:
        inp = t.get("input", {})
        out = t.get("output", {})
        if inp.get("content"):
            msgs.append({"role": "user", "content": inp["content"]})
        if out.get("content"):
            msgs.append({"role": "bot", "content": out["content"]})
    return msgs


def _rule_conversation_turns(args: dict, result: dict) -> tuple[bool, str]:
    conv = _get_conversation(result)
    turn_count = sum(1 for m in conv if m.get("role") == "bot")
    min_t = args.get("min", 1)
    max_t = args.get("max", 100)
    ok = min_t <= turn_count <= max_t
    return ok, f"{turn_count} turns {'within' if ok else 'outside'} [{min_t}, {max_t}]"


def _rule_all_turns_responded(args: dict, result: dict) -> tuple[bool, str]:
    conv = _get_conversation(result)
    if not conv:
        return False, "Empty conversation"
    for i in range(0, len(conv) - 1, 2):
        if conv[i].get("role") != "user":
            return False, f"Expected user at index {i}, got {conv[i].get('role', '?')}"
        if i + 1 >= len(conv) or conv[i + 1].get("role") != "bot":
            return False, f"No bot response after user message at index {i}"
    return True, f"All {len(conv) // 2} user messages got bot responses"


def _rule_no_role_violation(args: dict, result: dict) -> tuple[bool, str]:
    conv = _get_conversation(result)
    violations = []
    for i, msg in enumerate(conv):
        if msg.get("role") == "bot":
            content = msg.get("content", "").lower()
            if any(marker in content for marker in ["as a user", "user:", "i am the user"]):
                violations.append(i)
    if not violations:
        return True, "No role violations detected"
    return False, f"Potential role violations at indices: {violations}"


# --- Helpers ---

def _resolve_refs(args: dict[str, Any], dataset_item: dict[str, Any] | None) -> dict[str, Any]:
    if dataset_item is None:
        return args
    resolved = dict(args)
    if "values_from" in resolved:
        resolved["values"] = dataset_item.get(resolved.pop("values_from"), [])
    if "expected_from" in resolved:
        resolved["expected"] = dataset_item.get(resolved.pop("expected_from"))
    return resolved
