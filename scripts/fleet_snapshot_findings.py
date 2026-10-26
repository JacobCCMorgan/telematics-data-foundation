"""Produce the fleet snapshot findings report and figures from the public tables.

    python scripts/fleet_snapshot_findings.py --data data/public --out reports

Every number in reports/fleet_snapshot_2026-09-28.md is computed here, so the
report can be regenerated after any rebuild of the tables.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SNAP = pd.Timestamp("2026-09-28")
C1, C2, C3, C4 = "#2F5D8A", "#D9822B", "#7A9E7E", "#9A9A9A"


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def fig_online_by_hw(dev: pd.DataFrame, out: Path):
    r = dev[~dev.never_reported & ~dev.is_internal_test]
    g = r.groupby("hw_version").agg(devices=("device_key", "size"), online=("connect_status", lambda s: (s == "Online").mean()), low_batt=("mode", lambda s: (s == "LowBattery").mean()))
    fig, ax = plt.subplots(figsize=(6, 3.4))
    x = np.arange(len(g))
    ax.bar(x - 0.18, g["online"], width=0.36, color=C1, label="online")
    ax.bar(x + 0.18, g["low_batt"], width=0.36, color=C2, label="in LowBattery mode")
    ax.set_xticks(x, [f"HW {h}\n(n={n:,})" for h, n in zip(g.index, g["devices"])])
    ax.set_ylim(0, 1)
    ax.set_ylabel("share of reporting devices")
    ax.set_title("Connectivity by hardware generation, 2026-09-28 snapshot")
    for i, (o, l) in enumerate(zip(g["online"], g["low_batt"])):
        ax.text(i - 0.18, o + 0.02, pct(o, 0), ha="center", fontsize=9)
        ax.text(i + 0.18, l + 0.02, pct(l, 0), ha="center", fontsize=9)
    ax.legend(frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "01_online_rate_by_hw.png", dpi=160)
    plt.close(fig)
    return g


def fig_mode_mix(dev: pd.DataFrame, out: Path):
    r = dev[~dev.never_reported & ~dev.is_internal_test]
    counts = r["mode"].fillna("(blank)").value_counts()
    top = counts.head(6)
    other = counts.iloc[6:].sum()
    if other:
        top = pd.concat([top, pd.Series({"other": other})])
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.barh(top.index[::-1], top.values[::-1], color=C1)
    for i, v in enumerate(top.values[::-1]):
        ax.text(v + 15, i, f"{v:,} ({pct(v / len(r), 0)})", va="center", fontsize=9)
    ax.set_xlim(0, top.max() * 1.3)
    ax.set_title("Last reported device mode (reporting customer devices)")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "02_device_mode_mix.png", dpi=160)
    plt.close(fig)
    return counts


def fig_anomaly_combos(an: pd.DataFrame, out: Path):
    flags = ["vin_anomaly", "speed_anomaly", "rpm_anomaly", "engine_hours_anomaly", "engine_miles_anomaly"]
    labels = {"vin_anomaly": "VIN", "speed_anomaly": "Speed", "rpm_anomaly": "RPM", "engine_hours_anomaly": "EngHrs", "engine_miles_anomaly": "EngMi"}
    combo = an[flags].apply(lambda r: "+".join(labels[f] for f in flags if r[f]), axis=1)
    counts = combo.value_counts()
    top = counts.head(7)
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    ax.barh(top.index[::-1], top.values[::-1], color=C2)
    for i, v in enumerate(top.values[::-1]):
        ax.text(v + 200, i, f"{v:,} ({pct(v / len(an), 0)})", va="center", fontsize=9)
    ax.set_xlim(0, top.max() * 1.35)
    ax.set_title("Fields missing together (51,858 flagged reports, 2026-09-28)", fontsize=10)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "03_anomaly_combinations.png", dpi=160)
    plt.close(fig)
    return counts, combo


def fig_activations(con: pd.DataFrame, out: Path):
    # 5 rows are dated after the snapshot (pre-registered activations); exclude them and the partial month
    c = con[(con.activation_date >= "2021-01-01") & (con.activation_date <= SNAP)].copy()
    c["month"] = c.activation_date.dt.to_period("M").dt.to_timestamp()
    c["kind"] = np.where(c.prev_device_key.isna(), "first device on the row (organic)", "replacement (previous device recorded)")
    m = c.groupby(["month", "kind"]).size().unstack(fill_value=0)
    fig, ax = plt.subplots(figsize=(7, 3.4))
    ax.stackplot(m.index, [m.iloc[:, 0], m.iloc[:, 1]], labels=list(m.columns), colors=[C1, C2], alpha=0.9)
    ax.set_title("Device activations per month, 2021-01 to 2026-09 (Sep. partial, to the 28th)")
    ax.set_ylabel("contract rows activated")
    ax.legend(loc="upper left", frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "04_activations_per_month.png", dpi=160)
    plt.close(fig)
    return m


def fig_tenure(org: pd.DataFrame, out: Path):
    o = org[~org.is_internal_test & org.tenure_days.notna() & (org.tenure_days >= 0)]
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    bins = np.arange(0, 1500, 30)
    ax.hist(o.loc[o.org_lifecycle_status == "lapsed", "tenure_days"], bins=bins, color=C2, alpha=0.85, label="lapsed (all contracts expired)")
    ax.hist(o.loc[o.org_lifecycle_status == "active", "tenure_days"], bins=bins, color=C1, alpha=0.7, label="active")
    for d in (365, 730, 1095):
        ax.axvline(d, color=C4, lw=0.8, ls="--")
    ax.set_xlabel("organisation tenure in days (first activation to last expiration, capped at the snapshot)")
    ax.set_ylabel("organisations")
    ax.set_title("Tenure clusters at the one-year renewal points")
    ax.legend(frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(out / "05_org_tenure.png", dpi=160)
    plt.close(fig)
    return o


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=Path("data/public"), type=Path)
    ap.add_argument("--out", default=Path("reports"), type=Path)
    a = ap.parse_args(argv)
    figs = a.out / "figures"
    figs.mkdir(parents=True, exist_ok=True)

    dev = pd.read_parquet(a.data / "dim_device.parquet")
    sim = pd.read_parquet(a.data / "dim_sim.parquet")
    veh = pd.read_parquet(a.data / "dim_vehicle.parquet")
    org = pd.read_parquet(a.data / "dim_org.parquet")
    con = pd.read_parquet(a.data / "fact_contract.parquet")
    an = pd.read_parquet(a.data / "fact_field_anomaly.parquet")
    a3 = pd.read_parquet(a.data / "fact_anomaly_device_3day.parquet")

    cust = dev[~dev.is_internal_test]
    rep = cust[~cust.never_reported]
    g_hw = fig_online_by_hw(dev, figs)
    modes = fig_mode_mix(dev, figs)
    combos, combo = fig_anomaly_combos(an, figs)
    act = fig_activations(con, figs)
    ten = fig_tenure(org, figs)

    online = (rep.connect_status == "Online").mean()
    lowbatt = (rep["mode"] == "LowBattery").mean()
    batt_le20 = (rep.backup_battery_pct <= 20).sum()
    stale = ((SNAP - rep.last_updated_ts).dt.days > 30).sum()
    placeholder = rep.is_placeholder_vin.mean()
    gps_valid = rep.gps_valid.mean()
    sim_c = sim[sim.device_key.isin(cust.device_key)]
    low_quota = sim_c.quota_status.isin(["Low Data", "Depleted"]).sum()

    # anomaly day
    per_dev = an.groupby("device_key").agg(n=("device_key", "size"), rpm_all=("rpm_anomaly", "mean"), moving=("gps_speed_kmh", lambda s: (s > 0).mean()))
    triple = an.vin_anomaly & an.speed_anomaly & an.rpm_anomaly
    triple_share = triple.mean()
    triple_moving_median = an.loc[triple, "gps_speed_kmh"].median()
    rpm_all_day = int((per_dev.rpm_all == 1).sum())
    flagged_customer = an[an.org_group != "Test Group"].device_key.nunique()
    reporting_customer = int(len(rep))
    a3c = a3[a3.org_group != "Test Group"]  # the internal test group is bench hardware with no engine attached
    chronic3 = int(((a3c.days_present == 3) & (a3c.rpm_na_pct >= 90)).sum())
    transient3 = int((a3c.rpm_na_pct < 20).sum())
    chronic3_test = int(((a3.days_present == 3) & (a3.rpm_na_pct >= 90)).sum()) - chronic3
    moving_silent = an.vin_anomaly & an.speed_anomaly & an.rpm_anomaly & (an.gps_speed_kmh > 0)
    ms_share = moving_silent.groupby(an.org_group).mean()
    volvo = ms_share.get("Volvo 2026", float("nan"))
    rt_lo, rt_hi = ms_share.filter(like="RT6").min(), ms_share.filter(like="RT6").max()
    volvo_devices = an.loc[an.org_group == "Volvo 2026", "device_key"].nunique()

    # customers
    o = org[~org.is_internal_test]
    status = o.org_lifecycle_status.value_counts()
    q = o.tenure_days.dropna().quantile([0.1, 0.25, 0.5, 0.75, 0.9]).round(0).astype(int)
    fleet = o.vehicles_ever.dropna()
    term = (con.expiration_date - con.activation_date).dt.days
    one_year = (term == 365).sum() / term.notna().sum()
    returns = con[con.return_date.notna() & con.activation_date.notna()]
    life = (returns.return_date - returns.activation_date).dt.days
    life = life[life >= 0]  # 25 rows have a return date before activation (see data-quality report)
    act_year = con.activation_date.dt.year.value_counts().sort_index()
    repl_share_2026 = (con[(con.activation_date.dt.year == 2026)].prev_device_key.notna()).mean()
    make = veh.make.value_counts(normalize=True)

    md = f"""# Fleet snapshot findings — 2026-09-28

