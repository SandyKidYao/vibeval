# vibeval Protocol — Contract

## Purpose

A **contract** captures the negotiated agreement between the user and the VibeCoding Agent about what "good" means for a feature's tests. It is the shared standard that all phases (analyze, design, generate) work toward, and that the Evaluator Agent reviews against.

The contract exists because **code analysis alone cannot surface all requirements**. For AI applications, critical expectations often live outside the code:

- Behavioral requirements the user has in mind but hasn't implemented yet
- Quality standards that aren't encoded in any prompt or function
- Known gaps between current implementation and intended behavior
- Edge cases discovered through usage, not visible in source code

The contract makes these invisible requirements explicit, persistent, and enforceable across all phases.

## Relationship to Other Protocol Components

```
contract.yaml          The "what should be tested and why" — requirements + quality bar
    ↓
analysis.yaml          The "what exists in the code" — AI calls, data flow, mock points
    ↓
design.yaml            The "how to test it" — datasets, judge specs, test structure
    ↓
datasets/              The "test with what" — synthetic data + evaluation criteria
    ↓
results/               The "what happened" — traces + judge scores
```

The contract is the **upstream source** that informs all subsequent artifacts. When a requirement appears in the contract, it must be traceable through analysis → design → datasets → judge specs. The Evaluator Agent verifies this traceability at each phase.

## File Location

```
tests/vibeval/{feature}/contract.yaml
```

The contract is stored alongside all other feature artifacts. It is created during the initial `/vibeval` negotiation and updated as the user provides feedback across iterations.

## Format

```yaml
# vibeval Contract — negotiated standard for feature testing
# Created by /vibeval through user-agent negotiation

feature: "<feature_name>"
created: "<YYYY-MM-DD>"
updated: "<YYYY-MM-DD>"

# Rigor level: controls workflow depth for downstream phases.
# Inferred by the contract skill during negotiation; user may override.
#   light    — small features / no external docs; compressed loops, only high-severity issues reported
#   standard — default; current behavior (evaluator max 3 iterations, full phase sequence)
#   strict   — high-stakes features; extended dialogue, higher evaluator iteration cap
rigor: "<light|standard|strict>"

# Requirements: what the feature should do
# These come from five sources:
#   user       — stated by the user unprompted
#   code       — identified through code analysis (prompts, API calls, logic)
#   inferred   — inferred from code patterns, confirmed by user
#   brainstorm — surfaced during the contract skill's Socratic dialogue, confirmed by user
#   suggested  — DEPRECATED: was the Consultant-as-advisor output. New negotiations should use `brainstorm`.
requirements:
  - id: "<req-N>"
    description: "<what the feature should do>"
    source: "<user|code|inferred|brainstorm>"

# Known gaps: where code falls short of requirements
# These are the highest-priority areas for test coverage
known_gaps:
  - requirement: "<req-N>"
    gap: "<what's missing or insufficient in the code>"

# Quality criteria: the bar for test design quality
# The Evaluator Agent scores each dimension against these criteria
quality_criteria:
  coverage:
    bar: "<what coverage means for this feature>"
    user_emphasis: "<areas the user specifically cares about>"
  information_asymmetry:
    bar: "<standard for judge spec insider knowledge>"
  trap_quality:
    bar: "<standard for trap realism>"
  specificity:
    bar: "<standard for anchor/calibration specificity>"
  requirement_depth:
    bar: "<standard for requirement traceability>"

# Feedback log: user corrections and confirmations across iterations
# Each entry records what the user said and what action was taken
feedback_log:
  - date: "<YYYY-MM-DD>"
    phase: "<analyze|design|generate|run>"
    feedback: "<what the user said>"
    action: "<what was changed in response>"
```

## Field Definitions

### requirements

Each requirement describes a behavior the feature should exhibit. The `source` field tracks where the requirement came from:

| Source | Meaning | Example |
|---|---|---|
| `user` | Stated by the user unprompted during dialogue; not visible in code | "Must support Chinese, English, and Japanese" |
| `code` | Identified through code analysis (prompts, API calls, logic) | "Summarizes meeting transcripts into bullet points" |
| `inferred` | Inferred from code patterns, confirmed by user | "Prompt says 'be concise' → responses should be under 200 words" |
| `brainstorm` | Surfaced through Consultant-seeded dialogue with the user — either the contract skill's Socratic dialogue or the design skill's coverage review — and confirmed by the user | "Should handle prompt injection attempts without leaking system prompt" |
| `suggested` | DEPRECATED — produced by the old Consultant-as-advisor flow. Existing contracts keep this value; new contracts should use `brainstorm`. | — |

Requirements with `source: user` and `source: brainstorm` are the most valuable — they represent information that pure code analysis would miss entirely. The contract skill actively elicits these through Socratic dialogue, using a background brief from the Consultant Agent as seed questions.

