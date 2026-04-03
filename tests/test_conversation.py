"""Tests for simulate_user (atomic CLI capability)."""

from unittest.mock import patch

from vibeval.conversation import simulate_user


class TestSimulateUser:

    def _persona(self):
        return {
            "system_prompt": "You are a frustrated customer.",
            "opening_message": "Your product is broken!",
            "behavior_rules": ["If bot apologizes, demand refund"],
        }

    def test_basic(self):
        def mock_llm(prompt, llm_config=None):
            assert "frustrated customer" in prompt
            return "I want a full refund immediately!"

        with patch("vibeval.conversation._call_llm", side_effect=mock_llm):
            msg = simulate_user(self._persona(), [
                {"user": "Your product is broken!", "bot": "I'm sorry to hear that."},
            ])

        assert "refund" in msg.lower()

    def test_empty_history(self):
        """With no history, should still generate based on persona."""
        def mock_llm(prompt, llm_config=None):
            assert "frustrated customer" in prompt
            assert "Conversation So Far" not in prompt
            return "Hello, I have a complaint."

        with patch("vibeval.conversation._call_llm", side_effect=mock_llm):
            msg = simulate_user(self._persona(), [])

        assert len(msg) > 0

    def test_history_included_in_prompt(self):
        """Conversation history should be passed to LLM."""
        captured_prompt = []

        def mock_llm(prompt, llm_config=None):
            captured_prompt.append(prompt)
            return "Next message"

        history = [
            {"user": "Hi", "bot": "Hello"},
            {"user": "I'm angry", "bot": "Sorry"},
        ]

        with patch("vibeval.conversation._call_llm", side_effect=mock_llm):
            simulate_user(self._persona(), history)

        prompt = captured_prompt[0]
        assert "Hi" in prompt
        assert "Hello" in prompt
        assert "I'm angry" in prompt
        assert "Sorry" in prompt

    def test_behavior_rules_in_prompt(self):
        captured_prompt = []

        def mock_llm(prompt, llm_config=None):
            captured_prompt.append(prompt)
            return "Give me my money back"

        with patch("vibeval.conversation._call_llm", side_effect=mock_llm):
            simulate_user(self._persona(), [
                {"user": "broken!", "bot": "I apologize"},
            ])

        assert "demand refund" in captured_prompt[0]
