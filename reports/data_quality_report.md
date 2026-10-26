# Data quality report

Computed from `data/public` on the de-identified public tables. Rates are numerator / denominator.

## Leakage (identifier) checks

| table | check | n | N | rate | note |
|---|---|---:|---:|---:|---|
| * | leak:none_detected | 0 | 1 | 0.0% | no raw serials, VINs, IMEIs/ICCIDs, e-mails or phone numbers in any string column |

## Referential integrity

| table | check | n | N | rate | note |
|---|---|---:|---:|---:|---|
| dim_vehicle | ri:vehicle.device_key->dim_device | 3,512 | 3,516 | 99.9% | matched / non-null keys |
| dim_vehicle | ri:vehicle.org_key->dim_org | 3,525 | 3,525 | 100.0% | matched / non-null keys |
| dim_driver_account | ri:driver_account.org_key->dim_org | 4,604 | 4,604 | 100.0% | matched / non-null keys |
| dim_sim | ri:sim.device_key->dim_device | 4,970 | 4,970 | 100.0% | matched / non-null keys |
| fact_field_anomaly | ri:anomaly.device_key->dim_device | 51,858 | 51,858 | 100.0% | matched / non-null keys |
| fact_anomaly_device_3day | ri:anomaly3day.device_key->dim_device | 215 | 215 | 100.0% | matched / non-null keys |
| fact_contract | ri:contract.org_key->dim_org | 13,759 | 13,759 | 100.0% | matched / non-null keys |
| fact_contract | ri:contract.device_key->dim_device (current-generation rows only) | 3,513 | 3,514 | 100.0% | matched / non-null keys |
| fact_sim_topup | ri:topup.device_key->dim_device | 90 | 90 | 100.0% | matched / non-null keys |
| dim_device | ri:device.vin_key->dim_vehicle | 2,011 | 2,081 | 96.6% | real VINs seen by devices that exist in the vehicle master |

## Known defects and anomalies

| table | check | n | N | rate | note |
|---|---|---:|---:|---:|---|
| dim_vehicle | country_spelling_variants | 7 | 0 |  | count of distinct raw spellings of the country field (no rate) |
| dim_vehicle | country_not_mappable | 1 | 3,525 | 0.0% | rows whose country could not be normalised |
| dim_vehicle | state_not_mappable | 4 | 3,525 | 0.1% | rows whose state could not be normalised to USPS codes |
| dim_vehicle | model_year_out_of_range | 2 | 3,524 | 0.1% | model year outside 1980-2027 |
| dim_vehicle | placeholder_vin | 0 | 3,525 | 0.0% | VIN still 'not yet detected' in the vehicle master |
| dim_vehicle | device_key_missing | 9 | 3,525 | 0.3% | vehicles without an ELD serial |
| dim_device | never_reported | 1,445 | 4,970 | 29.1% | devices with no telemetry at all (shipping / inventory) |
| dim_device | placeholder_vin_among_reporting | 1,408 | 3,525 | 39.9% | reporting devices whose VIN was not yet read from the ECM |
| dim_device | engine_miles_gt_2M | 10 | 3,377 | 0.3% | implausible odometer readings |
| dim_device | engine_hours_gt_100k | 3 | 3,380 | 0.1% | implausible engine-hour readings |
| dim_device | speed_gt_200kmh | 8 | 3,319 | 0.2% | implausible ECM speed |
| dim_device | vehicle_year_lt_1990 | 1 | 3,295 | 0.0% | implausible model year on the device record |
| dim_device | dtc_column_populated | 0 | 4,970 | 0.0% | the DTC / pedal / transmission columns are entirely blank in this export |
| dim_driver_account | license_shared_by_multiple_accounts | 1,692 | 4,604 | 36.8% | accounts whose licence number also appears on another account |
| dim_driver_account | license_groups_shared | 752 | 4,604 | 16.3% | distinct licence numbers that appear on more than one account |
| dim_driver_account | country_blank_or_variant | 4,542 | 4,604 | 98.7% | country blank in the driver master |
| dim_org | crm_account_limit_negative | 1 | 5,641 | 0.0% | negative account limits |
| dim_org | crm_vehicle_limit_negative_or_gt_500 | 35 | 5,636 | 0.6% | vehicle limits outside 0-500 |
| dim_org | state_not_mappable | 14 | 5,662 | 0.2% | CRM state values that do not map to a USPS code |
| dim_org | internal_or_test_orgs | 8 | 5,675 | 0.1% | organisation names that look like internal/test accounts |
| dim_org | in_crm_not_in_app | 3,775 | 5,665 | 66.6% | historical CRM orgs absent from the current app master |
| dim_org | in_app_not_in_crm | 2 | 1,892 | 0.1% | app orgs whose normalised name is not in the CRM list |
| fact_contract | return_before_activation | 25 | 3,833 | 0.7% | return date earlier than activation date |
| fact_contract | expired_but_active | 26 | 3,703 | 0.7% | active rows whose expiration date is already past |
| fact_contract | model_year_out_of_range | 12 | 13,687 | 0.1% | e.g. 125, 2917 |
| fact_contract | contract_date_unparseable_or_missing | 2,499 | 13,759 | 18.2% | blank or unparseable contract dates (e.g. year 0021 in the raw export) |
| fact_contract | eld_type_invalid | 2 | 9,913 | 0.0% | placeholder product code |
| fact_contract | activation_after_snapshot | 5 | 11,624 | 0.0% | activation dates later than the export date (pre-registered) |
| fact_contract | status_missing | 330 | 13,759 | 2.4% |  |
| fact_contract | vin_missing | 205 | 13,759 | 1.5% |  |
| fact_contract | term_exactly_365_days | 7,997 | 10,787 | 74.1% | activation -> expiration spans of exactly one year |
| fact_driving_day_sample | daily_mileage_equals_cumulative_odometer | 4 | 16 | 25.0% | daily mileage column holds the cumulative odometer |
