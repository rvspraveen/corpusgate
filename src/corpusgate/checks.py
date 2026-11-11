"""RAG-specific checks.

Each check factory turns contract parameters into one or more wimsey
``GeneratedTest`` tuples: ``(narwhals_expression, result_fn)``. That is
wimsey's own public test shape, so the checks run through ``wimsey.test``
on any dataframe backend wimsey supports.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import narwhals.stable.v2 as nw
from wimsey.types import Result

from corpusgate.pii import PII_PATTERNS


@dataclass
class Probe:
    """A single measurable assertion produced by a check."""

    name: str
    expr: Any
    max_violations: float
    description: str
    columns: list[str] = field(default_factory=list)

    def as_wimsey_test(self) -> tuple[Any, Callable[[Any], Result]]:
        limit = self.max_violations
        name = self.name

        def _check(value: Any) -> Result:
            value = 0 if value is None else value
            if isinstance(value, float) and math.isnan(value):
                value = 0
            ok = value <= limit
            return Result(name=name, success=ok, unexpected=None if ok else value)

        return self.expr.alias(name), _check


@dataclass(frozen=True)
class CheckSpec:
    name: str
    summary: str
    required: tuple[str, ...]
    optional: dict[str, Any]
    build: Callable[..., list[Probe]]


def _col(c: str) -> Any:
    return nw.col(c)


def _required_fields(fields: list[str], max_violations: int = 0) -> list[Probe]:
    if not isinstance(fields, list) or not fields:
        raise ValueError("'fields' must be a non-empty list of column names")
    return [
        Probe(
            name=f"required_fields:{f}",
            expr=_col(f).is_null().sum(),
            max_violations=max_violations,
            description=f"null values in required field '{f}'",
            columns=[f],
        )
        for f in fields
    ]


def _unique_ids(column: str, max_violations: int = 0) -> list[Probe]:
    c = _col(column)
    return [
        Probe(
            name=f"unique_ids:{column}",
            expr=(c.is_duplicated() & ~c.is_null()).sum(),
            max_violations=max_violations,
            description=f"rows sharing a duplicate '{column}'",
            columns=[column],
        )
    ]


def _chunk_length(
    column: str = "text",
    min_chars: int | None = None,
    max_chars: int | None = None,
    min_tokens: int | None = None,
    max_tokens: int | None = None,
    max_violations: int = 0,
) -> list[Probe]:
    if min_tokens is not None or max_tokens is not None:
        if min_chars is not None or max_chars is not None:
            raise ValueError("use either *_chars or *_tokens, not both")
        # Approximation: ~4 characters per token for English text.
        length = _col(column).fill_null("").str.len_chars() / 4
        lo, hi, unit = min_tokens, max_tokens, "approx tokens"
    else:
        length = _col(column).fill_null("").str.len_chars()
        lo, hi, unit = min_chars, max_chars, "chars"
    if lo is None and hi is None:
        raise ValueError("set at least one of min/max chars or tokens")
    cond = None
    if lo is not None:
        cond = length < lo
    if hi is not None:
        cond = (length > hi) if cond is None else (cond | (length > hi))
    return [
        Probe(
            name=f"chunk_length:{column}",
            expr=cond.sum(),
            max_violations=max_violations,
            description=f"chunks outside [{lo}, {hi}] {unit}",
            columns=[column],
        )
    ]


def _duplicate_text(column: str = "text", max_violations: int = 0) -> list[Probe]:
    norm = _col(column).fill_null("").str.to_lowercase().str.replace_all(r"\s+", " ").str.strip_chars()
    return [
        Probe(
            name=f"duplicate_text:{column}",
            expr=(norm.is_duplicated() & (norm != "")).sum(),
            max_violations=max_violations,
            description=f"rows whose normalised '{column}' duplicates another row",
            columns=[column],
        )
    ]


def _acl_required(column: str = "acl", allowed: list[str] | None = None, max_violations: int = 0) -> list[Probe]:
    c = _col(column)
    probes = [
        Probe(
            name=f"acl_required:{column}:missing",
            expr=(c.is_null() | (c.cast(nw.String).str.strip_chars() == "")).sum(),
            max_violations=max_violations,
            description=f"chunks with no access label in '{column}'",
            columns=[column],
        )
    ]
    if allowed is not None:
        if not isinstance(allowed, list) or not allowed:
            raise ValueError("'allowed' must be a non-empty list")
        probes.append(
            Probe(
                name=f"acl_required:{column}:unknown",
                expr=(~c.is_in(allowed) & ~c.is_null()).sum(),
                max_violations=max_violations,
                description=f"labels in '{column}' outside {allowed}",
                columns=[column],
            )
        )
    return probes


def _embedding_dim(dim: int, column: str = "embedding", max_violations: int = 0) -> list[Probe]:
    if not isinstance(dim, int) or dim <= 0:
        raise ValueError("'dim' must be a positive integer")
    return [
        Probe(
            name=f"embedding_dim:{column}",
            expr=(_col(column).list.len() != dim).fill_null(value=True).sum(),
            max_violations=max_violations,
            description=f"vectors in '{column}' that are missing or not {dim}-dimensional",
            columns=[column],
        )
    ]


def _pii_patterns(
    column: str = "text",
    patterns: list[str] | None = None,
    custom: dict[str, str] | None = None,
    max_violations: int = 0,
) -> list[Probe]:
    selected = patterns if patterns is not None else list(PII_PATTERNS)
    unknown = [p for p in selected if p not in PII_PATTERNS]
    if unknown:
        raise ValueError(f"unknown PII pattern(s) {unknown}; available: {sorted(PII_PATTERNS)}")
    regexes = {p: PII_PATTERNS[p] for p in selected} | (custom or {})
    return [
        Probe(
            name=f"pii_patterns:{column}:{label}",
            expr=_col(column).fill_null("").str.contains(rx).sum(),
            max_violations=max_violations,
            description=f"chunks in '{column}' matching the '{label}' pattern",
            columns=[column],
        )
        for label, rx in regexes.items()
    ]


def _source_metadata(fields: list[str], max_null_pct: float = 0.0) -> list[Probe]:
    if not isinstance(fields, list) or not fields:
        raise ValueError("'fields' must be a non-empty list of column names")
    return [
        Probe(
            name=f"source_metadata:{f}",
            expr=_col(f).is_null().mean() * 100,
            max_violations=max_null_pct,
            description=f"% of chunks missing citation field '{f}' (limit {max_null_pct}%)",
            columns=[f],
        )
        for f in fields
    ]


CHECKS: dict[str, CheckSpec] = {
    s.name: s
    for s in [
        CheckSpec("required_fields", "Required columns exist and are never null", ("fields",), {"max_violations": 0}, _required_fields),
        CheckSpec("unique_ids", "Chunk IDs are unique", ("column",), {"max_violations": 0}, _unique_ids),
        CheckSpec(
            "chunk_length",
            "Chunks are neither empty, tiny nor oversized",
            (),
            {"column": "text", "min_chars": None, "max_chars": None, "min_tokens": None, "max_tokens": None, "max_violations": 0},
            _chunk_length,
        ),
        CheckSpec(
            "duplicate_text", "No exact duplicate chunk text (normalised)", (), {"column": "text", "max_violations": 0}, _duplicate_text
        ),
        CheckSpec(
            "acl_required",
            "Every chunk carries a known access label",
            (),
            {"column": "acl", "allowed": None, "max_violations": 0},
            _acl_required,
        ),
        CheckSpec(
            "embedding_dim",
            "Vectors exist and share the expected dimension",
            ("dim",),
            {"column": "embedding", "max_violations": 0},
            _embedding_dim,
        ),
        CheckSpec(
            "pii_patterns",
            "Regex smoke test for emails, phones, SSNs, card numbers, IPs",
            (),
            {"column": "text", "patterns": None, "custom": None, "max_violations": 0},
            _pii_patterns,
        ),
        CheckSpec(
            "source_metadata", "Citation fields (source, page, url) are populated", ("fields",), {"max_null_pct": 0.0}, _source_metadata
        ),
    ]
}
