# vibeval Evaluation Philosophy — Principles for Effective LLM Judging

## The Self-Proving Paradox

The fundamental contradiction of LLM-as-Judge: the judging LLM may not be stronger than the AI being judged. A person who only understands elementary math cannot determine whether a calculus result is correct. If the judge and the subject have equal information and equal capability, the judgment may be unreliable.

vibeval does not try to make the judging LLM "smarter" — it solves this problem through two structural advantages: **information asymmetry** and **global perspective**.

## Principle 1: Information Asymmetry — The Test Designer's Advantage

vibeval is both the test designer and the judge. The test designer naturally possesses information that the subject under test does not have:

- **Test intent**: What is this test case designed to evaluate? Where are the traps?
- **Expected behavior**: Given this input, what should a correct system do?
- **Reference answer**: What should the expected output look like (even if it cannot be precisely defined)?
- **Trap design**: Distractors, edge cases, and misleading information deliberately embedded in the data

**Design Principles:**

1. **Every data item must have a clear test rationale**

   Rather than randomly generating input and seeing how the AI responds, design deliberately: What capability does this input test? Where might the AI make mistakes?

   ```yaml
   # Poor design — no clear evaluation focus
   text: "An ordinary meeting transcript"
   
   # Good design — clear traps and evaluation focus
   text: "A meeting transcript containing contradictory time information"
   # Evaluation focus: Can the AI identify the contradiction rather than randomly picking one?
   # Trap: Alice says the deadline is Friday, but Bob later corrects it to next Monday
   ```

2. **anchors and calibrations in judge_specs must contain the test designer's "insider knowledge"**

   Rather than vaguely stating "the output should be accurate," define criteria based on the specific data design:

   ```yaml
   # Poor anchors — the judging LLM has no more information than the AI under test
   anchors:
     "0": "Output is inaccurate"
     "1": "Output is accurate"
   
   # Good anchors — the judging LLM knows what "accurate" means in this specific scenario
   anchors:
     "0": "Adopted Alice's initial Friday deadline, ignored Bob's correction"
     "1": "Correctly identified the final deadline as next Monday (Bob's correction), or explicitly noted the contradiction"
   ```

3. **calibrations must demonstrate the test designer's standards for "good" and "bad"**

   Calibrations are not arbitrary examples; they use the test designer's perspective to tell the judging LLM "in this type of test, what constitutes good performance and what constitutes poor performance":

   ```yaml
   calibrations:
     - output: "The deadline is Friday"
       score: 0
       reason: "Misled by surface information, failed to identify the subsequent correction"
     - output: "The deadline is disputed: Alice proposed Friday, but Bob corrected it to next Monday"
       score: 1
       reason: "Identified the contradiction and provided complete information"
   ```

4. **Test design information is invisible to the subject under test**

   judge_specs, anchors, calibrations, and test intent all reside in the dataset manifest and are never visible to the AI under test. The AI under test only receives the input, while the judging LLM receives input + output + trace + all test design information.

## Principle 2: Global Perspective — Process Review Advantage

The AI under test is constrained by context window limits and attention decay when processing tasks — it forgets earlier information late in long conversations and loses critical context in complex workflows.

vibeval's judging LLM is not subject to these limitations because it receives **structured process records (traces)** after the fact:

- Complete turn sequences with clear input/steps/output structure for each turn
- Independent records for each internal step (LLM calls, tool calls, context changes)
- Ability to review any step individually without processing the entire context at once

**Design Principles:**

5. **Trace collection must cover key decision points**

   Rather than collecting only the final output, capture every step where the AI makes a key decision. The judging LLM can then review these decisions step by step:

   - Was the tool selection correct? Why was this tool chosen over another?
   - Did context assembly miss critical information?
   - Did a deviation occur at some step in multi-step reasoning?

6. **judge_specs should evaluate both results and process**

   Evaluating only the final output is insufficient — an output that "looks correct" may have been reached through a flawed process by chance. Combine process evaluation:

   ```yaml
   judge_specs:
     # Result evaluation
     - method: llm
       scoring: binary
       criteria: "The final output correctly identifies the deadline contradiction"
       anchors: { ... }
       calibrations: [ ... ]
   
     # Process evaluation
     - method: rule
       rule: tool_called
       args: { tool_name: "check_calendar" }
   
     - method: llm
       scoring: binary
       criteria: "During processing, the AI noticed Bob's correction to Alice's statement, rather than only processing the first mentioned date"
       anchors:
         "0": "Trace shows the AI only used Alice's information to construct the response, without referencing Bob's correction"
         "1": "Trace shows the AI referenced Bob's correction during processing"
       calibrations: [ ... ]
   ```

7. **Long conversations/complex workflows should be evaluated in segments**

   For multi-turn conversations or complex workflows, do not expect a single judge_spec to evaluate the entire process. Split into multiple dimensions, each focusing on one aspect of the process:

   ```yaml
   # Segmented evaluation, rather than "give an overall score"
   - criteria: "In the first 3 turns of conversation, did the bot correctly understand the user's core request"
   - criteria: "When the user expressed negative emotions, did the bot avoid being dismissive or negating"
   - criteria: "Was the bot's tool call sequence reasonable"
   ```

## Summary: vibeval's Two Structural Advantages

```
AI under test has only:     vibeval judge has:
  - input                    - input (same)
  - its own capabilities     - output (complete output of the AI under test)
                             - trace (step-by-step process records)
                             - test intent (why this test was designed)
                             - trap design (evaluation focus in the data)
                             - expected behavior (what should be done)
                             - reference answer (ground truth)
                             - anchors (specific criteria for good/bad)
                             - calibrations (scoring calibration)
```

This information asymmetry ensures that the judging LLM always has more context than the AI under test when evaluating specific test scenarios. Not because the judging LLM is smarter, but because it knows more.

All vibeval commands (/vibeval-analyze, /vibeval-design, /vibeval-generate) must follow these two principles when generating test data and evaluation criteria.