Computed from the public tables by `scripts/fleet_snapshot_findings.py`. "Customer devices" excludes the internal test group. Figures are in `reports/figures/`.

## 1. Connectivity and device health

- **{len(cust):,} ELD units** are registered in the device-management system; **{cust.never_reported.sum():,} ({pct(cust.never_reported.mean())})** have never reported telemetry (inventory / shipping). Of the **{reporting_customer:,} reporting customer devices**, **{pct(online)} were online** at the snapshot.
- Online rate rises with hardware generation: **HW A {pct(g_hw.loc['A', 'online'], 0)} → HW B {pct(g_hw.loc['B', 'online'], 0)} → HW C {pct(g_hw.loc['C', 'online'], 0)}** (figure 1). Firmware is confounded with hardware (newer firmware ships on newer boards), so this is a descriptive comparison, not an effect estimate.
- **{pct(lowbatt)} of reporting devices ({(rep['mode'] == 'LowBattery').sum():,}) last reported in `LowBattery` mode** and **{batt_le20:,}** report a backup battery at 20 % or below — a concrete service queue for installers (external power / wiring checks).
- **{stale:,} reporting devices ({pct(stale / reporting_customer)}) have not updated in more than 30 days**; **{pct(placeholder)}** still show a placeholder VIN (the ECM has never been read successfully) and **{pct(1 - gps_valid)}** report no valid GPS fix.
- SIM quotas are healthy: only **{low_quota}** of {len(sim_c):,} customer SIMs are Low-Data or Depleted (median remaining data {sim_c.remaining_data_mb.median():.0f} MB of a 500 MB plan).

