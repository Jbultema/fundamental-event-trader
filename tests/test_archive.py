import json
import zipfile

import pytest
from test_sec import facts, submissions

from fundamental_event_trader.archive import all_submissions, extract_issuer, normalize
from fundamental_event_trader.sec import DataGateError


def archives(tmp_path, *, malicious=False, missing=False):
    source = submissions()
    history = {key: [values.pop(0)] for key, values in source["filings"]["recent"].items()}
    older = "CIK0000000123-submissions-001.json"
    source["filings"]["files"] = [{"name": older}]
    sub = tmp_path / "submissions.zip"
    comp = tmp_path / "companyfacts.zip"
    with zipfile.ZipFile(sub, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("CIK0000000123.json", json.dumps(source))
        if not missing:
            z.writestr(older, json.dumps(history))
        if malicious:
            z.writestr("../outside.json", "{}")
    with zipfile.ZipFile(comp, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("CIK0000000123.json", json.dumps(facts()))
    return sub, comp


def test_bulk_import_binds_older_acceptances_without_rewriting_timestamps(tmp_path):
    sub, facts_zip = archives(tmp_path)
    output = tmp_path / "import"
    extract_issuer(sub, facts_zip, "123", output, captured_at="2021-01-01T00:00:00Z")
    metadata = json.loads((output / "manifest.json").read_text())
    frame = all_submissions(output, metadata)
    assert len(frame) == 2
    assert frame.accepted_at.iloc[0].isoformat() == "2020-02-01T12:00:00+00:00"
    assert metadata["historical_strategy_authorized"] is False
    assert len(metadata["source_archives"]) == 2
    normalized = normalize(output, tmp_path / "normalized")
    assert json.loads(normalized.read_text())["facts"] == 2


@pytest.mark.parametrize("kind", ["unsafe", "missing", "corrupt"])
def test_archive_import_fails_closed(tmp_path, kind):
    sub, comp = archives(tmp_path, malicious=kind == "unsafe", missing=kind == "missing")
    if kind == "corrupt":
        sub.write_bytes(b"not a zip")
    with pytest.raises((DataGateError, zipfile.BadZipFile)):
        extract_issuer(sub, comp, "123", tmp_path / "import", captured_at="2021-01-01T00:00:00Z")


def test_normalization_rejects_tampered_official_bytes(tmp_path):
    sub, comp = archives(tmp_path)
    folder = tmp_path / "import"
    extract_issuer(sub, comp, "123", folder, captured_at="2021-01-01T00:00:00Z")
    (folder / "CIK0000000123-submissions-001.json").write_text("{}")
    with pytest.raises(DataGateError, match="bytes changed"):
        normalize(folder, tmp_path / "normalized")
