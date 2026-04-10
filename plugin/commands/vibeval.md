---
description: "vibeval — AI application testing workflow: analyze, design, generate, run, and update tests"
argument-hint: "[feature-name] [action]"
---

VibeCoding evaluation workflow for feature `$1`. Action: `$2` (optional — auto-detected from project state if omitted).

This command is the unified entry point. It detects the current project state, negotiates a contract with the user, and routes to phase skills with Evaluator-driven iteration.

---

## Step 0: Detect Project State and Decide Action

Before doing anything, assess the current state and decide which phase to enter. If `$2` is explicitly provided (e.g., `analyze`, `design`, `code`, `synthesize`, `run`, `update`), skip detection and go to that phase directly (but still ensure a contract exists — see Step 1). For backwards compatibility, `generate` is accepted and routes to code followed by synthesize.

### 0a. Check if vibeval has been used in this project

Look for `tests/vibeval/` directory.

**If `tests/vibeval/` does not exist → State: NEW_PROJECT**

This project has never used vibeval. Do the following:
1. Briefly scan the project structure to understand what it does
2. Identify AI-related code (LLM calls, AI frameworks, prompt templates, agent tools)
3. Present a short summary to the user:
   - Project overview (language, frameworks, AI components found)
   - Suggested features to test (each with a short description of what it does)
4. Ask the user which feature(s) they want to start with
5. Once confirmed, proceed to **Step 1: Negotiate Contract**

### 0b. Check the chosen feature's state

If `$1` is provided, check `tests/vibeval/$1/`. If `$1` is not provided, list existing features under `tests/vibeval/` and ask the user to choose, or ask for a new feature name.

Examine which artifacts exist for the feature:

| Artifacts present | State | Action |
|---|---|---|
| Nothing (new feature name) | FRESH_FEATURE | → Step 1: Negotiate Contract |
| `analysis/` only | ANALYZED | Verify analysis, check contract, then → Design |
| `analysis/` + `design/` | DESIGNED | Verify both, check contract, then → Code |
| `analysis/` + `design/` + `tests/` (no datasets) | CODE_GENERATED | Verify artifacts, then → Synthesize |
| `analysis/` + `design/` + `datasets/` + `tests/` | COMPLETE | → Step 0c |

**Verification**: When resuming from a partial state, quickly check whether the existing artifacts are still valid by comparing them against the current source code. If the source code has changed significantly since the artifacts were created, inform the user and suggest re-running from an earlier phase.

### 0c. For COMPLETE features — determine user intent

The feature has gone through the full workflow before. Check context and ask the user what they want to do:

1. **Run `git diff` to detect code changes** in files referenced by `analysis/analysis.yaml`
2. **Read the existing contract** at `tests/vibeval/$1/contract.yaml`
3. Present findings to the user:
   - If changes detected: show a summary of what changed, suggest incremental update
   - If no changes: ask what they'd like to do

Offer these options:
- **Update** — Code has changed; incrementally update analysis, design, datasets, and tests (→ Update phase)
- **Add tests** — Add new test cases or datasets to the existing suite (→ Design phase, additive mode)
- **Modify design** — Change judge specs, adjust scoring criteria, tune thresholds (→ Design phase, edit mode)
- **Run** — Re-run tests and judge for regression verification (→ Run phase)
- **Update contract** — Revise requirements, quality criteria, or known gaps (→ Step 1, update mode)
- **Full redo** — Start over from scratch (→ Step 1: Negotiate Contract)

---

## Step 1: Negotiate Contract

The contract is the shared standard for all phases. Contract negotiation is delegated to the `contract` skill, which runs a dialogue-driven workflow: the `vibeval-consultant` agent prepares a background research brief, and the main agent then runs a Socratic dialogue with the user using the brief as seed questions.

For the complete contract format specification, see `${CLAUDE_PLUGIN_ROOT}/protocol/references/06-contract.md`.

### For a new feature (no contract exists)

Read `${CLAUDE_PLUGIN_ROOT}/skills/contract/SKILL.md` and follow it end-to-end. The skill will:

1. Dispatch `vibeval-consultant` as a background researcher to produce `_research.md`.
2. Present a short anchor of findings to the user.
3. Run a Socratic dialogue (one question at a time) seeded by the brief.
4. Draft the contract with per-requirement `source` attribution (including the new `brainstorm` source).
5. Infer a `rigor` level (`light` / `standard` / `strict`) and confirm with the user.
6. Save `tests/vibeval/{feature}/contract.yaml` and delete the temporary research brief.