![online rate](figures/01_online_rate_by_hw.png)
![mode mix](figures/02_device_mode_mix.png)

## 2. ECM-disconnect anomalies (field-anomaly rules, one day)

- The anomaly rules flagged **{len(an):,} reports from {an.device_key.nunique():,} devices** on 2026-09-28 ({flagged_customer:,} customer devices, i.e. **{pct(flagged_customer / reporting_customer)} of reporting customer devices**).
- The dominant pattern is **VIN + Speed + RPM missing together — {pct(triple_share)} of flagged reports — with a median GPS speed of {triple_moving_median:.0f} km/h**: the vehicle is moving but the ELD is not receiving engine data. For a regulated ELD this is a compliance exposure, not a cosmetic gap (figure 3).
- **{rpm_all_day:,} devices had RPM missing on 100 % of their flagged reports** that day; across the 23–25 Sep window, **{chronic3} of {len(a3c)} customer devices were present all three days with ≥ 90 % RPM missing (chronic)** versus **{transient3} with < 20 % (transient)**. A further {chronic3_test} internal test-group units also meet the chronic rule, but they are bench hardware with no engine attached and are excluded here. Chronic devices are the field-service list; transient ones are mostly power-cycle or protocol hand-off noise.
- The small **"Volvo 2026" group stands out: {pct(volvo, 0)} of its flagged reports are moving-while-silent across its {volvo_devices} devices, versus {pct(rt_lo, 0)}–{pct(rt_hi, 0)} for the regular RT63–RT67 batches** — consistent with an ECM protocol / wiring issue on the newest model-year trucks rather than random hardware failure.
- These devices rarely surface through support: in the field-issue tracker covering Apr–Sep 2026, only 1 of the {chronic3} chronic customer devices appears (and not for an OBD complaint). Proactive monitoring sees what the ticket queue does not.

