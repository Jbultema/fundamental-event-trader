import numpy as np
import pandas as pd
import pytest

from fundamental_event_trader.news_vintage_research import (
    amend_freshness,
    build,
    features,
    parse_vintage,
    state,
)
from fundamental_event_trader.sec import DataGateError


def vintage_csv(*, column="USEPUINDXD_20190115", end="2019-01-15", duplicate=False):
    dates = pd.date_range("2017-01-01", end)
    frame = pd.DataFrame({"observation_date": dates.strftime("%Y-%m-%d"),
                          column: 100 + np.sin(np.arange(len(dates)) / 20) * 10})
    if duplicate:
        frame = pd.concat([frame, frame.iloc[-1:]])
    return frame.to_csv(index=False).encode()


def test_vintage_identity_and_historical_features():
    s = parse_vintage(vintage_csv(), "2019-01-15")
    f = features(s)
    assert f["last_observation"] == "2019-01-15"
    assert np.isfinite([f["level"], f["z"], f["change21"], f["change63"]]).all()


@pytest.mark.parametrize("kwargs", [{"column": "USEPUINDXD_20260115"}, {"end": "2019-01-16"},
                                    {"end": "2019-01-01"}, {"duplicate": True}])
def test_wrong_vintage_future_stale_or_duplicate_rejected(kwargs):
    with pytest.raises(DataGateError):
        parse_vintage(vintage_csv(**kwargs), "2019-01-15")


def test_constant_or_short_feature_window_rejected():
    with pytest.raises(DataGateError):
        features(pd.Series([100.] * 300, index=pd.date_range("2018-01-01", periods=300)))
    with pytest.raises(DataGateError):
        features(pd.Series(np.arange(100), index=pd.date_range("2018-01-01", periods=100)))


def test_rules_separate_contrarian_from_defensive_use():
    row = {"level": 200, "z": 2.5, "change21": .5, "change63": .4}
    assert state("contrarian1", row, False) == 1
    assert state("z1", row, False) == 0
    assert state("price_confirms", row, True) == 1
    assert state("staged", row, False) == 0
    row["change21"] = -.5
    assert state("staged", row, False) == .5
    assert state("price_repair", row, False) == 1


def test_unregistered_vintage_policy_rejected():
    with pytest.raises(DataGateError):
        state("invented", {"level": 100, "z": 0, "change21": 0, "change63": 0}, True)


def test_stale_release_can_be_preserved_without_becoming_a_fresh_signal():
    result = parse_vintage(vintage_csv(end="2019-01-01"), "2019-01-15", allow_stale=True)
    assert result.index[-1] == pd.Timestamp("2019-01-01")


def test_data_quality_amendment_preserves_original_policies_and_selection(tmp_path):
    import json

    original = {"policies": [{"id": "fixed", "threshold": 1.5}], "selection": "development_only"}
    file = tmp_path / "registry.json"
    file.write_text(json.dumps(original))
    original_bytes = file.read_bytes()
    amend_freshness(file)
    amended = json.loads(file.read_text())
    assert amended["policies"] == original["policies"]
    assert amended["selection"] == original["selection"]
    assert amended["stale_vintage_policy"]["action"] == "no_target_update_hold_previous"
    assert (tmp_path / "registry_original.json").read_bytes() == original_bytes
    with pytest.raises(DataGateError, match="already registered"):
        amend_freshness(file)


def test_sealed_vintage_study_is_never_overwritten(tmp_path):
    (tmp_path / "manifest.json").write_text("sealed")
    with pytest.raises(DataGateError, match="already sealed"):
        build(tmp_path / "registry.json", resume=True)
    assert (tmp_path / "manifest.json").read_text() == "sealed"


def test_resume_does_not_retry_denied_source(tmp_path):
    import json

    (tmp_path / "registry.json").write_text("{}")
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources/acquisition.json").write_text(json.dumps({"requests": [{"http_status": 403}]}))
    with pytest.raises(DataGateError, match="Denied access"):
        build(tmp_path / "registry.json", resume=True)


def test_resume_refuses_modified_cached_release(tmp_path):
    import json

    (tmp_path / "registry.json").write_text("{}")
    (tmp_path / "sources").mkdir()
    (tmp_path / "sources/release.csv").write_text("changed")
    (tmp_path / "sources/acquisition.json").write_text(json.dumps({"requests": [{
        "http_status": 200, "url": "https://alfred.stlouisfed.org/graph/alfredgraph.csv?id=USEPUINDXD&vintage_date=2019-01-15",
        "path": "release.csv", "sha256": "0" * 64}]}))
    with pytest.raises(DataGateError, match="Cached release"):
        build(tmp_path / "registry.json", resume=True)
