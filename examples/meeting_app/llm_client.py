"""LLM client — wraps the actual LLM API call.

In production this calls OpenAI/Anthropic. In tests this gets mocked.
"""

from __future__ import annotations


def chat(prompt: str, system: str = "") -> str:
    """Send a prompt to the LLM and return the response text."""
    # In a real app, this would be:
    #   client = openai.OpenAI()
    #   resp = client.chat.completions.create(
    #       model="gpt-4o",
    #       messages=[
    #           {"role": "system", "content": system},
    #           {"role": "user", "content": prompt},
    #       ],
    #   )
    #   return resp.choices[0].message.content
    raise RuntimeError(
        "LLM client not configured. "
        "Set OPENAI_API_KEY or mock this in tests."
    )
