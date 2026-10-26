# Data dictionary

All tables are de-identified derivatives of operational exports from a US ELD / fleet-telematics provider, snapshot 2026-09-28 unless stated. Identifiers are keyed HMAC pseudonyms (consistent across tables, irreversible without the key, which is not published). Coordinates are coarsened to a 0.05° grid. Names, addresses, phone numbers, e-mails, plates, licence numbers, IMEI/ICCID and USDOT numbers are not released.

## `dim_device`

One row per ELD unit in the device-management system (DMS) snapshot taken 2026-09-28.  
Grain: device_key. Rows: 4,970.

| column | type | non-null | description |
|---|---|---:|---|
| `device_key` | object | 100% | Pseudonymous ELD serial (HMAC). Same value across all tables. |
| `org_group` | object | 100% | DMS organisation group = shipment batch / special group (RT62–RT67, 'Volvo 2026', 'OBD II', '1708', 'Test Group'). Vendor and site names removed. |
| `is_internal_test` | bool | 100% | True for the vendor's internal test group / test accounts. Exclude for customer metrics. |
| `model_code` | object | 100% | Hardware model code (EHA554UA/UB/UC). |
| `hw_version` | object | 71% | ELD hardware generation (A, B, C). |
| `fw_version` | object | 71% | ELD firmware version. |
| `st_fw_version` | object | 71% | ST micro-controller firmware version. |
| `ble_fw_version` | object | 71% | Bluetooth module firmware version. |
| `vin_key` | object | 43% | Pseudonymous VIN (HMAC). Null when the ELD had not yet read a VIN (see is_placeholder_vin). |
| `is_placeholder_vin` | bool | 100% | True when the VIN field held the 'not yet detected' placeholder. |
| `driver_key` | object | 16% | Pseudonymous driver identifier from the telemetry stream (HMAC of the app UID). Null when no driver was logged in. |
| `has_trailer_gps` | bool | 100% | A trailer GPS tracker is paired with the ELD. |
| `vehicle_make` | object | 70% | Vehicle make as reported by the device record. |
| `vehicle_year` | float64 | 69% | Vehicle model year as reported by the device record. |
| `engine_hours` | float64 | 68% | ECM engine hours at the last report. |
| `engine_miles` | float64 | 68% | ECM odometer (miles) at the last report. |
| `engine_km` | float64 | 68% | ECM odometer (km) at the last report. |
| `device_temp_c` | float64 | 71% | Device temperature (°C). |
| `rpm` | float64 | 67% | Engine RPM at the last report (null when the ECM field was missing). |
| `speed_kmh` | float64 | 67% | ECM vehicle speed (km/h). Units confirmed as km/h. |
| `gps_speed_kmh` | float64 | 69% | GPS speed (km/h). |
| `lat_coarse` | float64 | 67% | Latitude rounded to a 0.05° grid (≈5 km). Null when 0/blank. |
| `lon_coarse` | float64 | 67% | Longitude rounded to a 0.05° grid (≈5 km). Null when 0/blank. |
| `timezone_offset` | object | 71% | UTC offset reported by the device. |
| `report_ts` | datetime64[ns] | 71% | Timestamp of the report (source timezone as exported). |
| `backup_battery_pct` | float64 | 71% | Backup battery level (%). |
| `car_battery_connected` | object | 71% | Vehicle battery voltage detected (Yes/No in the source). |
| `mode` | object | 70% | Device state machine mode at last report (Driving, Sleeping, LowBattery, Shipping, Standby, PreOta/ExitOta, Unidentified*...). |
| `disk_used_pct` | float64 | 71% | Device storage used (%). |
| `mileage_source_sa` | object | 65% | J1939 source address used for mileage (e.g. 23 = engine, 49, 39 ...). Blank when unknown. |
| `gps_valid` | object | 71% | GPS fix valid at the last report. |
| `connect_status` | object | 100% | Online / Offline at the snapshot. |
| `connect_ts` | datetime64[ns] | 71% | Last connection timestamp. |
| `remaining_data_mb` | float64 | 100% | Remaining SIM data quota (MB). |
| `last_updated_ts` | datetime64[ns] | 71% | Last telemetry update timestamp. |
| `created_ts` | datetime64[ns] | 100% | Device record creation timestamp. |
| `updated_ts` | datetime64[ns] | 100% | Device record update timestamp. |
| `last_event_type` | object | 10% | Last event type recorded on the device record (mostly blank). |
| `never_reported` | bool | 100% | True when the device has no telemetry at all (inventory, shipping). |

