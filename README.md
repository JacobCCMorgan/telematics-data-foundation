# telematics-data-foundation

**A de-identified, analysis-ready data model of a working ELD / fleet-telematics business — 4,970 ELD units, 3,525 vehicles, 5,667 customer organisations, seven years of contracts and one day of field-anomaly telemetry — with the pseudonymization pipeline, DuckDB warehouse, data-quality tests and first findings that every downstream project in this portfolio builds on.**

[Findings](reports/fleet_snapshot_2026-09-28.md) · [Data dictionary](data/public/DATA_DICTIONARY.md) · [Data-quality report](reports/data_quality_report.md) · [SQL views](sql/views.sql) · [Example queries](sql/examples.sql)

---

## Why this exists

Operational data from a telematics provider is the most informative material for fleet analytics and the least shareable: every table carries serial numbers, VINs, driver identities, company names and locations. This repository solves that once. Raw exports from the device-management system (DMS), the driver-app back office and the CRM go in; twelve Parquet tables come out in which every identifier is a keyed pseudonym that is **consistent across tables** (joins work) and **irreversible** (the HMAC key is never published), coordinates are coarsened to ≈5 km, and free text and contact details are dropped. The rest of the portfolio — ECM-disconnect persistence, device-log parsing, subscription lifecycle, FMCSA log-file tooling, telemetry replay — reads these tables instead of touching raw data again.

The data is real. Numbers describe one provider's fleet at a 2026-09-28 snapshot, not the industry, and nothing here is a statement about the provider's current commercial performance.

## What the data shows (snapshot 2026-09-28)

Full report with figures: [`reports/fleet_snapshot_2026-09-28.md`](reports/fleet_snapshot_2026-09-28.md). Headlines:

| Area | Finding |
|---|---|
| Connectivity | 29.5 % of registered units have never reported (inventory). Of 3,456 reporting customer devices, 61.4 % were online; the online rate climbs from **46 % on hardware generation A to 65 % on generation C**. |
| Service queue | **12.6 % of reporting devices last reported in `LowBattery` mode**, 85 units are at ≤ 20 % backup battery, 500 have not updated in 30+ days — a concrete installer work-list rather than a dashboard tile. |
| ECM connection | **40 % of reporting devices have never read a VIN from the ECM**. On the anomaly day, **47 % of flagged reports have VIN, speed and RPM missing simultaneously while the GPS says 96 km/h**: the truck is moving, the ELD hears nothing from the engine — a compliance exposure for a regulated device. 1,176 devices were silent on RPM for the whole day; in the 23–25 Sep window 29 devices were chronic (3/3 days, ≥ 90 % missing) versus 49 transient. |
| Batch signal | The newest **"Volvo 2026" batch has 98 % moving-while-silent reports versus 33–61 % for regular batches** — a protocol / wiring problem on new model-year trucks, not random hardware failure. |
| Support blind spot | Only **1 of the 29 chronic devices ever appears in the field-issue tracker** (Apr–Sep 2026), and not for an engine-data complaint. Monitoring finds what the ticket queue does not. |
| Customer base | Owner-operator heavy: median organisation contracted **2 vehicles**, 90 % ≤ 5. 2,025 organisations active, 2,224 lapsed. |
| Renewal cliff | **74 % of contract terms are exactly 365 days**; organisation tenure clusters at 365 / 730 / 1,095 days and **90 % of returned units came back before their first anniversary** — churn is a first-renewal event (figure below). |
| Migration | Activations grew every year (222 in 2021 → 3,468 in Jan–Sep 2026) and **82 % of 2026 activations replaced an earlier device**, i.e. volume is dominated by the hardware-generation migration. |

![tenure](reports/figures/05_org_tenure.png)
![anomaly combinations](reports/figures/03_anomaly_combinations.png)

## What is in the box

```
raw exports (private, never committed)
   │  DMS device snapshot · SIM tables · field-anomaly rules output · app vehicle/driver/company masters
   │  CRM organisation list · CRM contract history · 3-day anomaly summary · single-vehicle daily report
   ▼
src/tdf/build.py ──► de-identify (HMAC pseudonyms, coarse coordinates, drop PII/free text), normalise units & dates
   ▼
data/public/*.parquet (12 tables, 2.9 MB) + manifest.json + DATA_DICTIONARY.md
   ▼
src/tdf/warehouse.py ──► DuckDB warehouse + sql/views.sql (v_device_360, v_anomaly_device_day, v_org_lifecycle, v_contract)
   ▼
src/tdf/quality.py ──► reports/data_quality_report.md (leakage, referential integrity, 32 known-defect metrics)
scripts/fleet_snapshot_findings.py ──► reports/fleet_snapshot_2026-09-28.md + figures
tests/ ──► 16 tests: pseudonymizer behaviour, zero identifier leakage, join integrity, views, defect metrics
```

| Table | Grain | Rows | Source system |
|---|---|---:|---|
| `dim_device` | ELD unit | 4,970 | DMS snapshot |
| `dim_sim` | SIM | 4,970 | DMS / SIM management |
| `dim_vehicle` | vehicle | 3,525 | driver-app back office |
| `dim_driver_account` | login account | 4,604 | driver-app back office |
| `dim_org` | organisation | 5,675 | CRM ∪ app ∪ contracts |
| `fact_contract` | contract / device assignment | 13,759 | CRM, 2019–2026 |
| `fact_field_anomaly` | flagged telemetry report | 51,858 | DMS anomaly rules, 2026-09-28 |
| `fact_anomaly_device_3day` | device | 215 | DMS anomaly rules, 23–25 Sep |
| `fact_anomaly_daily` | day | 3 | DMS anomaly rules |
| `fact_sim_topup` / `fact_sim_usage` | event | 90 / 20 | SIM management |
| `fact_driving_day_sample` | vehicle-day | 30 | DMS monthly report (data-quality example) |

