"""Regenerate the synthetic sample corpora in this folder.

All content is fictional ("Northwind Renewables"). Planted PII in the bad
corpus uses reserved/invalid values only (000- SSN prefix, 555-01xx phone,
example.com email).

    python examples/make_samples.py
"""

from __future__ import annotations

import copy
import json
import random
from pathlib import Path

HERE = Path(__file__).parent
DIM = 16

TOPICS = {
    "public": [
        ("press/2026-wind-farm.md", "Northwind Renewables commissioned the Harlow Ridge wind farm"),
        ("web/sustainability.md", "Our sustainability report covers lifecycle emissions for every turbine"),
        ("web/careers.md", "Northwind hires field technicians, grid analysts and data engineers"),
    ],
    "internal": [
        ("ops/turbine-maintenance.md", "Gearbox inspections follow a 90-day cycle with vibration baselines"),
        ("ops/grid-dispatch.md", "Dispatch planners balance forecast output against interconnect limits"),
        ("it/data-retention.md", "Operational telemetry is retained for seven years in cold storage"),
    ],
    "hr": [
        ("hr/compensation-bands.md", "Compensation bands are reviewed each fiscal quarter by the HR committee"),
        ("hr/leave-policy.md", "Employees accrue paid leave monthly and may carry over ten days"),
    ],
    "finance": [
        ("finance/q3-forecast.md", "The Q3 revenue forecast assumes a capacity factor of 38 percent"),
        ("finance/capex-plan.md", "Capital expenditure for 2027 prioritises storage and substation upgrades"),
    ],
}

DETAILS = [
    "This section summarises the current process and the owners responsible for it.",
    "Figures are synthetic and exist only to demonstrate corpus validation.",
    "Changes require sign-off from the document owner and are logged for audit.",
    "Where regional rules differ, the stricter requirement applies.",
    "Questions should be raised through the internal service desk.",
    "The guidance is reviewed annually or after any material incident.",
    "Related procedures are linked from the document index.",
]


def _vector(rng: random.Random, dim: int = DIM) -> list[float]:
    return [round(rng.uniform(-1, 1), 4) for _ in range(dim)]


def build_good(seed: int = 7) -> list[dict]:
    rng = random.Random(seed)  # noqa: S311 - deterministic sample data, not crypto
    rows = []
    n = 0
    for acl, docs in TOPICS.items():
        for doc_idx, (source, lead) in enumerate(docs):
            doc_id = f"{acl}-{doc_idx + 1:02d}"
            for part in range(4):
                n += 1
                body = " ".join(rng.sample(DETAILS, k=3))
                rows.append(
                    {
                        "chunk_id": f"c{n:04d}",
                        "doc_id": doc_id,
                        "text": f"{lead} (part {part + 1}). {body}",
                        "acl": acl,
                        "source": source,
                        "page": part + 1,
                        "embedding": _vector(rng),
                    }
                )
    return rows


def build_bad(good: list[dict]) -> list[dict]:
    rows = copy.deepcopy(good)
    rows[3]["chunk_id"] = rows[2]["chunk_id"]  # duplicate id
    rows[5]["acl"] = None  # missing access label
    rows[6]["acl"] = "secret"  # label outside the allowed set
    rows[8]["embedding"] = rows[8]["embedding"][:3]  # wrong dimension
    rows[10]["text"] = rows[10]["text"] + " Contact payroll: SSN 000-12-3456."  # fake PII
    rows[12]["text"] = ""  # empty chunk
    rows[14]["text"] = rows[13]["text"]  # duplicate text
    rows[16]["source"] = None  # breaks citations
    return rows


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


if __name__ == "__main__":
    good = build_good()
    _write(HERE / "good_chunks.jsonl", good)
    _write(HERE / "bad_chunks.jsonl", build_bad(good))
    print(f"wrote {len(good)} rows to good_chunks.jsonl and bad_chunks.jsonl")