## `dim_sim`

One row per SIM, joined to its device by serial.  
Grain: device_key. Rows: 4,970.

| column | type | non-null | description |
|---|---|---:|---|
| `device_key` | object | 100% | Pseudonymous ELD serial (HMAC). Same value across all tables. |
| `org_group` | object | 100% | DMS organisation group = shipment batch / special group (RT62–RT67, 'Volvo 2026', 'OBD II', '1708', 'Test Group'). Vendor and site names removed. |
| `sim_service_status` | object | 100% | Online / Attached / Offline / Blocked. |
| `quota_status` | object | 100% | Normal / Low Data / Depleted. |
| `remaining_data_mb` | float64 | 100% | Remaining SIM data quota (MB). |
| `remaining_days` | float64 | 100% | Days until SIM expiry. |
| `expiry_date` | datetime64[ns] | 100% | SIM expiry date. |
| `last_updated_ts` | datetime64[ns] | 100% | Last telemetry update timestamp. |

## `dim_vehicle`

One row per vehicle in the driver-app back office (current state).  
Grain: vin_key (+ device_key). Rows: 3,525.

| column | type | non-null | description |
|---|---|---:|---|
| `vin_key` | object | 100% | Pseudonymous VIN (HMAC). Null when the ELD had not yet read a VIN (see is_placeholder_vin). |
| `is_placeholder_vin` | bool | 100% | True when the VIN field held the 'not yet detected' placeholder. |
| `org_key` | object | 100% | Pseudonymous organisation (HMAC of the normalised company name). Same value across tables. |
| `is_internal_test` | bool | 100% | True for the vendor's internal test group / test accounts. Exclude for customer metrics. |
| `device_key` | object | 100% | Pseudonymous ELD serial (HMAC). Same value across all tables. |
| `driver_assigned` | bool | 100% | A driver is assigned to the vehicle in the app master. |
| `make` | object | 100% | Vehicle make. |
| `model` | object | 89% | Vehicle model. |
| `model_year` | float64 | 100% | Vehicle model year. |
| `fuel_type` | object | 100% | Diesel / Gasoline. |
| `state_raw` | object | 100% | State field as exported (free text). |
| `state` | object | 100% | State normalised to USPS two-letter code; null when not mappable. |
| `country_raw` | object | 100% | Country field as exported (shows spelling variants). |
| `country` | object | 100% | Country normalised (US / CA); null when not mappable. |
| `terminal_timezone` | object | 100% | Terminal time zone (IANA). |
| `odometer_adjustment` | float64 | 8% | Odometer adjustment configured in the app. |
| `status` | object | 100% | Status field of the source row (meaning depends on table: contract status, vehicle status, account status, top-up status). |
| `last_synced_ts` | datetime64[ns, pytz.FixedOffset(-420)] | 100% | Last sync timestamp from the app back office. |

## `dim_driver_account`

One row per driver login account in the app back office. Not linkable to telemetry driver_key (different identifier spaces).  
Grain: account_key. Rows: 4,604.

| column | type | non-null | description |
|---|---|---:|---|
| `account_key` | object | 100% | Pseudonymous driver login account (HMAC of the e-mail). |
| `org_key` | object | 100% | Pseudonymous organisation (HMAC of the normalised company name). Same value across tables. |
| `is_internal_test` | bool | 100% | True for the vendor's internal test group / test accounts. Exclude for customer metrics. |
| `license_state` | object | 100% | Licence issuing state (USPS code). |
| `license_shared_by_n_accounts` | float64 | 100% | How many accounts share this licence number (1 = unique). The number itself is not released. |
| `status` | object | 100% | Status field of the source row (meaning depends on table: contract status, vehicle status, account status, top-up status). |
| `country_raw` | object | 1% | Country field as exported (shows spelling variants). |
| `last_synced_ts` | datetime64[ns, pytz.FixedOffset(-420)] | 100% | Last sync timestamp from the app back office. |

## `dim_org`

One row per customer organisation, merged from the CRM list, the app company master and the contract history.  
Grain: org_key. Rows: 5,675.

