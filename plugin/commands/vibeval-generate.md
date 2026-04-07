---
description: Generate vibeval test code and datasets from design
argument-hint: [feature-name]
---

Read the design file for feature `$1` at `tests/vibeval/$1/design/` and generate all vibeval test artifacts.

If `$1` is not provided, list available features under `tests/vibeval/` that have `design.yaml` and ask the user to choose.

## Prerequisites

The design file must exist at `tests/vibeval/$1/design/`. If not found, instruct the user to run `/vibeval-design $1` first.

Read the design file and vibeval protocol references before generating. In particular, read `${CLAUDE_PLUGIN_ROOT}/skills/protocol/references/00-philosophy.md` — the evaluation philosophy governs how synthetic data and judge_specs should be crafted.

## Generation Steps

### 1. Confirm LLM Provider

Before generating, ask the user which LLM provider to use for evaluation (judge and simulate):

> vibeval's evaluation and user simulation require calling an LLM. Which option would you like to use?
> 1. **Default (Claude Code)** — Use the installed Claude Code CLI
> 2. **Custom LLM** — Write a custom script to connect to your own LLM

#### If the user chooses default (Claude Code)

Run `claude -p "hello" --output-format text` to verify Claude Code CLI is installed, authenticated, and working.

- **If successful** (exit code 0 and returns a response): proceed normally. Generate `.vibeval.yml` without `judge.llm` section (defaults to `claude-code`).
- **If command not found**: Claude Code is not installed.
  - Install: `npm install -g @anthropic-ai/claude-code`
  - Docs: https://docs.anthropic.com/en/docs/claude-code
- **If command fails** (non-zero exit code): Claude Code is installed but not properly configured.
  - Not logged in: run `claude login` to authenticate
  - API key issue: check Claude Code settings
  - Network issue: verify internet connection

  In either failure case, inform the user and offer the custom LLM option as an alternative. Do NOT proceed with generation until the user resolves the issue or switches to the custom option.

#### If the user chooses custom LLM

Explain what they need to build:

1. **Write a script** (any language) that:
   - Reads the evaluation prompt from **stdin**
   - Calls their LLM (OpenAI, Ollama, local model, etc.)
   - Writes the LLM response to **stdout**
   - Exits with code 0 on success, non-zero on failure

   Example (Python with OpenAI):
   ```python
   #!/usr/bin/env python3
   import sys
   import openai

   prompt = sys.stdin.read()
   client = openai.OpenAI()  # uses OPENAI_API_KEY env var
   resp = client.chat.completions.create(
       model="gpt-4o",
       messages=[{"role": "user", "content": prompt}],
       temperature=0.0,
   )
   print(resp.choices[0].message.content)
   ```

2. **Configure `.vibeval.yml`** to use it:
   ```yaml
   vibeval_root: tests/vibeval
   judge:
     llm:
       provider: command
       command: "python3 path/to/my_llm.py"
   ```

After the user confirms their choice and the provider is ready, proceed to Step 2.

### 2. Generate .vibeval.yml

If `.vibeval.yml` does not exist at project root, create it.

- If using default Claude Code: only set `vibeval_root`
  ```yaml
  vibeval_root: tests/vibeval
  ```
- If using custom LLM: include the `judge.llm` section with the user's command
  ```yaml
  vibeval_root: tests/vibeval
  judge:
    llm:
      provider: command
      command: "python3 path/to/my_llm.py"
  ```

### 3. Generate Datasets

For each dataset in the design, create:

```
tests/vibeval/{feature}/datasets/{dataset_name}/
├── manifest.yaml
├── {item_id_1}.json
└── {item_id_2}.json
```

**manifest.yaml**: name, description, version, tags, judge_specs from design. For format details, consult `${CLAUDE_PLUGIN_ROOT}/skills/protocol/references/02-dataset.md`.

**Data items**: generate synthetic data applying the information asymmetry principle (see `${CLAUDE_PLUGIN_ROOT}/skills/protocol/references/00-philosophy.md`). Each item should have clear testing intent with deliberate traps that are visible only to the judge, never to the tested AI.

### 4. Generate Test Code

Generate test files in `tests/vibeval/{feature}/tests/` using the user's test framework.

