"""Generate data/public/DATA_DICTIONARY.md from the Parquet schemas plus the
column descriptions below. Run after every rebuild.

    python scripts/make_data_dictionary.py --data data/public
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

TABLES = {
    "dim_device": ("One row per ELD unit in the device-management system (DMS) snapshot taken 2026-09-28.", "device_key"),
    "dim_sim": ("One row per SIM, joined to its device by serial.", "device_key"),
    "dim_vehicle": ("One row per vehicle in the driver-app back office (current state).", "vin_key (+ device_key)"),
    "dim_driver_account": ("One row per driver login account in the app back office. Not linkable to telemetry driver_key (different identifier spaces).", "account_key"),
    "dim_org": ("One row per customer organisation, merged from the CRM list, the app company master and the contract history.", "org_key"),
    "fact_contract": ("One row per contract / device assignment record, 2019–2026 (CRM export).", "contract_row_id"),
    "fact_field_anomaly": ("One row per telemetry report flagged by the DMS field-anomaly rules on 2026-09-28 (only reports with at least one anomaly).", "device_key + report_ts"),
    "fact_anomaly_device_3day": ("One row per device flagged on 23–25 Sep 2026 under the condition 'car battery connected and GPS speed > 0'.", "device_key"),
    "fact_anomaly_daily": ("Daily totals for the 23–25 Sep window.", "report_date"),
    "fact_sim_topup": ("Manual SIM top-ups during September 2026.", "device_key + topup_ts"),
    "fact_sim_usage": ("Previous-day SIM usage detail (one day).", "device_key + usage_ts"),
    "fact_driving_day_sample": ("Daily driving summary for a single vehicle, September 2026 — kept as a data-quality example (the daily-mileage column holds the cumulative odometer).", "report_date"),
}

COLS = {
    # keys
    "device_key": "Pseudonymous ELD serial (HMAC). Same value across all tables.",
    "vin_key": "Pseudonymous VIN (HMAC). Null when the ELD had not yet read a VIN (see is_placeholder_vin).",
    "org_key": "Pseudonymous organisation (HMAC of the normalised company name). Same value across tables.",
    "dot_key": "Pseudonymous USDOT number (HMAC). Lets rows of the same carrier be matched without exposing the number.",
    "driver_key": "Pseudonymous driver identifier from the telemetry stream (HMAC of the app UID). Null when no driver was logged in.",
    "account_key": "Pseudonymous driver login account (HMAC of the e-mail).",
    "sales_rep_key": "Pseudonymous sales representative / channel (HMAC of the CRM sales field).",
    "operator_key": "Pseudonymous internal operator who performed the action.",
    "prev_device_key": "Pseudonymous serial of the device this contract row replaced, when recorded.",
    "last_valid_vin_key": "Pseudonymous VIN last read successfully in the 3-day window.",
    "contract_row_id": "Row number in the contract export (stable within this release).",
    # flags
    "is_internal_test": "True for the vendor's internal test group / test accounts. Exclude for customer metrics.",
    "is_placeholder_vin": "True when the VIN field held the 'not yet detected' placeholder.",
    "never_reported": "True when the device has no telemetry at all (inventory, shipping).",
    "has_trailer_gps": "A trailer GPS tracker is paired with the ELD.",
    "car_battery_connected": "Vehicle battery voltage detected (Yes/No in the source).",
    "gps_valid": "GPS fix valid at the last report.",
    "driver_assigned": "A driver is assigned to the vehicle in the app master.",
    "crm_active": "Active flag in the CRM organisation list.",
    "in_crm": "Organisation present in the CRM organisation list.",
    "in_app": "Organisation present in the app company master.",
    "in_contracts": "Organisation present in the contract history.",
    "is_reseller": "Reseller flag in the CRM.",
    "has_dot": "A USDOT number is recorded in the CRM.",
    "email_is_free_domain": "Contact e-mail uses a free webmail domain (gmail, yahoo, ...). Null when no e-mail.",
    "has_start_location": "A start location was recorded (location itself removed).",
    "has_end_location": "An end location was recorded (location itself removed).",
    # device
    "org_group": "DMS organisation group = shipment batch / special group (RT62–RT67, 'Volvo 2026', 'OBD II', '1708', 'Test Group'). Vendor and site names removed.",
    "model_code": "Hardware model code (EHA554UA/UB/UC).",
    "hw_version": "ELD hardware generation (A, B, C).",
    "fw_version": "ELD firmware version.",
    "st_fw_version": "ST micro-controller firmware version.",
    "ble_fw_version": "Bluetooth module firmware version.",
    "vehicle_make": "Vehicle make as reported by the device record.",
    "vehicle_year": "Vehicle model year as reported by the device record.",
    "engine_hours": "ECM engine hours at the last report.",
    "engine_miles": "ECM odometer (miles) at the last report.",
    "engine_km": "ECM odometer (km) at the last report.",
    "device_temp_c": "Device temperature (°C).",
    "rpm": "Engine RPM at the last report (null when the ECM field was missing).",
    "speed_kmh": "ECM vehicle speed (km/h). Units confirmed as km/h.",
    "gps_speed_kmh": "GPS speed (km/h).",
    "lat_coarse": "Latitude rounded to a 0.05° grid (≈5 km). Null when 0/blank.",
    "lon_coarse": "Longitude rounded to a 0.05° grid (≈5 km). Null when 0/blank.",
    "timezone_offset": "UTC offset reported by the device.",
    "report_ts": "Timestamp of the report (source timezone as exported).",
    "backup_battery_pct": "Backup battery level (%).",
    "mode": "Device state machine mode at last report (Driving, Sleeping, LowBattery, Shipping, Standby, PreOta/ExitOta, Unidentified*...).",
    "disk_used_pct": "Device storage used (%).",
    "mileage_source_sa": "J1939 source address used for mileage (e.g. 23 = engine, 49, 39 ...). Blank when unknown.",
    "connect_status": "Online / Offline at the snapshot.",
    "connect_ts": "Last connection timestamp.",
    "remaining_data_mb": "Remaining SIM data quota (MB).",
    "last_updated_ts": "Last telemetry update timestamp.",
    "created_ts": "Device record creation timestamp.",
    "updated_ts": "Device record update timestamp.",
    "last_event_type": "Last event type recorded on the device record (mostly blank).",
    # sim
    "sim_service_status": "Online / Attached / Offline / Blocked.",
    "quota_status": "Normal / Low Data / Depleted.",
    "remaining_days": "Days until SIM expiry.",
    "expiry_date": "SIM expiry date.",
    "plan": "Top-up plan (500 MB).",
    "topup_ts": "Top-up timestamp.",
    "status": "Status field of the source row (meaning depends on table: contract status, vehicle status, account status, top-up status).",
    "usage_ts": "Usage timestamp.",
    "used_mb": "Data used (MB).",
    "source": "Usage record source (Manual).",
    "sync_ts": "Sync timestamp.",
    # vehicle
    "make": "Vehicle make.",
    "model": "Vehicle model.",
    "model_year": "Vehicle model year.",
    "fuel_type": "Diesel / Gasoline.",
    "state_raw": "State field as exported (free text).",
    "state": "State normalised to USPS two-letter code; null when not mappable.",
    "country_raw": "Country field as exported (shows spelling variants).",
    "country": "Country normalised (US / CA); null when not mappable.",
    "terminal_timezone": "Terminal time zone (IANA).",
    "odometer_adjustment": "Odometer adjustment configured in the app.",
    "last_synced_ts": "Last sync timestamp from the app back office.",
    # driver account
    "license_state": "Licence issuing state (USPS code).",
    "license_shared_by_n_accounts": "How many accounts share this licence number (1 = unique). The number itself is not released.",
    # org
    "crm_account_limit": "Account limit configured in the CRM (contains dirty values).",
    "crm_vehicle_limit": "Vehicle limit configured in the CRM (contains dirty values).",
    "app_fleet_vehicles": "Vehicles registered in the app for this organisation.",
    "app_vehicle_limit": "Vehicle limit in the app.",
    "contract_rows": "Number of contract rows for the organisation.",
    "contract_rows_active": "Contract rows with status 'active'.",
    "vehicles_ever": "Distinct VINs ever contracted by the organisation.",
    "first_activation": "Earliest activation date across the organisation's contract rows.",
    "last_expiration": "Latest expiration date across the organisation's contract rows.",
    "tenure_days": "last_expiration (capped at 2026-09-28) minus first_activation.",
    "org_lifecycle_status": "active (≥1 active row) / lapsed (all expired, none active) / inactive_not_expired / no_dates, as of 2026-09-28.",
    # contract
    "eld_type": "Product generation code (rtps47, rtoa47 → gen 1; rtel47 → gen 2; rtps12, rtsa12 → gen 3; rtha55 → gen 4).",
    "contract_date": "Contract date.",
    "activation_date": "Device activation date.",
    "expiration_date": "Contract expiration date.",
    "return_date": "Device return date, when returned.",
    "vehicle_limit": "Vehicle limit on the contract row.",
    # anomaly
    "report_date": "Calendar date of the report / summary.",
    "engine_hours_anomaly": "Engine-hours field flagged by the rule.",
    "engine_miles_anomaly": "Engine-miles field flagged by the rule.",
    "vin_anomaly": "VIN field flagged (placeholder / unreadable).",
    "speed_anomaly": "Speed field flagged (missing while moving).",
    "rpm_anomaly": "RPM field flagged (missing while moving).",
    "days_present": "Days (of 3) the device appeared under the condition.",
    "n_records": "Reports under the condition.",
    "vin_missing_n": "Reports with VIN missing.", "vin_missing_pct": "Share of reports with VIN missing (%).",
    "speed_na_n": "Reports with Speed N/A.", "speed_na_pct": "Share of reports with Speed N/A (%).",
    "rpm_na_n": "Reports with RPM N/A.", "rpm_na_pct": "Share of reports with RPM N/A (%).",
    "all_three_missing_n": "Reports with VIN, Speed and RPM all missing.",
    "first_seen_ts": "First report under the condition.", "last_seen_ts": "Last report under the condition.", "last_valid_vin_ts": "Last time a valid VIN was read.",
    "devices_affected": "Devices flagged that day.", "vin_missing_devices": "Devices with VIN missing.", "speed_na_devices": "Devices with Speed N/A.", "rpm_na_devices": "Devices with RPM N/A.",
    # driving day
    "driving_hours": "Driving hours (DR) for the day.",
    "daily_mileage": "Daily mileage as exported — holds the cumulative odometer on some days (defect).",
    "start_engine_miles": "Odometer at start of day (miles).", "end_engine_miles": "Odometer at end of day (miles).",
    "start_engine_km": "Odometer at start of day (km).", "end_engine_km": "Odometer at end of day (km).",
}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=Path("data/public"), type=Path)
    args = ap.parse_args(argv)
    lines = ["# Data dictionary", "", "All tables are de-identified derivatives of operational exports from a US ELD / fleet-telematics provider, snapshot 2026-09-28 unless stated. Identifiers are keyed HMAC pseudonyms (consistent across tables, irreversible without the key, which is not published). Coordinates are coarsened to a 0.05° grid. Names, addresses, phone numbers, e-mails, plates, licence numbers, IMEI/ICCID and USDOT numbers are not released.", ""]
    missing = []
    for name, (desc, grain) in TABLES.items():
        df = pd.read_parquet(args.data / f"{name}.parquet")
        lines += [f"## `{name}`", "", f"{desc}  ", f"Grain: {grain}. Rows: {len(df):,}.", "", "| column | type | non-null | description |", "|---|---|---:|---|"]
        for col in df.columns:
            d = COLS.get(col)
            if d is None and not col.startswith("d09"):
                missing.append(f"{name}.{col}")
                d = ""
            # per-day columns of the 3-day summary
            if col.startswith("d09"):
                d = f"Per-day value for 2026-{col[1:3]}-{col[3:5]}: " + {"n_records": "reports under the condition", "vin_missing_n": "VIN missing", "speed_na_n": "Speed N/A", "rpm_na_n": "RPM N/A"}[col[6:]]
            lines.append(f"| `{col}` | {df[col].dtype} | {df[col].notna().mean():.0%} | {d} |")
        lines.append("")
    (args.data / "DATA_DICTIONARY.md").write_text("\n".join(lines), encoding="utf-8")
    if missing:
        print("undocumented columns:", missing)
    print("wrote", args.data / "DATA_DICTIONARY.md")


if __name__ == "__main__":
    main()
