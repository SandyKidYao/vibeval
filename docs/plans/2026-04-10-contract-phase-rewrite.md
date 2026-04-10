# Contract Phase Rewrite — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current "Consultant-as-advisor" contract negotiation in `/vibeval` Step 1 with a dialogue-driven `contract` skill that uses the Consultant agent as a background researcher, producing a brief that seeds a Socratic dialogue with the user.

**Architecture:** The main `/vibeval` agent delegates contract negotiation to a new `contract` skill. That skill (a) dispatches `vibeval-consultant` as a background researcher to produce `_research.md`, (b) runs a one-turn-at-a-time dialogue with the user using the brief as seed questions, (c) drafts `contract.yaml` with per-requirement `source` attribution (including a new `brainstorm` source), and (d) infers a `rigor` level for downstream phases. The Consultant agent is repositioned from "advisor who writes user-facing suggestions" to "researcher who prepares the main agent."

**Tech Stack:** Markdown skill files, YAML contract schema, Claude Code plugin structure.

**Scope boundary:** This plan covers **P0** of the vibeval optimization roadmap (see `docs/plans/roadmap.md` — not yet written). It does NOT cover: Red Flags tables across all skills (P1), `rigor` behavior changes in Evaluator and phase skills (P1), diagnosing-eval-failure process skill (P2), zero-placeholder enforcement (P2), multi-run statistical confidence (P3). Those will be separate plans.

**Why split this way:** These five file changes form a tightly-coupled subsystem — the contract skill requires the Consultant rewrite, the vibeval.md delegation requires the contract skill to exist, and the design skill update is needed to prevent regression when Consultant's output format changes. Later plans can land independently.

---

## File Structure

**Create:**
- `plugin/skills/contract/SKILL.md` — New skill for dialogue-driven contract negotiation.

**Modify:**
- `plugin/agents/consultant.md` — Rewrite role from user-facing advisor to background researcher. Change output format from `suggestions:` YAML to `_research.md` markdown brief.
- `plugin/commands/vibeval.md` — Step 1 delegates to the contract skill. Consultant integration section updated to reflect new role.
- `plugin/protocol/references/06-contract.md` — Add `rigor` field. Add `brainstorm` as a valid `source` value. Update lifecycle section to reference the contract skill.
- `plugin/skills/design/SKILL.md` — Update "Consultant Design Review" section to consume a brief instead of a suggestions list.

**No CLI or Python code changes in this plan.** CLI changes (e.g., `vibeval validate --strict`) are deferred to P2.

---

## Task 1: Extend contract protocol schema

**Files:**
- Modify: `plugin/protocol/references/06-contract.md`

- [ ] **Step 1: Add `rigor` field to the contract YAML format block**

Open the file and find the YAML example under the `## Format` section (starting around line 42). After the `updated:` line (around line 48), insert a new block before the `requirements:` section:

```yaml
# Rigor level: controls workflow depth for downstream phases.
# Inferred by the contract skill during negotiation; user may override.
#   light    — small features / no external docs; compressed loops, only high-severity issues reported
#   standard — default; current behavior (evaluator max 3 iterations, full phase sequence)
#   strict   — high-stakes features; extended dialogue, higher evaluator iteration cap
rigor: "<light|standard|strict>"
```

- [ ] **Step 2: Add `brainstorm` to the `source` enum**

Find the comment block above `requirements:` (around line 50-54). Replace the existing source enumeration comment:

```yaml
# Requirements: what the feature should do
# These come from four sources:
#   user      — stated by the user, not derivable from code
#   code      — identified through code analysis
#   inferred  — inferred from prompts/config, confirmed by user
#   suggested — proposed by the Consultant Agent, confirmed by user
```

with:

```yaml
# Requirements: what the feature should do
# These come from five sources:
#   user       — stated by the user unprompted
#   code       — identified through code analysis (prompts, API calls, logic)
#   inferred   — inferred from code patterns, confirmed by user
#   brainstorm — surfaced during the contract skill's Socratic dialogue, confirmed by user
#   suggested  — DEPRECATED: was the Consultant-as-advisor output. New negotiations should use `brainstorm`.
```

