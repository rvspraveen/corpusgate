# Limitations

Please read this before relying on corpusgate as a gate.

- **PII detection is a regex smoke test, not DLP.** The patterns cover common US formats (email, phone, SSN, card-like numbers, IPv4). They miss names, addresses, non-US identifiers and anything that depends on context, and the card and IP patterns will produce false positives. That's why the example contract uses `severity: warn`. Use a dedicated PII/DLP tool for regulated data.
- **Duplicate detection only catches exact matches** after lower-casing and collapsing whitespace. Near-duplicates and paraphrases aren't caught yet (planned: MinHash).
- **Token counts are approximate** (characters ÷ 4). Use `*_chars` bounds if you need exact limits.
- **Everything runs in memory** through polars. Fine for typical corpora; very large corpora should be checked in shards. Benchmarks are not published yet.
- **`corpusgate suggest` produces a draft.** It sets limits from the data you give it, so if that data has problems, the drafted limits will accept them. Review every threshold.
- **Access control is checked for presence, not enforced.** corpusgate confirms each chunk carries a known label. It doesn't check that your retriever filters on that label.
- **Content quality and retrieval quality are out of scope.** A corpus can pass every check and still give wrong answers. Evaluation is the job of a separate eval gate.
- **Depends on wimsey's public API** (`wimsey.test` and its `Result` type), pinned to `>=1.1,<2`.
