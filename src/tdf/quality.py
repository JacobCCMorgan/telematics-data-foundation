"""Data-quality checks on the public tables.

Each check returns a row: (table, check, numerator, denominator, rate, note).
The report is written as Markdown so the numbers in the README can be traced
back to a reproducible computation.

    python -m tdf.quality --data data/public --out reports/data_quality_report.md
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import pandas as pd

SNAPSHOT = pd.Timestamp("2026-09-28")

LEAK_PATTERNS = {
    "raw_device_serial": re.compile(r"^RT\d{8}$"),
    "raw_vin": re.compile(r"^[A-HJ-NPR-Z0-9]{17}$"),
    "raw_imei_or_iccid": re.compile(r"^\d{15,20}$"),
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "phone": re.compile(r"\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}"),
}


@dataclass
class Check:
    table: str
    check: str
    numerator: int
    denominator: int
    note: str = ""

    @property
    def rate(self) -> float | None:
        return None if self.denominator == 0 else self.numerator / self.denominator

    def row(self) -> dict:
        d = asdict(self)
        d["rate"] = None if self.rate is None else round(self.rate, 4)
        return d


def load(data_dir: Path) -> dict[str, pd.DataFrame]:
    return {p.stem: pd.read_parquet(p) for p in sorted(data_dir.glob("*.parquet"))}


# ---------------------------------------------------------------------------
# leakage
# ---------------------------------------------------------------------------

def leakage_checks(tables: dict[str, pd.DataFrame]) -> list[Check]:
    out = []
    for name, df in tables.items():
        for col in df.columns:
            s = df[col]
            if s.dtype != object and not pd.api.types.is_string_dtype(s):
                continue
            vals = s.dropna().astype(str)
            if vals.empty:
                continue
            for label, pat in LEAK_PATTERNS.items():
                hits = int(vals.map(lambda v: bool(pat.search(v))).sum())
                if hits:
                    out.append(Check(name, f"leak:{label}:{col}", hits, len(vals), "identifier-looking value present"))
    if not out:
        out.append(Check("*", "leak:none_detected", 0, 1, "no raw serials, VINs, IMEIs/ICCIDs, e-mails or phone numbers in any string column"))
    return out


# ---------------------------------------------------------------------------
# referential integrity
# ---------------------------------------------------------------------------

def ri(child: pd.DataFrame, child_col: str, parent: pd.DataFrame, parent_col: str, table: str, label: str, mask=None) -> Check:
    keys = child[child_col] if mask is None else child.loc[mask, child_col]
    keys = keys.dropna()
    ok = keys.isin(set(parent[parent_col].dropna())).sum()
    return Check(table, label, int(ok), int(len(keys)), "matched / non-null keys")


def integrity_checks(t: dict[str, pd.DataFrame]) -> list[Check]:
    out = [
        ri(t["dim_vehicle"], "device_key", t["dim_device"], "device_key", "dim_vehicle", "ri:vehicle.device_key->dim_device"),
        ri(t["dim_vehicle"], "org_key", t["dim_org"], "org_key", "dim_vehicle", "ri:vehicle.org_key->dim_org"),
        ri(t["dim_driver_account"], "org_key", t["dim_org"], "org_key", "dim_driver_account", "ri:driver_account.org_key->dim_org"),
        ri(t["dim_sim"], "device_key", t["dim_device"], "device_key", "dim_sim", "ri:sim.device_key->dim_device"),
        ri(t["fact_field_anomaly"], "device_key", t["dim_device"], "device_key", "fact_field_anomaly", "ri:anomaly.device_key->dim_device"),
        ri(t["fact_anomaly_device_3day"], "device_key", t["dim_device"], "device_key", "fact_anomaly_device_3day", "ri:anomaly3day.device_key->dim_device"),
        ri(t["fact_contract"], "org_key", t["dim_org"], "org_key", "fact_contract", "ri:contract.org_key->dim_org"),
        ri(t["fact_contract"], "device_key", t["dim_device"], "device_key", "fact_contract", "ri:contract.device_key->dim_device (current-generation rows only)", mask=t["fact_contract"]["eld_type"].eq("rtha55")),
        ri(t["fact_sim_topup"], "device_key", t["dim_device"], "device_key", "fact_sim_topup", "ri:topup.device_key->dim_device"),
    ]
    # VIN overlap between the DMS snapshot and the app vehicle master
    dev_vins = set(t["dim_device"]["vin_key"].dropna())
    veh_vins = set(t["dim_vehicle"]["vin_key"].dropna())
    out.append(Check("dim_device", "ri:device.vin_key->dim_vehicle", len(dev_vins & veh_vins), len(dev_vins), "real VINs seen by devices that exist in the vehicle master"))
    return out


# ---------------------------------------------------------------------------
# known defects
# ---------------------------------------------------------------------------

def defect_checks(t: dict[str, pd.DataFrame]) -> list[Check]:
    out = []
    dev, veh, drv, org, con = t["dim_device"], t["dim_vehicle"], t["dim_driver_account"], t["dim_org"], t["fact_contract"]

    # vehicle master
    out.append(Check("dim_vehicle", "country_spelling_variants", int(veh["country_raw"].dropna().nunique()), 0, "count of distinct raw spellings of the country field (no rate)"))
    out.append(Check("dim_vehicle", "country_not_mappable", int(veh["country"].isna().sum()), len(veh), "rows whose country could not be normalised"))
    out.append(Check("dim_vehicle", "state_not_mappable", int(veh["state"].isna().sum()), len(veh), "rows whose state could not be normalised to USPS codes"))
    bad_year = ~veh["model_year"].between(1980, 2027)
    out.append(Check("dim_vehicle", "model_year_out_of_range", int((bad_year & veh["model_year"].notna()).sum()), int(veh["model_year"].notna().sum()), "model year outside 1980-2027"))
    out.append(Check("dim_vehicle", "placeholder_vin", int(veh["is_placeholder_vin"].sum()), len(veh), "VIN still 'not yet detected' in the vehicle master"))
    out.append(Check("dim_vehicle", "device_key_missing", int(veh["device_key"].isna().sum()), len(veh), "vehicles without an ELD serial"))

    # device snapshot
    reported = dev[~dev["never_reported"]]
    out.append(Check("dim_device", "never_reported", int(dev["never_reported"].sum()), len(dev), "devices with no telemetry at all (shipping / inventory)"))
    out.append(Check("dim_device", "placeholder_vin_among_reporting", int(reported["is_placeholder_vin"].sum()), len(reported), "reporting devices whose VIN was not yet read from the ECM"))
    out.append(Check("dim_device", "engine_miles_gt_2M", int((reported["engine_miles"] > 2_000_000).sum()), int(reported["engine_miles"].notna().sum()), "implausible odometer readings"))
    out.append(Check("dim_device", "engine_hours_gt_100k", int((reported["engine_hours"] > 100_000).sum()), int(reported["engine_hours"].notna().sum()), "implausible engine-hour readings"))
    out.append(Check("dim_device", "speed_gt_200kmh", int((reported["speed_kmh"] > 200).sum()), int(reported["speed_kmh"].notna().sum()), "implausible ECM speed"))
    out.append(Check("dim_device", "vehicle_year_lt_1990", int((reported["vehicle_year"] < 1990).sum()), int(reported["vehicle_year"].notna().sum()), "implausible model year on the device record"))
    out.append(Check("dim_device", "dtc_column_populated", 0, len(dev), "the DTC / pedal / transmission columns are entirely blank in this export"))

    # driver accounts
    shared = drv["license_shared_by_n_accounts"]
    out.append(Check("dim_driver_account", "license_shared_by_multiple_accounts", int((shared > 1).sum()), int(shared.notna().sum()), "accounts whose licence number also appears on another account"))
    groups = float((1.0 / shared[shared > 1]).sum()) if (shared > 1).any() else 0.0
    out.append(Check("dim_driver_account", "license_groups_shared", int(round(groups)), int(shared.notna().sum()), "distinct licence numbers that appear on more than one account"))
    out.append(Check("dim_driver_account", "country_blank_or_variant", int(drv["country_raw"].isna().sum()), len(drv), "country blank in the driver master"))

    # CRM org list
    out.append(Check("dim_org", "crm_account_limit_negative", int((org["crm_account_limit"] < 0).sum()), int(org["crm_account_limit"].notna().sum()), "negative account limits"))
    out.append(Check("dim_org", "crm_vehicle_limit_negative_or_gt_500", int(((org["crm_vehicle_limit"] < 0) | (org["crm_vehicle_limit"] > 500)).sum()), int(org["crm_vehicle_limit"].notna().sum()), "vehicle limits outside 0-500"))
    out.append(Check("dim_org", "state_not_mappable", int((org["state"].isna() & org["state_raw"].notna()).sum()), int(org["state_raw"].notna().sum()), "CRM state values that do not map to a USPS code"))
    out.append(Check("dim_org", "internal_or_test_orgs", int(org["is_internal_test"].sum()), len(org), "organisation names that look like internal/test accounts"))
    out.append(Check("dim_org", "in_crm_not_in_app", int((org["in_crm"] & ~org["in_app"]).sum()), int(org["in_crm"].sum()), "historical CRM orgs absent from the current app master"))
    out.append(Check("dim_org", "in_app_not_in_crm", int((org["in_app"] & ~org["in_crm"]).sum()), int(org["in_app"].sum()), "app orgs whose normalised name is not in the CRM list"))

    # contracts
    out.append(Check("fact_contract", "return_before_activation", int((con["return_date"] < con["activation_date"]).sum()), int((con["return_date"].notna() & con["activation_date"].notna()).sum()), "return date earlier than activation date"))
    out.append(Check("fact_contract", "expired_but_active", int((con["status"].eq("active") & (con["expiration_date"] < SNAPSHOT)).sum()), int(con["status"].eq("active").sum()), "active rows whose expiration date is already past"))
    out.append(Check("fact_contract", "model_year_out_of_range", int((~con["model_year"].between(1980, 2027) & con["model_year"].notna()).sum()), int(con["model_year"].notna().sum()), "e.g. 125, 2917"))
    out.append(Check("fact_contract", "contract_date_unparseable_or_missing", int(con["contract_date"].isna().sum()), len(con), "blank or unparseable contract dates (e.g. year 0021 in the raw export)"))
    out.append(Check("fact_contract", "eld_type_invalid", int(con["eld_type"].isin(["123456"]).sum()), int(con["eld_type"].notna().sum()), "placeholder product code"))
    out.append(Check("fact_contract", "activation_after_snapshot", int((con["activation_date"] > SNAPSHOT).sum()), int(con["activation_date"].notna().sum()), "activation dates later than the export date (pre-registered)"))
    out.append(Check("fact_contract", "status_missing", int(con["status"].isna().sum()), len(con), ""))
    out.append(Check("fact_contract", "vin_missing", int(con["vin_key"].isna().sum()), len(con), ""))
    span = (con["expiration_date"] - con["activation_date"]).dt.days
    out.append(Check("fact_contract", "term_exactly_365_days", int((span == 365).sum()), int(span.notna().sum()), "activation -> expiration spans of exactly one year"))

    # single-vehicle daily report
    dd = t["fact_driving_day_sample"]
    out.append(Check("fact_driving_day_sample", "daily_mileage_equals_cumulative_odometer", int((dd["daily_mileage"] > 100_000).sum()), int(dd["daily_mileage"].notna().sum()), "daily mileage column holds the cumulative odometer"))
    return out


def run_all(data_dir: Path) -> pd.DataFrame:
    t = load(data_dir)
    rows = [c.row() for c in leakage_checks(t) + integrity_checks(t) + defect_checks(t)]
    return pd.DataFrame(rows)


def to_markdown(df: pd.DataFrame, data_dir: Path) -> str:
    lines = ["# Data quality report", "", f"Computed from `{data_dir}` on the de-identified public tables. Rates are numerator / denominator.", ""]
    for section, prefix in [("Leakage (identifier) checks", "leak:"), ("Referential integrity", "ri:"), ("Known defects and anomalies", None)]:
        sub = df[df["check"].str.startswith(prefix)] if prefix else df[~df["check"].str.startswith(("leak:", "ri:"))]
        lines += [f"## {section}", "", "| table | check | n | N | rate | note |", "|---|---|---:|---:|---:|---|"]
        for _, r in sub.iterrows():
            rate = "" if r["rate"] is None or pd.isna(r["rate"]) else f"{r['rate']:.1%}"
            lines.append(f"| {r['table']} | {r['check']} | {r['numerator']:,} | {r['denominator']:,} | {rate} | {r['note']} |")
        lines.append("")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=Path("data/public"), type=Path)
    ap.add_argument("--out", default=Path("reports/data_quality_report.md"), type=Path)
    args = ap.parse_args(argv)
    df = run_all(args.data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(to_markdown(df, args.data), encoding="utf-8")
    df.to_csv(args.out.with_suffix(".csv"), index=False)
    print(df.to_string(index=False, max_colwidth=60))


if __name__ == "__main__":
    main()
