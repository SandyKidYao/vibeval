"""Tests for rule engine (v0.2 turn-based trace format)."""

from vibeval.rules import evaluate_rule


class TestOutputRules:
    def test_contains(self):
        spec = {"method": "rule", "rule": "contains", "args": {"field": "outputs.summary", "value": "9:00 AM"}}
        result = {"outputs": {"summary": "Meeting started at 9:00 AM"}}
        assert evaluate_rule(spec, result)["score"] == 1

    def test_contains_fail(self):
        spec = {"method": "rule", "rule": "contains", "args": {"field": "outputs.summary", "value": "9:00 AM"}}
        result = {"outputs": {"summary": "Meeting started in the morning"}}
        assert evaluate_rule(spec, result)["score"] == 0

    def test_contains_all(self):
        spec = {"method": "rule", "rule": "contains_all", "args": {"field": "outputs.summary", "values": ["9:00 AM", "3:00 PM"]}}
        result = {"outputs": {"summary": "Meeting at 9:00 AM, review at 3:00 PM"}}
        assert evaluate_rule(spec, result)["score"] == 1

    def test_contains_all_partial(self):
        spec = {"method": "rule", "rule": "contains_all", "args": {"field": "outputs.summary", "values": ["9:00 AM", "3:00 PM"]}}
        result = {"outputs": {"summary": "Meeting at 9:00 AM"}}
        jr = evaluate_rule(spec, result)
        assert jr["score"] == 0
        assert "missing" in jr["reason"]

    def test_contains_all_values_from(self):
        spec = {"method": "rule", "rule": "contains_all", "args": {"field": "outputs.summary", "values_from": "expected_times"}}
        result = {"outputs": {"summary": "Meeting at 9:00 AM, review at 3:00 PM"}}
        assert evaluate_rule(spec, result, {"expected_times": ["9:00 AM", "3:00 PM"]})["score"] == 1

    def test_equals(self):
        spec = {"method": "rule", "rule": "equals", "args": {"field": "outputs.status", "expected": "success"}}
        assert evaluate_rule(spec, {"outputs": {"status": "success"}})["score"] == 1

    def test_equals_from(self):
        spec = {"method": "rule", "rule": "equals", "args": {"field": "outputs.answer", "expected_from": "expected"}}
        assert evaluate_rule(spec, {"outputs": {"answer": "greeting"}}, {"expected": "greeting"})["score"] == 1

    def test_matches(self):
        spec = {"method": "rule", "rule": "matches", "args": {"field": "outputs.summary", "pattern": r"\d{1,2}:\d{2}\s*(AM|PM)"}}
        assert evaluate_rule(spec, {"outputs": {"summary": "Meeting at 9:00 AM"}})["score"] == 1

    def test_is_json(self):
        spec = {"method": "rule", "rule": "is_json", "args": {"field": "outputs.data"}}
        assert evaluate_rule(spec, {"outputs": {"data": '{"key": "value"}'}})["score"] == 1
        assert evaluate_rule(spec, {"outputs": {"data": "not json"}})["score"] == 0

    def test_length_between(self):
        spec = {"method": "rule", "rule": "length_between", "args": {"field": "outputs.summary", "min": 5, "max": 100}}
        assert evaluate_rule(spec, {"outputs": {"summary": "A short summary"}})["score"] == 1

    def test_not_contains(self):
        spec = {"method": "rule", "rule": "not_contains", "args": {"field": "outputs.summary", "value": "ERROR"}}
        assert evaluate_rule(spec, {"outputs": {"summary": "All good"}})["score"] == 1

    def test_contains_any(self):
        spec = {"method": "rule", "rule": "contains_any", "args": {"field": "outputs.summary", "values": ["sun", "rain"]}}
        assert evaluate_rule(spec, {"outputs": {"summary": "It's going to rain"}})["score"] == 1


