---
description: Update vibeval tests and datasets after code changes
argument-hint: [scope]
---

Detect code changes and incrementally update vibeval test artifacts. Scope can be a file path, "all", or empty (auto-detect from git diff).

## Prerequisites

Existing vibeval test artifacts must be present:
- `tests/vibeval/{feature}/analysis/`
- `tests/vibeval/{feature}/design/`
- `tests/vibeval/datasets/` with at least one dataset

If these do not exist, instruct the user to run the full workflow: `/vibeval-analyze` → `/vibeval-design` → `/vibeval-generate`.

## Update Steps

### 1. Detect Changes

Determine what changed:

**If scope is a file path:** analyze only that file.

**If scope is "all":** re-analyze the full codebase.

**If scope is empty:** use git to find changes:
```
git diff --name-only HEAD
git diff --name-only --staged
```

Filter to files relevant to vibeval (files containing AI call points from `analysis/`).

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

**Update `tests/vibeval/analysis/`:**
- Add new AI calls and dependencies
- Update changed function signatures and mock targets
- Remove deleted entries
- Re-run evaluability suggestions for changed code

**Update `tests/vibeval/design/`:**
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
  ⚠ Review updated mock responses for module.existing_function
  ⚠ New calibration examples needed for new judge spec
```

## Output

Update files in place:
- `tests/vibeval/analysis/` — updated
- `tests/vibeval/design/` — updated
- `tests/vibeval/datasets/` — items added/updated
- Test code files — updated

Inform the user what changed and what needs manual review.
