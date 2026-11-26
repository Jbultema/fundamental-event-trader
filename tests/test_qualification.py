import json

import numpy as np
import pandas as pd
import pytest

from fundamental_event_trader.qualification import CRITERIA, qualify
from fundamental_event_trader.sec import sha


def dataset(root):
    root.mkdir()
    dates = pd.date_range("2000-01-03 14:30", periods=3000, freq="B", tz="UTC")
    names = [f"S{i}" for i in range(100)]
    prices = pd.DataFrame(100.0, index=dates, columns=[*names, "SPY"])
    prices.loc[prices.index >= "2010-01-01", "S99"] = np.nan
    identity = pd.DataFrame(
        {
            "security_id": names,
            "cik": [str(i + 1).zfill(10) for i in range(100)],
            "valid_from": "1995-01-01T00:00:00Z",
            "valid_until": ["2020-01-01T00:00:00Z"] * 99 + ["2010-01-01T00:00:00Z"],
            "known_at": "1995-01-01T00:00:00Z",
            "delisted": [False] * 99 + [True],
            "terminal_treatment_verified": True,
        }
    )
    events = pd.DataFrame(
        {
            "security_id": ["S0"],
            "cik": ["0000000001"],
            "accepted_at": ["2005-01-03T21:00:00Z"],
            "directional_signal": [1.0],
        }
    )
    events.to_parquet(root / "events.parquet")
    identity.to_parquet(root / "identity.parquet")
    prices.to_parquet(root / "prices.parquet")
    (root / "synthetic_test_evidence.json").write_text(
        '{"fixture_only":true,"not_real_research_data":true}'
    )
    seal(root)
    return root


def seal(root):
    payload = {
        "criteria": {
            c: {"passed": True, "evidence_artifact": "synthetic_test_evidence.json"}
            for c in CRITERIA
        },
        "artifacts": {p.name: sha(p) for p in root.iterdir() if p.name != "manifest.json"},
    }
    (root / "manifest.json").write_text(json.dumps(payload))


def test_complete_synthetic_contract_unlocks_event_study_not_strategy(tmp_path):
    status = qualify(dataset(tmp_path / "dataset"))
    assert status["historical_event_study_allowed"] is True
    assert status["portfolio_allocation_allowed"] is False
    assert status["strategy_promotion_allowed"] is False


@pytest.mark.parametrize(
    "manifest",
    [[], None, True, {"criteria": [], "artifacts": {}}, {"criteria": {"x": True}, "artifacts": {}}],
)
def test_malformed_manifest_remains_a_blocked_qualification(tmp_path, manifest):
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    status = qualify(tmp_path)
    assert status["status"] == "blocked"
    assert status["historical_event_study_allowed"] is False


@pytest.mark.parametrize(
    "kind",
    [
        "future_identity",
        "wrong_issuer",
        "post_delisting_prices",
        "no_dead_securities",
        "unbound_evidence",
        "infinite_price",
        "missing_benchmark",
        "nan_signal",
        "empty_events",
        "invalid_identity_interval",
        "duplicate_prices",
    ],
)
def test_adversarial_dataset_cannot_pass(kind, tmp_path):
    root = dataset(tmp_path / "dataset")
    if kind in {"future_identity", "wrong_issuer", "no_dead_securities"}:
        identity = pd.read_parquet(root / "identity.parquet")
        if kind == "future_identity":
            identity.loc[0, "known_at"] = "2020-01-01T00:00:00Z"
        elif kind == "wrong_issuer":
            identity.loc[0, "cik"] = "0000009999"
        else:
            identity["delisted"] = False
        identity.to_parquet(root / "identity.parquet")
    elif kind == "post_delisting_prices":
        prices = pd.read_parquet(root / "prices.parquet")
        prices.iloc[-1, prices.columns.get_loc("S99")] = 100.0
        prices.to_parquet(root / "prices.parquet")
    elif kind == "unbound_evidence":
        (root / "synthetic_test_evidence.json").unlink()
    elif kind in {"infinite_price", "missing_benchmark", "duplicate_prices"}:
        prices = pd.read_parquet(root / "prices.parquet")
        if kind == "infinite_price":
            prices.iloc[200, 0] = np.inf
        elif kind == "missing_benchmark":
            prices.iloc[200, prices.columns.get_loc("SPY")] = np.nan
        else:
            prices = pd.concat([prices.iloc[:1], prices])
        prices.to_parquet(root / "prices.parquet")
    elif kind in {"nan_signal", "empty_events"}:
        events = pd.read_parquet(root / "events.parquet")
        if kind == "nan_signal":
            events["directional_signal"] = np.nan
        else:
            events = events.iloc[:0]
        events.to_parquet(root / "events.parquet")
    else:
        identity = pd.read_parquet(root / "identity.parquet")
        identity.loc[0, "valid_until"] = "1994-01-01T00:00:00Z"
        identity.to_parquet(root / "identity.parquet")
    seal(root)
    assert qualify(root)["historical_event_study_allowed"] is False
