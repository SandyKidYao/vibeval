# vibeval Protocol — Comparison (横评)

横评结果独立存储，不影响各 run 的独立评估。

## 目录结构

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

## 消除位置偏差

每次对比做两轮评估，交换 A/B 顺序：
- 两轮一致 → `confidence: "consistent"`
- 两轮矛盾 → `winner: "inconclusive"`, `confidence: "inconsistent"`

## 横评范围

横评只对 LLM judge_specs 执行（rule 是确定性的，比较无意义）。