**IMPORTANT constraints:**
- Do NOT import from `vibeval` package — zero Python dependency on vibeval
- Use ONLY the user's test framework for mocking
- All helpers (result collector, dataset loader) are generated inline using standard library only
- For multi-turn user simulation, shell out to `vibeval simulate` CLI

#### 4a. Generate VibevalResultCollector (inline helper)

Generate a `VibevalResultCollector` class in conftest/setup using only standard library (json, time, pathlib, subprocess). It must produce result files conforming to the trace protocol defined in `${CLAUDE_PLUGIN_ROOT}/skills/protocol/references/04-result.md`.

The collector API:

```python
collector = VibevalResultCollector(test_name, dataset, item_id, item_data)

# For each turn:
collector.begin_turn({"content": "user input"})
collector.step("tool_call", {"name": "search", "args": {...}})
collector.step("tool_result", {"name": "search", "result": "..."})
collector.step("llm_call", {"prompt_preview": "..."})
collector.step("llm_output", {"content_preview": "..."})
collector.end_turn({"content": "bot output"})

collector.outputs = {"summary": "...", ...}
collector.save(run_id="latest")
```

This pattern is identical for single-turn (1 turn) and multi-turn (N turns).

#### 4b. Generate Single-Turn Tests

For single-turn pipelines, generate a test function that:
1. Receives data item from parameterized fixture
2. Creates collector, calls `begin_turn` with input
3. Defines tracked mock wrappers that call `collector.step(type, data)` around the mock
4. Applies mocks, calls pipeline entry function
5. Calls `end_turn` with output, sets `collector.outputs`, saves

Example structure (Python/pytest):

```python
def test_summarize(meeting_item):
    item_id, item_data = meeting_item
    collector = VibevalResultCollector("test_summarize", "meetings", item_id, item_data)

    collector.begin_turn({"content": f"Summarize meeting {item_data['meeting_id']}"})

    llm_responses = iter(MOCK_RESPONSES[item_id])
    def tracked_llm(prompt, system=""):
        collector.step("llm_call", {"prompt_preview": prompt[:200]})
        response = next(llm_responses)
        collector.step("llm_output", {"content_preview": response[:200]})
        return response

    with patch("app.llm.chat", side_effect=tracked_llm):
        result = summarize(item_data["meeting_id"])

    collector.end_turn({"content": result["summary"]})
    collector.outputs = {"summary": result["summary"]}
    collector.save(run_id="latest")
```

#### 4c. Generate Multi-Turn Tests

For multi-turn pipelines, generate a test function that:
1. Receives persona from parameterized fixture
2. Sets up the bot with any necessary state
3. Runs a for loop: send user message → bot responds → capture turn → get next user message
4. First round uses `opening_message`, subsequent rounds use `vibeval simulate` CLI
5. Saves the complete result

Example structure (Python/pytest):

```python
import subprocess, json, tempfile

def test_chatbot_safety(persona_item):
    item_id, persona = persona_item
    collector = VibevalResultCollector("test_chatbot", "safety", item_id, persona)

    bot = MyChatBot()
    rounds = persona.get("rounds", 5)
    user_msg = persona["opening_message"]
    history = []

    for i in range(rounds):
        collector.begin_turn({"content": user_msg})

        # Bot responds (wrapper captures internal steps if needed)
        bot_response = bot.chat(user_msg)

        collector.end_turn({"content": bot_response})
        history.append({"user": user_msg, "bot": bot_response})

        # Generate next user message via vibeval simulate
        if i < rounds - 1:
            # Write persona and history to temp files
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as pf:
                json.dump(persona, pf)
                persona_path = pf.name
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as hf:
                json.dump(history, hf)
                history_path = hf.name

            result = subprocess.run(
                ["vibeval", "simulate", "--persona", persona_path, "--history", history_path],
                capture_output=True, text=True,
            )
            user_msg = result.stdout.strip()

    collector.outputs = {
        "conversation": [
            msg for h in history for msg in [
                {"role": "user", "content": h["user"]},
                {"role": "bot", "content": h["bot"]},
            ]
        ],
        "turn_count": rounds,
    }
    collector.save(run_id="latest")
```