| column | type | non-null | description |
|---|---|---:|---|
| `org_key` | object | 100% | Pseudonymous organisation (HMAC of the normalised company name). Same value across tables. |
| `is_internal_test` | bool | 100% | True for the vendor's internal test group / test accounts. Exclude for customer metrics. |
| `crm_active` | object | 100% | Active flag in the CRM organisation list. |
| `state_raw` | object | 100% | State field as exported (free text). |
| `state` | object | 100% | State normalised to USPS two-letter code; null when not mappable. |
| `dot_key` | object | 99% | Pseudonymous USDOT number (HMAC). Lets rows of the same carrier be matched without exposing the number. |
| `has_dot` | object | 100% | A USDOT number is recorded in the CRM. |
| `email_is_free_domain` | object | 90% | Contact e-mail uses a free webmail domain (gmail, yahoo, ...). Null when no e-mail. |
| `crm_account_limit` | float64 | 99% | Account limit configured in the CRM (contains dirty values). |
| `crm_vehicle_limit` | float64 | 99% | Vehicle limit configured in the CRM (contains dirty values). |
| `is_reseller` | bool | 100% | Reseller flag in the CRM. |
| `sales_rep_key` | object | 73% | Pseudonymous sales representative / channel (HMAC of the CRM sales field). |
| `in_crm` | bool | 100% | Organisation present in the CRM organisation list. |
| `app_fleet_vehicles` | float64 | 33% | Vehicles registered in the app for this organisation. |
| `app_vehicle_limit` | float64 | 33% | Vehicle limit in the app. |
| `in_app` | bool | 100% | Organisation present in the app company master. |
| `contract_rows` | float64 | 94% | Number of contract rows for the organisation. |
| `contract_rows_active` | float64 | 94% | Contract rows with status 'active'. |
| `vehicles_ever` | float64 | 94% | Distinct VINs ever contracted by the organisation. |
| `first_activation` | datetime64[ns] | 85% | Earliest activation date across the organisation's contract rows. |
| `last_expiration` | datetime64[ns] | 81% | Latest expiration date across the organisation's contract rows. |
| `org_lifecycle_status` | object | 94% | active (≥1 active row) / lapsed (all expired, none active) / inactive_not_expired / no_dates, as of 2026-09-28. |
| `tenure_days` | float64 | 81% | last_expiration (capped at 2026-09-28) minus first_activation. |
| `in_contracts` | bool | 100% | Organisation present in the contract history. |

## `fact_contract`

One row per contract / device assignment record, 2019–2026 (CRM export).  
Grain: contract_row_id. Rows: 13,759.

| column | type | non-null | description |
|---|---|---:|---|
| `contract_row_id` | int64 | 100% | Row number in the contract export (stable within this release). |
| `org_key` | object | 100% | Pseudonymous organisation (HMAC of the normalised company name). Same value across tables. |
| `is_internal_test` | bool | 100% | True for the vendor's internal test group / test accounts. Exclude for customer metrics. |
| `dot_key` | object | 100% | Pseudonymous USDOT number (HMAC). Lets rows of the same carrier be matched without exposing the number. |
| `vin_key` | object | 99% | Pseudonymous VIN (HMAC). Null when the ELD had not yet read a VIN (see is_placeholder_vin). |
| `eld_type` | object | 72% | Product generation code (rtps47, rtoa47 → gen 1; rtel47 → gen 2; rtps12, rtsa12 → gen 3; rtha55 → gen 4). |
| `device_key` | object | 82% | Pseudonymous ELD serial (HMAC). Same value across all tables. |
| `prev_device_key` | object | 45% | Pseudonymous serial of the device this contract row replaced, when recorded. |
| `make` | object | 81% | Vehicle make. |
| `model_year` | float64 | 99% | Vehicle model year. |
| `status` | object | 98% | Status field of the source row (meaning depends on table: contract status, vehicle status, account status, top-up status). |
| `contract_date` | datetime64[ns] | 82% | Contract date. |
| `activation_date` | datetime64[ns] | 84% | Device activation date. |
| `expiration_date` | datetime64[ns] | 78% | Contract expiration date. |
| `return_date` | datetime64[ns] | 30% | Device return date, when returned. |
| `vehicle_limit` | float64 | 100% | Vehicle limit on the contract row. |
| `sales_rep_key` | object | 63% | Pseudonymous sales representative / channel (HMAC of the CRM sales field). |

## `fact_field_anomaly`

One row per telemetry report flagged by the DMS field-anomaly rules on 2026-09-28 (only reports with at least one anomaly).  
Grain: device_key + report_ts. Rows: 51,858.

