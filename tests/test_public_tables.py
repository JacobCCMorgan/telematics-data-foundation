"""Tests that run against the committed public tables (no raw data needed)."""
import json
import re
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from tdf import quality

DATA = Path(__file__).resolve().parents[1] / "data" / "public"
SQL = Path(__file__).resolve().parents[1] / "sql" / "views.sql"


@pytest.fixture(scope="module")
def tables():
    return quality.load(DATA)


def test_manifest_matches_files(tables):
    manifest = json.loads((DATA / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest["tables"]) == set(tables)
    for name, meta in manifest["tables"].items():
        assert len(tables[name]) == meta["rows"], name
        assert list(tables[name].columns) == meta["columns"], name


def test_no_identifier_leakage(tables):
    checks = quality.leakage_checks(tables)
    leaks = [c for c in checks if not c.check.startswith("leak:none")]
    assert not leaks, [c.check for c in leaks]


def test_pseudonym_formats(tables):
    pat = {"device_key": r"^DEV-[0-9a-f]{10}$", "vin_key": r"^VIN-[0-9a-f]{10}$", "org_key": r"^ORG-[0-9a-f]{10}$",
           "driver_key": r"^DRV-[0-9a-f]{10}$", "account_key": r"^USR-[0-9a-f]{10}$", "sales_rep_key": r"^REP-[0-9a-f]{10}$", "dot_key": r"^DOT-[0-9a-f]{10}$"}
    for name, df in tables.items():
        for col, rx in pat.items():
            if col in df.columns:
                vals = df[col].dropna().astype(str)
                assert vals.str.match(rx).all(), f"{name}.{col}"


def test_referential_integrity_thresholds(tables):
    rates = {c.check: c.rate for c in quality.integrity_checks(tables)}
    assert rates["ri:vehicle.device_key->dim_device"] > 0.99
    assert rates["ri:vehicle.org_key->dim_org"] == 1.0
    assert rates["ri:driver_account.org_key->dim_org"] == 1.0
    assert rates["ri:sim.device_key->dim_device"] == 1.0
    assert rates["ri:anomaly.device_key->dim_device"] == 1.0
    assert rates["ri:contract.org_key->dim_org"] == 1.0
    assert rates["ri:contract.device_key->dim_device (current-generation rows only)"] > 0.99


def test_coordinates_are_coarse(tables):
    for name in ("dim_device", "fact_field_anomaly"):
        df = tables[name]
        for col in ("lat_coarse", "lon_coarse"):
            vals = df[col].dropna()
            # multiples of 0.05 within floating tolerance
            assert ((vals * 20).round(6) % 1 == 0).all(), f"{name}.{col}"


def test_internal_test_flags_present(tables):
    assert tables["dim_device"]["is_internal_test"].dtype == bool
    assert tables["dim_device"]["is_internal_test"].sum() > 0
    assert tables["dim_org"]["is_internal_test"].dtype == bool


def test_views_build_and_return_rows():
    con = duckdb.connect()
    for pq in DATA.glob("*.parquet"):
        con.execute(f"CREATE TABLE {pq.stem} AS SELECT * FROM read_parquet('{pq.as_posix()}')")
    con.execute(SQL.read_text(encoding="utf-8"))
    assert con.execute("SELECT COUNT(*) FROM v_device_360").fetchone()[0] == len(pd.read_parquet(DATA / "dim_device.parquet"))
    assert con.execute("SELECT COUNT(*) FROM v_anomaly_device_day").fetchone()[0] == 1845
    assert con.execute("SELECT COUNT(DISTINCT org_lifecycle_status) FROM v_org_lifecycle").fetchone()[0] >= 3


def test_known_defects_are_measured(tables):
    df = pd.DataFrame([c.row() for c in quality.defect_checks(tables)])
    assert (df["denominator"] >= 0).all() and (df["numerator"] >= 0).all()
    # the defects the data dictionary documents must still be observable
    expect = {"return_before_activation", "expired_but_active", "license_shared_by_multiple_accounts", "country_spelling_variants"}
    assert expect <= set(df["check"])