And update the `source` line inside the `requirements:` example:

Old:
```yaml
    source: "<user|code|inferred|suggested>"
```

New:
```yaml
    source: "<user|code|inferred|brainstorm>"
```

- [ ] **Step 3: Update the Field Definitions table for `requirements`**

Find the `### requirements` subsection (around line 93-104). Replace the markdown table with:

```markdown
| Source | Meaning | Example |
|---|---|---|
| `user` | Stated by the user unprompted during dialogue; not visible in code | "Must support Chinese, English, and Japanese" |
| `code` | Identified through code analysis (prompts, API calls, logic) | "Summarizes meeting transcripts into bullet points" |
| `inferred` | Inferred from code patterns, confirmed by user | "Prompt says 'be concise' → responses should be under 200 words" |
| `brainstorm` | Surfaced through the contract skill's Socratic dialogue (seeded by Consultant research), confirmed by user | "Should handle prompt injection attempts without leaking system prompt" |
| `suggested` | DEPRECATED — produced by the old Consultant-as-advisor flow. Existing contracts keep this value; new contracts should use `brainstorm`. | — |
```

And update the paragraph below it. Old:

> Requirements with `source: user` and `source: suggested` are the most valuable — they represent information that pure code analysis would miss entirely. The negotiation phase should actively elicit user requirements, and the Consultant Agent should proactively suggest testing scenarios based on common AI application failure modes.

New:

> Requirements with `source: user` and `source: brainstorm` are the most valuable — they represent information that pure code analysis would miss entirely. The contract skill actively elicits these through Socratic dialogue, using a background brief from the Consultant Agent as seed questions.

- [ ] **Step 4: Add a "Rigor" subsection**

After the `### feedback_log` subsection (ends around line 134) and before `## Contract Lifecycle`, insert:

```markdown
### rigor

The `rigor` field controls how thoroughly downstream phases execute. It is inferred by the contract skill based on feature size, external documentation availability, and user input; the user can override at any point.

| Level | When it applies | Downstream effects |
|---|---|---|
| `light` | Small features (<200 LOC code footprint), no external PRD, exploratory work | Contract dialogue compressed to ~3 seed questions; evaluator loops capped at 1 iteration; evaluator only surfaces high-severity issues; code and synthesize phases may be merged in future plans |
| `standard` | Default | Current behavior — evaluator max 3 iterations, full phase sequence, all severity levels reported |
| `strict` | High-stakes features with rich external context (PRD, historical bad cases, compliance requirements) | Extended dialogue until convergence; evaluator iteration cap raised to 5; all phases run independently; no shortcuts |

The contract skill writes the inferred level into `rigor` and explains it to the user for confirmation. Phase skills that honor `rigor` will be updated in a follow-up plan (P1).
```

- [ ] **Step 5: Update the Lifecycle "Creation" steps**

Find `### Creation` (around line 138-146). Replace the numbered steps:

```markdown
1. Agent analyzes code and presents initial findings
2. Agent asks: "What requirements exist beyond what the code shows?"
3. User provides additional context (multilingual support, safety rules, etc.)
4. Agent drafts contract, user reviews and confirms
5. Contract is saved; all subsequent phases reference it
```

with:

```markdown
1. The `/vibeval` command delegates to the `contract` skill (see `plugin/skills/contract/SKILL.md`).
2. The skill dispatches the `vibeval-consultant` agent as a background researcher; the researcher writes a brief to `tests/vibeval/{feature}/_research.md`.
3. The skill presents a brief anchor of findings to the user and runs a Socratic dialogue (one question per turn), using the researcher's seed questions and adapting based on user answers.
4. The skill drafts `contract.yaml` with per-requirement `source` attribution and infers a `rigor` level.
5. User approves; contract is saved; `_research.md` is deleted; all subsequent phases reference the contract.
```

- [ ] **Step 6: Verify**

