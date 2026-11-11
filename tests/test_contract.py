from __future__ import annotations

import polars as pl
import pytest

from corpusgate.contract import ContractError, load_contract, parse_contract
from corpusgate.runner import run_contract


@pytest.mark.parametrize(
    ("data", "msg"),
    [
        ([], "must be a mapping"),
        ({"version": 2, "rag": [{"test": "unique_ids", "column": "x"}]}, "unsupported contract version"),
        ({"version": 1, "extra": []}, "unknown top-level"),
        ({"version": 1}, "no checks"),
        ({"rag": ["unique_ids"]}, "needs a 'test'"),
        ({"rag": [{"test": "nope"}]}, "unknown check"),
        ({"rag": [{"test": "unique_ids"}]}, "missing required"),
        ({"rag": [{"test": "unique_ids", "column": "x", "colum": "y"}]}, "unknown parameter"),
        ({"rag": [{"test": "unique_ids", "column": "x", "severity": "fatal"}]}, "severity"),
        ({"rag": [{"test": "chunk_length"}]}, "at least one"),
        ({"rag": [{"test": "chunk_length", "min_chars": 1, "max_tokens": 9}]}, "either"),
        ({"rag": [{"test": "embedding_dim", "dim": 0}]}, "positive integer"),
        ({"rag": [{"test": "pii_patterns", "patterns": ["dna"]}]}, "unknown PII"),
        ({"rag": [{"test": "acl_required", "allowed": []}]}, "non-empty"),
        ({"rag": [{"test": "required_fields", "fields": []}]}, "non-empty"),
        ({"rag": [{"test": "source_metadata", "fields": "source"}]}, "non-empty"),
        ({"wimsey": [{"be": 1}]}, "needs a 'test'"),
    ],
)
def test_invalid_contracts_raise_clear_errors(data, msg):
    with pytest.raises(ContractError, match=msg):
        parse_contract(data)


def test_load_contract_file_errors(tmp_path):
    with pytest.raises(ContractError, match="not found"):
        load_contract(tmp_path / "missing.yaml")
    bad = tmp_path / "bad.yaml"
    bad.write_text("rag: [unclosed", encoding="utf-8")
    with pytest.raises(ContractError, match="invalid YAML"):
        load_contract(bad)


def test_native_wimsey_tests_pass_through():
    df = pl.DataFrame({"x": [1, 2, 3]})
    contract = parse_contract(
        {
            "wimsey": [
                {"test": "max_should", "column": "x", "be_less_than": 10},
                {"test": "row_count_should", "be_greater_than": 5, "severity": "warn"},
                {"test": "max_should", "column": "missing", "be_less_than": 10},
            ]
        }
    )
    report = run_contract(contract, df)
    statuses = [(o.passed, o.severity) for o in report.outcomes]
    assert statuses[0] == (True, "error")
    assert statuses[1] == (False, "warn")
    assert statuses[2][0] is False
    assert "error" in str(report.outcomes[2].observed)
