"""Build the public, de-identified Parquet tables from the raw exports.

Usage:
    TDF_DEID_KEY_FILE=/path/to/key python -m tdf.build --raw-dir /path/to/raw --out data/public

Raw files are the DMS / app back-office / CRM exports described in
data/public/DATA_DICTIONARY.md. They are never committed. Every table below
documents what is kept, what is pseudonymized and what is dropped.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .deid import (
    PLACEHOLDER_DRIVER,
    PLACEHOLDER_TRAILER,
    PLACEHOLDER_VIN,
    Pseudonymizer,
    clean_country,
    clean_dot,
    clean_state,
    coarsen_coordinate,
    extract_dot,
    normalize_org_name,
    to_datetime,
    to_number,
)

SNAPSHOT_DATE = "2026-09-28"

RAW_FILES = {
    "device_list": "ED-01_device_list_2026-09-28.csv",
    "sim_list": "ED-02_sim_list_2026-09-28.csv",
    "sim_topup": "ED-03_sim_topup_2026-09.csv",
    "sim_usage": "ED-04_sim_traffic_2026-09-27.csv",
    "field_anomaly": "ED-05_eld_field_anomaly_2026-09-28.zip",
    "vehicle": "ED-11_vehicle_2026-09-28.csv",
    "driver": "ED-12_driver_2026-09-28.csv",
    "company": "ED-13_company_2026-09-28.xlsx",
    "org_list": "ED-14_excelOrgList_crm.xlsx",
    "contracts": "ED-15_excelVehicleList_contracts.xlsx",
    "driving_month": "ED-16_driving_monthly_report_2026-09.xlsx",
    "anomaly_3day": "ED-18_3day_anomaly_summary.csv",
    "anomaly_daily": "ED-19_3day_anomaly_daily_trend.csv",
}

# Organisation names that denote internal / test accounts. The vendor's own
# company name is supplied privately via TDF_INTERNAL_ORG_EXTRA (regex) so it
# never appears in the public code.
_extra = __import__("os").environ.get("TDF_INTERNAL_ORG_EXTRA", "")
INTERNAL_ORG_PATTERN = re.compile(r"^(1111|empty|delete|wrong|test\b|testing\b" + (f"|{_extra}" if _extra else "") + ")", re.I)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def read_raw(raw_dir: Path, key: str) -> pd.DataFrame:
    path = raw_dir / RAW_FILES[key]
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            member = [m for m in z.namelist() if m.lower().endswith(".csv")][0]
            return pd.read_csv(io.BytesIO(z.read(member)), low_memory=False)
    if path.suffix == ".xlsx":
        return pd.read_excel(path)
    return pd.read_csv(path, low_memory=False)


def org_group(series: pd.Series) -> pd.Series:
    """'Vendor / Site / RT64' -> 'RT64'. The vendor and site names are dropped."""
    return series.astype(str).str.split("/").str[-1].str.strip().replace({"nan": None, "-": None})


def flag_internal_org(norm_name: pd.Series) -> pd.Series:
    return norm_name.fillna("").map(lambda s: bool(INTERNAL_ORG_PATTERN.search(s)))


# ---------------------------------------------------------------------------
# table builders
# ---------------------------------------------------------------------------

def build_dim_device(raw: pd.DataFrame, p: Pseudonymizer) -> pd.DataFrame:
    d = pd.DataFrame()
    d["device_key"] = p.series(raw["Serial Number"], "device", "DEV-")
    d["org_group"] = org_group(raw["Organization"])
    d["is_internal_test"] = d["org_group"].fillna("").str.contains("test", case=False)
    d["model_code"] = raw["Model Code"].astype(str).str.strip()
    d["hw_version"] = raw["ELD Hardware Version"].replace("-", np.nan)
    d["fw_version"] = raw["ELD Firmware Version"].replace("-", np.nan)
    d["st_fw_version"] = raw["ST Firmware Version"].replace("-", np.nan)
    d["ble_fw_version"] = raw["BLE Firmware Version"].replace("-", np.nan)
    d["vin_key"] = p.series(raw["VIN ID"], "vin", "VIN-", placeholders=PLACEHOLDER_VIN)
    d["is_placeholder_vin"] = raw["VIN ID"].astype(str).str.strip().str.upper().isin(PLACEHOLDER_VIN)
    d["driver_key"] = p.series(raw["Driver ID"], "driver_uid", "DRV-", normalize=lambda x: str(x).strip(), placeholders=PLACEHOLDER_DRIVER)
    d["has_trailer_gps"] = ~raw["Trailer GPS"].astype(str).str.strip().str.upper().isin(PLACEHOLDER_TRAILER | {"-"})
    vm = raw["Vehicle model / year"].astype(str).str.strip().replace("-", np.nan)
    d["vehicle_make"] = vm.str.split("/").str[0].str.strip()
    d["vehicle_year"] = pd.to_numeric(vm.str.split("/").str[-1].str.strip(), errors="coerce")
    d["engine_hours"] = to_number(raw["Engine Hours"])
    d["engine_miles"] = to_number(raw["Engine Miles"])
    d["engine_km"] = to_number(raw["Engine KM"])
    d["device_temp_c"] = to_number(raw["Device Temperature"])
    d["rpm"] = to_number(raw["RPM"])
    d["speed_kmh"] = to_number(raw["Speed"])
    d["gps_speed_kmh"] = to_number(raw["GPS Speed"])
    d["lat_coarse"] = raw["Latitude"].map(coarsen_coordinate)
    d["lon_coarse"] = raw["Longitude"].map(coarsen_coordinate)
    d["timezone_offset"] = raw["Time Zone"].replace("-", np.nan)
    d["report_ts"] = to_datetime(raw["Time Stamp"])
    d["backup_battery_pct"] = to_number(raw["Backup Battery"])
    d["car_battery_connected"] = raw["Car Battery Voltage"].map({"Yes": True, "No": False})
    d["mode"] = raw["Mode"].replace("-", np.nan)
    d["disk_used_pct"] = to_number(raw["Disk Size"])
    d["mileage_source_sa"] = raw["Mileage Source (SA)"].replace("-", np.nan)
    d["gps_valid"] = raw["GPS Valid"].map({"1": True, "0": False, 1: True, 0: False})
    d["connect_status"] = raw["Connect Status"]
    d["connect_ts"] = to_datetime(raw["Connect Time"])
    d["remaining_data_mb"] = to_number(raw["Remaining Data"])
    d["last_updated_ts"] = to_datetime(raw["Last Updated Time"])
    d["created_ts"] = to_datetime(raw["Created At"])
    d["updated_ts"] = to_datetime(raw["Updated At"])
    d["last_event_type"] = raw["Event Type"].replace("-", np.nan)
    d["never_reported"] = raw["ELD Hardware Version"].astype(str).str.strip().eq("-")
    return d


def build_dim_sim(raw: pd.DataFrame, p: Pseudonymizer) -> pd.DataFrame:
    d = pd.DataFrame()
    d["device_key"] = p.series(raw["Serial No."], "device", "DEV-")
    d["org_group"] = org_group(raw["Organization"])
    d["sim_service_status"] = raw["SIM / Service Status"]
    d["quota_status"] = raw["Quota Status"]
    d["remaining_data_mb"] = to_number(raw["Remaining Data"])
    d["remaining_days"] = to_number(raw["Remaining Days"])
    d["expiry_date"] = to_datetime(raw["Expiry Date"])
    d["last_updated_ts"] = to_datetime(raw["Last Updated"])
    return d


def build_fact_sim_topup(raw: pd.DataFrame, p: Pseudonymizer) -> pd.DataFrame:
    d = pd.DataFrame()
    d["device_key"] = p.series(raw["Serial No."], "device", "DEV-")
    d["org_group"] = org_group(raw["Organization"])
    d["plan"] = raw["Plan"]
    d["operator_key"] = p.series(raw["Applicant"], "staff", "STF-")
    d["topup_ts"] = to_datetime(raw["Top-up Time"])
    d["status"] = raw["Status"]
    return d


def build_fact_sim_usage(raw: pd.DataFrame, p: Pseudonymizer) -> pd.DataFrame:
    d = pd.DataFrame()
    d["device_key"] = p.series(raw["Serial No."], "device", "DEV-")
    d["org_group"] = org_group(raw["Organization"])
    d["usage_ts"] = to_datetime(raw["Usage Time"])
    d["used_mb"] = to_number(raw["Used"])
    d["source"] = raw["Source"]
    d["sync_ts"] = to_datetime(raw["Sync Time"])
    return d


def build_fact_field_anomaly(raw: pd.DataFrame, p: Pseudonymizer) -> pd.DataFrame:
    d = pd.DataFrame()
    d["report_date"] = to_datetime(raw["Date"]).dt.date
    d["report_ts"] = to_datetime(raw["Time Stamp"])
    d["org_group"] = org_group(raw["Organization"])
    d["device_key"] = p.series(raw["Serial Number"], "device", "DEV-")
    d["driver_key"] = p.series(raw["Driver ID"], "driver_uid", "DRV-", normalize=lambda x: str(x).strip(), placeholders=PLACEHOLDER_DRIVER)
    d["vin_key"] = p.series(raw["VIN"], "vin", "VIN-", placeholders=PLACEHOLDER_VIN)
    d["is_placeholder_vin"] = raw["VIN"].astype(str).str.strip().str.upper().isin(PLACEHOLDER_VIN)
    d["speed_kmh"] = to_number(raw["Speed"])
    d["rpm"] = to_number(raw["RPM"])
    d["engine_hours"] = to_number(raw["Engine Hours"])
    d["engine_miles"] = to_number(raw["Engine Miles"])
    d["car_battery_connected"] = raw["Car Battery Voltage"].map({"Yes": True, "No": False})
    d["gps_speed_kmh"] = to_number(raw["GPS Speed"])
    d["lat_coarse"] = raw["Latitude"].map(coarsen_coordinate)
    d["lon_coarse"] = raw["Longitude"].map(coarsen_coordinate)
    for src, dst in [
        ("VIN Anomaly", "vin_anomaly"),
        ("Speed Anomaly", "speed_anomaly"),
        ("RPM Anomaly", "rpm_anomaly"),
        ("Engine Hours Anomaly", "engine_hours_anomaly"),
        ("Engine Miles Anomaly", "engine_miles_anomaly"),
    ]:
        d[dst] = raw[src].astype(str).str.strip().eq("Anomaly")
    return d


def build_dim_vehicle(raw: pd.DataFrame, p: Pseudonymizer) -> pd.DataFrame:
    d = pd.DataFrame()
    d["vin_key"] = p.series(raw["VIN"], "vin", "VIN-", placeholders=PLACEHOLDER_VIN)
    d["is_placeholder_vin"] = raw["VIN"].astype(str).str.strip().str.upper().isin(PLACEHOLDER_VIN)
    norm = raw["Company"].map(normalize_org_name)
    d["org_key"] = p.series(norm, "org", "ORG-", normalize=lambda x: x)
    d["is_internal_test"] = flag_internal_org(norm)
    d["device_key"] = p.series(raw["ELD Serial"], "device", "DEV-")
    d["driver_assigned"] = ~raw["Driver"].astype(str).str.strip().isin(["-", "", "nan"])
    d["make"] = raw["Make"].replace("-", np.nan)
    d["model"] = raw["Model"].replace("-", np.nan)
    d["model_year"] = pd.to_numeric(raw["Year"], errors="coerce")
    d["fuel_type"] = raw["Fuel Type"].replace("-", np.nan)
    d["state_raw"] = raw["State / Province"].replace("-", np.nan)
    d["state"] = raw["State / Province"].map(clean_state)
    d["country_raw"] = raw["Country"].replace("-", np.nan)
    d["country"] = raw["Country"].map(clean_country)
    d["terminal_timezone"] = raw["Terminal Timezone"].replace("-", np.nan)
    d["odometer_adjustment"] = to_number(raw["Odometer Adjustment"])
    d["status"] = raw["Status"]
    d["last_synced_ts"] = to_datetime(raw["Last Synced At"])
    return d


def build_dim_driver_account(raw: pd.DataFrame, p: Pseudonymizer) -> pd.DataFrame:
    d = pd.DataFrame()
    d["account_key"] = p.series(raw["Username (Email)"], "account_email", "USR-", normalize=lambda x: str(x).strip().lower())
    norm = raw["Company"].map(normalize_org_name)
    d["org_key"] = p.series(norm, "org", "ORG-", normalize=lambda x: x)
    d["is_internal_test"] = flag_internal_org(norm)
    d["license_state"] = raw["License Issue State"].map(clean_state)
    lic = raw["License Number"].astype(str).str.strip().str.upper().replace({"-": np.nan, "": np.nan, "NAN": np.nan})
    counts = lic.map(lic.value_counts())
    d["license_shared_by_n_accounts"] = counts.where(lic.notna()).astype("float64")
    d["status"] = raw["Status"]
    d["country_raw"] = raw["Country"].replace("-", np.nan)
    d["last_synced_ts"] = to_datetime(raw["Last Synced At"])
    return d


def build_dim_org(org_list: pd.DataFrame, company: pd.DataFrame, contracts: pd.DataFrame, p: Pseudonymizer) -> pd.DataFrame:
    # CRM organization list (historical, includes inactive)
    crm = pd.DataFrame()
    crm_norm = org_list["Name"].map(normalize_org_name)
    crm["org_key"] = p.series(crm_norm, "org", "ORG-", normalize=lambda x: x)
    crm["is_internal_test"] = flag_internal_org(crm_norm)
    crm["crm_active"] = org_list["Active"].astype(str).str.upper().eq("Y")
    crm["state_raw"] = org_list["State"]
    crm["state"] = org_list["State"].map(clean_state)
    dot = org_list["DOT#"].map(clean_dot)
    crm["dot_key"] = p.series(dot, "dot", "DOT-", normalize=lambda x: str(x))
    crm["has_dot"] = dot.notna()
    email = org_list["Email"].astype(str).str.strip().str.lower()
    domain = email.str.extract(r"@([\w.-]+)$")[0]
    free = domain.isin({"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "icloud.com", "msn.com", "live.com"})
    crm["email_is_free_domain"] = free.where(domain.notna())
    crm["crm_account_limit"] = to_number(org_list["Account Limits"])
    crm["crm_vehicle_limit"] = to_number(org_list["Vehicle Limits"])
    crm["is_reseller"] = org_list["Reseller"].astype(str).str.upper().eq("Y")
    crm["sales_rep_key"] = p.series(org_list["Sales"], "sales", "REP-", normalize=lambda x: str(x).strip().lower())
    crm = crm.drop_duplicates("org_key")

    # app back-office company master (current)
    app = pd.DataFrame()
    app_norm = company["Company Name"].map(normalize_org_name)
    app["org_key"] = p.series(app_norm, "org", "ORG-", normalize=lambda x: x)
    app["app_fleet_vehicles"] = to_number(company["Fleet Vehicles"])
    app["app_vehicle_limit"] = to_number(company["Vehicle Limit"])
    app = app.drop_duplicates("org_key")

    crm["in_crm"] = True
    app["in_app"] = True
    out = crm.merge(app, on="org_key", how="outer")

    # contract-derived lifecycle fields (as of the snapshot date)
    c = contracts
    if len(c):
        snap = pd.Timestamp(SNAPSHOT_DATE)
        g = c.groupby("org_key").agg(
            contract_rows=("contract_row_id", "size"),
            contract_rows_active=("status", lambda s: (s == "active").sum()),
            vehicles_ever=("vin_key", "nunique"),
            first_activation=("activation_date", "min"),
            last_expiration=("expiration_date", "max"),
        ).reset_index()
        g["org_lifecycle_status"] = np.select(
            [
                g["contract_rows_active"] > 0,
                g["last_expiration"].notna() & (g["last_expiration"] < snap),
                g["last_expiration"].notna() & (g["last_expiration"] >= snap),
            ],
            ["active", "lapsed", "inactive_not_expired"],
            default="no_dates",
        )
        g["tenure_days"] = (g["last_expiration"].clip(upper=snap) - g["first_activation"]).dt.days
        out = out.merge(g, on="org_key", how="outer")
        out["in_contracts"] = out["contract_rows"].notna()
    for col in ("in_crm", "in_app", "is_internal_test", "is_reseller"):
        out[col] = out[col].map(lambda v: bool(v) if v is not None and not (isinstance(v, float) and np.isnan(v)) else False).astype(bool)
    return out


def build_fact_contract(raw: pd.DataFrame, p: Pseudonymizer) -> pd.DataFrame:
    d = pd.DataFrame()
    d["contract_row_id"] = np.arange(1, len(raw) + 1)
    norm = raw["Org Name(DOT#)"].map(normalize_org_name)
    d["org_key"] = p.series(norm, "org", "ORG-", normalize=lambda x: x)
    d["is_internal_test"] = flag_internal_org(norm)
    dot = raw["Org Name(DOT#)"].map(extract_dot)
    d["dot_key"] = p.series(dot, "dot", "DOT-", normalize=lambda x: str(x))
    d["vin_key"] = p.series(raw["VIN"], "vin", "VIN-", placeholders=PLACEHOLDER_VIN)
    d["eld_type"] = raw["ELD Type"].astype(str).str.strip().str.lower().replace({"nan": np.nan, "-": np.nan})
    d["device_key"] = p.series(raw["ELD SN."], "device", "DEV-")
    d["prev_device_key"] = p.series(raw["Previous ELD"], "device", "DEV-")
    d["make"] = raw["Make"].astype(str).str.strip().replace({"nan": np.nan, "-": np.nan})
    d["model_year"] = pd.to_numeric(raw["Year"], errors="coerce")
    d["status"] = raw["Status"].astype(str).str.strip().str.lower().replace({"nan": np.nan})
    d["contract_date"] = to_datetime(raw["Contract Date"])
    d["activation_date"] = to_datetime(raw["Activation Date"])
    d["expiration_date"] = to_datetime(raw["Expiration Date"])
    d["return_date"] = to_datetime(raw["Return Date"])
    d["vehicle_limit"] = to_number(raw["Vehicle Limit"])
    d["sales_rep_key"] = p.series(raw["Sales"], "sales", "REP-", normalize=lambda x: str(x).strip().lower())
    return d


def build_fact_anomaly_device_3day(raw: pd.DataFrame, p: Pseudonymizer) -> pd.DataFrame:
    """Three-day anomaly summary (23-25 Sep 2026).

    The source workbook has localized (non-English) column headers. They are
    mapped by position, which is stable for this export: 27 columns in the
    order documented in data/public/DATA_DICTIONARY.md.
    """
    expected = 27
    if raw.shape[1] != expected:
        raise ValueError(f"3-day summary: expected {expected} columns, got {raw.shape[1]}")
    names = [
        "serial", "organization", "days_present", "n_records",
        "vin_missing_n", "vin_missing_pct", "speed_na_n", "speed_na_pct", "rpm_na_n", "rpm_na_pct",
        "all_three_missing_n",
        "d0923_n_records", "d0923_vin_missing_n", "d0923_speed_na_n", "d0923_rpm_na_n",
        "d0924_n_records", "d0924_vin_missing_n", "d0924_speed_na_n", "d0924_rpm_na_n",
        "d0925_n_records", "d0925_vin_missing_n", "d0925_speed_na_n", "d0925_rpm_na_n",
        "first_seen_ts", "last_seen_ts", "last_valid_vin", "last_valid_vin_ts",
    ]
    raw = raw.copy()
    raw.columns = names
    d = pd.DataFrame()
    d["device_key"] = p.series(raw["serial"], "device", "DEV-")
    d["org_group"] = org_group(raw["organization"])
    for col in names[2:]:
        if col in ("serial", "organization", "last_valid_vin"):
            continue
        d[col] = to_datetime(raw[col]) if col.endswith("_ts") else to_number(raw[col])
    d["last_valid_vin_key"] = p.series(raw["last_valid_vin"], "vin", "VIN-", placeholders=PLACEHOLDER_VIN)
    return d


def build_fact_anomaly_daily(raw: pd.DataFrame) -> pd.DataFrame:
    """Daily totals for the three-day window; localized headers mapped by position."""
    names = ["report_date", "n_records", "devices_affected", "vin_missing_devices", "vin_missing_n",
             "speed_na_devices", "speed_na_n", "rpm_na_devices", "rpm_na_n", "all_three_missing_n"]
    if raw.shape[1] != len(names):
        raise ValueError(f"daily trend: expected {len(names)} columns, got {raw.shape[1]}")
    raw = raw.copy()
    raw.columns = names
    d = pd.DataFrame()
    d["report_date"] = to_datetime(raw["report_date"]).dt.date
    for col in names[1:]:
        d[col] = to_number(raw[col])
    return d


def build_fact_driving_day_sample(raw: pd.DataFrame) -> pd.DataFrame:
    d = pd.DataFrame()
    d["report_date"] = to_datetime(raw["Date"]).dt.date
    hrs = raw["DR (hours)"].astype(str).str.strip()
    def hh(v):
        m = re.match(r"^(\d+):(\d+)", v)
        if m:
            return int(m.group(1)) + int(m.group(2)) / 60
        try:
            return float(v)
        except ValueError:
            return np.nan
    d["driving_hours"] = hrs.map(hh)
    d["daily_mileage"] = to_number(raw["Daily Mileage"])
    d["start_engine_miles"] = to_number(raw["Start Engine Miles"])
    d["end_engine_miles"] = to_number(raw["End Engine Miles"])
    d["start_engine_km"] = to_number(raw["Start Engine KM"])
    d["end_engine_km"] = to_number(raw["End Engine KM"])
    d["has_start_location"] = ~raw["Start Location (Lat/Lng)"].astype(str).str.strip().isin(["-", "", "nan"])
    d["has_end_location"] = ~raw["End Location (Lat/Lng)"].astype(str).str.strip().isin(["-", "", "nan"])
    return d


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------

def build_all(raw_dir: Path, out_dir: Path, key_file: Path) -> dict:
    p = Pseudonymizer.from_file(key_file)
    out_dir.mkdir(parents=True, exist_ok=True)
    tables: dict[str, pd.DataFrame] = {}

    tables["fact_contract"] = build_fact_contract(read_raw(raw_dir, "contracts"), p)
    tables["dim_org"] = build_dim_org(read_raw(raw_dir, "org_list"), read_raw(raw_dir, "company"), tables["fact_contract"], p)
    tables["dim_device"] = build_dim_device(read_raw(raw_dir, "device_list"), p)
    tables["dim_sim"] = build_dim_sim(read_raw(raw_dir, "sim_list"), p)
    tables["fact_sim_topup"] = build_fact_sim_topup(read_raw(raw_dir, "sim_topup"), p)
    tables["fact_sim_usage"] = build_fact_sim_usage(read_raw(raw_dir, "sim_usage"), p)
    tables["fact_field_anomaly"] = build_fact_field_anomaly(read_raw(raw_dir, "field_anomaly"), p)
    tables["dim_vehicle"] = build_dim_vehicle(read_raw(raw_dir, "vehicle"), p)
    tables["dim_driver_account"] = build_dim_driver_account(read_raw(raw_dir, "driver"), p)
    tables["fact_anomaly_device_3day"] = build_fact_anomaly_device_3day(read_raw(raw_dir, "anomaly_3day"), p)
    tables["fact_anomaly_daily"] = build_fact_anomaly_daily(read_raw(raw_dir, "anomaly_daily"))
    tables["fact_driving_day_sample"] = build_fact_driving_day_sample(read_raw(raw_dir, "driving_month"))

    manifest = {"built_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "snapshot_date": SNAPSHOT_DATE, "tables": {}}
    for name, df in tables.items():
        path = out_dir / f"{name}.parquet"
        df.to_parquet(path, index=False)
        manifest["tables"][name] = {"rows": int(len(df)), "columns": list(df.columns), "file": path.name}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw-dir", required=True, type=Path)
    ap.add_argument("--out", default=Path("data/public"), type=Path)
    ap.add_argument("--key-file", type=Path, default=None, help="defaults to $TDF_DEID_KEY_FILE")
    args = ap.parse_args(argv)
    key_file = args.key_file or Path(__import__("os").environ["TDF_DEID_KEY_FILE"])
    manifest = build_all(args.raw_dir, args.out, key_file)
    for name, meta in manifest["tables"].items():
        print(f"{name:28s} {meta['rows']:>8,} rows  {len(meta['columns']):>3} cols")


if __name__ == "__main__":
    main()
