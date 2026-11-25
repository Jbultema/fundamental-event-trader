import json

import pandas as pd
import pytest
import requests

from fundamental_event_trader.sec import (
    DataGateError,
    capture,
    facts_as_of,
    normalize_facts,
    normalize_submissions,
    timestamp,
)


def submissions():
    return {
        "cik": 123,
        "filings": {
            "recent": {
                "accessionNumber": ["0000000123-20-000001", "0000000123-20-000002"],
                "acceptanceDateTime": ["2020-02-01T12:00:00Z", "2020-04-01T12:00:00Z"],
                "form": ["10-K", "10-K/A"],
                "filingDate": ["2020-02-01", "2020-04-01"],
                "reportDate": ["2019-12-31", "2019-12-31"],
            }
        },
    }


def facts():
    return {
        "cik": 123,
        "facts": {
            "us-gaap": {
                "Assets": {
                    "units": {
                        "USD": [
                            {"accn": "0000000123-20-000001", "end": "2019-12-31", "val": 100},
                            {"accn": "0000000123-20-000002", "end": "2019-12-31", "val": 200},
                        ]
                    }
                }
            }
        },
    }


def test_restatement_is_not_backdated():
    filings = normalize_submissions(submissions(), "2021-01-01T00:00:00Z")
    normalized = normalize_facts(facts(), filings)
    assert facts_as_of(normalized, "2020-03-01T00:00:00Z").value.iloc[0] == 100
    assert facts_as_of(normalized, "2020-05-01T00:00:00Z").value.iloc[0] == 200
    assert (
        facts_as_of(
            normalized, "2020-05-01T00:00:00Z", amendment_policy="first_reported"
        ).value.iloc[0]
        == 100
    )


def test_future_filings_are_excluded():
    normalized = normalize_submissions(submissions(), "2020-03-01T00:00:00Z")
    assert len(normalized) == 1


def test_unknown_acceptance_facts_are_not_guessed_from_filing_date():
    filings = normalize_submissions(submissions(), "2020-03-01T00:00:00Z")
    assert len(normalize_facts(facts(), filings)) == 1


@pytest.mark.parametrize(
    "kind", ["array_lengths", "duplicate_accession", "invalid_accession", "naive_acceptance"]
)
def test_malformed_submissions_fail_closed(kind):
    payload = submissions()
    recent = payload["filings"]["recent"]
    if kind == "array_lengths":
        recent["form"] = []
    elif kind == "duplicate_accession":
        recent["accessionNumber"][1] = recent["accessionNumber"][0]
    elif kind == "invalid_accession":
        recent["accessionNumber"][1] = "bad"
    else:
        recent["acceptanceDateTime"][1] = "2020-04-01"
    with pytest.raises(DataGateError):
        normalize_submissions(payload, "2021-01-01T00:00:00Z")


def test_cross_issuer_join_rejected():
    p = facts()
    p["cik"] = 999
    with pytest.raises(DataGateError):
        normalize_facts(p, normalize_submissions(submissions(), "2021-01-01T00:00:00Z"))


def test_ambiguous_same_filing_context_is_rejected():
    normalized = normalize_facts(
        facts(), normalize_submissions(submissions(), "2021-01-01T00:00:00Z")
    )
    conflict = normalized.iloc[[0]].copy()
    conflict["value"] = 150
    with pytest.raises(DataGateError):
        facts_as_of(pd.concat([normalized, conflict]), "2021-01-01T00:00:00Z")


def test_403_is_preserved_without_retry_or_mirror(tmp_path):
    class Client:
        calls = 0

        def get(self, *args, **kwargs):
            self.calls += 1
            response = requests.Response()
            response.status_code = 403
            response._content = b"access denied"
            return response

    client = Client()
    path = capture("123", tmp_path / "capture", session=client)
    result = json.loads(path.read_text())
    assert result["status"] == "blocked"
    assert result["historical_strategy_authorized"] is False
    assert client.calls == 1


@pytest.mark.parametrize("value", ["2020-01-01", "not a date", None])
def test_acceptance_timezone_required(value):
    with pytest.raises((ValueError, DataGateError, TypeError)):
        timestamp(value)
