---
name: update
description: Incrementally update vibeval test artifacts after code changes — preserves existing tests, adds/modifies only what's necessary. Use when entering the update phase of the /vibeval workflow.
---

# vibeval Update Phase

**Scope: AI capability evaluation only.** When updating test artifacts, focus on changes that affect AI behavior (prompt changes, model switches, AI pipeline restructuring). Changes to deterministic logic (routing, validation, formatting) do not require vibeval test updates.

Detect code changes and incrementally update test artifacts. This phase preserves existing tests and adds/modifies only what's necessary.

## Prerequisites

Existing vibeval test artifacts must be present:
- `tests/vibeval/{feature}/contract.yaml`
- `tests/vibeval/{feature}/analysis/`
- `tests/vibeval/{feature}/design/`
- `tests/vibeval/{feature}/datasets/` with at least one dataset
- `tests/vibeval/{feature}/tests/`

If these do not exist, the `/vibeval` command should route to the full workflow instead.

**Before starting, read:**
- `tests/vibeval/{feature}/contract.yaml` — The negotiated contract. Updates must maintain coverage of all requirements.

## Output Language

Read `contract.yaml:output_language` (defaults to `English` if absent). Apply the same rule the originating phase uses: narrative output (descriptions, findings, suggestions, summaries) goes in `output_language`; code, identifiers, paths, and language-locked test payloads stay unchanged. When updating each artifact, follow that artifact's source skill (analyze / design / synthesize / code) for the precise scope.

## Steps

### 1. Detect Changes

Determine what changed:

**If a specific scope was provided (file path):** analyze only that file.

**If scope is "all":** re-analyze the full codebase.

**If no scope:** use git to find changes:
```
git diff --name-only HEAD
git diff --name-only --staged
```

Filter to files relevant to vibeval (files containing AI call points from `analysis/analysis.yaml`).

### 2. Assess Impact

For each changed file, determine impact on existing tests:

**AI call signature changed** (parameters, return type):
- Update mock wrappers in test code
- Update trace capture extractors
- Flag for review

**New AI call added:**
- Add to `analysis/`
- Design new test cases in `design/`
- Generate new dataset items and test code

**AI call removed:**
- Mark as removed in `analysis/`
- Warn about orphaned tests/datasets

**Prompt or context logic changed:**
- Re-evaluate if synthetic data is still valid
- Check if judge specs still align with expected behavior
- May need new calibration examples

**Data flow changed** (new fields, removed fields, reordering):
- Update trace capture points
- Update `no_lost_keys` and `no_overwritten_keys` rule args
- Update `contains_all` expected values if schema changed

### 3. Update Artifacts

Update in place — add new, modify changed, preserve unchanged:

**Update `tests/vibeval/{feature}/analysis/`:**
- Add new AI calls and dependencies
- Update changed function signatures and mock targets
- Remove deleted entries
- Re-run testability suggestions for changed code

**Update `tests/vibeval/{feature}/design/`:**
- Add new test cases for new AI calls
- Update mock responses if call signatures changed
- Add new judge specs for new behaviors
- Keep existing specs unless explicitly obsoleted

**Update datasets:**
- Add new data items for new test scenarios
- Update existing items if expected values changed
- Do NOT delete existing items unless explicitly requested

**Update test code:**
- Update mock wrapper functions for changed signatures
- Add new test functions for new pipelines
- Update trace capture to match new data flow
- Preserve existing test structure

### 4. Generate Change Summary

Compare before/after state and report:

```
vibeval Update Summary
==================
Files analyzed: N changed files

Analysis updates:
  + 1 new AI call: module.new_function
  ~ 1 modified: module.existing_function (signature changed)
  - 0 removed

Dataset updates:
  + 2 new data items in dataset_name
  ~ 1 updated manifest (new judge spec)

Test code updates:
  ~ 1 mock wrapper updated (new parameter)
  + 1 new test function

Action needed:
  - Review updated mock responses for module.existing_function
  - New calibration examples needed for new judge spec
```

## Checkpoint

Present the change summary, then ask: **"Update complete. Would you like to run the tests to verify?"**

If yes, proceed to the run phase.
