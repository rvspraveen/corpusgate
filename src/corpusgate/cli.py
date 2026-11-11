"""Command-line entry point: ``corpusgate``."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from corpusgate import __version__
from corpusgate.checks import CHECKS
from corpusgate.contract import ContractError, load_contract
from corpusgate.report import render_console, render_json, render_markdown
from corpusgate.runner import DataError, read_corpus, run_contract
from corpusgate.suggest import suggest_yaml

EXIT_OK, EXIT_FAILED, EXIT_USAGE = 0, 1, 2


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="corpusgate", description="Data contracts and CI gates for RAG corpora.")
    p.add_argument("--version", action="version", version=f"corpusgate {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("check", help="Validate a corpus against a contract")
    c.add_argument("--contract", "-c", required=True, help="Path to contract YAML")
    c.add_argument("--data", "-d", required=True, help="Corpus file (.jsonl, .ndjson, .parquet, .csv)")
    c.add_argument("--format", "-f", choices=["console", "markdown", "json"], default="console")
    c.add_argument("--out", "-o", help="Write the report to this file instead of stdout")
    c.add_argument("--fail-on-warn", action="store_true", help="Treat warnings as failures")

    s = sub.add_parser("suggest", help="Draft a starter contract from a sample corpus")
    s.add_argument("--data", "-d", required=True)
    s.add_argument("--margin", type=float, default=0.2, help="Slack added to observed bounds (default 0.2)")
    s.add_argument("--out", "-o", help="Write the contract here instead of stdout")

    sub.add_parser("list-checks", help="List available RAG checks and their parameters")
    return p


def _write_stdout(text: str) -> None:
    """Write to stdout, degrading unencodable characters instead of raising."""
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        sys.stdout.reconfigure(errors="replace")
        sys.stdout.write(text)


def _emit(text: str, out: str | None) -> None:
    if out:
        Path(out).write_text(text, encoding="utf-8")
    else:
        _write_stdout(text if text.endswith("\n") else text + "\n")


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "list-checks":
            for spec in CHECKS.values():
                req = ", ".join(spec.required) or "-"
                opt = ", ".join(f"{k}={v}" for k, v in spec.optional.items())
                print(f"{spec.name:<16} {spec.summary}\n{'':<16} required: {req} | optional: {opt}, severity=error")
            return EXIT_OK

        if args.command == "suggest":
            _emit(suggest_yaml(read_corpus(args.data), args.margin), args.out)
            return EXIT_OK

        contract = load_contract(args.contract)
        df = read_corpus(args.data)
        report = run_contract(contract, df, data_label=args.data)
        if args.format == "console" and not args.out:
            render_console(report)
        else:
            if args.format == "json":
                text = render_json(report)
            else:
                # Files are written as UTF-8; stdout may be a narrower codepage.
                encoding = "utf-8" if args.out else getattr(sys.stdout, "encoding", None)
                text = render_markdown(report, encoding)
            _emit(text, args.out)
        failed = not report.passed or (args.fail_on_warn and report.warnings)
        return EXIT_FAILED if failed else EXIT_OK
    except (ContractError, DataError) as exc:
        print(f"corpusgate: error: {exc}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
