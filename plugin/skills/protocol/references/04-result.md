# vibeval Protocol — Result & Trace

## 目录结构

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
        "input": {"content": "总结这个会议"},
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

多轮 TestResult 结构完全相同，只是 turns 数组有多个元素。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| test_name | string | 是 | 测试用例名称 |
| dataset | string | 否 | 关联的数据集名称 |
| item_id | string | 否 | 关联的数据项 ID |
| judge_results | list[JudgeResult] | 是 | 评估结果列表 |
| trace | Trace | 否 | 过程记录 |
| inputs | object | 否 | 测试输入 |
| outputs | object | 否 | 测试输出 |
| timestamp | number | 否 | 执行时间 |
| duration | number | 否 | 耗时（秒） |
| metadata | object | 否 | 附加信息 |

## Trace

按轮次组织的过程记录。每轮：input → steps[] → output。

### Turn

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| turn | number | 是 | 轮次编号，从 1 开始 |
| input | object | 是 | 该轮的输入 |
| steps | list[Step] | 是 | 处理过程（可为空列表） |
| output | object | 是 | 该轮的输出 |

### Step

`type` 完全开放，常见值：

| type | 含义 | 典型 data |
|------|------|----------|
| `llm_call` | 调用 LLM | model, prompt_preview, system |
| `llm_output` | LLM 返回 | content, thinking, token_count |
| `tool_call` | 调用工具 | name, args |
| `tool_result` | 工具返回 | name, result |
| `handoff` | Agent 交接 | from, to, context |
| `context_update` | 上下文变更 | added, removed, modified |
| `retrieval` | RAG 检索 | query, results |

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| type | string | 是 | 步骤类型 |
| data | object | 是 | 步骤数据 |
| timestamp | number | 否 | 时间戳 |
| metadata | object | 否 | 附加信息 |

## JudgeResult

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| spec | JudgeSpec | 是 | 使用的评判规格 |
| score | number | 是 | rule/binary: 0 或 1；five-point: 1-5 |
| reason | string | 否 | 评估理由 |
| details | object | 否 | 附加信息 |

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
