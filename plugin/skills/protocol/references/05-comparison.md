# vibeval Protocol — Comparison

Comparison results are stored independently and do not affect the standalone evaluation of each run.

## Directory Structure

```
tests/vibeval/{feature}/
├── results/
│   ├── run_a/
│   └── run_b/
└── comparisons/
    └── {run_a}_vs_{run_b}.json
```

## ComparisonResult

```json
{
  "run_a": "2026-03-30_001",
  "run_b": "2026-03-31_001",
  "timestamp": 1774936200.0,
  "pairs": [
    {
      "test_name": "test_summarize",
      "item_id": "standup",
      "criteria": "summary accurately reflects all key decisions",
      "winner": "b",
      "confidence": "consistent",
      "reason": "run_b includes action item owners missing in run_a",
      "details": {
        "ab_order": {"winner": "b", "reason": "..."},
        "ba_order": {"winner": "b", "reason": "..."}
      }
    }
  ],
  "summary": {
    "total_pairs": 4,
    "a_wins": 1,
    "b_wins": 2,
    "ties": 0,
    "inconclusive": 1
  }
}
```

## Eliminating Position Bias

Each comparison performs two rounds of evaluation with swapped A/B order:
- Both rounds agree → `confidence: "consistent"`
- Both rounds disagree → `winner: "inconclusive"`, `confidence: "inconsistent"`

## Comparison Scope

Comparisons are only performed for LLM judge_specs (rules are deterministic, so comparison is meaningless).