| column | type | non-null | description |
|---|---|---:|---|
| `report_date` | object | 100% | Calendar date of the report / summary. |
| `report_ts` | datetime64[ns] | 100% | Timestamp of the report (source timezone as exported). |
| `org_group` | object | 100% | DMS organisation group = shipment batch / special group (RT62–RT67, 'Volvo 2026', 'OBD II', '1708', 'Test Group'). Vendor and site names removed. |
| `device_key` | object | 100% | Pseudonymous ELD serial (HMAC). Same value across all tables. |
| `driver_key` | object | 30% | Pseudonymous driver identifier from the telemetry stream (HMAC of the app UID). Null when no driver was logged in. |
| `vin_key` | object | 47% | Pseudonymous VIN (HMAC). Null when the ELD had not yet read a VIN (see is_placeholder_vin). |
| `is_placeholder_vin` | bool | 100% | True when the VIN field held the 'not yet detected' placeholder. |
| `speed_kmh` | float64 | 25% | ECM vehicle speed (km/h). Units confirmed as km/h. |
| `rpm` | float64 | 30% | Engine RPM at the last report (null when the ECM field was missing). |
| `engine_hours` | float64 | 99% | ECM engine hours at the last report. |
| `engine_miles` | float64 | 99% | ECM odometer (miles) at the last report. |
| `car_battery_connected` | bool | 100% | Vehicle battery voltage detected (Yes/No in the source). |
| `gps_speed_kmh` | float64 | 100% | GPS speed (km/h). |
| `lat_coarse` | float64 | 100% | Latitude rounded to a 0.05° grid (≈5 km). Null when 0/blank. |
| `lon_coarse` | float64 | 100% | Longitude rounded to a 0.05° grid (≈5 km). Null when 0/blank. |
| `vin_anomaly` | bool | 100% | VIN field flagged (placeholder / unreadable). |
| `speed_anomaly` | bool | 100% | Speed field flagged (missing while moving). |
| `rpm_anomaly` | bool | 100% | RPM field flagged (missing while moving). |
| `engine_hours_anomaly` | bool | 100% | Engine-hours field flagged by the rule. |
| `engine_miles_anomaly` | bool | 100% | Engine-miles field flagged by the rule. |

## `fact_anomaly_device_3day`

One row per device flagged on 23–25 Sep 2026 under the condition 'car battery connected and GPS speed > 0'.  
Grain: device_key. Rows: 215.

| column | type | non-null | description |
|---|---|---:|---|
| `device_key` | object | 100% | Pseudonymous ELD serial (HMAC). Same value across all tables. |
| `org_group` | object | 100% | DMS organisation group = shipment batch / special group (RT62–RT67, 'Volvo 2026', 'OBD II', '1708', 'Test Group'). Vendor and site names removed. |
| `days_present` | float64 | 100% | Days (of 3) the device appeared under the condition. |
| `n_records` | float64 | 100% | Reports under the condition. |
| `vin_missing_n` | float64 | 100% | Reports with VIN missing. |
| `vin_missing_pct` | float64 | 100% | Share of reports with VIN missing (%). |
| `speed_na_n` | float64 | 100% | Reports with Speed N/A. |
| `speed_na_pct` | float64 | 100% | Share of reports with Speed N/A (%). |
| `rpm_na_n` | float64 | 100% | Reports with RPM N/A. |
| `rpm_na_pct` | float64 | 100% | Share of reports with RPM N/A (%). |
| `all_three_missing_n` | float64 | 100% | Reports with VIN, Speed and RPM all missing. |
| `d0923_n_records` | float64 | 87% | Per-day value for 2026-09-23: reports under the condition |
| `d0923_vin_missing_n` | float64 | 87% | Per-day value for 2026-09-23: VIN missing |
| `d0923_speed_na_n` | float64 | 87% | Per-day value for 2026-09-23: Speed N/A |
| `d0923_rpm_na_n` | float64 | 87% | Per-day value for 2026-09-23: RPM N/A |
| `d0924_n_records` | float64 | 88% | Per-day value for 2026-09-24: reports under the condition |
| `d0924_vin_missing_n` | float64 | 88% | Per-day value for 2026-09-24: VIN missing |
| `d0924_speed_na_n` | float64 | 88% | Per-day value for 2026-09-24: Speed N/A |
| `d0924_rpm_na_n` | float64 | 88% | Per-day value for 2026-09-24: RPM N/A |
| `d0925_n_records` | float64 | 86% | Per-day value for 2026-09-25: reports under the condition |
| `d0925_vin_missing_n` | float64 | 86% | Per-day value for 2026-09-25: VIN missing |
| `d0925_speed_na_n` | float64 | 86% | Per-day value for 2026-09-25: Speed N/A |
| `d0925_rpm_na_n` | float64 | 86% | Per-day value for 2026-09-25: RPM N/A |
| `first_seen_ts` | datetime64[ns] | 100% | First report under the condition. |
| `last_seen_ts` | datetime64[ns] | 100% | Last report under the condition. |
| `last_valid_vin_ts` | datetime64[ns] | 90% | Last time a valid VIN was read. |
| `last_valid_vin_key` | object | 90% | Pseudonymous VIN last read successfully in the 3-day window. |

