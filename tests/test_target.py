"""Tests for target-based trace filtering in LLM judge."""

from vibeval.llm import _filter_trace, _build_prompt


def _make_result():
    """Create a multi-turn result with various step types."""
    return {
        "inputs": {"query": "test"},
        "outputs": {"answer": "result"},
        "trace": {"turns": [
            {
                "turn": 1,
                "input": {"content": "hello"},
                "steps": [
                    {"type": "llm_call", "data": {"prompt": "..."}},
                    {"type": "llm_output", "data": {"content": "hi"}},
                ],
                "output": {"content": "hi"},
            },
            {
                "turn": 2,
                "input": {"content": "search for X"},
                "steps": [
                    {"type": "tool_call", "data": {"name": "search", "args": {"q": "X"}}},
                    {"type": "tool_result", "data": {"name": "search", "result": "found"}},
                    {"type": "llm_call", "data": {"prompt": "..."}},
                    {"type": "llm_output", "data": {"content": "I found X"}},
                ],
                "output": {"content": "I found X"},
            },
            {
                "turn": 3,
                "input": {"content": "summarize"},
                "steps": [
                    {"type": "tool_call", "data": {"name": "summarize", "args": {}}},
                    {"type": "tool_result", "data": {"name": "summarize", "result": "summary"}},
                    {"type": "llm_call", "data": {"prompt": "..."}},
                    {"type": "llm_output", "data": {"content": "Here is the summary"}},
                ],
                "output": {"content": "Here is the summary"},
            },
        ]},
    }


class TestFilterTrace:

    def test_default_returns_all(self):
        result = _make_result()
        turns, steps = _filter_trace(result, "output")
        assert turns is not None
        assert len(turns) == 3
        assert steps is None

    def test_empty_target_returns_all(self):
        result = _make_result()
        turns, steps = _filter_trace(result, "")
        assert turns is not None
        assert len(turns) == 3

    def test_turn_range(self):
        result = _make_result()
        turns, steps = _filter_trace(result, {"turns": [1, 2]})
        assert turns is not None
        assert len(turns) == 2
        assert turns[0]["turn"] == 1
        assert turns[1]["turn"] == 2
        assert steps is None

    def test_single_turn(self):
        result = _make_result()
        turns, steps = _filter_trace(result, {"turns": [2, 2]})
        assert len(turns) == 1
        assert turns[0]["turn"] == 2

    def test_step_type_filter(self):
        result = _make_result()
        turns, steps = _filter_trace(result, {"step_type": "tool_call"})
        assert turns is None
        assert steps is not None
        # Turn 1 has no tool_call, turns 2 and 3 each have 1
        assert len(steps) == 2
        assert steps[0][0] == 2  # turn number
        assert steps[0][1][0]["data"]["name"] == "search"
        assert steps[1][0] == 3
        assert steps[1][1][0]["data"]["name"] == "summarize"

    def test_step_type_no_match(self):
        result = _make_result()
        turns, steps = _filter_trace(result, {"step_type": "handoff"})
        assert turns is None
        assert steps == []

    def test_combined_turns_and_step_type(self):
        result = _make_result()
        turns, steps = _filter_trace(result, {"turns": [2, 2], "step_type": "tool_call"})
        assert turns is None
        assert len(steps) == 1
        assert steps[0][0] == 2
        assert steps[0][1][0]["data"]["name"] == "search"

    def test_no_trace_returns_none(self):
        result = {"inputs": {}, "outputs": {}}
        turns, steps = _filter_trace(result, {"step_type": "tool_call"})
        assert turns is None
        assert steps is None


class TestPromptWithTarget:

    def test_default_includes_all_turns(self):
        spec = {
            "scoring": "binary",
            "criteria": "test",
            "test_intent": "verify output",
            "anchors": {"0": "bad", "1": "good"},
        }
        result = _make_result()
        prompt = _build_prompt(spec, result, None)
        assert "Turn 1" in prompt
        assert "Turn 2" in prompt
        assert "Turn 3" in prompt

    def test_turn_range_filters(self):
        spec = {
            "scoring": "binary",
            "criteria": "check early turns",
            "target": {"turns": [1, 1]},
            "anchors": {"0": "bad", "1": "good"},
        }
        result = _make_result()
        prompt = _build_prompt(spec, result, None)
        assert "Turn 1" in prompt
        assert "Turn 2" not in prompt
        assert "Turn 3" not in prompt

    def test_step_type_shows_targeted(self):
        spec = {
            "scoring": "binary",
            "criteria": "check tool calls",
            "target": {"step_type": "tool_call"},
            "anchors": {"0": "bad", "1": "good"},
        }
        result = _make_result()
        prompt = _build_prompt(spec, result, None)
        assert "Targeted Steps" in prompt
        assert "search" in prompt
        assert "summarize" in prompt
        # Should not include llm_call steps
        assert "llm_call" not in prompt or "Targeted Steps (type: tool_call)" in prompt

    def test_insider_knowledge_included(self):
        spec = {
            "scoring": "binary",
            "criteria": "test",
            "test_intent": "check contradiction handling",
            "trap_design": "Alice says Friday, Bob corrects to Monday",
            "target": {"turns": [1, 1]},
            "anchors": {"0": "bad", "1": "good"},
        }
        prompt = _build_prompt(spec, _make_result(), None)
        assert "check contradiction handling" in prompt
        assert "Alice says Friday" in prompt
