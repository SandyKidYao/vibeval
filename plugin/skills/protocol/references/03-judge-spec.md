# vibeval Protocol — JudgeSpec

评判方法只有两类：**rule**（确定性规则）和 **llm**（LLM 评判）。

## 通用结构

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| method | string | 是 | `rule` 或 `llm` |
| weight | number \| "gate" | 否 | `"gate"` = 不通过则整体失败。默认 1.0 |

## method: rule — 规则评判

确定性规则，结果完全可复现。

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| rule | string | 是 | 内置规则名称 |
| args | object | 否 | 规则参数 |

### 输出规则

| 规则名 | 说明 | 参数 |
|--------|------|------|
| `contains` | 包含指定文本 | `field`, `value` |
| `contains_all` | 包含所有指定文本 | `field`, `values` 或 `values_from` |
| `contains_any` | 包含任一指定文本 | `field`, `values` |
| `not_contains` | 不包含指定文本 | `field`, `value` |
| `equals` | 等于预期值 | `field`, `expected` 或 `expected_from` |
| `matches` | 匹配正则表达式 | `field`, `pattern` |
| `is_json` | 是合法 JSON | `field` |
| `length_between` | 长度在范围内 | `field`, `min`, `max` |

### Trace 规则

| 规则名 | 说明 | 参数 |
|--------|------|------|
| `tool_sequence` | 工具调用顺序符合预期 | `expected` |
| `tool_called` | 指定工具被调用过 | `tool_name` |
| `tool_not_called` | 指定工具未被调用 | `tool_name` |
| `max_turns` | 轮次数不超过上限 | `max` |
| `max_steps` | 总 steps 数不超过上限 | `max` |

### 对话规则

| 规则名 | 说明 | 参数 |
|--------|------|------|
| `conversation_turns` | 对话轮次在范围内 | `min`, `max` |
| `all_turns_responded` | 每轮 input 都有 output | |
| `no_role_violation` | bot 未扮演用户角色 | |

### 字段引用

- `field` 使用点号路径：`outputs.summary`
- `values_from` / `expected_from` 引用数据项字段

## method: llm — LLM 评判

### 核心原则

1. **输入默认 full** — 完整 trace + inputs + outputs 全量提供给 LLM
2. **ground truth 自动纳入** — `reference_from` 指向数据项字段
3. **评分严格二选一** — binary（0/1）或 five-point（1-5）
4. **锚点和校准必填** — 评分稳定性的根基

### Binary（0/1 制）

```json
{
  "method": "llm",
  "scoring": "binary",
  "criteria": "summary does not fabricate information",
  "test_intent": "检验 AI 是否会将会议中的争议描述为共识",
  "trap_design": "Alice 提出将截止日期改到周五，Bob 明确反对并建议下周一。陷阱：AI 可能忽略反对意见，输出'大家同意了周五'",
  "anchors": {
    "0": "采用了 Alice 最初的周五方案，忽略了 Bob 的反对或将争议描述为共识",
    "1": "正确反映了 Alice 和 Bob 的不同意见，或以最终结论（下周一）为准"
  },
  "calibrations": [
    {"output": "团队同意将截止日期改到周五。", "score": 0, "reason": "将争议描述为共识，Bob 的反对被完全忽略"},
    {"output": "Alice 提议改到周五，但 Bob 反对并建议下周一。", "score": 1, "reason": "准确反映了双方立场"}
  ]
}
```

统计指标：**通过率**

### Five-point（5 分制）

```json
{
  "method": "llm",
  "scoring": "five-point",
  "criteria": "completeness of the summary",
  "anchors": {
    "1": "misses most key topics",
    "2": "captures some topics, misses decisions",
    "3": "covers main topics, omits some details",
    "4": "covers all key topics, minor gaps",
    "5": "comprehensive coverage"
  },
  "calibrations": [
    {"output": "They had a meeting.", "score": 1, "reason": "no information"},
    {"output": "Discussed timeline. Alice mentioned deadline.", "score": 3, "reason": "main topic but no specifics"},
    {"output": "Alice set April 15 deadline. Bob handles API. Charlie does demo.", "score": 5, "reason": "all decisions covered"}
  ]
}
```

不设通过阈值。统计指标：**分数分布**

### 评判目标（target）

默认情况下 LLM 评判接收完整的 trace + inputs + outputs。通过 `target` 字段可以聚焦到特定范围，让评判 LLM 专注审查特定的过程片段，而非面对整个上下文：

**评判最终输出（默认）：**
```json
{
  "method": "llm",
  "target": "output",
  "criteria": "summary is accurate"
}
```

**评判特定轮次范围：**
```json
{
  "method": "llm",
  "target": {"turns": [1, 3]},
  "criteria": "前 3 轮 bot 是否正确理解了用户的核心诉求",
  "test_intent": "验证 bot 在对话早期的理解能力",
  "anchors": {"0": "误解了用户意图", "1": "准确把握了核心诉求"}
}
```

**评判特定类型的 step：**
```json
{
  "method": "llm",
  "target": {"step_type": "tool_call"},
  "criteria": "所有工具选择是否合理，是否有冗余或遗漏",
  "test_intent": "验证 Agent 的工具选择决策",
  "trap_design": "场景中有两个功能相似的工具，只有一个能返回完整信息"
}
```

**评判特定轮次中的特定 step 类型：**
```json
{
  "method": "llm",
  "target": {"turns": [2, 2], "step_type": "llm_call"},
  "criteria": "第 2 轮的 LLM 调用是否正确包含了第 1 轮的关键上下文"
}
```

target 取值：

| 值 | 含义 | 送入 LLM 的数据 |
|---|------|----------------|
| `"output"` 或省略 | 评判最终输出（默认） | 完整 trace + inputs + outputs |
| `{"turns": [start, end]}` | 评判指定轮次范围 | 该范围内的 turns + 对应 inputs/outputs |
| `{"step_type": "..."}` | 评判特定类型的 step | 所有 turns 中该类型的 steps |
| `{"turns": [...], "step_type": "..."}` | 组合过滤 | 指定轮次内指定类型的 steps |

### 字段汇总

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| scoring | string | 是 | `"binary"` 或 `"five-point"` |
| criteria | string | 是 | 评判标准 |
| test_intent | string | 是 | 出题意图——考察被测 AI 的什么能力或弱点 |
| trap_design | string | 否 | 陷阱设计——数据中故意设置的干扰项 |
| target | string \| object | 否 | 评判目标范围。默认 `"output"`（完整上下文） |
| anchors | object | 是 | 各分值的锚点描述 |
| calibrations | list | 是 | 校准样本 |
| reference_from | string | 否 | 引用数据项字段作为 ground truth |
| model | string | 否 | 指定评判模型 |

`test_intent` 和 `trap_design` 是信息不对称原则的核心体现（见 `00-philosophy.md`）。
`target` 是全局视野原则的核心体现——允许对过程做逐步、分段的细粒度审查。
