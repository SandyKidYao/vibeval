# vibeval Project Development Guide

## Project Overview

vibeval (Vibe Coding Eval) is an AI application evaluation framework consisting of two parts:
- **vibeval CLI** (`src/vibeval/`) — Evaluation tools (judge, compare, simulate, diff, report, check, etc.)
- **Claude Code Plugin** (`plugin/`) — VibeCoding workflow (unified `/vibeval` command)

## Core Principles

### 1. Protocol First

The protocol documents under `plugin/protocol/references/` are the project's Source of Truth. All plugin commands, CLI code, and documentation must follow and adhere to the protocol. When any content conflicts with the protocol, the protocol takes precedence. When writing documentation or commands, avoid duplicating definitions already present in the protocol; reference the protocol files instead.

Protocol files:
- `00-philosophy.md` — Evaluation philosophy (information asymmetry + global perspective + contract)
- `01-overview.md` — Directory structure, unified turn model
- `02-dataset.md` — Dataset format
- `03-judge-spec.md` — Judge specification (rule/llm, target, all field definitions)
- `04-result.md` — Result format (trace turns/steps)
- `05-comparison.md` — Comparison format
- `06-contract.md` — Contract format (requirements, known gaps, quality criteria)

### 2. Language Agnostic

All designs must avoid language coupling. vibeval CLI provides generic functionality that can be executed directly from the command line, without requiring code-level dependencies. User test code does not import the vibeval package; instead, it invokes the CLI via subprocess (e.g., `vibeval simulate`) or generates files directly in the protocol format. The CLI serves both developers and VibeCoding Agents.

### 3. CLI Help Is the Single Source of Truth for Command Documentation

Every CLI command must maintain a complete, up-to-date `--help` description (including purpose, parameter descriptions, and usage examples). Plugin command documentation and SKILL.md should not duplicate CLI parameter details; instead, they should direct users to check via `vibeval --help` / `vibeval <command> --help`. This ensures the CLI and documentation never fall out of sync.

### 4. English as Primary Language

All code, documentation, commit messages, comments, and CLI output in this project must be written in English.

## Development Conventions

### Running Tests

```bash
# vibeval's own tests
python -m pytest tests/ -v
```

### Modifying the Protocol

After modifying protocol files, check whether the following need to be updated accordingly:
- Code implementation in `src/vibeval/` (rules.py, llm.py, judge.py, compare.py, result.py)
- Command documentation in `plugin/commands/` (should reference the protocol rather than duplicate content)
- `plugin/protocol/README.md` (Quick Reference summary)
- CLI `--help` descriptions

### Modifying the CLI

When adding or modifying CLI commands:
- Provide complete `help` and `description` text in `cli.py`
- No need to update command details in plugin documentation — plugin documentation should direct users to check `vibeval --help`
- Add corresponding tests to `tests/`

### Version Management

The project version is maintained in three places and must be kept consistent:
- `pyproject.toml` — `version` field
- `plugin/plugin.json` — `version` field
- `src/vibeval/__init__.py` — `__version__` variable

When releasing or changing the version number, update all three places simultaneously.

### Modifying the Plugin

When modifying plugin commands or skills:
- Core concept definitions (data formats, fields, rule names, etc.) must always reference the protocol files in `references/`; do not duplicate them inline
- Operational guidance (how to design, how to generate) can be elaborated in command documentation, but should reference the protocol as the source of definitions
- For CLI command parameters and usage, direct users to check `vibeval --help`

### Project Structure

```
vibeval/
├── src/vibeval/            # CLI tool implementation
│   └── serve/              # Web dashboard (vibeval serve)
│       └── static/         # Frontend assets (HTML, CSS, JS)
├── plugin/                # Claude Code plugin
│   ├── commands/vibeval.md # /vibeval — unified entry point (state detection + contract + routing)
│   ├── agents/             # Subagents
│   │   ├── evaluator.md    # Evaluator (reviews phase outputs against contract)
│   │   └── consultant.md   # Consultant (suggests test scenarios and edge cases)
│   ├── protocol/           # Data protocol references (Source of Truth)
│   └── skills/             # Phase skills (loaded on demand by /vibeval)
│       ├── analyze/        # Codebase analysis
│       ├── design/         # Test plan design
│       ├── generate/       # Code and dataset generation
│       ├── run/            # Test execution and evaluation
│       └── update/         # Incremental updates after code changes
├── tests/                 # vibeval's own tests
├── CLAUDE.md
├── README.md
└── pyproject.toml
```