Read the file end-to-end. Check:
- YAML example parses mentally as valid YAML (no duplicated keys, proper indentation).
- `rigor` field appears in the YAML block before `requirements`.
- `brainstorm` appears in both the comment, the table, and the example.
- No leftover references to "Consultant suggests to user" in the lifecycle section.

- [ ] **Step 7: Commit**

```bash
git add plugin/protocol/references/06-contract.md
git commit -m "protocol: add rigor field and brainstorm source to contract schema"
```

---

## Task 2: Rewrite consultant.md as researcher

**Files:**
- Modify: `plugin/agents/consultant.md` (full rewrite)

- [ ] **Step 1: Replace the agent file with the new researcher role**

Replace the entire contents of `plugin/agents/consultant.md` with:

```markdown
---
name: vibeval-consultant
description: >
  Background researcher for the vibeval contract phase. Reads the feature's
  code, prompts, and existing analysis, then writes a structured research
  brief to a file for the main agent to use as seed questions during a
  Socratic dialogue with the user. Does NOT communicate directly with the
  user and does NOT produce user-facing suggestions.
tools: Read, Glob, Grep, Write
model: sonnet
---

You are the vibeval Consultant — a background researcher that prepares the main agent for a contract negotiation dialogue with the user.

## Your Role

You do NOT talk to the user. You do NOT produce a suggestions list for the user to review. You produce a **research brief** — a file the main agent reads before running a Socratic dialogue with the user. Your value comes from digging into code, prompts, and domain knowledge faster and more thoroughly than the main agent can do mid-dialogue.

Think of yourself as a research assistant preparing briefing notes for someone about to interview a domain expert. Your notes should list questions to ask, background facts to anchor the conversation, and pitfalls to probe — NOT conclusions or recommendations.

## Your Expertise

You have deep knowledge of common AI application failure modes. Draw on this knowledge when identifying likely failure points and when drafting seed questions.

### LLM Output Failures
- **Hallucination**: fabricating facts, citations, or data that don't exist in the input
- **Format degradation**: output starts structured but degrades over long responses (JSON breaks, markdown nests incorrectly)
- **Instruction leakage**: system prompt content bleeding into user-visible output
- **Refusal drift**: over-refusing safe requests, or under-refusing unsafe ones
- **Verbosity creep**: ignoring length constraints, especially in multi-turn conversations

### Input Handling Failures
- **Language mixing**: user writes in one language with technical terms in another
- **Adversarial inputs**: prompt injection, jailbreak attempts, delimiter manipulation
- **Boundary lengths**: extremely short inputs (single word), extremely long inputs (exceeding context)
- **Ambiguous intent**: requests that could be interpreted multiple ways
- **Typos and noise**: misspellings, OCR artifacts, informal abbreviations

### Multi-Turn Failures
- **Context forgetting**: losing information from earlier turns as conversation grows
- **Contradiction handling**: user contradicts themselves across turns
- **Topic drift**: conversation gradually shifts topic, bot loses track of original intent
- **State accumulation bugs**: conversation state grows incorrectly over many turns
- **Recovery from errors**: bot makes a mistake in turn N, can it recover in turn N+1?

### Integration Failures
- **Tool call errors**: calling the wrong tool, passing wrong arguments, misinterpreting results
- **Data pipeline issues**: upstream data missing fields, unexpected types, null values
- **Rate limiting / timeout**: external API calls failing under load
- **Partial failures**: one step in a multi-step pipeline fails, how does the system degrade?

### Domain-Specific Patterns
- **Numerical reasoning**: math errors, unit conversions, date calculations
- **Temporal reasoning**: confusing "today" vs "yesterday", timezone issues
- **Entity confusion**: mixing up names, confusing similar entities
- **Negation handling**: "do NOT include X" being ignored
- **Conditional logic**: "if A then do B, otherwise do C" being simplified to always doing B

## Inputs

You receive:
1. **Feature name** and the feature's working directory
2. **Paths to relevant code**: prompts, AI call entry points, tool definitions, existing analysis (if available)
3. **User's initial description** (if any — often just the feature name)
4. **Existing contract** (if updating; usually absent for fresh negotiations)
5. **Target output path** for your brief (typically `tests/vibeval/{feature}/_research.md`)

## Output Format

Write your brief directly to the target output path as a single markdown file. Use this exact structure:

    # Research Brief: {feature}

    _Generated by vibeval-consultant as background for the contract skill. This file is temporary and will be deleted after the contract is saved._

    ## Identified AI Call Points

    For each AI call point found in the code:

    - `module.path:function_name` — <one-line purpose>
      - **Prompt shape**: <what the prompt asks for, 1-2 sentences>
      - **Likely failure modes**: <2-3 concrete failures specific to THIS prompt, not generic>

    ## Hidden Contract (from prompts)

    Requirements the prompts imply but the code doesn't enforce:

    - <requirement in plain language> — evidence: `<quote from prompt, file:line>`

    If no hidden contract found, write "None identified" and move on.

    ## Seed Questions

    Ordered by priority. The main agent will use these as the backbone of the dialogue, but should adapt based on user answers and skip questions that become redundant.

    ### High Priority
    1. **<question>** — why it matters: <one sentence>
    2. ...

    ### Medium Priority
    1. **<question>** — why it matters: <one sentence>
    2. ...

    ## Same-Domain Failure Patterns (reference)

    Common failures seen in similar features. The main agent should surface these only if the dialogue naturally touches them — do NOT use as scripted questions.

    - **<pattern name>**: <brief explanation tied to this feature>

    ## Notes for the Main Agent

    - <any nuance the main agent should keep in mind during dialogue>
    - <any areas where the main agent should probe deeper than the default seed questions>
    - <any prompts or code that the main agent should re-read before the dialogue>

## Behavior Rules

1. **Be specific to THIS feature** — generic testing advice is useless. Every item in every section must reference concrete code, prompts, or domain context for this specific feature.
2. **Seed questions must be answerable by a non-expert user** — avoid "is the system safe?" Ask "does the bot need to refuse requests involving X?" or "what does a bad response look like to you?" Frame around user experience, not implementation details.
3. **5-10 seed questions is the target** — quality over quantity. The main agent will generate follow-ups during the dialogue, so exhaustiveness is wasted effort.
4. **Probe the prompt, not just the code** — prompt text reveals intentions that control flow does not. Quote specific lines when surfacing a hidden contract.
5. **Your brief is throwaway** — it will be deleted after the contract is saved. Don't make it user-presentable. Optimize for main-agent consumption.
6. **Silent on failure modes you can't justify** — if you can't explain why a failure mode matters for THIS feature, don't mention it. No boilerplate.
```

