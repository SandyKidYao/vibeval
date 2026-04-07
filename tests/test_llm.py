"""Tests for LLM provider routing, claude-code check, and custom command."""

import subprocess
from unittest.mock import patch, MagicMock

import pytest

from vibeval.config import LLMConfig
from vibeval.llm import (
    _call_llm,
    _call_custom_command,
    check_claude_code,
)


class TestCheckClaudeCode:

    def test_success(self):
        mock_result = MagicMock(returncode=0, stdout="Hello!")
        with patch("vibeval.llm.subprocess.run", return_value=mock_result):
            check_claude_code()  # should not raise

    def test_not_installed(self):
        with patch("vibeval.llm.subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(RuntimeError, match="not installed or not in PATH"):
                check_claude_code()

    def test_not_authenticated(self):
        mock_result = MagicMock(returncode=1, stderr="Not authenticated")
        with patch("vibeval.llm.subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="failed to respond"):
                check_claude_code()

    def test_error_suggests_login(self):
        mock_result = MagicMock(returncode=1, stderr="auth error")
        with patch("vibeval.llm.subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="claude login"):
                check_claude_code()


class TestCallLLMRouting:

    def test_claude_code_provider(self):
        config = LLMConfig(provider="claude-code")
        with patch("vibeval.llm._call_claude_code", return_value="response") as mock:
            result = _call_llm("hello", config)
        assert result == "response"
        mock.assert_called_once_with("hello", config)

    def test_command_provider(self):
        config = LLMConfig(provider="command", command="echo test")
        with patch("vibeval.llm._call_custom_command", return_value="response") as mock:
            result = _call_llm("hello", config)
        assert result == "response"
        mock.assert_called_once_with("hello", config)

    def test_unknown_provider(self):
        config = LLMConfig(provider="unknown")
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            _call_llm("hello", config)


class TestCallClaudeCode:

    def test_passes_model_flag(self):
        config = LLMConfig(provider="claude-code", model="claude-sonnet-4-6")
        mock_result = MagicMock(returncode=0, stdout="response")
        with patch("vibeval.llm.subprocess.run", return_value=mock_result) as mock_run:
            # Patch check so it doesn't actually run claude --version
            with patch("vibeval.llm.check_claude_code"):
                from vibeval.llm import _call_claude_code
                result = _call_claude_code("prompt", config)

        cmd = mock_run.call_args[0][0]
        assert "--model" in cmd
        assert "claude-sonnet-4-6" in cmd
        assert result == "response"

    def test_no_model_flag_when_empty(self):
        config = LLMConfig(provider="claude-code", model="")
        mock_result = MagicMock(returncode=0, stdout="response")
        with patch("vibeval.llm.subprocess.run", return_value=mock_result) as mock_run:
            with patch("vibeval.llm.check_claude_code"):
                from vibeval.llm import _call_claude_code
                _call_claude_code("prompt", config)

        cmd = mock_run.call_args[0][0]
        assert "--model" not in cmd


class TestCallCustomCommand:

    def test_success(self):
        config = LLMConfig(provider="command", command="cat")
        mock_result = MagicMock(returncode=0, stdout="  llm response  ")
        with patch("vibeval.llm.subprocess.run", return_value=mock_result) as mock_run:
            result = _call_custom_command("hello", config)

        assert result == "llm response"
        mock_run.assert_called_once_with(
            "cat",
            input="hello",
            capture_output=True,
            text=True,
            shell=True,
            timeout=120,
        )

    def test_no_command_configured(self):
        config = LLMConfig(provider="command", command="")
        with pytest.raises(ValueError, match="no command is configured"):
            _call_custom_command("hello", config)

    def test_command_fails(self):
        config = LLMConfig(provider="command", command="false")
        mock_result = MagicMock(returncode=1, stderr="bad input")
        with patch("vibeval.llm.subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="Custom LLM command error"):
                _call_custom_command("hello", config)

    def test_prompt_passed_via_stdin(self):
        config = LLMConfig(provider="command", command="my-llm")
        mock_result = MagicMock(returncode=0, stdout="ok")
        with patch("vibeval.llm.subprocess.run", return_value=mock_result) as mock_run:
            _call_custom_command("the prompt text", config)

        assert mock_run.call_args[1]["input"] == "the prompt text"
