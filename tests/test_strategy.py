import exchange_calendars as xcals
import numpy as np
import pandas as pd
import pytest

from fundamental_event_trader.sec import DataGateError
from fundamental_event_trader.strategy import (
    Policy,
    eligible_events,
    policies,
    session_schedule,
    targets,
)


@pytest.fixture
def inputs():
    cal = xcals.get_calendar("XNYS")
    days = cal.sessions_in_range("2020-01-02", "2020-04-01")
    opens = pd.DatetimeIndex([cal.session_open(day) for day in days])
    events = pd.DataFrame(
        {
            "security_id": ["A"],
            "cik": ["0000000001"],
            "accepted_at": ["2020-01-02T22:00:00Z"],
            "available_at": ["2020-01-02T22:00:00Z"],
            "accession": ["0000000001-20-000001"],
            "source_sha256": ["a" * 64],
            "profitability_change": [0.03],
        }
    )
    identity = pd.DataFrame(
        {
            "security_id": ["A"],
            "cik": ["0000000001"],
            "known_at": ["2010-01-01T00:00:00Z"],
            "valid_from": ["2010-01-01T00:00:00Z"],
            "valid_until": ["2030-01-01T00:00:00Z"],
        }
    )
    return events, opens, identity


def test_filing_after_close_is_not_a_same_day_decision(inputs):
    events, opens, identity = inputs
    weights = targets(events, opens, identity, Policy("test", "profitability_change", 0.02, 21))
    assert weights.A.iloc[0] == 0.0
    assert weights.A.iloc[1] == 0.1
    assert weights.A.iloc[21] == 0.1
    assert weights.A.iloc[22] == 0.0


def test_filing_before_close_can_affect_that_close_not_its_prior_open(inputs):
    events, opens, identity = inputs
    events["accepted_at"] = events["available_at"] = "2020-01-02T19:00:00Z"
    weights = targets(events, opens, identity, Policy("test", "profitability_change", 0.02, 21))
    assert weights.A.iloc[0] == 0.1
    assert weights.A.iloc[21] == 0.0


def test_earlier_targets_are_invariant_to_future_events(inputs):
    events, opens, identity = inputs
    policy = Policy("test", "profitability_change", 0.02, 21)
    original = targets(events, opens, identity, policy)
    later = events.copy()
    later["accepted_at"] = later["available_at"] = "2020-03-02T20:00:00Z"
    later["accession"] = "0000000001-20-000002"
    combined = targets(pd.concat([events, later], ignore_index=True), opens, identity, policy)
    pd.testing.assert_frame_equal(original.loc[:"2020-02-28"], combined.loc[:"2020-02-28"])


def test_future_identity_cannot_unlock_a_historical_event(inputs):
    events, opens, identity = inputs
    identity.known_at = "2025-01-01T00:00:00Z"
    with pytest.raises(DataGateError, match="future-known"):
        targets(events, opens, identity, Policy("test", "profitability_change", 0.02, 21))


def test_registry_contains_48_distinct_specifications():
    registered = policies()
    assert len(registered) == len({p.name for p in registered}) == 48


def test_generic_directional_signal_does_not_impersonate_a_feature(inputs):
    events, _, _ = inputs
    events = events.drop(columns="profitability_change").assign(directional_signal=1.0)
    with pytest.raises(DataGateError, match="unavailable content"):
        eligible_events(events, Policy("test", "profitability_change", 0.02, 21))


@pytest.mark.parametrize(
    "kind", ["future_feature", "missing_source", "duplicate", "infinite", "naive"]
)
def test_adversarial_event_evidence(inputs, kind):
    events, _, _ = inputs
    if kind == "future_feature":
        events.available_at = "2020-01-01T20:00:00Z"
    elif kind == "missing_source":
        events.source_sha256 = "invented"
    elif kind == "duplicate":
        events = pd.concat([events, events])
    elif kind == "infinite":
        events.profitability_change = np.inf
    else:
        events.accepted_at = "2020-01-02"
    with pytest.raises(DataGateError):
        eligible_events(events, Policy("test", "profitability_change", 0.02, 21))


def test_post_filing_drift_waits_for_its_price_window(inputs):
    events, _, _ = inputs
    events["post_filing_return"] = 0.03
    events["price_window_end"] = "2020-01-10T21:00:00Z"
    with pytest.raises(DataGateError, match="window ends"):
        eligible_events(events, Policy("test", "post_filing_drift", 0.01, 21))
    events.available_at = "2020-01-10T21:00:00Z"
    assert len(eligible_events(events, Policy("test", "post_filing_drift", 0.01, 21))) == 1


def test_content_specific_events_require_actual_verification(inputs):
    events, _, _ = inputs
    events["stake_change"] = 0.1
    policy = Policy("test", "ownership_change", 0.02, 21)
    with pytest.raises(DataGateError, match="verification flags"):
        eligible_events(events, policy)
    events["ownership_content_verified"] = False
    assert eligible_events(events, policy).empty


def test_half_day_and_dst_use_the_exchange_calendar():
    cal = xcals.get_calendar("XNYS")
    days = cal.sessions_in_range("2026-11-25", "2026-11-30")
    frame = session_schedule(pd.DatetimeIndex([cal.session_open(day) for day in days]))
    assert frame.iloc[1].close == pd.Timestamp("2026-11-27T18:00:00Z")
    assert len(frame) == 3