- [ ] **Step 2: Verify**

Re-read the file. Check:
- Frontmatter includes `Write` in the `tools:` list (new capability — needed because the agent now writes a file).
- No remaining references to "propose to user" or "user confirms" in the behavior rules.
- The output format section is a single markdown template, not YAML.

- [ ] **Step 3: Commit**

```bash
git add plugin/agents/consultant.md
git commit -m "agents: repurpose consultant as background researcher for contract skill"
```

---

## Task 3: Create the contract skill

**Files:**
- Create: `plugin/skills/contract/SKILL.md`

- [ ] **Step 1: Create the directory and skill file**

```bash
mkdir -p plugin/skills/contract
```

Write `plugin/skills/contract/SKILL.md` with the following content:

```markdown
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
- The rigor minimum for the inferred level (Phase E) has been met AND the user seems uninterested in further questions.

**Rigor-aware minimums** (enforce to prevent premature stopping):
- `light`: at least 3 questions answered AND one summary round completed.
- `standard`: at least 5 questions answered AND two summary rounds completed.
- `strict`: no minimum — continue until genuine convergence.

If you don't yet know the rigor level (Phase E runs at the end), assume `standard` minimums during the dialogue.

### Phase D: Draft and Approve

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

4. **Show the draft to the user**:

   > Here's the contract I've drafted based on our discussion. Let me know if anything is wrong, missing, or should be emphasized differently.
   >
   > [paste the full YAML]

5. **If the user has edits**, apply them, show the updated draft, and ask again. Loop until the user confirms.

6. **When the user confirms**:
   - Save to `tests/vibeval/{feature}/contract.yaml`.
   - Delete `tests/vibeval/{feature}/_research.md`.

### Phase E: Rigor Inference

If the user has not explicitly set a rigor level, infer it now:

1. **Check code footprint**: count LOC of files referenced by `analysis/analysis.yaml` if it exists, or estimate from the feature's source directory. Threshold: <200 LOC → lean toward `light`; ≥200 LOC → lean toward `standard`.

2. **Check external context**: during the dialogue, did the user mention a PRD, historical bad cases, compliance requirements, or production feedback? If yes → lean toward `standard` or `strict` regardless of code size.

3. **Combine**:
   - `<200 LOC AND no external context` → suggest `light`.
   - `<200 LOC AND external context` → suggest `standard`.
   - `≥200 LOC AND no external context` → suggest `standard`.
   - `≥200 LOC AND rich external context AND user expressed high stakes` → suggest `strict`.

4. **Confirm with user**:

   > Based on the feature size (~<N> LOC) and our discussion, I'd suggest running vibeval at rigor = `<level>`. This means:
   > - <one-line description of what that entails downstream>
   >
   > Sound right, or do you want to override?

5. Record `rigor` in `contract.yaml` and re-save.

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
   - New requirements go in with `source: brainstorm` (or `user` if unprompted).
   - Updated quality criteria or user emphasis update the relevant fields.
   - Bump `updated:` to today's date.
   - Append an entry to `feedback_log` recording this update round.
5. Save. Skip Phase E (rigor) unless the user explicitly wants to revisit it.
```

