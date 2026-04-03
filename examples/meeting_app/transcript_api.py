"""Transcript API client — fetches meeting transcripts from an external service."""

from __future__ import annotations

from typing import Any


def fetch_transcript(meeting_id: str) -> dict[str, Any]:
    """Fetch a meeting transcript by ID.

    Returns:
        {
            "meeting_id": "mtg-123",
            "speakers": ["Alice", "Bob"],
            "text": "Alice: Good morning...",
            "duration_minutes": 30,
        }
    """
    # In a real app, this would call a REST API:
    #   resp = requests.get(f"https://api.meetings.com/v1/transcripts/{meeting_id}")
    #   return resp.json()
    raise RuntimeError(
        "Transcript API not configured. "
        "Set TRANSCRIPT_API_URL or mock this in tests."
    )
