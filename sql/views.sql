-- Analysis views over the public tables (DuckDB dialect).
-- Rebuilt by `python -m tdf.warehouse`; also executed by the test-suite.

-- One row per ELD device with its SIM state and, where the device is assigned
-- to a vehicle in the app master, the vehicle and organisation.
CREATE OR REPLACE VIEW v_device_360 AS
SELECT
    d.device_key,
    d.org_group,
    d.is_internal_test,
    d.never_reported,
    d.hw_version,
    d.fw_version,
    d.model_code,
    d.mode,
    d.connect_status,
    d.last_updated_ts,
    d.backup_battery_pct,
    d.car_battery_connected,
    d.gps_valid,
    d.is_placeholder_vin,
    d.mileage_source_sa,
    d.engine_hours,
    d.engine_miles,
    d.remaining_data_mb,
    s.sim_service_status,
    s.quota_status,
    s.remaining_days AS sim_remaining_days,
    v.vin_key,
    v.org_key,
    v.make,
    v.model,
    v.model_year,
    v.state,
    v.terminal_timezone,
    v.status AS vehicle_status
FROM dim_device d
LEFT JOIN dim_sim s USING (device_key)
LEFT JOIN (
    -- a device can appear on more than one vehicle row (re-assignments); keep the active one first
    SELECT * FROM (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY device_key ORDER BY (status = 'active') DESC, last_synced_ts DESC) AS rn
        FROM dim_vehicle WHERE device_key IS NOT NULL
    ) WHERE rn = 1
) v USING (device_key);

-- Device-day anomaly summary for the 2026-09-28 export: share of flagged reports
-- per device by anomaly type, and whether the vehicle was moving while the ECM
-- fields were missing.
CREATE OR REPLACE VIEW v_anomaly_device_day AS
SELECT
    device_key,
    org_group,
    report_date,
    COUNT(*)                                        AS flagged_reports,
    AVG(CASE WHEN vin_anomaly THEN 1 ELSE 0 END)    AS vin_anomaly_share,
    AVG(CASE WHEN speed_anomaly THEN 1 ELSE 0 END)  AS speed_anomaly_share,
    AVG(CASE WHEN rpm_anomaly THEN 1 ELSE 0 END)    AS rpm_anomaly_share,
    AVG(CASE WHEN engine_hours_anomaly THEN 1 ELSE 0 END) AS engine_hours_anomaly_share,
    AVG(CASE WHEN engine_miles_anomaly THEN 1 ELSE 0 END) AS engine_miles_anomaly_share,
    SUM(CASE WHEN vin_anomaly AND speed_anomaly AND rpm_anomaly AND gps_speed_kmh > 0 THEN 1 ELSE 0 END) AS ecm_silent_while_moving_reports,
    MEDIAN(gps_speed_kmh)                           AS median_gps_speed_kmh,
    MIN(report_ts)                                  AS first_report_ts,
    MAX(report_ts)                                  AS last_report_ts
FROM fact_field_anomaly
GROUP BY ALL;

-- Organisation lifecycle as of the 2026-09-28 snapshot, with CRM and app context.
CREATE OR REPLACE VIEW v_org_lifecycle AS
SELECT
    o.org_key,
    o.is_internal_test,
    o.state,
    o.crm_active,
    o.in_crm,
    o.in_app,
    o.in_contracts,
    o.is_reseller,
    o.sales_rep_key,
    o.app_fleet_vehicles,
    o.contract_rows,
    o.contract_rows_active,
    o.vehicles_ever,
    o.first_activation,
    o.last_expiration,
    o.tenure_days,
    o.org_lifecycle_status,
    CASE
        WHEN o.vehicles_ever IS NULL THEN NULL
        WHEN o.vehicles_ever <= 1 THEN '1 (owner-operator)'
        WHEN o.vehicles_ever <= 5 THEN '2-5'
        WHEN o.vehicles_ever <= 20 THEN '6-20'
        ELSE '21+'
    END AS fleet_size_band
FROM dim_org o;

-- Contract rows with derived term length and product generation ordering.
CREATE OR REPLACE VIEW v_contract AS
SELECT
    c.*,
    DATE_DIFF('day', c.activation_date, c.expiration_date) AS term_days,
    DATE_DIFF('day', c.activation_date, c.return_date)     AS days_to_return,
    CASE c.eld_type
        WHEN 'rtps47' THEN 1 WHEN 'rtoa47' THEN 1 WHEN 'rtel47' THEN 2
        WHEN 'rtps12' THEN 3 WHEN 'rtsa12' THEN 3 WHEN 'rtha55' THEN 4 ELSE NULL
    END AS product_generation,
    YEAR(c.activation_date) AS activation_year
FROM fact_contract c;
