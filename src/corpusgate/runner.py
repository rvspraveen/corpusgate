"""Execute a contract against a corpus via wimsey's public API."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import polars as pl
import wimsey

from corpusgate.contract import Contract

READERS = {
    ".jsonl": pl.read_ndjson,
    ".ndjson": pl.read_ndjson,
    ".parquet": pl.read_parquet,
    ".csv": pl.read_csv,
}


@dataclass
class CheckOutcome:
    check: str
    probe: str
    severity: str
    passed: bool
    observed: Any = None
    limit: Any = None
    description: str = ""


@dataclass
class Report:
    data: str
    rows: int
    outcomes: list[CheckOutcome] = field(default_factory=list)

    @property
    def errors(self) -> list[CheckOutcome]:
        return [o for o in self.outcomes if not o.passed and o.severity == "error"]

    @property
    def warnings(self) -> list[CheckOutcome]:
        return [o for o in self.outcomes if not o.passed and o.severity == "warn"]

    @property
    def passed(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "data": self.data,
            "rows": self.rows,
            "passed": self.passed,
            "summary": {
                "checks": len(self.outcomes),
                "failed_errors": len(self.errors),
                "failed_warnings": len(self.warnings),
            },
            "outcomes": [asdict(o) for o in self.outcomes],
        }


class DataError(ValueError):
    """Raised when the corpus file cannot be read."""


def read_corpus(path: str | Path) -> pl.DataFrame:
    p = Path(path)
    if not p.exists():
        raise DataError(f"data file not found: {p}")
    reader = READERS.get(p.suffix.lower())
    if reader is None:
        raise DataError(f"unsupported data format {p.suffix!r}; use one of {sorted(READERS)}")
    try:
        return reader(p)
    except Exception as exc:  # polars raises several error types
        raise DataError(f"could not read {p}: {exc}") from exc


def _jsonable(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, (int, str, bool)) or value is None:
        return value
    return str(value)


def run_contract(contract: Contract, df: pl.DataFrame, data_label: str = "<dataframe>") -> Report:
    report = Report(data=data_label, rows=df.height)
    columns = set(df.columns)

    runnable = []
    for check in contract.rag:
        for probe in check.probes:
            missing = [c for c in probe.columns if c not in columns]
            if missing:
                report.outcomes.append(
                    CheckOutcome(
                        check.test,
                        probe.name,
                        check.severity,
                        False,
                        f"missing column(s) {missing}",
                        probe.max_violations,
                        probe.description,
                    )
                )
            else:
                runnable.append((check, probe))

    if runnable:
        result = wimsey.test(df, [probe.as_wimsey_test() for _, probe in runnable])
        by_name = {r.name: r for r in result.results}
        for check, probe in runnable:
            r = by_name[probe.name]
            report.outcomes.append(
                CheckOutcome(
                    check.test, probe.name, check.severity, r.success, _jsonable(r.unexpected), probe.max_violations, probe.description
                )
            )

    for native in contract.wimsey:
        label = f"wimsey:{native.spec.get('test')}"
        try:
            result = wimsey.test(df, [native.spec])
        except Exception as exc:  # surface wimsey config/column errors as a failed check
            report.outcomes.append(CheckOutcome("wimsey", label, native.severity, False, f"error: {exc}", None, "native wimsey test"))
            continue
        for r in result.results:
            report.outcomes.append(
                CheckOutcome("wimsey", f"wimsey:{r.name}", native.severity, r.success, _jsonable(r.unexpected), None, "native wimsey test")
            )
    return report