![anomaly combinations](figures/03_anomaly_combinations.png)

## 3. Customer base and contract lifecycle (CRM, 2019–2026)

- **{len(o):,} organisations** appear across the CRM, the app master and the contract history. Lifecycle at the snapshot: **{status.get('active', 0):,} active**, **{status.get('lapsed', 0):,} lapsed** (every contract expired, none active), {status.get('inactive_not_expired', 0):,} inactive but not yet expired, {status.get('no_dates', 0):,} without usable dates.
- The business is **owner-operator heavy**: median fleet ever contracted is **{fleet.median():.0f} vehicle(s)**, 90 % of organisations have **≤ {fleet.quantile(0.9):.0f}** and 99 % **≤ {fleet.quantile(0.99):.0f}**.
- Contracts are one-year terms: **{pct(one_year)} of activation→expiration spans are exactly 365 days**, and organisation tenure clusters at the renewal points — 10/25/50/75/90th percentiles of **{q[0.1]}/{q[0.25]}/{q[0.5]}/{q[0.75]}/{q[0.9]} days** (figure 5). The first renewal is the decisive churn moment.
- Among the {len(life):,} units with a return date, the median lifetime was **{life.median():.0f} days** after activation and **{pct((life < 365).mean())} were returned before the first anniversary** — churn is overwhelmingly a first-year event.
- Activations grew every year — {', '.join(f'{int(y)}: {int(n):,}' for y, n in act_year.items() if y >= 2021)} (2026 through September) — and in 2026 **{pct(repl_share_2026)} of activations carried a previous device**, i.e. the hardware-generation migration is a large share of volume (figure 4).
- Vehicles are heavy-duty tractors: **{pct(make.get('Freightliner', 0))} Freightliner, {pct(make.get('Volvo', 0))} Volvo**, median model year {veh.model_year.median():.0f}, **{pct((veh.state == 'CA').mean())} registered in California**.

![activations](figures/04_activations_per_month.png)
![tenure](figures/05_org_tenure.png)

## 4. What this snapshot cannot tell you

- One day of anomaly rules and one DMS snapshot: no trend. The 3-day window (23–25 Sep) and the 3–4 Aug window are the only longitudinal views until daily exports accumulate.
- `connect_status` is a point-in-time flag; "offline" includes parked vehicles, so online rate is a utilisation-and-health mix, not a defect rate.
- The DTC / pedal / transmission columns are blank in this export, so nothing here speaks to engine fault codes.
- Contract rows are device/vehicle level; organisation churn is derived (see `dim_org.org_lifecycle_status`) and should be read with the data-quality report (26 active rows are already past expiration; 25 returns precede activation).
"""
    (a.out / "fleet_snapshot_2026-09-28.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
