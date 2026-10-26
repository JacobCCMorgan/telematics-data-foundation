import pandas as pd
import pytest

from tdf.deid import (
    Pseudonymizer,
    clean_country,
    clean_dot,
    clean_state,
    coarsen_coordinate,
    extract_dot,
    normalize_org_name,
    scrub_text,
    to_number,
)

KEY = b"unit-test-key-0123456789abcdef"


@pytest.fixture
def p():
    return Pseudonymizer(KEY)


def test_pseudonym_is_deterministic_and_namespaced(p):
    a = p.one("device", "DEV-", "RT64000281")
    b = p.one("device", "DEV-", " rt64000281 ")  # whitespace / case normalised by series(); one() strips
    assert a.startswith("DEV-") and len(a) == 14
    assert p.one("device", "DEV-", "RT64000281") == a
    assert p.one("vin", "VIN-", "RT64000281") != a.replace("DEV-", "VIN-")
    assert Pseudonymizer(b"another-key-0123456789abcdef").one("device", "DEV-", "RT64000281") != a


def test_series_normalises_case_and_maps_placeholders(p):
    s = pd.Series(["RT64000281", " rt64000281", "-", None, "VINNOTYETDETECTED"])
    out = p.series(s, "device", "DEV-", placeholders={"VINNOTYETDETECTED"})
    assert out[0] == out[1]
    assert out[2] is None and out[3] is None and out[4] is None


def test_short_key_rejected():
    with pytest.raises(ValueError):
        Pseudonymizer(b"short")


def test_org_name_normalisation_strips_dot_suffix():
    assert normalize_org_name("ACME Trucking, LLC (1234567)") == "acme trucking llc"
    assert normalize_org_name("  Acme   Trucking LLC ") == "acme trucking llc"
    assert extract_dot("ACME Trucking (1234567)") == "1234567"
    assert extract_dot("ACME Trucking") is None
    assert clean_dot(" 1,234,567 ") == "1234567"
    assert clean_dot("abc") is None


def test_state_and_country_cleaning():
    assert clean_state("ca") == "CA"
    assert clean_state("California") == "CA"
    assert clean_state("CALIFORNIA") == "CA"
    assert clean_state("-") is None
    assert clean_state("Los Angeles") is None
    assert clean_country("United State") == "US"
    assert clean_country("Untied States") == "US"
    assert clean_country("Canada") == "CA"
    assert clean_country("-") is None


def test_coordinate_coarsening():
    assert coarsen_coordinate("34.0522") == 34.05
    assert coarsen_coordinate(-118.2437) == -118.25
    assert coarsen_coordinate("0") is None
    assert coarsen_coordinate("-") is None


def test_to_number_handles_units_and_placeholders():
    s = pd.Series(["432.5 MB", "7 B", "1,234", "60%", "-", None, "abc"])
    out = to_number(s).tolist()
    assert out[0] == 432.5 and abs(out[1] - 7e-6) < 1e-12 and out[2] == 1234 and out[3] == 60
    assert all(pd.isna(x) for x in out[4:])


def test_scrub_text_replaces_identifiers():
    text = "device RT64000281 imei 350435037240565 vin 1FUJGLDR6CLBP8834 mail a.b@x.com tel 626-416-5555 at 34.05221,-118.24368"
    out = scrub_text(text)
    for token in ("<SERIAL>", "<IMEI>", "<VIN>", "<EMAIL>", "<PHONE>", "<LATLON>"):
        assert token in out
    assert "RT64000281" not in out and "350435037240565" not in out and "a.b@x.com" not in out