- [ ] **Step 2: Verify**

Read the file end-to-end. Check:
- Frontmatter has `name: contract` and a descriptive `description`.
- All five phases (A-E) are present.
- Red Flags table is present.
- "One question per turn" rule is explicit in Phase C.
- Rigor inference logic in Phase E matches the decision table in 06-contract.md.

- [ ] **Step 3: Commit**

```bash
git add plugin/skills/contract/SKILL.md
git commit -m "skills: add contract skill for dialogue-driven contract negotiation"
```

---

## Task 4: Update `/vibeval` command to delegate to the contract skill

**Files:**
- Modify: `plugin/commands/vibeval.md`

- [ ] **Step 1: Replace Step 1 contents**

Find the section between `## Step 1: Negotiate Contract` and `## Step 2: Phase Execution with Evaluator Loop` (currently lines 67-113). Replace everything in between (keeping both headings) with:

```markdown
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

```

- [ ] **Step 2: Update the Consultant integration section**

Find the `### Consultant integration` subsection inside Step 2 (currently lines 154-162). Replace its contents with:

```markdown
### Consultant integration

The `vibeval-consultant` agent's role is **background researcher**, not user-facing advisor. It writes a `_research.md` brief for the main agent; the main agent uses it to seed dialogue or coverage checks with the user.

It is invoked at two points:

1. **Step 1 (Contract Negotiation)** — via the `contract` skill, as Phase A (Research). The main agent runs a Socratic dialogue using the brief as seed questions.

2. **Design phase** — after the initial design is produced, the `vibeval-consultant` is dispatched with the current design as context. It writes a coverage-focused brief. The main agent reads the brief and surfaces any high-priority coverage gaps to the user as targeted questions (not as a suggestions list). See `${CLAUDE_PLUGIN_ROOT}/skills/design/SKILL.md` for details.

The Consultant never communicates directly with the user. The main agent owns the dialogue.
```

- [ ] **Step 3: Verify**

Re-read the Step 1 section and the Consultant integration section. Check:
- Step 1 no longer contains the old "elicit requirements → delegate to Consultant → draft → present → save" flow.
- Step 1 points to the contract skill file path.
- The Consultant integration section no longer mentions "suggestions with severity ratings" or "user can accept all, accept some, or skip entirely" — those were the old advisor-style phrasing.
- No dangling references to `source: suggested` in this file.

