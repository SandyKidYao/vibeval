---
name: code
description: Generate vibeval test code infrastructure from design — produces runnable test framework with zero vibeval dependency. Use when entering the code phase of the /vibeval workflow.
---

# vibeval Code Phase

**Scope: Test code infrastructure only.** This phase generates the test framework code that will run against data items produced by the synthesize phase. It does NOT generate synthetic data — that is handled separately by the synthesize phase with parallel Data Synthesizer agents.

Read `tests/vibeval/{feature}/design/` and generate test code artifacts.

**Before starting, read:**
- `tests/vibeval/{feature}/contract.yaml` — The negotiated contract.
- `tests/vibeval/{feature}/design/design.yaml` — The test design specifying datasets, judge specs, mock targets, and test structure.
- `${CLAUDE_PLUGIN_ROOT}/protocol/references/04-result.md` — Result and trace format (the test code must produce conforming files).

## Output Language

Read `contract.yaml:output_language` (defaults to `English` if absent). Generated test code itself — function names, variable names, file names, and inline comments — stays in English regardless, because it must remain editable by anyone on the team and because Python/TypeScript/Go convention is English. Only the Checkpoint summary you present to the user, and any human-readable explanation you produce while walking through the generated code, should be written in `output_language`. See `${CLAUDE_PLUGIN_ROOT}/protocol/references/06-contract.md`.

## Steps

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

### 3. Generate Test Code

Generate test files in `tests/vibeval/{feature}/tests/` using the user's test framework.

**IMPORTANT constraints:**
- Do NOT import from `vibeval` package — zero Python dependency on vibeval
- Use ONLY the user's test framework for mocking
- All helpers (result collector, dataset loader) are generated inline using standard library only
- For multi-turn user simulation, shell out to `vibeval simulate` CLI

#### 3a. Generate VibevalResultCollector (inline helper)

Generate a `VibevalResultCollector` class in conftest/setup using only standard library (json, time, pathlib, subprocess). It must produce result files conforming to the trace protocol defined in `${CLAUDE_PLUGIN_ROOT}/protocol/references/04-result.md`.

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

#### 3b. Generate Mock Infrastructure That Reads from _mock_context

**Critical:** Mock responses must be loaded from `_mock_context` in each data item, NOT hardcoded in the test code. This is the key architectural decision that separates test code (infrastructure) from test data (datasets).

Generate a helper that:
1. Reads the data item's `_mock_context` field
2. For each mock target, creates a mock function that returns responses from the `responses` list in order
3. Applies these mocks using the test framework's mock mechanism

Example pattern (Python/pytest):

```python
def apply_mock_context(item_data, collector, mocker):
    """Apply _mock_context from a data item as mocks, with trace capture."""
    mock_context = item_data.get("_mock_context", {})
    applied_mocks = {}

    for target, config in mock_context.items():
        responses = iter(config["responses"])

        def make_side_effect(target_name, resp_iter):
            def side_effect(*args, **kwargs):
                collector.step("tool_call", {"name": target_name, "args": str(args)[:200]})
                response = next(resp_iter)
                collector.step("tool_result", {"name": target_name, "result": str(response)[:200]})
                return response
            return side_effect

        mock = mocker.patch(target, side_effect=make_side_effect(target, responses))
        applied_mocks[target] = mock

    return applied_mocks
```

#### 3c. Generate Single-Turn Tests

For single-turn pipelines, generate a test function that:
1. Receives data item from parameterized fixture
2. Creates collector, calls `begin_turn` with input
3. Calls `apply_mock_context` to set up all mocks from the data item's `_mock_context`
4. Calls pipeline entry function
5. Calls `end_turn` with output, sets `collector.outputs`, saves

Example structure (Python/pytest):

```python
def test_summarize(meeting_item):
    item_id, item_data = meeting_item
    collector = VibevalResultCollector("test_summarize", "meetings", item_id, item_data)

    collector.begin_turn({"content": f"Summarize meeting {item_data['meeting_id']}"})

    # Mocks come from data item, not hardcoded
    applied = apply_mock_context(item_data, collector, mocker)

    result = summarize(item_data["meeting_id"])

    collector.end_turn({"content": result["summary"]})
    collector.outputs = {"summary": result["summary"]}
    collector.save(run_id="latest")
```

#### 3d. Generate Multi-Turn Tests

For multi-turn pipelines, generate a test function that:
1. Receives persona from parameterized fixture
2. Sets up the bot with any necessary state
3. Runs a for loop: send user message -> bot responds -> capture turn -> get next user message
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

#### 3e. Generate Internal Step Capture (optional)

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

### 4. Verify Protocol Compliance

Before finalizing, verify the generated test code against protocol references:
- Result format: validate against `${CLAUDE_PLUGIN_ROOT}/protocol/references/04-result.md` (trace structure, file naming)
- No imports from `vibeval` package in test code
- Multi-turn tests use `vibeval simulate` CLI (not Python API)
- Mock infrastructure reads from `_mock_context` in data items (no hardcoded mock responses in test code)

### 5. Validate Protocol Compliance via CLI

After generating all test code, run `vibeval validate` to validate all existing artifacts (datasets, results) against the protocol:

```bash
vibeval validate {feature}
```

This validates manifest structure, judge_spec fields, data item format, `_mock_context` structure, trace format, and cross-references. If errors are reported, fix them before proceeding.

## Checkpoint

After code generation, present to the user:

1. Files created:
   - `.vibeval.yml` (if new)
   - `tests/vibeval/{feature}/tests/` — conftest + test files

2. Mock infrastructure summary:
   - Which mock targets are wired up
   - How `_mock_context` is loaded from data items

3. LLM provider: confirm which provider is configured and how to switch if needed

4. Ask: **"Test code generated. Shall I proceed to generate test datasets?"**

Wait for user confirmation before proceeding to the synthesize phase.
