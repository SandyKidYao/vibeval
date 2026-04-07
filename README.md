# vibeval — Vibe Coding Eval

A fast evaluation framework for AI applications. Install Claude Code and the vibeval CLI to get an end-to-end workflow from code analysis to test generation to evaluation.

## What Problem Does It Solve

Traditional software testing frameworks cannot assess the quality of AI outputs; traditional AI evaluation platforms rely on dataset construction and cannot keep up with the pace of feature iteration. vibeval strikes a balance between the two:

- Analyze your code via VibeCoding to quickly generate synthetic data and test cases
- Deterministic rules + LLM semantic judgment for dual-layer evaluation
- Cross-version comparison to track quality changes over time
- Language-agnostic: generated test code adapts to your project's framework without depending on the vibeval package

## Prerequisites

- [Claude Code](https://claude.ai/code)
- Python 3.10+

## Installation

```bash
# Install the vibeval CLI
pip install vibeval

# Install the Claude Code plugin (run this inside Claude Code)
/install-plugin https://github.com/SandyKidYao/vibeval
```

## Usage

Before first use, verify that the LLM provider is set up correctly:

```bash
vibeval check
```

Then run everything inside Claude Code without ever leaving the conversation:

```
/vibeval-analyze  →  /vibeval-design  →  /vibeval-generate  →  /vibeval-run
                                                      ↑
                      Code changes → /vibeval-update ──────┘
```

### Analyze Code

```
/vibeval-analyze meeting_summary src/services/
```

Analyze source code to identify AI call sites, data flows, and mock points, and provide suggestions for improving testability.

### Design Tests

```
/vibeval-design meeting_summary
```

Design synthetic data specifications, judging criteria, and test structure. Each step produces editable intermediate files that you can review and modify.

### Generate Code and Data

```
/vibeval-generate meeting_summary
```

Generate a complete test suite (synthetic data + test code) using your project's test framework (pytest/vitest/jest/...).

### Run + Evaluate

```
/vibeval-run meeting_summary
```

All in one step: run tests → evaluate → diagnostic analysis.

### Update After Code Changes

```
/vibeval-update meeting_summary
```

Detect code changes and incrementally update the test suite and data.

### Cross-Version Comparison

```bash
# Statistical comparison
vibeval diff meeting_summary run_a run_b

# LLM deep comparison
vibeval compare meeting_summary run_a run_b
```

### Interactive Dashboard

```bash
vibeval serve --open
```

Launch a web dashboard to browse all features, view test results and traces, visualize trends across runs, and manage datasets and judge specs.

### Other Commands

```bash
# Show evaluation summary
vibeval summary meeting_summary latest

# List features and runs
vibeval features
vibeval runs meeting_summary

# See all commands
vibeval --help
```

## License

MIT