## `fact_anomaly_daily`

Daily totals for the 23–25 Sep window.  
Grain: report_date. Rows: 3.

| column | type | non-null | description |
|---|---|---:|---|
| `report_date` | object | 100% | Calendar date of the report / summary. |
| `n_records` | float64 | 100% | Reports under the condition. |
| `devices_affected` | float64 | 100% | Devices flagged that day. |
| `vin_missing_devices` | float64 | 100% | Devices with VIN missing. |
| `vin_missing_n` | float64 | 100% | Reports with VIN missing. |
| `speed_na_devices` | float64 | 100% | Devices with Speed N/A. |
| `speed_na_n` | float64 | 100% | Reports with Speed N/A. |
| `rpm_na_devices` | float64 | 100% | Devices with RPM N/A. |
| `rpm_na_n` | float64 | 100% | Reports with RPM N/A. |
| `all_three_missing_n` | float64 | 100% | Reports with VIN, Speed and RPM all missing. |

## `fact_sim_topup`

Manual SIM top-ups during September 2026.  
Grain: device_key + topup_ts. Rows: 90.

| column | type | non-null | description |
|---|---|---:|---|
| `device_key` | object | 100% | Pseudonymous ELD serial (HMAC). Same value across all tables. |
| `org_group` | object | 100% | DMS organisation group = shipment batch / special group (RT62–RT67, 'Volvo 2026', 'OBD II', '1708', 'Test Group'). Vendor and site names removed. |
| `plan` | object | 100% | Top-up plan (500 MB). |
| `operator_key` | object | 100% | Pseudonymous internal operator who performed the action. |
| `topup_ts` | datetime64[ns] | 100% | Top-up timestamp. |
| `status` | object | 100% | Status field of the source row (meaning depends on table: contract status, vehicle status, account status, top-up status). |

## `fact_sim_usage`

Previous-day SIM usage detail (one day).  
Grain: device_key + usage_ts. Rows: 20.

| column | type | non-null | description |
|---|---|---:|---|
| `device_key` | object | 100% | Pseudonymous ELD serial (HMAC). Same value across all tables. |
| `org_group` | object | 100% | DMS organisation group = shipment batch / special group (RT62–RT67, 'Volvo 2026', 'OBD II', '1708', 'Test Group'). Vendor and site names removed. |
| `usage_ts` | datetime64[ns] | 100% | Usage timestamp. |
| `used_mb` | float64 | 100% | Data used (MB). |
| `source` | object | 100% | Usage record source (Manual). |
| `sync_ts` | datetime64[ns] | 100% | Sync timestamp. |

## `fact_driving_day_sample`

Daily driving summary for a single vehicle, September 2026 — kept as a data-quality example (the daily-mileage column holds the cumulative odometer).  
Grain: report_date. Rows: 30.

| column | type | non-null | description |
|---|---|---:|---|
| `report_date` | object | 100% | Calendar date of the report / summary. |
| `driving_hours` | float64 | 57% | Driving hours (DR) for the day. |
| `daily_mileage` | float64 | 53% | Daily mileage as exported — holds the cumulative odometer on some days (defect). |
| `start_engine_miles` | float64 | 53% | Odometer at start of day (miles). |
| `end_engine_miles` | float64 | 57% | Odometer at end of day (miles). |
| `start_engine_km` | float64 | 53% | Odometer at start of day (km). |
| `end_engine_km` | float64 | 57% | Odometer at end of day (km). |
| `has_start_location` | bool | 100% | A start location was recorded (location itself removed). |
| `has_end_location` | bool | 100% | An end location was recorded (location itself removed). |
