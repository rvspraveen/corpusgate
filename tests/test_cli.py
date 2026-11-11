from __future__ import annotations

import json

import polars as pl
import yaml

from corpusgate.cli import EXIT_FAILED, EXIT_OK, EXIT_USAGE, main
from corpusgate.contract import parse_contract
from corpusgate.report import render_markdown
from corpusgate.runner import run_contract
from corpusgate.suggest import suggest_contract


def test_limit_falls_back_to_ascii_on_narrow_codepages(examples, tmp_path):
    """A cp1252 terminal cannot encode '≤'; the report must degrade, not crash."""
    contract = tmp_path / "c.yaml"
    contract.write_text(yaml.safe_dump({"rag": [{"test": "unique_ids", "column": "chunk_id"}]}), encoding="utf-8")
    out = tmp_path / "r.md"
    assert main(["check", "-c", str(contract), "-d", str(examples / "good_chunks.jsonl"), "-f", "markdown", "-o", str(out)]) == EXIT_OK
    # Files are UTF-8, so the glyph is preserved.
    assert "≤" in out.read_text(encoding="utf-8")

    report = run_contract(parse_contract({"rag": [{"test": "unique_ids", "column": "chunk_id"}]}), pl.DataFrame({"chunk_id": ["a"]}))
    assert "≤" in render_markdown(report, "utf-8")
    assert "<=" in render_markdown(report, "cp1252")


def test_check_good_passes(examples, capsys):
    assert main(["check", "-c", str(examples / "contract.yaml"), "-d", str(examples / "good_chunks.jsonl")]) == EXIT_OK
    assert "PASSED" in capsys.readouterr().out


def test_check_bad_fails_with_markdown(examples, tmp_path):
    out = tmp_path / "report.md"
    code = main(
        ["check", "-c", str(examples / "contract.yaml"), "-d", str(examples / "bad_chunks.jsonl"), "-f", "markdown", "-o", str(out)]
    )
    assert code == EXIT_FAILED
    text = out.read_text(encoding="utf-8")
    assert "FAILED" in text
    assert "`unique_ids:chunk_id`" in text


def test_check_json_and_fail_on_warn(examples, capsys, tmp_path):
    # Strip error-level checks so only the PII warning remains.
    contract = tmp_path / "warn_only.yaml"
    contract.write_text(yaml.safe_dump({"rag": [{"test": "pii_patterns", "severity": "warn"}]}), encoding="utf-8")
    data = str(examples / "bad_chunks.jsonl")
    assert main(["check", "-c", str(contract), "-d", data, "-f", "json"]) == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["passed"] is True
    assert payload["summary"]["failed_warnings"] >= 1
    assert main(["check", "-c", str(contract), "-d", data, "-f", "json", "--fail-on-warn"]) == EXIT_FAILED


def test_usage_errors_exit_2(examples, tmp_path, capsys):
    assert main(["check", "-c", str(tmp_path / "nope.yaml"), "-d", str(examples / "good_chunks.jsonl")]) == EXIT_USAGE
    assert main(["check", "-c", str(examples / "contract.yaml"), "-d", str(tmp_path / "x.jsonl")]) == EXIT_USAGE
    (tmp_path / "x.txt").write_text("hi", encoding="utf-8")
    assert main(["check", "-c", str(examples / "contract.yaml"), "-d", str(tmp_path / "x.txt")]) == EXIT_USAGE
    (tmp_path / "broken.jsonl").write_text("{not json", encoding="utf-8")
    assert main(["check", "-c", str(examples / "contract.yaml"), "-d", str(tmp_path / "broken.jsonl")]) == EXIT_USAGE
    assert "corpusgate: error" in capsys.readouterr().err


def test_stdout_emission_degrades_unencodable_characters(monkeypatch, capsys):
    """Writing markdown to a cp1252 stdout must not raise UnicodeEncodeError."""
    import io
    import sys

    from corpusgate.cli import _write_stdout

    stream = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", stream)
    _write_stdout("emoji: ✅\n")
    stream.flush()
    assert b"emoji" in stream.buffer.getvalue()


def test_other_formats_are_read(examples, tmp_path):
    df = pl.read_ndjson(examples / "good_chunks.jsonl")
    df.write_parquet(tmp_path / "c.parquet")
    df.drop("embedding").write_csv(tmp_path / "c.csv")
    contract = tmp_path / "c.yaml"
    contract.write_text(yaml.safe_dump({"rag": [{"test": "unique_ids", "column": "chunk_id"}]}), encoding="utf-8")
    for f in ("c.parquet", "c.csv"):
        assert main(["check", "-c", str(contract), "-d", str(tmp_path / f), "-f", "json", "-o", str(tmp_path / "r.json")]) == EXIT_OK


def test_suggest_roundtrip_passes_on_source(examples, tmp_path, capsys):
    out = tmp_path / "suggested.yaml"
    assert main(["suggest", "-d", str(examples / "good_chunks.jsonl"), "-o", str(out)]) == EXIT_OK
    assert main(["check", "-c", str(out), "-d", str(examples / "good_chunks.jsonl"), "-f", "json"]) == EXIT_OK
    assert main(["suggest", "-d", str(examples / "good_chunks.jsonl")]) == EXIT_OK
    assert "Review every threshold" in capsys.readouterr().out


def test_suggest_handles_sparse_frames():
    contract = suggest_contract(pl.DataFrame({"content": ["a", "b"], "visibility": [None, None]}))
    tests = [t["test"] for t in contract["rag"]]
    assert "unique_ids" not in tests
    acl = next(t for t in contract["rag"] if t["test"] == "acl_required")
    assert "allowed" not in acl


def test_list_checks(capsys):
    assert main(["list-checks"]) == EXIT_OK
    out = capsys.readouterr().out
    for name in ("required_fields", "embedding_dim", "pii_patterns"):
        assert name in out