class TestTraceRules:
    """Trace rules using v0.2 turns-based format."""

    def _trace(self, turns):
        return {"trace": {"turns": turns}}

    def test_tool_sequence(self):
        spec = {"method": "rule", "rule": "tool_sequence", "args": {"expected": ["search", "calculate"]}}
        result = self._trace([{
            "turn": 1, "input": {}, "output": {},
            "steps": [
                {"type": "tool_call", "data": {"name": "search"}},
                {"type": "tool_result", "data": {"name": "search", "result": "..."}},
                {"type": "tool_call", "data": {"name": "calculate"}},
                {"type": "tool_result", "data": {"name": "calculate", "result": "42"}},
            ],
        }])
        assert evaluate_rule(spec, result)["score"] == 1

    def test_tool_sequence_wrong(self):
        spec = {"method": "rule", "rule": "tool_sequence", "args": {"expected": ["search", "calculate"]}}
        result = self._trace([{
            "turn": 1, "input": {}, "output": {},
            "steps": [{"type": "tool_call", "data": {"name": "calculate"}}],
        }])
        assert evaluate_rule(spec, result)["score"] == 0

    def test_tool_called(self):
        spec = {"method": "rule", "rule": "tool_called", "args": {"tool_name": "search"}}
        result = self._trace([{
            "turn": 1, "input": {}, "output": {},
            "steps": [{"type": "tool_call", "data": {"name": "search"}}],
        }])
        assert evaluate_rule(spec, result)["score"] == 1

    def test_tool_not_called(self):
        spec = {"method": "rule", "rule": "tool_not_called", "args": {"tool_name": "dangerous"}}
        result = self._trace([{
            "turn": 1, "input": {}, "output": {},
            "steps": [{"type": "tool_call", "data": {"name": "safe"}}],
        }])
        assert evaluate_rule(spec, result)["score"] == 1

    def test_max_turns(self):
        spec = {"method": "rule", "rule": "max_turns", "args": {"max": 5}}
        result = self._trace([
            {"turn": 1, "input": {}, "steps": [], "output": {}},
            {"turn": 2, "input": {}, "steps": [], "output": {}},
        ])
        assert evaluate_rule(spec, result)["score"] == 1

    def test_max_steps(self):
        spec = {"method": "rule", "rule": "max_steps", "args": {"max": 3}}
        result = self._trace([{
            "turn": 1, "input": {}, "output": {},
            "steps": [
                {"type": "llm_call", "data": {}},
                {"type": "llm_output", "data": {}},
            ],
        }])
        assert evaluate_rule(spec, result)["score"] == 1

    def test_tool_across_turns(self):
        """Tool sequence spans multiple turns."""
        spec = {"method": "rule", "rule": "tool_sequence", "args": {"expected": ["search", "summarize"]}}
        result = self._trace([
            {"turn": 1, "input": {}, "output": {},
             "steps": [{"type": "tool_call", "data": {"name": "search"}}]},
            {"turn": 2, "input": {}, "output": {},
             "steps": [{"type": "tool_call", "data": {"name": "summarize"}}]},
        ])
        assert evaluate_rule(spec, result)["score"] == 1


class TestConversationRules:
    def test_conversation_turns(self):
        spec = {"method": "rule", "rule": "conversation_turns", "args": {"min": 2, "max": 5}}
        result = {"outputs": {"conversation": [
            {"role": "user", "content": "hi"}, {"role": "bot", "content": "hello"},
            {"role": "user", "content": "bye"}, {"role": "bot", "content": "goodbye"},
        ]}}
        assert evaluate_rule(spec, result)["score"] == 1

    def test_conversation_turns_too_few(self):
        spec = {"method": "rule", "rule": "conversation_turns", "args": {"min": 3}}
        result = {"outputs": {"conversation": [
            {"role": "user", "content": "hi"}, {"role": "bot", "content": "hello"},
        ]}}
        assert evaluate_rule(spec, result)["score"] == 0

    def test_all_turns_responded(self):
        spec = {"method": "rule", "rule": "all_turns_responded", "args": {}}
        result = {"outputs": {"conversation": [
            {"role": "user", "content": "hi"}, {"role": "bot", "content": "hello"},
            {"role": "user", "content": "bye"}, {"role": "bot", "content": "goodbye"},
        ]}}
        assert evaluate_rule(spec, result)["score"] == 1

    def test_missing_response(self):
        spec = {"method": "rule", "rule": "all_turns_responded", "args": {}}
        result = {"outputs": {"conversation": [
            {"role": "user", "content": "hi"}, {"role": "user", "content": "hello?"},
        ]}}
        assert evaluate_rule(spec, result)["score"] == 0

    def test_no_role_violation(self):
        spec = {"method": "rule", "rule": "no_role_violation", "args": {}}
        result = {"outputs": {"conversation": [
            {"role": "user", "content": "hi"}, {"role": "bot", "content": "Hello!"},
        ]}}
        assert evaluate_rule(spec, result)["score"] == 1

    def test_role_violation_detected(self):
        spec = {"method": "rule", "rule": "no_role_violation", "args": {}}
        result = {"outputs": {"conversation": [
            {"role": "user", "content": "hi"}, {"role": "bot", "content": "As a user, I think this is great"},
        ]}}
        assert evaluate_rule(spec, result)["score"] == 0

    def test_conversation_from_trace_turns(self):
        """Conversation rules can extract data from trace turns fallback."""
        spec = {"method": "rule", "rule": "all_turns_responded", "args": {}}
        result = {
            "trace": {"turns": [
                {"turn": 1, "input": {"content": "hi"}, "steps": [], "output": {"content": "hello"}},
                {"turn": 2, "input": {"content": "bye"}, "steps": [], "output": {"content": "goodbye"}},
            ]},
            "outputs": {},
        }
        assert evaluate_rule(spec, result)["score"] == 1
