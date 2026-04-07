---
name: protocol
description: This skill should be used when the user works with vibeval test files, mentions "vibeval", "judge_specs", "trace", "turns", edits files under "tests/vibeval/", or asks about AI application testing data formats. Provides the vibeval data protocol specification and evaluation philosophy.
---

# vibeval Data Protocol

vibeval (Vibe Coding Eval) is a protocol-driven AI application testing framework. All vibeval commands and workflows MUST conform to this protocol.

## Evaluation Philosophy

LLM-as-Judge works NOT because the judge is smarter, but because vibeval gives it **structural advantages**:

1. **Information asymmetry** — The judge knows test intent, trap design, expected behavior. The tested AI only sees input.
2. **Global process visibility** — The judge reviews structured traces step-by-step, free from context window limits.

**Always consult `${CLAUDE_SKILL_DIR}/references/00-philosophy.md` first when designing tests, data, and judge specs.**

## Quick Reference (Summary)

The following is a condensed overview. For complete definitions and field specs, consult the reference files listed below.

- All tests are N-turn interactions (single-turn = N=1). Each turn: **input → steps[] → output**
- Tests organized by feature: `tests/vibeval/{feature}/`
- Two evaluation methods: **rule** (deterministic) and **llm** (binary 0/1 or five-point 1-5)
- LLM specs require: `test_intent`, `anchors`, `calibrations` (mandatory); `trap_design`, `target` (optional)
- Test code has ZERO dependency on vibeval Python package

## vibeval CLI

To see all available commands and usage:

```bash
vibeval --help
vibeval <command> --help
```

## Reference Files (Source of Truth)

All foundational definitions live here. Commands and other docs reference these, not the other way around.

- **`${CLAUDE_SKILL_DIR}/references/00-philosophy.md`** — Evaluation philosophy: information asymmetry, global process visibility. **Read first.**
- **`${CLAUDE_SKILL_DIR}/references/01-overview.md`** — Directory structure, unified turn model, data flow
- **`${CLAUDE_SKILL_DIR}/references/02-dataset.md`** — Manifest, data items, persona format, single-file datasets
- **`${CLAUDE_SKILL_DIR}/references/03-judge-spec.md`** — Rule types, LLM scoring, target options, all field definitions
- **`${CLAUDE_SKILL_DIR}/references/04-result.md`** — TestResult, Trace (turns/steps), JudgeResult, RunSummary
- **`${CLAUDE_SKILL_DIR}/references/05-comparison.md`** — Pairwise comparison, position bias elimination
