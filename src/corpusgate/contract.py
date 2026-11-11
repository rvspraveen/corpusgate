"""Contract loading and validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from corpusgate.checks import CHECKS, Probe

SEVERITIES = ("error", "warn")


class ContractError(ValueError):
    """Raised when a contract file is malformed."""


@dataclass
class RagCheck:
    test: str
    severity: str
    probes: list[Probe]


@dataclass
class NativeCheck:
    severity: str
    spec: dict[str, Any]


@dataclass
class Contract:
    rag: list[RagCheck] = field(default_factory=list)
    wimsey: list[NativeCheck] = field(default_factory=list)


def _severity(item: dict[str, Any], where: str) -> str:
    sev = item.pop("severity", "error")
    if sev not in SEVERITIES:
        raise ContractError(f"{where}: severity must be one of {SEVERITIES}, got {sev!r}")
    return sev


def parse_contract(data: Any) -> Contract:
    if not isinstance(data, dict):
        raise ContractError("contract must be a mapping with 'version' and 'rag' and/or 'wimsey' keys")
    if data.get("version", 1) != 1:
        raise ContractError(f"unsupported contract version {data.get('version')!r}; expected 1")
    unknown_keys = set(data) - {"version", "rag", "wimsey"}
    if unknown_keys:
        raise ContractError(f"unknown top-level key(s): {sorted(unknown_keys)}")
    contract = Contract()
    for i, raw in enumerate(data.get("rag") or []):
        where = f"rag[{i}]"
        if not isinstance(raw, dict) or "test" not in raw:
            raise ContractError(f"{where}: each item needs a 'test' key")
        item = dict(raw)
        name = item.pop("test")
        spec = CHECKS.get(name)
        if spec is None:
            raise ContractError(f"{where}: unknown check {name!r}; available: {sorted(CHECKS)}")
        severity = _severity(item, where)
        allowed = set(spec.required) | set(spec.optional)
        extra = set(item) - allowed
        if extra:
            raise ContractError(f"{where} ({name}): unknown parameter(s) {sorted(extra)}; allowed: {sorted(allowed)}")
        missing = [p for p in spec.required if p not in item]
        if missing:
            raise ContractError(f"{where} ({name}): missing required parameter(s) {missing}")
        try:
            probes = spec.build(**item)
        except (TypeError, ValueError) as exc:
            raise ContractError(f"{where} ({name}): {exc}") from exc
        contract.rag.append(RagCheck(test=name, severity=severity, probes=probes))
    for i, raw in enumerate(data.get("wimsey") or []):
        where = f"wimsey[{i}]"
        if not isinstance(raw, dict) or "test" not in raw:
            raise ContractError(f"{where}: each item needs a 'test' key (any wimsey test)")
        item = dict(raw)
        severity = _severity(item, where)
        contract.wimsey.append(NativeCheck(severity=severity, spec=item))
    if not contract.rag and not contract.wimsey:
        raise ContractError("contract defines no checks")
    return contract


def load_contract(path: str | Path) -> Contract:
    p = Path(path)
    if not p.exists():
        raise ContractError(f"contract not found: {p}")
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ContractError(f"invalid YAML in {p}: {exc}") from exc
    return parse_contract(data)
