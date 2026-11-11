# Changelog

## 0.2.0 (2026-11-11)

Renamed from `rag-corpus-contracts` to **corpusgate**. The CLI command is now
`corpusgate` (was `rcc`) and the Python package is `corpusgate` (was `rcc`).

- New project identity: `corpusgate`, owned by Praveen RVS
- GitHub Action moved to `rvspraveen/corpusgate`
- Contract format is unchanged: the `rag:` and `wimsey:` sections still work as before
- Fixed a crash on Windows terminals that cannot encode `≤` in the console report

## 0.1.0 (2026-11-11)

First release.

- `rcc check` with console, Markdown and JSON reports; exit codes 0/1/2
- 8 RAG checks: `required_fields`, `unique_ids`, `chunk_length`, `duplicate_text`, `acl_required`, `embedding_dim`, `pii_patterns`, `source_metadata`
- Per-check `severity` (`error` / `warn`) and `max_violations` budgets
- Pass-through for any native wimsey test
- `rcc suggest` drafts a starter contract from a sample corpus
- Composite GitHub Action that writes the report to the job summary
- Synthetic sample corpora with a generator script
