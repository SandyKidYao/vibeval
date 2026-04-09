---
description: "vibeval — AI application testing workflow: analyze, design, generate, run, and update tests"
argument-hint: "[feature-name] [action]"
---

VibeCoding evaluation workflow for feature `$1`. Action: `$2` (optional — auto-detected from project state if omitted).

This command is the unified entry point. It detects the current project state, negotiates a contract with the user, and routes to phase skills with Evaluator-driven iteration.

---

## Step 0: Detect Project State and Decide Action

Before doing anything, assess the current state and decide which phase to enter. If `$2` is explicitly provided (e.g., `analyze`, `design`, `generate`, `run`, `update`), skip detection and go to that phase directly (but still ensure a contract exists — see Step 1).

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
| `analysis/` + `design/` | DESIGNED | Verify both, check contract, then → Generate |
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

The contract is the shared standard for all phases. For the complete format specification, see `${CLAUDE_PLUGIN_ROOT}/protocol/references/06-contract.md`.

### For a new feature (no contract exists)

1. **Present initial findings** from code analysis:
   - What the feature does (from code)
   - What the prompts/config suggest (inferred requirements)
   - Potential edge cases and failure modes identified

2. **Actively elicit user requirements beyond code**:
   > "What should this feature do that isn't reflected in the code? For example:
   > - Behavioral expectations (language support, tone, length limits)
   > - Safety or compliance constraints
   > - Edge cases you've encountered in real usage
   > - Quality standards for the output"

3. **Delegate to the `vibeval-consultant` agent** for proactive suggestions:
   - Pass the feature context (code structure, prompts, identified AI calls) and user-stated requirements
   - The Consultant returns suggested test scenarios with severity ratings and proposed requirements
   - Present the Consultant's suggestions to the user:
     > "Based on your feature's code and requirements, here are additional testing scenarios you may want to consider: ..."
   - For each suggestion the user confirms, add it to requirements with `source: suggested`
   - User can accept all, accept some, or skip entirely — the Consultant advises, the user decides

4. **Draft the contract** with:
   - `requirements`: combine code-derived, inferred, user-stated, and consultant-suggested requirements
   - `known_gaps`: where code falls short of stated requirements
   - `quality_criteria`: defaults + any user-specific emphasis

5. **Present the draft** for user review and confirmation

6. **Save** to `tests/vibeval/{feature}/contract.yaml`

### For an existing feature (contract already exists)

1. Read the existing contract
2. Ask: "Would you like to update the contract? Any new requirements, changed priorities, or feedback?"
3. If yes, update the relevant sections and save
4. If no, proceed with the existing contract

### Contract is required

Every feature MUST have a contract before entering any phase. If a phase is entered without a contract (e.g., resuming from a partial state), create one first by negotiating with the user.

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
| **Generate** | `${CLAUDE_PLUGIN_ROOT}/skills/generate/SKILL.md` | After design is reviewed and confirmed |
| **Run** | `${CLAUDE_PLUGIN_ROOT}/skills/run/SKILL.md` | After generation; regression verification |
| **Update** | `${CLAUDE_PLUGIN_ROOT}/skills/update/SKILL.md` | Code changed on a complete feature |

### Consultant integration

The `vibeval-consultant` agent is invoked at two points:

1. **During Step 1 (Contract Negotiation)**: after gathering user requirements and code analysis, the Consultant suggests additional test scenarios and failure modes. User confirms which suggestions to adopt.

2. **During Design phase**: after the initial design is produced (before Evaluator review), optionally delegate to the Consultant to suggest additional test scenarios that the design doesn't cover. This is especially useful when the design feels thin or covers only obvious cases. Present suggestions to the user for confirmation, then incorporate accepted ones into the design.

The Consultant is advisory — it suggests, the user decides. Accepted suggestions become `source: suggested` requirements in the contract or additional items in the design.

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

- Negotiate Contract → Analyze → Design → Generate → Run (full flow)
- Update → Run (incremental flow)
- Design (additive/edit) → Generate → Run (modification flow)

The Run phase does NOT go through the Evaluator loop (it has its own diagnosis step built in). The Update phase triggers Evaluator review on the updated artifacts.