- [ ] **Step 4: Commit**

```bash
git add plugin/commands/vibeval.md
git commit -m "commands: delegate vibeval Step 1 to contract skill"
```

---

## Task 5: Update design skill to consume the Consultant brief

**Files:**
- Modify: `plugin/skills/design/SKILL.md`

- [ ] **Step 1: Rewrite the "Consultant Design Review" section**

Find the `## Consultant Design Review (default)` section (currently lines 36-44). Replace with:

```markdown
## Consultant Design Review (default)

After producing the initial design, dispatch the `vibeval-consultant` agent to produce a **coverage-focused research brief**. This is a **default step**, not optional — the Consultant's value is highest at this stage because it catches coverage gaps before code and data generation invest effort in the wrong direction.

Dispatch context:
- Feature name and contract path
- Current `design.yaml` (draft)
- Target output path: `tests/vibeval/{feature}/_design_research.md`

The Consultant reads the design and the feature context, then writes a brief containing:
- Coverage gaps — requirements or failure modes not addressed by any dataset/judge spec
- Missing test dimensions — e.g., adversarial inputs, mock environment failures, multi-turn state issues
- Seed questions the main agent should ask the user to decide whether each gap matters

**Main agent behavior after receiving the brief:**

1. Read `_design_research.md`.
2. For each high-priority gap, ask the user a targeted question (one at a time, not a list):
   > "The design doesn't currently cover <X>. Is that intentional, or should I add a dataset/spec for it?"
3. For each gap the user confirms is important:
   - If it implies a new requirement, add it to the contract with `source: brainstorm`.
   - Add corresponding items to the relevant dataset or create a new dataset.
4. Delete `_design_research.md` when done.

The Consultant never talks to the user directly. The main agent owns the dialogue.

The user can skip this step by explicitly requesting it, but it runs by default.
```

- [ ] **Step 2: Verify**

Re-read the design skill. Check:
- No remaining references to Consultant "suggesting scenarios" as a YAML list to the user.
- The main agent is explicitly responsible for turning the brief into dialogue questions.
- `source: brainstorm` is used (not `source: suggested`).

- [ ] **Step 3: Commit**

```bash
git add plugin/skills/design/SKILL.md
git commit -m "skills: update design skill to consume consultant brief instead of suggestions"
```

---

## Task 6: Smoke test the rewritten flow

**Files:**
- No modifications. This is a dry-run validation task.

- [ ] **Step 1: Pick a test feature**

Choose an existing feature under `tests/vibeval/` that has a `contract.yaml`. If none exists, pick any small AI feature from the project codebase.

Record the feature name as `<smoke-feature>`.

- [ ] **Step 2: Dry-run the contract skill mentally**

Walk through `plugin/skills/contract/SKILL.md` end-to-end with `<smoke-feature>` in mind. For each phase, write down in a scratch note:

- **Phase A**: What would you pass to the Consultant? Can you identify the AI call sites from `Grep`?
- **Phase B**: Draft the anchor message (5-8 sentences). Does it read naturally?
- **Phase C**: Draft the first 3 seed questions the Consultant would likely return. Are they specific to this feature, or generic?
- **Phase D**: If the user gave minimal answers, what `source` values would the drafted requirements have? Are any requirements forced into `brainstorm` when they should be `code`?
- **Phase E**: What `rigor` would you infer? Does the reasoning align with the table?

- [ ] **Step 3: Check the reference chain**

Run these greps to confirm no broken references:

```bash
grep -rn "source: suggested" plugin/
grep -rn "source: brainstorm" plugin/
grep -rn "contract skill" plugin/
grep -rn "_research.md" plugin/
```

Expected:
- `source: suggested` should appear ONLY in `06-contract.md` (as DEPRECATED note) and nowhere else in `plugin/commands/` or `plugin/skills/` or `plugin/agents/`.
- `source: brainstorm` should appear in `06-contract.md`, `plugin/skills/contract/SKILL.md`, `plugin/commands/vibeval.md`, and `plugin/skills/design/SKILL.md`.
- `contract skill` should appear in `plugin/commands/vibeval.md`.
- `_research.md` should appear in `plugin/agents/consultant.md` and `plugin/skills/contract/SKILL.md`.

