---
name: contract
description: Negotiate a feature's vibeval contract through Socratic dialogue with the user, seeded by a background research brief from the vibeval-consultant agent. Use when entering Step 1 of /vibeval for a new feature, or when updating an existing contract.
---

# vibeval Contract Skill

Produce `tests/vibeval/{feature}/contract.yaml` through a dialogue with the user, informed by a research brief prepared in the background by the `vibeval-consultant` agent.

**Before starting, read:**
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/06-contract.md` — contract schema, including `rigor` and the `brainstorm` source.
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/00-philosophy.md` — information asymmetry + why external (user-held) requirements matter more than code-visible ones.

## Red Flags

Stop and reconsider if you catch yourself thinking any of these:

| Inner voice | Reality |
|---|---|
| "用户应该没什么要补的" / "User probably has nothing to add" | 没问 ≠ 没有. You cannot know until you ask. Run the dialogue. |
| "从代码推就够了" / "I can derive enough from the code" | Code encodes what the developer built, not what the user wants. External requirements are the highest-value signal. |
| "Consultant 给的建议我直接塞进 contract 就行" / "Just put the Consultant brief into the contract" | The brief is seed questions, NOT an answer key. Every contract requirement must come from a user answer, not from the brief alone. |
| "对话太麻烦，默认填一份给用户 review" / "Dialogue is tedious, let me fill in a draft for review" | A self-drafted contract is always code-perspective. Review has far less signal than dialogue. Run the dialogue. |
| "用户说 '差不多了' 就收工" / "User said 'good enough' so we're done" | Check: did you ask about external sources (PRD, bad cases, user feedback)? If not, one more question before stopping. |

## Workflow

### Phase A: Research (silent to user)

1. **Gather context** for the Consultant:
   - Feature name and working directory
   - Paths to: AI call sites, prompt files, tool definitions (quick scan with `Grep` for `llm`, `prompt`, `chat`, `completion`, `invoke_model`, etc.)
   - User's initial description if any
   - Existing `analysis/analysis.yaml` if present

2. **Dispatch the `vibeval-consultant` agent** with the gathered context and the target output path `tests/vibeval/{feature}/_research.md`.

3. **Wait for the Consultant to write the brief.** When it returns, read `_research.md` yourself. This is internal — do not show it to the user.

4. **Internalize the seed questions.** You will ask them in order of priority during Phase C, but adapt based on user answers.

### Phase B: Initial Anchor (one short message to user)

Present a brief orientation — not a review document. Keep it under 8 sentences:

- What you see the feature doing (derived from code, 2-3 sentences)
- That you found N potential areas worth discussing (from the brief's "Identified AI Call Points" and "Hidden Contract" sections, summarized — do NOT list all of them)
- That you will ask some questions to understand what matters to the user

Example template:

> Looking at `{feature}`, I see it does <X> by calling <Y>. I noticed the prompts imply expectations like <Z> that aren't explicitly enforced in code, and there are a few failure modes common to this kind of feature I want to ask you about. Before we design any tests, I want to spend a few minutes understanding what actually matters to you — so I'll ask questions one at a time.

Do NOT dump the Consultant brief into this message. The anchor is orientation, not a review document.

### Phase C: Socratic Dialogue (the core)

Run a turn-by-turn dialogue. Apply these rules strictly:

1. **One question per turn.** Never ask multiple questions in a single message. Users answer the first and skip the rest.
2. **Listen and adapt.** The next question is determined by the user's previous answer, not by the script. If the user volunteers information that answers a later seed question, skip it.
3. **Always probe for concrete examples.** When the user says something abstract like "it should handle edge cases", ask: "Can you give me a specific example of an input or a bad output you're worried about?"
4. **Ask about external sources at least once.** At some point in the dialogue, ask: "Do you have a PRD, user feedback, or any documented bad cases I should read?" If yes, offer to read them (`Read` the file paths they give you) before continuing.
5. **Summarize every 3-4 turns.** "OK so far I'm hearing: <A>, <B>, <C>. Did I get that right, or should I adjust?"
6. **Never put words in the user's mouth.** If a seed question from the brief is speculative, ask it as an open question, not a leading one. Bad: "So you want prompt injection protection, right?" Good: "Has prompt injection come up as a concern for you here?"

**Stop conditions** (stop when ANY is met):
- User explicitly says "enough" / "let's move on" / "我们开始下一步".
- All high-priority seed questions from the brief have been addressed AND two consecutive turns produced no new dimensions.
- The rigor minimum for the level you will infer at Phase D (see "Rigor-aware minimums" below) has been met AND the user seems uninterested in further questions.

**Rigor-aware minimums** (enforce to prevent premature stopping):
- `light`: at least 3 questions answered AND one summary round completed.
- `standard`: at least 5 questions answered AND two summary rounds completed.
- `strict`: no minimum — continue until genuine convergence.

If you don't yet know the rigor level (it is inferred at Phase D, after the dialogue completes), assume `standard` minimums during the dialogue.

### Phase D: Draft, Infer Rigor, and Save

1. **Draft `contract.yaml`** from the dialogue transcript. Apply these rules:

   - Every `requirement` must have a `source` field set according to these rules:
     - `user` — the user said it unprompted (you did not ask a question that set it up).
     - `brainstorm` — surfaced by a seed question (from the Consultant brief) and confirmed by the user during dialogue.
     - `inferred` — derived from code or prompt content, then explicitly confirmed by the user (e.g., "yes, that's correct").
     - `code` — directly visible in code and self-evidently true (no user confirmation needed).
   - Every `description` must be concrete. Reject generic phrasing.
     - Bad: "handle edge cases", "be robust", "support multiple languages"
     - Good: "when search returns empty results, the bot must tell the user explicitly instead of fabricating results"
     - Good: "responses must default to Chinese when the user writes in Chinese, even if the prompt is in English"

2. **Draft `known_gaps`** by cross-referencing each requirement against the code:
   - If the requirement is listed as `brainstorm` or `user` and there is no code path that enforces it → it's a gap.
   - If the requirement is partially implemented → describe the gap precisely.

3. **Draft `quality_criteria`** with defaults, biased by `user_emphasis` captured in the dialogue:
   - If the user emphasized specific dimensions (e.g., "I really care about language handling"), set the corresponding `user_emphasis` field.
   - Otherwise, use defaults from the protocol reference.

4. **Infer `rigor`** (if the user has not explicitly set it). This is folded into the draft so the contract is saved exactly once, with `rigor` populated from the start.

   a. **Check code footprint**: count LOC of files referenced by `analysis/analysis.yaml` if it exists, or estimate from the feature's source directory. Threshold: <200 LOC → lean toward `light`; ≥200 LOC → lean toward `standard`.

   b. **Check external context**: during the dialogue, did the user mention a PRD, historical bad cases, compliance requirements, or production feedback? If yes → lean toward `standard` or `strict` regardless of code size.

   c. **Combine**:
   - `<200 LOC AND no external context` → suggest `light`.
   - `<200 LOC AND external context` → suggest `standard`.
   - `≥200 LOC AND no external context` → suggest `standard`.
   - `≥200 LOC AND rich external context AND user expressed high stakes` → suggest `strict`.

   Write the inferred level into the in-memory draft's `rigor` field. Do not save yet.

5. **Show the draft to the user** (including the inferred `rigor`):

   > Here's the contract I've drafted based on our discussion, including a suggested rigor level of `<level>` (meaning: <one-line description of what that entails downstream>). Let me know if anything is wrong, missing, or should be emphasized differently — including whether you want to override the rigor.
   >
   > [paste the full YAML]

6. **If the user has edits**, apply them (including any `rigor` override), show the updated draft, and ask again. Loop until the user confirms.

7. **When the user confirms, save and clean up in this order**:
   - Save the complete draft to `tests/vibeval/{feature}/contract.yaml` **exactly once** — this single write includes requirements, known_gaps, quality_criteria, AND `rigor`. No intermediate state on disk.
   - Delete `tests/vibeval/{feature}/_research.md`.

## Checkpoint

After the contract is saved, present to the user:

1. **Contract file path**: `tests/vibeval/{feature}/contract.yaml`
2. **Requirement counts by source**: `code=N, inferred=N, brainstorm=N, user=N`
3. **Rigor level** and a one-line description of what it affects
4. **Known gaps** identified
5. **What happens next**: hand back to `/vibeval` which will proceed to the next phase (typically Analyze).

## Updating an existing contract

If `tests/vibeval/{feature}/contract.yaml` already exists:

1. Read the existing contract and its `feedback_log`.
2. **Skip Phase A.** No fresh Consultant research needed unless the code has changed substantially since the contract was created (in which case, do run a lightweight research pass on the changed files).
3. Short dialogue (one summary turn + one "what's changed" turn):
   - Summarize the existing contract: "Here's what we agreed on last time: <brief summary>."
   - Ask: "What's changed since then? Any new requirements, feedback from users, or priorities to adjust?"
4. Apply the user's changes:
   - New requirements go in with `source: user` if the user raised them unprompted, or `source: inferred` if you surfaced them (e.g., from noticing code changes during your lightweight re-scan) and the user confirmed. Do NOT use `source: brainstorm` during updates — that source requires a fresh Consultant research pass, which updates skip.
   - Updated quality criteria or user emphasis update the relevant fields.
   - Bump `updated:` to today's date.
   - Append an entry to `feedback_log` recording this update round.
5. Save. Skip rigor re-inference unless the user explicitly wants to revisit it.