Column-level definitions: [`data/public/DATA_DICTIONARY.md`](data/public/DATA_DICTIONARY.md).

## De-identification policy

| Field class | Treatment |
|---|---|
| ELD serial, IMEI, ICCID, device id | serial → `DEV-` + HMAC-SHA256 (first 10 hex); IMEI / ICCID not released |
| VIN | `VIN-` pseudonym; make / model / year kept as attributes; placeholder VINs flagged, not hashed |
| Driver UID (telemetry) / login e-mail (app) | `DRV-` / `USR-` pseudonyms in separate namespaces; names, licence numbers, phones, addresses dropped (only the *count* of accounts sharing a licence is kept) |
| Company name, USDOT number | `ORG-` pseudonym of the normalised name; `DOT-` pseudonym so carrier matching remains possible without the number; contacts, e-mails, addresses dropped; state kept |
| Sales representative | `REP-` pseudonym |
| Coordinates | rounded to a 0.05° grid (≈ 5 km); zero / blank → null |
| DMS organisation group | only the batch label is kept (`RT64`, `Volvo 2026`, `Test Group` …); vendor and site names removed |
| Free text, notes, call outcomes | not released |
| Payment, credentials | never read |
| Internal test devices / accounts | kept and flagged `is_internal_test` so analyses can exclude them transparently |

The HMAC key lives outside the repository (`TDF_DEID_KEY_FILE`). The test-suite scans every string column of every public table for serial, VIN, IMEI/ICCID, e-mail and phone patterns on every CI run (`tests/test_public_tables.py::test_no_identifier_leakage`).

## Data quality, measured

[`reports/data_quality_report.md`](reports/data_quality_report.md) is regenerated in CI and must match the committed numbers. Among the 43 checks (32 defect metrics):

- **Referential integrity after pseudonymization**: vehicle → device 3,512 / 3,516 (99.9 %), current-generation contract rows → device 3,513 / 3,514, device VIN → vehicle master 2,011 / 2,081, every organisation key in contracts, vehicles and accounts resolves to `dim_org`.
- **Country spelled 7 ways** in the vehicle master (`United State`, `Untied States`, `USA`, …); 4 states and 14 CRM states not mappable to USPS codes.
- **1,692 driver accounts (36.8 %) share a licence number with another account** (duplicate logins for the same person, or shared logins) — a direct input for the driver-identity work in later projects.
- **26 contract rows are `active` past their expiration date; 25 returns precede activation**; 12 model years are impossible (125, 2917); one product code is a placeholder.
- **DTC, pedal and transmission columns are entirely blank** in the DMS export: engine fault-code analytics are not possible from this source.
- The single-vehicle daily report carries the cumulative odometer in the "daily mileage" column on 4 of 16 populated days.

These are kept as data, not fixed silently: `*_raw` columns preserve the original value next to the normalised one.

## Reproduce

```bash
git clone https://github.com/JacobCCMorgan/telematics-data-foundation
cd telematics-data-foundation
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# everything below runs on the committed public tables — no raw data needed
python -m pytest -q                                   # 16 tests
python -m tdf.warehouse                               # builds data/warehouse.duckdb + views
python -m tdf.quality                                 # regenerates reports/data_quality_report.md
python scripts/fleet_snapshot_findings.py             # regenerates the findings report and figures
duckdb data/warehouse.duckdb < sql/examples.sql       # five business questions in SQL
```

Rebuilding the public tables from raw exports (owner only):

```bash
export TDF_DEID_KEY_FILE=/secure/location/deid_key.txt   # 32 random bytes, hex
python -m tdf.build --raw-dir /secure/location/raw --out data/public
python scripts/make_data_dictionary.py
```

## Limitations

- One DMS snapshot and one anomaly day (plus a 3-day summary). Trends, device survival and SIM depletion need daily exports; those projects start once the exports accumulate.
- `connect_status` mixes utilisation and health: an offline device may simply be parked.
- Telemetry driver pseudonyms (`DRV-`, from app UIDs) and login accounts (`USR-`, from e-mails) cannot be linked — the source systems share no key.
- Organisation lifecycle is derived from contract rows (device-level); it is the best available proxy for customer churn, not a billing fact.
- Contract-date strings that could not be parsed (e.g. year `0021`) are null, and 330 rows have no status.

## Related projects

This repository is the shared foundation for the portfolio at [`fleet-data-lab`](https://github.com/JacobCCMorgan/fleet-data-lab):

- `eld-ecm-disconnect` — chronic vs. transient ECM disconnects, day-4 persistence model, field-service prioritisation
- `eld-device-log-parser` — ELD firmware logs → structured events, MQTT latency, state-machine reconstruction
- `eld-subscription-lifecycle` — organisation-level survival analysis, first-renewal churn, device-generation migration
- `fmcsa-eld-logbook-toolkit` — FMCSA output-file parser / validator, eRODS reconciliation, HOS rule engine
- `eld-telemetry-replay` — 30-second telemetry replay, trip / stop segmentation, late-data handling

`scripts/filter_fmcsa_census.py` prepares the public FMCSA Motor Carrier Census subset used by the lifecycle project (joined on `dot_key`).

## License

Code: MIT. Public data files: evaluation / educational / portfolio-review use, no re-identification attempts (see `LICENSE`).
