import json

import pytest

from fundamental_event_trader.conditional_export import verified_report
from fundamental_event_trader.sec import DataGateError, sha


def report(root, *, allocation=False, code=None):
    root.mkdir()
    (root / "summary.json").write_text(json.dumps({"portfolio_allocation_allowed": allocation}))
    meta = {"artifacts": {"summary.json": sha(root / "summary.json")}, "code_hashes": code or {}}
    (root / "manifest.json").write_text(json.dumps(meta))


def test_native_export_rejects_admitted_or_modified_conditional_evidence(tmp_path):
    root = tmp_path / "study"
    report(root, allocation=True)
    with pytest.raises(DataGateError, match="allocation authority"):
        verified_report(root)
    (root / "summary.json").write_text("{}")
    with pytest.raises(DataGateError):
        verified_report(root)


def test_native_export_requires_same_source_policy(tmp_path):
    root = tmp_path / "study"
    report(root, code={"event_sample_portfolio.py": "0" * 64})
    with pytest.raises(DataGateError, match="Source policy changed"):
        verified_report(root)
