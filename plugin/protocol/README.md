# vibeval Data Protocol

vibeval (Vibe Coding Eval) is a protocol-driven AI application testing framework. All vibeval commands and workflows MUST conform to this protocol.

## Evaluation Philosophy

LLM-as-Judge works NOT because the judge is smarter, but because vibeval gives it **structural advantages**:

1. **Information asymmetry** — The judge knows test intent, trap design, expected behavior. The tested AI only sees input.
2. **Global process visibility** — The judge reviews structured traces step-by-step, free from context window limits.

**Always consult `${CLAUDE_PLUGIN_ROOT}/protocol/references/00-philosophy.md` first when designing tests, data, and judge specs.**

## Quick Reference (Summary)

The following is a condensed overview. For complete definitions and field specs, consult the reference files listed below.

- **Contract** (`contract.yaml`): negotiated standard between user and agent — captures requirements beyond code, quality criteria, known gaps. All phases reference it; the Evaluator Agent reviews against it.
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

- **`${CLAUDE_PLUGIN_ROOT}/protocol/references/00-philosophy.md`** — Evaluation philosophy: information asymmetry, global process visibility. **Read first.**
- **`${CLAUDE_PLUGIN_ROOT}/protocol/references/01-overview.md`** — Directory structure, unified turn model, data flow
- **`${CLAUDE_PLUGIN_ROOT}/protocol/references/02-dataset.md`** — Manifest, data items, persona format, `_mock_context` for environment data, single-file datasets
- **`${CLAUDE_PLUGIN_ROOT}/protocol/references/03-judge-spec.md`** — Rule types, LLM scoring, target options, all field definitions
- **`${CLAUDE_PLUGIN_ROOT}/protocol/references/04-result.md`** — TestResult, Trace (turns/steps), JudgeResult, RunSummary
- **`${CLAUDE_PLUGIN_ROOT}/protocol/references/05-comparison.md`** — Pairwise comparison, position bias elimination
- **`${CLAUDE_PLUGIN_ROOT}/protocol/references/06-contract.md`** — Contract format: requirements, known gaps, quality criteria, feedback log
- **`${CLAUDE_PLUGIN_ROOT}/protocol/references/07-agent-tools.md`** — Agent tools: inventory entry structure, static design-audit findings, per-tool coverage matrix (applies to features with a tool catalogue)
