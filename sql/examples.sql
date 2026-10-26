-- Example questions answered directly from the warehouse.
-- Run: duckdb data/warehouse.duckdb < sql/examples.sql

-- 1. Online rate by hardware generation (reporting devices only, customer fleets).
SELECT hw_version,
       COUNT(*)                                             AS devices,
       ROUND(AVG(CASE WHEN connect_status = 'Online' THEN 1.0 ELSE 0 END), 3) AS online_rate,
       ROUND(AVG(CASE WHEN mode = 'LowBattery' THEN 1.0 ELSE 0 END), 3)        AS low_battery_share
FROM v_device_360
WHERE NOT never_reported AND NOT is_internal_test
GROUP BY hw_version ORDER BY hw_version;

-- 2. Devices whose ECM fields were missing all day while the vehicle was moving.
SELECT org_group,
       COUNT(*) FILTER (WHERE rpm_anomaly_share = 1)             AS devices_rpm_missing_all_day,
       COUNT(*)                                                   AS devices_flagged,
       ROUND(AVG(ecm_silent_while_moving_reports), 1)             AS avg_moving_silent_reports
FROM v_anomaly_device_day
GROUP BY org_group ORDER BY devices_flagged DESC;

-- 3. Contract term distribution by product generation.
SELECT product_generation, eld_type,
       COUNT(*)                                        AS rows,
       ROUND(AVG(CASE WHEN term_days = 365 THEN 1.0 ELSE 0 END), 3) AS exactly_one_year_share,
       MEDIAN(days_to_return)                          AS median_days_to_return
FROM v_contract
WHERE activation_date IS NOT NULL
GROUP BY ALL ORDER BY product_generation, eld_type;

-- 4. Organisation lifecycle by fleet-size band.
SELECT fleet_size_band, org_lifecycle_status, COUNT(*) AS orgs, MEDIAN(tenure_days) AS median_tenure_days
FROM v_org_lifecycle
WHERE NOT is_internal_test AND fleet_size_band IS NOT NULL
GROUP BY ALL ORDER BY fleet_size_band, org_lifecycle_status;

-- 5. Monthly activations: first-time organisations vs. replacements (previous device present).
SELECT DATE_TRUNC('month', activation_date) AS month,
       COUNT(*) FILTER (WHERE prev_device_key IS NULL)     AS organic,
       COUNT(*) FILTER (WHERE prev_device_key IS NOT NULL) AS replacement
FROM fact_contract
WHERE activation_date >= DATE '2021-01-01'
GROUP BY 1 ORDER BY 1;
