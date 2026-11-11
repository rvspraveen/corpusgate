# corpusgate

[![CI](https://github.com/rvspraveen/corpusgate/actions/workflows/ci.yml/badge.svg)](https://github.com/rvspraveen/corpusgate/actions/workflows/ci.yml)
[![CodeQL](https://github.com/rvspraveen/corpusgate/actions/workflows/codeql.yml/badge.svg)](https://github.com/rvspraveen/corpusgate/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**Data contracts and CI gates for RAG corpora.** Point `corpusgate` at your chunk files and a YAML contract. It catches duplicate IDs, empty chunks, missing access labels, wrong vector sizes, broken citation fields and obvious PII *before* they reach your vector store. It exits non-zero, so the ingest job or pull request stops.

## Run it (60 seconds)

```bash
git clone https://github.com/rvspraveen/corpusgate && cd corpusgate
pip install .
corpusgate check --contract examples/contract.yaml --data examples/bad_chunks.jsonl
```

Real output (the 8 passing rows are trimmed):

```text
┃ Status ┃ Check                         ┃ Observed ┃ Limit ┃ What it means                                                   ┃
│ FAIL   │ required_fields:acl           │ 1        │ ≤ 0   │ null values in required field 'acl'                             │
│ FAIL   │ unique_ids:chunk_id           │ 2        │ ≤ 0   │ rows sharing a duplicate 'chunk_id'                             │
│ FAIL   │ chunk_length:text             │ 1        │ ≤ 0   │ chunks outside [80, 2000] chars                                 │
│ FAIL   │ duplicate_text:text           │ 2        │ ≤ 0   │ rows whose normalised 'text' duplicates another row             │
│ FAIL   │ acl_required:acl:missing      │ 1        │ ≤ 0   │ chunks with no access label in 'acl'                            │
│ FAIL   │ acl_required:acl:unknown      │ 1        │ ≤ 0   │ labels in 'acl' outside ['public', 'internal', 'hr', 'finance'] │
│ FAIL   │ embedding_dim:embedding       │ 1        │ ≤ 0   │ vectors in 'embedding' that are missing or not 16-dimensional   │
│ FAIL   │ source_metadata:source        │ 2.5      │ ≤ 0   │ % of chunks missing citation field 'source' (limit 0%)          │
│ WARN   │ pii_patterns:text:us_ssn      │ 1        │ ≤ 0   │ chunks in 'text' matching the 'us_ssn' pattern                  │
Contract FAILED: 17 checks on 40 rows · 8 error(s) · 1 warning(s)
```

The same command on `examples/good_chunks.jsonl` passes with exit code `0`. Every failure above was planted on purpose by [`examples/make_samples.py`](examples/make_samples.py). All sample data is synthetic.

## Why

Bad chunks rarely crash anything. Retrieval just gets quietly worse: duplicate chunks take up the top-k results, empty chunks waste embedding spend, missing `source` fields break citations, and a chunk with no access label can leak through a permission filter. A contract makes these problems loud, so they can be fixed before the data is indexed.

## Checks

| Check | Catches | Key parameters |
|---|---|---|
| `required_fields` | Null values in required columns | `fields` |
| `unique_ids` | Duplicate chunk IDs | `column` |
| `chunk_length` | Empty, tiny or oversized chunks | `min_chars`/`max_chars` or `min_tokens`/`max_tokens` |
| `duplicate_text` | Exact duplicate text after normalising | `column` |
| `acl_required` | Missing access labels, or labels outside an allowed set | `column`, `allowed` |
| `embedding_dim` | Missing or wrong-size vectors | `column`, `dim` |
| `pii_patterns` | Email, US phone, SSN, card-like numbers, IPv4, or your own regex | `patterns`, `custom` |
| `source_metadata` | Missing citation fields (`source`, `page`, `url`) | `fields`, `max_null_pct` |

Every check also takes `severity: error | warn` (default `error`) and `max_violations` (default `0`). Run `corpusgate list-checks` for the full list of parameters.

## Contracts

```yaml
version: 1
rag:
  - test: unique_ids
    column: chunk_id
  - test: chunk_length
    column: text
    min_chars: 80
    max_chars: 2000
  - test: acl_required
    allowed: [public, internal, hr, finance]
  - test: pii_patterns
    patterns: [email, us_ssn]
    custom: { employee_id: "EMP-\\d{5}" }
    severity: warn
wimsey:            # any native wimsey test, passed through unchanged
  - test: row_count_should
    be_greater_than_or_equal_to: 20
```

Contract typos fail fast with exit code `2` (for example: `unknown parameter(s) ['colum']`), so a misspelled check can't silently pass.

**No contract yet?** Draft one from a corpus you trust, then review it:

```bash
corpusgate suggest --data examples/good_chunks.jsonl > contract.yaml
```

## CLI

```text
corpusgate check   -c CONTRACT -d DATA [-f console|markdown|json] [-o FILE] [--fail-on-warn]
corpusgate suggest -d DATA [--margin 0.2] [-o FILE]
corpusgate list-checks
```

Data formats: `.jsonl`, `.ndjson`, `.parquet`, `.csv`. Exit codes: `0` passed · `1` contract failed · `2` usage or config error.

## GitHub Action

```yaml
- uses: rvspraveen/corpusgate@v0.2.0
  with:
    contract: rag/contract.yaml
    data: rag/chunks.jsonl
    # fail-on-warn: "true"
```

The Markdown report is written to the job summary, and the step fails if any `error` check fails.

## Python API

`corpusgate` is also a library, so you can gate an ingest pipeline in-process:

```python
from corpusgate import load_contract, read_corpus, run_contract

report = run_contract(load_contract("rag/contract.yaml"), read_corpus("rag/chunks.jsonl"))
if report.errors:
    raise SystemExit(f"{len(report.errors)} contract check(s) failed")
```

## How it works

Every check is compiled into a narwhals expression that counts violating rows, and all of them are executed through the [wimsey](https://github.com/benrutter/wimsey) test API, so the same contract can mix RAG-specific checks with native wimsey tests such as `row_count_should` or `null_percentage_should`.

| corpusgate | wimsey (dependency, unmodified) |
|---|---|
| 8 RAG checks, severity and violation budgets, strict contract validation, missing-column handling, `suggest`, console/Markdown/JSON reports, CLI, GitHub Action, sample corpora | Contract engine, dataframe-agnostic evaluation through narwhals, native test library |

## Limitations

PII detection is regex only, duplicate detection only catches exact matches, token counts are approximate, and all checks run in memory. See [LIMITATIONS.md](LIMITATIONS.md) before using this as a gate on regulated data.

## Credits

Uses [wimsey](https://github.com/benrutter/wimsey) by Ben Rutter (MIT) as an unmodified dependency. See [NOTICE](NOTICE).

## License

MIT — Copyright (c) 2026 Praveen RVS. See [LICENSE](LICENSE).
