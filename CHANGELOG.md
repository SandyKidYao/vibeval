# Changelog

## 0.5.0 (2026-04-09)

### New Features

- **Split generate into code + synthesize phases.** The monolithic generate phase is replaced by two focused phases: `code` (test infrastructure — conftest, collector, mock wiring, fixtures) and `synthesize` (dataset generation via parallel Data Synthesizer agents). This separates engineering work from creative data design, improving data quality.
- **`_mock_context` in dataset protocol.** Data items now support a `_mock_context` field for embedding mock responses from tools, APIs, and databases. Mock data is now first-class test data designed alongside user inputs, not an engineering afterthought hardcoded in test code.
- **`vibeval validate` command.** New CLI command to validate all datasets and results against the protocol format — manifests, judge specs, data items, `_mock_context`, traces, results, and cross-references (`values_from`/`expected_from`).
- **Data Synthesizer agent.** New subagent specialized in generating dataset items with full `_mock_context`. Spawned in parallel by the synthesize phase, one instance per dataset.
- **Consultant design review is now default.** The Consultant agent's design-stage coverage review runs by default after the initial design, catching blind spots before code and data generation.

### Breaking Changes

- The `generate` skill has been removed. `/vibeval` now routes through `code` then `synthesize`. The `generate` action is still accepted for backwards compatibility.
- Mock responses should now live in `_mock_context` within data items, not hardcoded in test code.

### Bug Fixes

- Removed stale `skills: protocol` reference from all agent definitions.
