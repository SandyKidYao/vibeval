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

# Requirements: what the feature should do
# These come from four sources:
#   user      — stated by the user, not derivable from code
#   code      — identified through code analysis
#   inferred  — inferred from prompts/config, confirmed by user
#   suggested — proposed by the Consultant Agent, confirmed by user
requirements:
  - id: "<req-N>"
    description: "<what the feature should do>"
    source: "<user|code|inferred|suggested>"

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
| `user` | Stated by the user during negotiation; not visible in code | "Must support Chinese, English, and Japanese" |
| `code` | Identified through code analysis (prompts, API calls, logic) | "Summarizes meeting transcripts into bullet points" |
| `inferred` | Inferred from code patterns, confirmed by user | "Prompt says 'be concise' → responses should be under 200 words" |
| `suggested` | Proposed by the Consultant Agent based on testing expertise, confirmed by user | "Should handle prompt injection attempts without leaking system prompt" |

Requirements with `source: user` and `source: suggested` are the most valuable — they represent information that pure code analysis would miss entirely. The negotiation phase should actively elicit user requirements, and the Consultant Agent should proactively suggest testing scenarios based on common AI application failure modes.

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

## Contract Lifecycle

### Creation

The contract is created during the `/vibeval` command's Step 0 (state detection), specifically during the negotiation phase:

1. Agent analyzes code and presents initial findings
2. Agent asks: "What requirements exist beyond what the code shows?"
3. User provides additional context (multilingual support, safety rules, etc.)
4. Agent drafts contract, user reviews and confirms
5. Contract is saved; all subsequent phases reference it

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
