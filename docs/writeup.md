# corpusgate: data contracts for RAG corpora

*A short write-up on why corpusgate exists and how it is built. Code, quick start and full reference: [README](../README.md) · [github.com/rvspraveen/corpusgate](https://github.com/rvspraveen/corpusgate).*

## The problem: bad chunks fail quietly

Most RAG quality work happens at the model and retrieval layers: prompts, rerankers, eval sets. The corpus itself, the chunk files that get embedded and indexed, usually gets far less scrutiny, even though it's where many problems start.

The issue is that bad chunks rarely crash anything. A duplicated chunk doesn't raise an exception; it just takes up two slots in the top-k results. An empty or tiny chunk still gets embedded, so you pay for a vector that retrieves noise. A chunk with no `source` field still answers questions, but the citation is gone. A chunk with no access label can pass straight through a permission filter that assumes every row has one. Each of these shows up later as "retrieval got worse" or "why did that user see that document?", long after the bad batch was indexed.

Analytics teams solved this kind of problem years ago with data contracts: a declared expectation of what the data must look like, checked automatically before the data moves on. corpusgate applies the same idea to RAG corpora. You write a YAML contract for your chunk files, corpusgate checks every file against it, and a non-zero exit code stops the ingest job or the pull request.

## What it checks

corpusgate ships eight RAG-specific checks, each aimed at a failure mode above:

| Check | Catches |
|---|---|
| `required_fields` | Null values in required columns |
| `unique_ids` | Duplicate chunk IDs |
| `chunk_length` | Empty, tiny or oversized chunks (by characters or approximate tokens) |
| `duplicate_text` | Exact duplicate text after lower-casing and collapsing whitespace |
| `acl_required` | Missing access labels, or labels outside an allowed set |
| `embedding_dim` | Missing or wrong-size vectors |
| `pii_patterns` | Email, US phone, SSN, card-like numbers, IPv4, or your own regex |
| `source_metadata` | Missing citation fields such as `source`, `page` or `url` |

Every check takes a `severity` (`error` or `warn`) and a `max_violations` budget, so a team can start strict on IDs and access labels and lenient on PII heuristics. Input can be `.jsonl`, `.ndjson`, `.parquet` or `.csv`. A column the contract expects but the data lacks shows up as a failed check with a clear message, not a stack trace.

## Design choices

**wimsey as an unmodified dependency, not a fork.** The contract engine is [wimsey](https://github.com/benrutter/wimsey) (MIT), used only through its public `wimsey.test` API and pinned to `>=1.1,<2`. Each corpusgate check compiles into a narwhals expression that counts violating rows, and every check runs through wimsey. Two benefits follow. First, corpusgate stays small: the RAG logic is the original part, and the general evaluation engine is someone else's well-scoped library, credited in [NOTICE](../NOTICE). Second, one contract can mix RAG checks with any native wimsey test, such as `row_count_should`, under a separate `wimsey:` section that is passed through unchanged.

**Exit codes built for CI.** `0` means the contract passed, `1` means it failed, and `2` means a usage or configuration error. Keeping "your data is bad" (1) separate from "your contract is broken" (2) matters in a pipeline: a misconfigured gate shouldn't look like a data failure, and neither should ever look like a pass. `--fail-on-warn` promotes warnings to failures for teams that want a stricter gate.

**Strict YAML contracts.** Contracts are plain YAML so they can be reviewed in a pull request next to the data they guard. Parsing is deliberately unforgiving: unknown checks, unknown parameters, missing required parameters, invalid severities and unknown top-level keys all fail with exit code `2`. A typo like `colum:` can't silently turn a check into a no-op.

**`suggest` to get started.** Writing a first contract by hand is the main barrier to adoption, so `corpusgate suggest` drafts one from a corpus you trust. It guesses the ID, text, ACL, vector and citation columns from common names, sets chunk-length bounds from the 1st and 99th percentiles with a configurable margin (default 20%), takes the allowed ACL labels and the embedding dimension from the observed data, and adds a row-count floor. The output is labelled as a draft that needs review, and it should be reviewed (see Limitations).

**Reports for people and machines.** Results render as a console table, Markdown (for PR comments and job summaries) or JSON (for anything downstream). corpusgate is also a Python library (`load_contract`, `read_corpus`, `run_contract`), so an ingest pipeline can gate in-process instead of shelling out.

## Using it in CI

The repo is a composite GitHub Action:

```yaml
- uses: rvspraveen/corpusgate@v0.2.0
  with:
    contract: rag/contract.yaml
    data: rag/chunks.jsonl
    # fail-on-warn: "true"
```

The action installs corpusgate, runs the contract, writes the Markdown report to the job summary and fails the step if any `error` check fails. The repo's own CI dogfoods it against the bundled synthetic samples: `examples/good_chunks.jsonl` must pass and `examples/bad_chunks.jsonl`, which has deliberately planted defects, must fail. Outside GitHub Actions, the CLI works the same way in any CI system that respects exit codes.

## Limitations

These are spelled out in [LIMITATIONS.md](../LIMITATIONS.md); the short version:

- **PII detection is a regex smoke test, not DLP.** It covers common US formats, misses names, addresses and non-US identifiers, and the card and IP patterns produce false positives. Use a dedicated DLP tool for regulated data.
- **Duplicate detection is exact-match only** after normalisation. Near-duplicates and paraphrases get through.
- **Token counts are approximate** (characters ÷ 4). Use character bounds when limits must be exact.
- **Everything runs in memory** through polars. Very large corpora should be checked in shards, and no benchmarks are published yet.
- **`suggest` learns from the data you give it.** If that sample has problems, the drafted limits will accept them.
- **Access labels are checked for presence, not enforced.** corpusgate confirms each chunk has a known label; it doesn't verify that your retriever filters on it.
- **Content and retrieval quality are out of scope.** A corpus can pass every check and still produce wrong answers. That's the job of an evaluation gate, not a data contract.

## What's next

- **Near-duplicate detection** (MinHash), so paraphrased and lightly edited copies are caught, not only exact matches.
- **Published benchmarks and sharded runs** for large corpora.
- **A PyPI release**, so `pip install corpusgate` works without cloning.
- **Pairing with an eval gate.** corpusgate answers "is this data fit to index?"; the natural companion is a gate that answers "did retrieval and answer quality regress?" Running both in CI covers the data and the behaviour.

---

Back to the [README](../README.md) · [Changelog](../CHANGELOG.md) · [Limitations](../LIMITATIONS.md)
