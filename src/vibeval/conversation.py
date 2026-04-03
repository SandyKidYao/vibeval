"""Simulate user — generate the next user message given persona + history.

This is an atomic CLI capability. The test code (any language) controls
the conversation loop and calls `vibeval simulate` when it needs the next
user message.
"""

from __future__ import annotations

import json
from typing import Any

from .config import LLMConfig
from .llm import _call_llm


def simulate_user(
    persona: dict[str, Any],
    history: list[dict[str, str]],
    llm_config: LLMConfig | None = None,
) -> str:
    """Generate the next user message based on persona and conversation history.

    Args:
        persona: Persona dict with system_prompt, behavior_rules, etc.
        history: List of {"user": "...", "bot": "..."} dicts.
        llm_config: LLM config. Defaults to claude-code.

    Returns:
        The next user message string.
    """
    if llm_config is None:
        llm_config = LLMConfig()

    system_prompt = persona.get("system_prompt", "")
    behavior_rules = persona.get("behavior_rules", [])

    parts = [
        "You are simulating a user in a conversation with an AI bot.",
        "Stay in character based on the following persona and rules.",
        f"\n## Persona\n{system_prompt}",
    ]

    if behavior_rules:
        parts.append("\n## Behavior Rules")
        for rule in behavior_rules:
            parts.append(f"- {rule}")

    if history:
        parts.append("\n## Conversation So Far")
        for exchange in history:
            parts.append(f"User (you): {exchange.get('user', '')}")
            parts.append(f"Bot: {exchange.get('bot', '')}")

    parts.append("\n## Instruction\nGenerate the next user message. Reply with ONLY the message content, nothing else.")

    return _call_llm("\n".join(parts), llm_config)
