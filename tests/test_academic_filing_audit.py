import json

import pandas as pd
import pytest

from fundamental_event_trader.academic_filing_audit import (
    decode_object,
    extract_row,
    filing_date,
    verify_acquisition,
)
from fundamental_event_trader.sec import DataGateError


def example_row(form="4"):
    xml = """<ownershipDocument><issuer><issuerCik>123</issuerCik><issuerTradingSymbol>EXAMPLE</issuerTradingSymbol></issuer><reportingOwner><reportingOwnerId><rptOwnerCik>555</rptOwnerCik></reportingOwnerId></reportingOwner><nonDerivativeTable><nonDerivativeTransaction><transactionCoding><transactionCode>P</transactionCode></transactionCoding><transactionDate><value>2020-01-01</value></transactionDate><transactionAmounts><transactionShares><value>100</value></transactionShares><transactionPricePerShare><value>10</value></transactionPricePerShare></transactionAmounts></nonDerivativeTransaction></nonDerivativeTable></ownershipDocument>"""
    return {"metadata_accession-number": "0000000123-20-000001", "metadata_filing-date": "20200102",
            "metadata_documents": json.dumps([{"type": form, "filename": "example.xml"}]),
            "metadata_filer": json.dumps({"company-data": {"cik": "123"}}),
            "content": xml if form == "4" else "This filing is synthetic software-test content."}


def extract(row):
    return extract_row(row, source_hash="1" * 64, row_number=0, shard="fixture.parquet")


def test_filing_date_convention_is_explicit_not_actual_acceptance():
    date, cutoff = filing_date("20200102")
    assert str(date.date()) == "2020-01-02"
    assert cutoff == pd.Timestamp("2020-01-03T05:00:00Z")
    base, transactions = extract(example_row())
    assert base["cutoff_is_verified_acceptance"] is False
    assert base["historical_strategy_allowed"] is False
    assert "accepted_at" not in transactions and "available_at" not in transactions
    assert "directional_signal" not in transactions
    assert transactions.dollars.tolist() == [1000.]
    assert transactions.purchase_scope.tolist() == ["open_market_or_private"]


@pytest.mark.parametrize("date", ["2020", "2020-01-02", "20200230", None])
def test_no_guessed_or_invalid_publication_dates(date):
    with pytest.raises((DataGateError, ValueError)):
        filing_date(date)


def test_transaction_after_filing_date_rejected_even_with_next_day_model_cutoff():
    row = example_row()
    row["content"] = row["content"].replace("2020-01-01", "2020-01-03")
    with pytest.raises(DataGateError, match="follows the corpus filing date"):
        extract(row)


@pytest.mark.parametrize("mutation", ["duplicate_documents", "preview_truncated", "entity", "accession", "wrong_form"])
def test_incomplete_or_ambiguous_source_content_is_rejected(mutation):
    row = example_row()
    if mutation == "duplicate_documents":
        row["metadata_documents"] = json.dumps([{"type": "4"}, {"type": "4"}])
    elif mutation == "preview_truncated":
        row["metadata_documents"] = row["metadata_documents"][:12]
    elif mutation == "entity":
        row["content"] = '<!DOCTYPE x [<!ENTITY e "unsafe">]>' + row["content"]
    elif mutation == "accession":
        row["metadata_accession-number"] = "invented"
    else:
        row["metadata_documents"] = '[{"type":"10-K"}]'
    with pytest.raises((DataGateError, ValueError)):
        extract(row)


def test_eightk_metadata_is_not_a_directional_event():
    base, transactions = extract(example_row("8-K"))
    assert base["issuer_cik"] == "0000000123"
    assert base["content_status"] == "indexed_only_directional_content_unverified"
    assert transactions.empty
    assert "directional_signal" not in base


def test_structured_metadata_decodes_without_evaluation():
    assert decode_object(json.dumps(json.dumps({"a": 1})), dict) == {"a": 1}
    with pytest.raises((DataGateError, ValueError)):
        decode_object("__import__('os').system('invalid')", dict)


def test_unverified_acquisition_cannot_be_imported(tmp_path):
    (tmp_path / "acquisition.json").write_text(json.dumps({"kind": "pinned_academic_filing_shards_not_performance", "action_authorized": True, "checks": []}))
    with pytest.raises(DataGateError):
        verify_acquisition(tmp_path)