**Adapt this pattern to the user's language and framework:**
- TypeScript: use `child_process.execSync("vibeval simulate ...")`
- Go: use `exec.Command("vibeval", "simulate", ...)`
- Any language: shell out to `vibeval simulate`, read stdout

If `use_vibeval_simulate: false` in design, the user handles user simulation themselves — just generate the loop structure without the `vibeval simulate` call.

#### 4d. Generate Internal Step Capture (optional)

If the design specifies `trace_steps` for multi-turn tests, generate bot wrapper functions that capture internal processing steps. The wrapper manages a shared `turn_traces` list:

```python
def make_tracked_bot(bot, collector):
    def tracked(user_msg):
        collector.step("llm_call", {"prompt_preview": "..."})
        response = bot.chat(user_msg)
        collector.step("llm_output", {"content_preview": response[:200]})
        return response
    return tracked
```

This wrapper is called between `begin_turn` and `end_turn`, so steps are automatically associated with the current turn.

### 5. Review Design–Implementation Consistency

After generating all artifacts (datasets + test code), review them together to catch issues that are invisible when looking at the design or implementation in isolation. This step iterates until no new issues are found.

#### 5a. Cross-Validation

For each rule-type judge_spec, trace the `field` reference (e.g. `outputs.content`) into the generated test code and check:

- **Type match**: does the value assigned to that field in the test code match what the rule expects? For example, `length_between` expects a single string, not a concatenation of all turns.
- **Semantic match**: does the value represent what the designer intended? If the design says "single reply length ≤ 200 chars" but the implementation assigns a multi-turn concatenation to `outputs.content`, the rule will evaluate the wrong thing.
- **Multi-turn attention**: for multi-turn tests, pay special attention to how `collector.outputs` fields are assembled — concatenation, last-turn-only, or per-turn list — and verify this matches the judge_spec's assumptions.

#### 5b. Coverage Check

For each judge_spec defined at the **dataset level** (applies to all items):

- Enumerate every item in that dataset.
- For each item, determine whether the spec's expected behavior is correct. For example, a `tool_called: generate_image` spec is wrong for an item whose intent is to reject image requests.
- If a dataset-level spec conflicts with any item's expected behavior, move it to per-item `_judge_specs` with appropriate per-item values, or split into separate specs.

#### 5c. Iterate

If either check above finds issues:

1. Fix the problem — this may involve modifying the design file (`design.yaml`), the generated datasets (manifest, data items), or the generated test code.
2. Re-run both checks (5a and 5b) on the updated artifacts.
3. Repeat until a full pass produces no new issues.

Report all issues found and fixes applied to the user before proceeding.

### 6. Verify Protocol Compliance

Before finalizing, verify all generated artifacts against the protocol references:
- Judge specs: validate against `${CLAUDE_PLUGIN_ROOT}/skills/protocol/references/03-judge-spec.md` (methods, scoring, required fields)
- Result format: validate against `${CLAUDE_PLUGIN_ROOT}/skills/protocol/references/04-result.md` (trace structure, file naming)
- Dataset format: validate against `${CLAUDE_PLUGIN_ROOT}/skills/protocol/references/02-dataset.md` (manifest, data items)
- No imports from `vibeval` package in test code
- Multi-turn tests use `vibeval simulate` CLI (not Python API)

## Output Summary

After generation, inform the user:

1. Files created:
   - `.vibeval.yml` (if new)
   - `tests/vibeval/{feature}/datasets/{name}/` — manifest + N data items
   - `tests/vibeval/{feature}/tests/` — conftest + test files

2. How to run:
   ```bash
   # Run tests to produce result files
   pytest tests/vibeval/{feature}/tests/
   # or: npx vitest tests/vibeval/{feature}/tests/
   # or: go test ./tests/vibeval/{feature}/tests/

   # Evaluate
   vibeval judge {feature} latest

   # View results
   vibeval summary {feature} latest
   ```

3. For multi-turn: ensure `vibeval` CLI is installed and accessible in PATH

4. Mention that design–implementation consistency has been reviewed (Step 5) and list any issues that were found and fixed

5. LLM provider: confirm which provider is configured and how to switch if needed
