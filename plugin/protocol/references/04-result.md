# vibeval Protocol — Result & Trace

## Directory Structure

```
tests/vibeval/{feature}/
├── datasets/
├── results/
│   ├── 2026-03-31_001/
│   │   ├── summary.json
│   │   ├── test_a__item1.result.json
│   │   └── test_b__item2.result.json
│   └── 2026-03-31_002/
├── comparisons/
│   └── run_a_vs_run_b.json
└── tests/
```

## TestResult

```json
{
  "test_name": "test_summarize",
  "dataset": "meeting_summaries",
  "item_id": "standup",
  "judge_results": [],
  "trace": {
    "turns": [
      {
        "turn": 1,
        "input": {"content": "Summarize this meeting"},
        "steps": [
          {"type": "tool_call",   "data": {"name": "fetch_transcript", "args": {"id": "123"}}},
          {"type": "tool_result", "data": {"name": "fetch_transcript", "result": "Alice: ..."}},
          {"type": "llm_call",    "data": {"model": "gpt-4o", "prompt_preview": "Summarize..."}},
          {"type": "llm_output",  "data": {"content": "Meeting summary: ..."}}
        ],
        "output": {"content": "Meeting summary: ..."}
      }
    ]
  },
  "inputs": {"speakers": ["Alice", "Bob"], "text": "..."},
  "outputs": {"summary": "Meeting summary: ..."},
  "timestamp": 1774936200.0,
  "duration": 1.5,
  "metadata": {}
}
```

Multi-turn TestResult has the exact same structure, with multiple elements in the turns array.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| test_name | string | Yes | Test case name |
| dataset | string | No | Associated dataset name |
| item_id | string | No | Associated data item ID |
| judge_results | list[JudgeResult] | Yes | List of evaluation results |
| trace | Trace | No | Process record |
| inputs | object | No | Test inputs |
| outputs | object | No | Test outputs |
| timestamp | number | No | Execution time |
| duration | number | No | Duration (seconds) |
| metadata | object | No | Additional information |

## Trace

Process records organized by turn. Each turn: input → steps[] → output.

### Turn

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| turn | number | Yes | Turn number, starting from 1 |
| input | object | Yes | Input for this turn |
| steps | list[Step] | Yes | Processing steps (may be empty list) |
| output | object | Yes | Output for this turn |

### Step

`type` is fully open-ended. Common values:

| type | Meaning | Typical data |
|------|---------|--------------|
| `llm_call` | LLM invocation | model, prompt_preview, system |
| `llm_output` | LLM response | content, thinking, token_count |
| `tool_call` | Tool invocation | name, args |
| `tool_result` | Tool response | name, result |
| `handoff` | Agent handoff | from, to, context |
| `context_update` | Context change | added, removed, modified |
| `retrieval` | RAG retrieval | query, results |

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| type | string | Yes | Step type |
| data | object | Yes | Step data |
| timestamp | number | No | Timestamp |
| metadata | object | No | Additional information |

## JudgeResult

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| spec | JudgeSpec | Yes | The judge specification used |
| score | number | Yes | rule/binary: 0 or 1; five-point: 1-5 |
| reason | string | No | Evaluation rationale |
| details | object | No | Additional information |

## RunSummary

```json
{
  "run_id": "2026-03-31_001",
  "timestamp": 1774936200.0,
  "total": 10,
  "duration": 15.3,
  "binary_stats": {
    "total": 25, "passed": 22, "failed": 3, "pass_rate": 0.88
  },
  "five_point_stats": {
    "completeness": {"1": 0, "2": 1, "3": 2, "4": 5, "5": 2, "avg": 3.8}
  },
  "metadata": {}
}
```
