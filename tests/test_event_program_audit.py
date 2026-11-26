import hashlib
import json

import pytest

from fundamental_event_trader.event_program_audit import (
    FAMILIES,
    audit,
    current_listing,
    fda_sample,
    program,
    real_data_qualification,
    verify_audit,
    verify_receipt,
)
from fundamental_event_trader.sec import DataGateError, sha


def dump(path, value):
    path.write_text(json.dumps(value))


@pytest.fixture
def inputs(tmp_path):
    sources = tmp_path / "receipts"
    sources.mkdir()
    body = json.dumps({"meta": {"results": {"total": 3}}, "results": [
        {"report_date": "20120620", "event_id": "a", "recalling_firm": "Example",
         "recall_initiation_date": "20120601", "termination_date": "20150101"},
        {"report_date": "20120620", "event_id": "a", "recalling_firm": "Example",
         "recall_initiation_date": "20120601", "termination_date": "20150101"},
    ]}).encode()
    (sources / "fda.bin").write_bytes(body)
    (sources / "nasdaq.bin").write_bytes(b"Symbol|Security Name\nABC|Example\nFile Creation Time: 11252026||||\n")
    checks = [
        {"source": "fda_enforcement", "path": "fda.bin", "sha256": sha(sources / "fda.bin"), "http_status": 200},
        {"source": "nasdaq_current_list", "path": "nasdaq.bin", "sha256": sha(sources / "nasdaq.bin"), "http_status": 200},
        {"source": "sec_submissions", "http_status": 403},
    ]
    dump(sources / "probe.json", {"kind": "source_feasibility_not_performance", "action_authorized": False, "checks": checks})
    protocol = tmp_path / "protocol.md"
    protocol.write_text("# Explicitly a software fixture, not investment evidence.\n")
    return sources, protocol


def test_ten_distinct_families_thirty_registered_not_tested_formulations(inputs):
    registry = program(inputs[1])
    assert len(FAMILIES) == len(registry["families"]) == 10
    formulations = [v for f in registry["families"] for v in f["formulations"]]
    assert len(formulations) == len({v["id"] for v in formulations}) == 30
    assert all(v["status"] == "registered_not_implemented_not_tested" for v in formulations)
    assert registry["source_checks_are_performance_tests"] is False
    assert {"lag": 5, "cost_bps": 50} in registry["simultaneous_stress"]


def test_fda_future_resolution_and_duplicate_products_not_onset_evidence(inputs):
    result = fda_sample((inputs[0] / "fda.bin").read_bytes())
    assert result["termination_after_report"] == 2
    assert result["duplicate_event_id_products"] == 1
    assert result["sample_unique_event_ids"] == 1
    assert result["security_id_fields_present"] == []
    assert result["historical_strategy_qualified"] is False


def test_current_list_never_becomes_historical_census(inputs):
    result = current_listing((inputs[0] / "nasdaq.bin").read_bytes())
    assert result["rows"] == 1
    assert result["historical_universe_qualified"] is False


def test_synthetic_or_incomplete_legacy_qualification_is_not_a_real_dataset(tmp_path, monkeypatch):
    monkeypatch.setattr("fundamental_event_trader.event_program_audit.qualify", lambda _: {
        "status": "qualified_for_retrospective_event_study",
        "historical_event_study_allowed": True, "errors": [],
    })

    def refuse_fixture(_):
        raise DataGateError("Real-data research cannot use synthetic datasets")

    monkeypatch.setattr("fundamental_event_trader.research.load_dataset", refuse_fixture)
    result = real_data_qualification(tmp_path)
    assert result["historical_event_study_allowed"] is False
    assert "synthetic" in result["errors"][0]


def test_unqualified_inputs_emit_blocks_not_negative_or_zero_return_results(inputs, tmp_path):
    root = tmp_path / "audit"
    result = audit(*inputs, root)
    assert result["qualified_real_data_strategies_tested"] == 0
    assert result["performance_scenarios_tested"] == 0
    assert result["research_options_exhausted"] is False
    rows = json.loads((root / "family_decisions.json").read_text())
    assert len(rows) == 10
    assert all(row["benefit_estimate"] is None and row["status"] == "blocked_data" for row in rows)
    assert all(row["negative_performance_finding"] is False for row in rows)
    assert verify_audit(root)["verified"] is True
    with pytest.raises(DataGateError, match="immutable"):
        audit(*inputs, root)


@pytest.mark.parametrize("mutation", ["bytes", "escape", "authority"])
def test_receipt_integrity_and_no_performance_authority(inputs, mutation, tmp_path):
    folder, _ = inputs
    receipt = json.loads((folder / "probe.json").read_text())
    if mutation == "bytes":
        (folder / "fda.bin").write_bytes(b"changed")
    elif mutation == "escape":
        (tmp_path / "outside.bin").write_bytes(b"not an approved source")
        receipt["checks"][0] |= {"path": "../outside.bin", "sha256": hashlib.sha256(b"not an approved source").hexdigest()}
    else:
        receipt["action_authorized"] = True
    dump(folder / "probe.json", receipt)
    with pytest.raises(DataGateError):
        verify_receipt(folder)


@pytest.mark.parametrize("mutation", ["counts", "decisions", "fda_diagnostic", "listing_diagnostic", "registry_stress"])
def test_rehashed_false_report_is_rejected_by_semantic_reconstruction(inputs, tmp_path, mutation):
    root = tmp_path / "audit"
    audit(*inputs, root)
    manifest = json.loads((root / "manifest.json").read_text())
    if mutation == "counts":
        manifest["qualified_real_data_strategies_tested"] = 30
    else:
        filename = {"decisions": "family_decisions.json", "fda_diagnostic": "fda_structure_audit.json", "listing_diagnostic": "current_listing_audit.json", "registry_stress": "registry.json"}[mutation]
        payload = json.loads((root / filename).read_text())
        if mutation == "decisions":
            payload[0]["benefit_estimate"] = .22
        elif mutation == "fda_diagnostic":
            payload["termination_after_report"] = 0
        elif mutation == "listing_diagnostic":
            payload["historical_universe_qualified"] = True
        else:
            payload["simultaneous_stress"] = []
        dump(root / filename, payload)
        manifest["artifacts"][filename] = sha(root / filename)
    dump(root / "manifest.json", manifest)
    with pytest.raises(DataGateError):
        verify_audit(root)