If any of the above is wrong, fix the referencing file and re-run the greps.

- [ ] **Step 4: Check protocol consistency**

```bash
grep -n "rigor" plugin/protocol/references/06-contract.md
```

Expected: at least 3 matches (YAML field, field definition subsection, lifecycle section).

- [ ] **Step 5: Report**

Write a short report (~10 lines) in the conversation summarizing:
- Smoke feature name
- Any issues found in the dry-run
- Whether all reference-chain greps passed
- Any ambiguities in the contract skill phases that need clarification

If issues were found, fix them before calling this task done.

- [ ] **Step 6: Commit the plan itself (if not already committed)**

```bash
git add docs/plans/2026-04-10-contract-phase-rewrite.md
git commit -m "docs: add contract phase rewrite plan"
```

---

## Self-Review Checklist

Run this review yourself after the plan is written (not as a separate task):

**1. Spec coverage:** Does every piece of the P0 agreement from the design discussion appear as a task?
- [ ] A1 (Consultant repurposed as researcher) → Task 2
- [ ] A2 (contract skill with brainstorming) → Task 3
- [ ] Protocol schema updates (rigor + brainstorm source) → Task 1
- [ ] vibeval.md Step 1 delegation → Task 4
- [ ] Design skill not broken by the Consultant rewrite → Task 5
- [ ] Smoke test before declaring done → Task 6

**2. Placeholder scan:** Searched the plan for "TBD", "TODO", "implement later", "similar to above", "handle edge cases" — none present except inside quoted examples that illustrate bad requirement phrasing.

**3. Type consistency:** `brainstorm` is spelled the same way everywhere. `vibeval-consultant` (with hyphen) matches existing frontmatter `name`. `_research.md` filename is consistent across consultant.md and contract SKILL.md. Skill name is `contract`, directory is `plugin/skills/contract/`.

**4. Execution ordering:** Can these tasks be done in order without referencing not-yet-created files?
- Task 1 (schema) is pure additive — no dependencies.
- Task 2 (consultant rewrite) depends only on Task 1 for the `brainstorm` vocabulary.
- Task 3 (contract skill) references the new consultant behavior — must come after Task 2.
- Task 4 (vibeval.md) references the contract skill — must come after Task 3.
- Task 5 (design skill) references the new consultant behavior — must come after Task 2 (can be parallel with Task 3/4).
- Task 6 (smoke test) requires everything to be in place.

Ordering is OK as listed: 1 → 2 → 3 → 4 → 5 → 6, or 1 → 2 → (3 ∥ 5) → 4 → 6.

---

## Follow-up Plans (not in this doc)

After this plan lands, produce these in order:

1. **`2026-04-XX-red-flags-and-verification-gates.md`** (P1) — Adds Red Flags tables to `code`, `synthesize`, `run`, `design` skills. Adds hard verification-before-completion gates requiring `vibeval validate` output to be pasted before a phase is declared complete. Corresponds to B1 + B2 of the design.

2. **`2026-04-XX-rigor-level-enforcement.md`** (P1) — Makes Evaluator and phase skills honor `contract.rigor`: iteration caps, severity filtering, loop compression. Corresponds to C1.

3. **`2026-04-XX-diagnosing-eval-failure.md`** (P2) — New process skill under `plugin/skills/process/` (or flat if subdir causes issues) for structured failure triage in the Run phase. Corresponds to C2.

4. **`2026-04-XX-dataset-quality-gates.md`** (P2 + P3) — Zero-placeholder enforcement in Design, multi-run statistical confidence (`vibeval run --n 3`), variance flagging. Corresponds to B3 + C3.

---

## Execution Handoff

Plan complete. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration. Use `superpowers:subagent-driven-development`.

**2. Inline Execution** — Execute tasks in this session with checkpoints. Use `superpowers:executing-plans`.

Which approach?