**Agent features.** Tool-related behavioral requirements (e.g., "the agent must call the search tool before answering factual questions") are recorded here as ordinary requirements, typically with `source: user` or `source: brainstorm`. The contract format is unchanged by Agent-tool validation. When the design phase plans per-tool coverage, such requirements surface as additional test points for the relevant tool's positive-selection or sequence dimensions. See `07-agent-tools.md` for how contract requirements map to per-tool coverage.

### known_gaps

Each gap links a requirement to a deficiency in the current implementation. Gaps are high-priority test targets because they represent areas where the AI is most likely to fail:

- A requirement exists but no code supports it → test whether the AI handles it despite no explicit implementation
- A requirement is partially implemented → test the boundary between implemented and unimplemented behavior
- A requirement conflicts with current implementation → test how the AI resolves the conflict

### quality_criteria

These criteria define the quality bar for the test design itself (not the AI under test). The Evaluator Agent uses them to review phase outputs. Each criterion has:

- `bar`: the objective standard to meet
- `user_emphasis` (optional): specific areas the user wants extra attention on

Default criteria are provided by the `/vibeval` command, but the user can customize them during negotiation.

### feedback_log

A chronological record of user feedback across iterations. Each entry captures:

- When it happened (`date`)
- Which phase was being reviewed (`phase`)
- What the user said (`feedback`)
- What changed as a result (`action`)

The feedback log serves two purposes:
1. **Accountability**: the Evaluator can check that past feedback has been addressed
2. **Learning**: patterns in feedback reveal systematic issues in the workflow

### rigor

The `rigor` field controls how thoroughly downstream phases execute. It is inferred by the contract skill based on feature size, external documentation availability, and user input; the user can override at any point.

| Level | When it applies | Downstream effects |
|---|---|---|
| `light` | Small features (<200 LOC code footprint), no external PRD, exploratory work | Contract dialogue compressed to ~3 seed questions; evaluator loops capped at 1 iteration; evaluator only surfaces high-severity issues; code and synthesize phases may be merged in future plans |
| `standard` | Default | Current behavior — evaluator max 3 iterations, full phase sequence, all severity levels reported |
| `strict` | High-stakes features with rich external context (PRD, historical bad cases, compliance requirements) | Extended dialogue until convergence; evaluator iteration cap raised to 5; all phases run independently; no shortcuts |

The contract skill writes the inferred level into `rigor` and explains it to the user for confirmation. The `/vibeval` orchestrator reads `rigor` to cap evaluator iterations per phase (see `${CLAUDE_PLUGIN_ROOT}/commands/vibeval.md`). Individual phase skills may read `rigor` for additional behavior (e.g., light-rigor dialogue compression, evaluator severity filtering) as they are updated over time.

## Contract Lifecycle

### Creation

The contract is created during the `/vibeval` command's Step 0 (state detection), specifically during the negotiation phase:

1. The `/vibeval` command delegates to the `contract` skill (see `plugin/skills/contract/SKILL.md`).
2. The skill dispatches the `vibeval-consultant` agent as a background researcher; the researcher writes a brief to `tests/vibeval/{feature}/_research.md`.
3. The skill presents a brief anchor of findings to the user and runs a Socratic dialogue (one question per turn), using the researcher's seed questions and adapting based on user answers.
4. The skill drafts `contract.yaml` with per-requirement `source` attribution and infers a `rigor` level.
5. User approves; contract is saved; `_research.md` is deleted; all subsequent phases reference the contract.

### Evolution

The contract evolves through:

- **User feedback at checkpoints**: after each phase, the user may add requirements, adjust quality bars, or note issues → appended to `feedback_log`, relevant fields updated
- **Gap resolution**: when code changes address a known gap, the gap entry is updated or removed
- **Requirement discovery**: during design or generate phases, new requirements may surface → added with `source: inferred`, confirmed by user

### Persistence

The contract persists across sessions. When `/vibeval` is invoked on a COMPLETE feature, it reads the existing contract and asks the user if it needs updating before proceeding.

## Traceability

Every requirement in the contract should be traceable through the artifact chain:

```
contract.yaml                    requirements[req-1]: "Support multilingual"
    ↓
analysis/analysis.yaml           suggestions: "No multilingual handling found"
    ↓
design/design.yaml               datasets[multilingual]: items testing zh/en/ja
                                  judge_specs: language match evaluation
    ↓
datasets/multilingual/           data items with Chinese, English, Japanese inputs
    manifest.yaml                judge_specs checking language detection
    ↓
results/                         scores showing pass/fail on language matching
```

The Evaluator Agent checks this traceability: if a requirement exists in the contract but has no corresponding test coverage, it flags this as a gap.
