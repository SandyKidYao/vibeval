"""Meeting summarizer — the core AI pipeline.

Pipeline:
  1. Fetch transcript from API
  2. Call LLM to generate summary
  3. Call LLM to extract action items
  4. Return structured result
"""

from __future__ import annotations

from typing import Any

from . import llm_client, transcript_api


def summarize_meeting(meeting_id: str) -> dict[str, Any]:
    """Run the full meeting summarization pipeline."""

    # Step 1: Fetch transcript
    transcript = transcript_api.fetch_transcript(meeting_id)
    speakers = transcript.get("speakers", [])
    text = transcript.get("text", "")

    # Step 2: Generate summary
    summary_prompt = (
        f"Summarize the following meeting transcript.\n"
        f"Speakers: {', '.join(speakers)}\n\n"
        f"Transcript:\n{text}\n\n"
        f"Requirements:\n"
        f"- Include ALL mentioned times, dates, and deadlines\n"
        f"- Attribute key points to the correct speaker\n"
        f"- Be concise but complete"
    )
    summary = llm_client.chat(
        prompt=summary_prompt,
        system="You are a meeting summarizer. Be thorough and accurate.",
    )

    # Step 3: Extract action items
    actions_prompt = (
        f"Extract action items from this meeting summary:\n\n"
        f"{summary}\n\n"
        f"Format each as: - [Owner] Action (deadline if mentioned)"
    )
    action_items = llm_client.chat(
        prompt=actions_prompt,
        system="You extract action items from meeting summaries.",
    )

    # Step 4: Return structured result
    return {
        "meeting_id": meeting_id,
        "speakers": speakers,
        "summary": summary,
        "action_items": action_items,
        "transcript_length": len(text),
    }