### For an existing feature (contract already exists)

Read the contract skill and use the "Updating an existing contract" section. No fresh research is needed unless code has changed substantially.

### Contract is required

Every feature MUST have a contract before entering any phase. If a phase is entered without a contract (e.g., resuming from a partial state), invoke the contract skill first.

---

## Step 2: Phase Execution with Evaluator Loop

Once the phase is determined and a contract exists, execute with this pattern:

```
┌─────────────────────────────────────────┐
│                                         │
▼                                         │
Read phase skill → Execute phase          │
        │                                 │
        ▼                                 │
Delegate to vibeval-evaluator agent       │
  (review output against contract)        │
        │                                 │
        ├── Issues found → Feed back ─────┘
        │   (max 3 iterations per phase)
        │
        └── All pass → Checkpoint
                │
                ▼
        Present to user
                │
                ├── User confirms → Next phase
                ├── User has feedback → Update contract.feedback_log
                │   → Re-iterate if needed
                └── User wants changes → Re-enter phase
```

### Phase routing table

| Phase | Skill | When to enter |
|---|---|---|
| **Analyze** | `${CLAUDE_PLUGIN_ROOT}/skills/analyze/SKILL.md` | New project or feature; full redo |
| **Design** | `${CLAUDE_PLUGIN_ROOT}/skills/design/SKILL.md` | After analysis; adding tests; modifying design |
| **Code** | `${CLAUDE_PLUGIN_ROOT}/skills/code/SKILL.md` | After design is reviewed and confirmed — generates test infrastructure |
| **Synthesize** | `${CLAUDE_PLUGIN_ROOT}/skills/synthesize/SKILL.md` | After test code exists — synthesizes datasets with parallel Data Synthesizer agents |
| **Run** | `${CLAUDE_PLUGIN_ROOT}/skills/run/SKILL.md` | After generation; regression verification |
| **Update** | `${CLAUDE_PLUGIN_ROOT}/skills/update/SKILL.md` | Code changed on a complete feature |

### Consultant integration

The `vibeval-consultant` agent's role is **background researcher**, not user-facing advisor. It writes a `_research.md` brief for the main agent; the main agent uses it to seed dialogue or coverage checks with the user.

It is invoked at two points:

1. **Step 1 (Contract Negotiation)** — via the `contract` skill, as Phase A (Research). The main agent runs a Socratic dialogue using the brief as seed questions.

2. **Design phase** — after the initial design is produced, the `vibeval-consultant` is dispatched with the current design as context. It writes a coverage-focused brief. The main agent reads the brief and surfaces any high-priority coverage gaps to the user as targeted questions (not as a suggestions list). See `${CLAUDE_PLUGIN_ROOT}/skills/design/SKILL.md` for details.

The Consultant never communicates directly with the user. The main agent owns the dialogue.

### Evaluator integration

After each phase (Analyze, Design, Generate) produces its output:

1. **Delegate to the `vibeval-evaluator` agent** with:
   - The feature name
   - The phase that just completed
   - Path to the contract: `tests/vibeval/{feature}/contract.yaml`
   - Path to the phase output (analysis.yaml, design.yaml, or generated files)

2. **Process the evaluator's review**:
   - If all dimensions score 2 (pass): proceed to checkpoint
   - If any dimension scores 0 or 1: address the feedback, re-execute the phase, re-evaluate
   - Maximum 3 evaluator iterations per phase to avoid infinite loops

3. **At the checkpoint**, present to the user:
   - Phase output summary
   - Evaluator review results (including any issues found and fixed during iteration)
   - Ask for confirmation to proceed

4. **If the user provides feedback** at the checkpoint:
   - Record in `contract.yaml` → `feedback_log`
   - If the feedback changes requirements or quality criteria, update those sections too
   - Re-iterate the phase if the feedback warrants it

### Phase transitions

After each phase's checkpoint, if the user confirms to continue, read the next phase's skill file and proceed:

- Negotiate Contract → Analyze → Design → Code → Synthesize → Run (full flow)
- Update → Run (incremental flow)
- Design (additive/edit) → Code → Synthesize → Run (modification flow)

The Code and Synthesize phases each include a `vibeval check` step for protocol compliance validation. The Run phase does NOT go through the Evaluator loop (it has its own diagnosis step built in). The Update phase triggers Evaluator review on the updated artifacts.
