# vibeval Protocol — JudgeSpec

There are only two types of evaluation methods: **rule** (deterministic rules) and **llm** (LLM evaluation).

## Common Structure

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| method | string | Yes | `rule` or `llm` |
| weight | number \| "gate" | No | `"gate"` = failure causes overall failure. Default 1.0 |

## method: rule — Rule-based Evaluation

Deterministic rules with fully reproducible results.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| rule | string | Yes | Built-in rule name |
| args | object | No | Rule arguments |

### Output Rules

| Rule Name | Description | Arguments |
|-----------|-------------|-----------|
| `contains` | Contains specified text | `field`, `value` |
| `contains_all` | Contains all specified texts | `field`, `values` or `values_from` |
| `contains_any` | Contains any specified text | `field`, `values` |
| `not_contains` | Does not contain specified text | `field`, `value` |
| `equals` | Equals expected value | `field`, `expected` or `expected_from` |
| `matches` | Matches regular expression | `field`, `pattern` |
| `is_json` | Is valid JSON | `field` |
| `length_between` | Length within range | `field`, `min`, `max` |

### Trace Rules

| Rule Name | Description | Arguments |
|-----------|-------------|-----------|
| `tool_sequence` | Tool call order matches expected | `expected` |
| `tool_called` | Specified tool was called | `tool_name` |
| `tool_not_called` | Specified tool was not called | `tool_name` |
| `max_turns` | Number of turns does not exceed limit | `max` |
| `max_steps` | Total steps count does not exceed limit | `max` |

### Conversation Rules

| Rule Name | Description | Arguments |
|-----------|-------------|-----------|
| `conversation_turns` | Conversation turns within range | `min`, `max` |
| `all_turns_responded` | Every input turn has an output | |
| `no_role_violation` | Bot did not impersonate the user role | |

### Field References

- `field` uses dot notation paths: `outputs.summary`
- `values_from` / `expected_from` reference data item fields

## method: llm — LLM Evaluation

### Core Principles

1. **Full input by default** — Complete trace + inputs + outputs are provided to the LLM
2. **Ground truth automatically included** — `reference_from` points to a data item field
3. **Scoring is strictly one of two modes** — binary (0/1) or five-point (1-5)
4. **Anchors and calibrations are required** — The foundation for scoring stability

### Binary (0/1)

```json
{
  "method": "llm",
  "scoring": "binary",
  "criteria": "summary does not fabricate information",
  "test_intent": "Test whether the AI will describe a disputed point in a meeting as consensus",
  "trap_design": "Alice proposed changing the deadline to Friday, Bob explicitly objected and suggested next Monday. Trap: The AI may ignore the objection and output 'everyone agreed to Friday'",
  "anchors": {
    "0": "Adopted Alice's initial Friday proposal, ignoring Bob's objection or describing the dispute as consensus",
    "1": "Correctly reflected Alice and Bob's differing opinions, or used the final conclusion (next Monday) as the basis"
  },
  "calibrations": [
    {"output": "The team agreed to change the deadline to Friday.", "score": 0, "reason": "Described the dispute as consensus, Bob's objection was completely ignored"},
    {"output": "Alice proposed changing to Friday, but Bob objected and suggested next Monday.", "score": 1, "reason": "Accurately reflected both positions"}
  ]
}
```

Statistical metric: **pass rate**

### Five-point (1-5)

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

No pass threshold is set. Statistical metric: **score distribution**

### Evaluation Target (target)

By default, the LLM judge receives the complete trace + inputs + outputs. The `target` field allows focusing on a specific scope, letting the judging LLM concentrate on reviewing specific process segments rather than facing the entire context:

**Evaluate final output (default):**
```json
{
  "method": "llm",
  "target": "output",
  "criteria": "summary is accurate"
}
```

**Evaluate a specific turn range:**
```json
{
  "method": "llm",
  "target": {"turns": [1, 3]},
  "criteria": "In the first 3 turns, did the bot correctly understand the user's core request",
  "test_intent": "Verify the bot's comprehension ability in early conversation",
  "anchors": {"0": "Misunderstood the user's intent", "1": "Accurately grasped the core request"}
}
```

**Evaluate a specific step type:**
```json
{
  "method": "llm",
  "target": {"step_type": "tool_call"},
  "criteria": "Whether all tool selections are reasonable, with no redundancy or omissions",
  "test_intent": "Verify the Agent's tool selection decisions",
  "trap_design": "The scenario has two functionally similar tools, but only one returns complete information"
}
```

**Evaluate a specific step type within specific turns:**
```json
{
  "method": "llm",
  "target": {"turns": [2, 2], "step_type": "llm_call"},
  "criteria": "Whether the LLM call in turn 2 correctly includes the key context from turn 1"
}
```

Target values:

| Value | Meaning | Data sent to LLM |
|-------|---------|-------------------|
| `"output"` or omitted | Evaluate final output (default) | Complete trace + inputs + outputs |
| `{"turns": [start, end]}` | Evaluate specified turn range | Turns within that range + corresponding inputs/outputs |
| `{"step_type": "..."}` | Evaluate specific step type | Steps of that type across all turns |
| `{"turns": [...], "step_type": "..."}` | Combined filter | Steps of the specified type within the specified turns |

### Field Summary

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| scoring | string | Yes | `"binary"` or `"five-point"` |
| criteria | string | Yes | Evaluation criteria |
| test_intent | string | Yes | Test intent — what capability or weakness of the tested AI is being evaluated |
| trap_design | string | No | Trap design — deliberate distractors embedded in the data |
| target | string \| object | No | Evaluation target scope. Default `"output"` (full context) |
| anchors | object | Yes | Anchor descriptions for each score value |
| calibrations | list | Yes | Calibration samples |
| reference_from | string | No | Reference a data item field as ground truth |
| model | string | No | Specify the evaluation model |

`test_intent` and `trap_design` are the core embodiment of the information asymmetry principle (see `00-philosophy.md`).
`target` is the core embodiment of the global visibility principle — enabling step-by-step, segmented, fine-grained process auditing.
