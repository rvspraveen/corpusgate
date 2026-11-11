from __future__ import annotations

import polars as pl
import pytest

from corpusgate.contract import parse_contract
from corpusgate.runner import run_contract


def _run(rag: list[dict], df: pl.DataFrame):
    return run_contract(parse_contract({"version": 1, "rag": rag}), df)


def _failed(report) -> set[str]:
    return {o.probe for o in report.outcomes if not o.passed}


BASE = pl.DataFrame(
    {
        "chunk_id": ["a", "b", "c"],
        "text": ["alpha chunk text here", "bravo chunk text here", "charlie chunk text"],
        "acl": ["public", "hr", "public"],
        "source": ["a.md", "b.md", "c.md"],
        "embedding": [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]],
    }
)


@pytest.mark.parametrize(
    ("rag", "mutate", "expected"),
    [
        ([{"test": "required_fields", "fields": ["acl"]}], {"acl": ["public", None, "hr"]}, "required_fields:acl"),
        ([{"test": "unique_ids", "column": "chunk_id"}], {"chunk_id": ["a", "a", "c"]}, "unique_ids:chunk_id"),
        ([{"test": "chunk_length", "min_chars": 5, "max_chars": 50}], {"text": ["ok text", "", "fine text"]}, "chunk_length:text"),
        (
            [{"test": "chunk_length", "min_tokens": 1, "max_tokens": 10}],
            {"text": ["x" * 60, "short one", "fine text"]},
            "chunk_length:text",
        ),
        ([{"test": "duplicate_text"}], {"text": ["Same  Text", "same text", "other"]}, "duplicate_text:text"),
        ([{"test": "acl_required"}], {"acl": ["public", " ", "hr"]}, "acl_required:acl:missing"),
        ([{"test": "acl_required", "allowed": ["public", "hr"]}], {"acl": ["public", "secret", "hr"]}, "acl_required:acl:unknown"),
        ([{"test": "embedding_dim", "dim": 2}], {"embedding": [[0.1, 0.2], [0.3], None]}, "embedding_dim:embedding"),
        ([{"test": "pii_patterns", "patterns": ["email"]}], {"text": ["mail jo@example.com", "b", "c"]}, "pii_patterns:text:email"),
        ([{"test": "pii_patterns", "patterns": ["us_ssn"]}], {"text": ["ssn 000-12-3456", "b", "c"]}, "pii_patterns:text:us_ssn"),
        ([{"test": "pii_patterns", "patterns": ["us_phone"]}], {"text": ["call 555-010-1234", "b", "c"]}, "pii_patterns:text:us_phone"),
        ([{"test": "pii_patterns", "custom": {"emp_id": r"EMP-\d{5}"}}], {"text": ["EMP-12345", "b", "c"]}, "pii_patterns:text:emp_id"),
        ([{"test": "source_metadata", "fields": ["source"]}], {"source": ["a.md", None, "c.md"]}, "source_metadata:source"),
    ],
)
def test_each_check_passes_clean_and_fails_dirty(rag, mutate, expected):
    assert _run(rag, BASE).passed, "clean frame should pass"
    dirty = BASE.with_columns(**{k: pl.Series(v) for k, v in mutate.items()})
    report = _run(rag, dirty)
    assert expected in _failed(report)
    assert not report.passed


def test_max_violations_tolerates_budget():
    dirty = BASE.with_columns(acl=pl.Series(["public", None, "hr"]))
    assert _run([{"test": "required_fields", "fields": ["acl"], "max_violations": 1}], dirty).passed


def test_source_metadata_percentage_budget():
    dirty = BASE.with_columns(source=pl.Series(["a.md", None, "c.md"]))
    assert _run([{"test": "source_metadata", "fields": ["source"], "max_null_pct": 50}], dirty).passed


def test_warn_severity_does_not_fail_gate():
    dirty = BASE.with_columns(text=pl.Series(["jo@example.com here", "b text", "c text"]))
    report = _run([{"test": "pii_patterns", "patterns": ["email"], "severity": "warn"}], dirty)
    assert report.passed
    assert [o.probe for o in report.warnings] == ["pii_patterns:text:email"]


def test_missing_column_is_reported_not_crashed():
    report = _run([{"test": "embedding_dim", "dim": 4, "column": "vector"}], BASE)
    assert not report.passed
    assert "missing column" in str(report.errors[0].observed)


def test_sample_corpora_trip_exactly_planted_faults(good_df, bad_df, examples):
    from corpusgate.contract import load_contract

    contract = load_contract(examples / "contract.yaml")
    assert run_contract(contract, good_df).passed
    bad = run_contract(contract, bad_df)
    assert {o.probe for o in bad.errors} == {
        "required_fields:acl",
        "unique_ids:chunk_id",
        "chunk_length:text",
        "duplicate_text:text",
        "acl_required:acl:missing",
        "acl_required:acl:unknown",
        "embedding_dim:embedding",
        "source_metadata:source",
    }
    assert {o.probe for o in bad.warnings} == {"pii_patterns:text:us_ssn"}
