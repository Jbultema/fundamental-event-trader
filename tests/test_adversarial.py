import json

import pandas as pd
import pytest

from fundamental_event_trader.features import event_study, parse_form4
from fundamental_event_trader.qualification import qualify
from fundamental_event_trader.sec import DataGateError, import_swing_sidecar, sha


def test_missing_failed_security_is_not_omitted_as_if_no_event():
    dates = pd.date_range("2020-01-01 14:30", periods=10, freq="B", tz="UTC")
    events = pd.DataFrame(
        {
            "security_id": ["DELISTED"],
            "accepted_at": ["2020-01-01T20:00:00Z"],
            "directional_signal": [1],
        }
    )
    with pytest.raises(DataGateError, match="survivor"):
        event_study(events, pd.DataFrame(100.0, index=dates, columns=["SPY"]), horizon=2)


def test_qualification_boolean_without_evidence_cannot_pass(tmp_path):
    from fundamental_event_trader.qualification import CRITERIA

    (tmp_path / "manifest.json").write_text(
        json.dumps({"criteria": {c: {"passed": True} for c in CRITERIA}, "artifacts": {}})
    )
    assert not qualify(tmp_path)["historical_event_study_allowed"]


def test_entity_xml_is_rejected():
    with pytest.raises(DataGateError, match="entity"):
        parse_form4(
            b'<!DOCTYPE x [<!ENTITY a "test">]><ownershipDocument/>', "2020-01-01T20:00:00Z"
        )


def test_missing_form4_issuer_cannot_be_invented():
    with pytest.raises(DataGateError, match="issuer"):
        parse_form4(b"<ownershipDocument/>", "2020-01-01T20:00:00Z")


def test_existing_swing_sidecar_reused_without_directional_upgrade(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    frame = pd.DataFrame(
        {"ticker": ["A"], "accepted_at_utc": [pd.Timestamp("2020-01-01T20:00:00Z")]}
    )
    frame.to_parquet(source / "events.parquet")
    metadata = {
        "data_file": "events.parquet",
        "data_file_sha256": sha(source / "events.parquet"),
        "record_type": "candidate_bound_sec_filing_event_snapshot",
        "event_data_gate_passed": True,
        "captured_at_utc": "2020-01-02T20:00:00Z",
    }
    (source / "manifest.json").write_text(json.dumps(metadata))
    output = import_swing_sidecar(source / "manifest.json", tmp_path / "imported")
    result = json.loads(output.read_text())
    assert result["historical_strategy_authorized"] is False
    assert "not_directional" in result["role"]


def test_corrupt_swing_sidecar_is_rejected_before_parsing(tmp_path):
    (tmp_path / "events.parquet").write_bytes(b"not parquet")
    (tmp_path / "manifest.json").write_text(
        json.dumps({"data_file": "events.parquet", "data_file_sha256": "wrong"})
    )
    with pytest.raises(DataGateError, match="integrity"):
        import_swing_sidecar(tmp_path / "manifest.json", tmp_path / "output")
