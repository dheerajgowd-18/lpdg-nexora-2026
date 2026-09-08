# Phase 5.1 — Feature Feasibility & Signal Construction Report

**Project:** LPDG Innovation Hub Selection Challenge 2026 (NEXORA 2026)  
**Author:** Candidate Engineering Team  
**Phase Status:** Phase 5.1 — Complete  
**Date:** September 2026  
**Reference Documents:**  
- [PHASE_3_DEEP_DATA_INVESTIGATION.md](PHASE_3_DEEP_DATA_INVESTIGATION.md)  
- [PHASE_3_VERIFICATION.md](PHASE_3_VERIFICATION.md)  
- [PHASE_3_EXPLAINED.md](PHASE_3_EXPLAINED.md)  
- [PHASE_4_1_OPERATIONAL_DEFINITION.md](PHASE_4_1_OPERATIONAL_DEFINITION.md)  
- [PHASE_4_2_FEATURE_SPECIFICATION.md](PHASE_4_2_FEATURE_SPECIFICATION.md)  
- [PHASE_4_2_VERIFICATION.md](PHASE_4_2_VERIFICATION.md)  
- [PHASE_4_EXPLAINED.md](PHASE_4_EXPLAINED.md)  
- `baseline_3sigma.py`  
- Challenge Brief & Data Dictionary  

---

## 1. Objective

The objective of Micro-Phase 5.1 is to rigorously evaluate the **technical feasibility and constructibility** of the 20 candidate features specified in Phase 4.2 using the actual local challenge datasets under the strict NEXORA temporal contract.

Phase 4.2 defined *what signals could conceptually represent an operational need for a technician visit*. Phase 5.1 answers the practical engineering question:
> *"Can each candidate feature actually be computed correctly, reproducibly, and without temporal leakage from the local raw files for every scored prediction Monday?"*

This phase classifies every feature into actionable operational statuses (**READY**, **CONDITIONAL**, or **DEFERRED**) based on empirical data availability, counter semantics, missing-data mechanics, lifecycle dynamics, and pairwise collinearity.

---

## 2. Scope & Micro-Phase Boundaries

To maintain absolute methodological discipline and prevent premature optimization, the following strict boundaries are enforced throughout Phase 5.1:

- **DO NOT create final ranking formulas:** No composite scoring formulas are implemented.
- **DO NOT assign final feature weights:** No subjective or empirical weights ($w_1, w_2, \dots$) are assigned.
- **DO NOT train ML models:** No supervised classifiers, regression models, or clustering algorithms are fitted.
- **DO NOT modify baseline or submission files:** `baseline_3sigma.py`, `validate_submission.py`, and `predictions.csv` remain completely untouched.
- **DO NOT perform final backtesting or cost optimization:** Financial evaluation against historical work orders is deferred to Phase 6.
- **DO NOT alter raw datasets or commit changes:** Source files in `data/` remain read-only.

This phase is strictly about **signal constructibility and data reality**, answering: *"Can we compute this feature accurately?"* rather than *"Which gateway should we visit?"*

---

## 3. Input Documents & Data Architecture

The feasibility assessment is grounded in the verified schemas and properties of five primary local datasets:

| Dataset | Storage Format | Temporal Coverage | Entity Grain | Verified Row Count | Natural Key |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`telemetry/`** | Parquet (8 monthly partitions) | 2025-08-01 00:00:00Z to 2026-03-31 23:00:00Z | Gateway × Hour | 1,433,387 | `(gateway_id, ts_utc)` |
| **`gateway_master.csv`** | CSV (`encoding='latin1'`) | Static asset register snapshot | Gateway (Asset) | 332 | `gateway_id` |
| **`meter_read_success.csv`** | CSV (`utf-8`) | 2025-08-04 to 2026-01-26 (26 Mondays) | Gateway × Week | 7,226 | `(week_start, gateway_id)` |
| **`field_visits.csv`** | CSV (`utf-8`) | 2025-02-03 to 2026-01-30 (work orders) | Work Order (Event) | 642 | `visit_id` |
| **`engineer_review_2026-02.xlsx`** | Excel OpenXML | 2026-02-15 (single audit date) | Gateway (Sample) | 120 | `gateway_id` |

---

## 4. Temporal Contract Enforcement

All feature construction logic must strictly satisfy the **Right-Open Information Horizon**:

$$\text{For prediction Monday } T \in \{\text{2026-02-02}, \text{2026-02-09}, \dots, \text{2026-03-23}\}:$$
$$\text{Recent Window: } [T - 7\text{ days}, T) \equiv \{t \mid T - 7\text{ days} \le t < T\}$$
$$\text{Historical Baseline: } [T - 28\text{ days}, T) \equiv \{t \mid T - 28\text{ days} \le t < T\}$$
$$\text{Strict Invariant: } \text{timestamp} < T \quad (\text{NEVER } t \ge T)$$

### 4.1 Verification Across Scored Mondays
Every scored prediction Monday was programmatically verified for historical telemetry availability:
- **Week 1 (2026-02-02):** Trailing 7d spans `2026-01-26 00:00:00` to `2026-02-01 23:59:59` (41,653 deduplicated rows across 290 active gateways). Trailing 28d spans back to `2026-01-05` (162,675 deduplicated rows).
- **Weeks 2–8 (2026-02-09 to 2026-03-23):** Trailing 7d and 28d windows fall squarely within the February and March 2026 Parquet partitions, ensuring 100% telemetry availability.
- **The Meter-Read Horizon:** `meter_read_success.csv` terminates on `2026-01-26`. For Week 1, the lag is exactly 7 days. For Week 8 (`2026-03-23`), the lag is 8 weeks. Meter-read data **cannot** provide live weekly rolling features during the scored window and is constructible only as a static pre-February prior ($t \le \text{2026-01-26} < T$).
- **The Engineer Review Horizon:** Dated `2026-02-15`. It is physically unavailable for Week 1 (Feb 2) and Week 2 (Feb 9). Any feature utilizing it prior to Feb 15 constitutes severe lookahead leakage.

---

## 5. Complete Feature Feasibility Matrix

The following master matrix evaluates all 20 candidate features specified in Phase 4.2 across 15 rigorous criteria:

| ID | Feature Name | Tier | Required Dataset(s) | Required Column(s) | Window | Transformation | Leakage Risk | Missing-Data Risk | Counter Dep. | Lifecycle Dep. | Constructible? | Confidence | Recommendation | Reason |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **F01** | `reported_hours_7d` | Core | `telemetry` | `gateway_id`, `ts_utc` | 7d $[T-7\text{d}, T)$ | Count unique hourly timestamps | None ($t < T$) | Handled (returns 0) | None | High (Gate) | **YES** | HIGH | **READY** | Direct, robust measure of weekly operational presence. |
| **F02** | `missing_hours_7d` | Supporting | `telemetry` | `gateway_id`, `ts_utc` | 7d $[T-7\text{d}, T)$ | $168 - \text{F01}$ | None ($t < T$) | Handled (returns 168) | None | High (Gate) | **YES** | HIGH | **READY** | Exact linear complement of F01; useful for deficit scoring. |
| **F03** | `reporting_ratio_7d` | Context | `telemetry` | `gateway_id`, `ts_utc` | 7d $[T-7\text{d}, T)$ | $\text{F01} / 168.0$ | None ($t < T$) | Handled (returns 0.0) | None | High (Gate) | **YES** | HIGH | **READY** | Normalized availability fraction in $[0, 1]$. |
| **F04** | `consecutive_missing_at_cutoff` | Core | `telemetry` | `gateway_id`, `ts_utc` | 28d $[T-28\text{d}, T)$ | $(T - t_{\text{latest}}) / 3600\text{s}$ | None ($t < T$) | Handled (caps at 672h) | None | High (Gate) | **YES** | HIGH | **READY** | Critical primary signal for ongoing blackout at dispatch Monday. |
| **F05** | `is_completely_silent_7d` | Core | `telemetry` | `gateway_id`, `ts_utc` | 7d $[T-7\text{d}, T)$ | $\mathbb{I}(\text{F01} == 0)$ | None ($t < T$) | Handled (binary 1) | None | High (Gate) | **YES** | HIGH | **READY** | Addresses the baseline blind spot where dead gateways produce no telemetry. |
| **F06** | `offline_duration_max_7d` | Core | `telemetry` | `offline_duration_sec` | 7d $[T-7\text{d}, T)$ | $\max(\texttt{offline\_sec})$ | None ($t < T$) | Impute 0 or null if silent | Peak Env. | High (Gate) | **YES** | HIGH | **READY** | Peak reported offline-duration counter value within 7d window; bypasses compounding (caveat: unresolved counter semantics). |
| **F07** | `offline_duration_delta_7d` | Supporting | `telemetry` | `offline_duration_sec`, `ts_utc` | 7d $[T-7\text{d}, T)$ | $\sum \max(0, \Delta C)$ | None ($t < T$) | Sensitive to multi-hour gaps | Differencing | High (Gate) | **CONDITIONAL** | MEDIUM | **CONDITIONAL** | Observed gaps show both drops and increases; counter reset convention requires calibration. |
| **F08** | `offline_hours_gt_3600_7d` | Supporting | `telemetry` | `offline_duration_sec` | 7d $[T-7\text{d}, T)$ | $\sum \mathbb{I}(C \ge 3600)$ | None ($t < T$) | Handled (returns 0) | Threshold | High (Gate) | **YES** | HIGH | **READY** | Count of observations where reported offline counter >= 3600s; bypasses cumulative scaling. |
| **F09** | `reboot_cnt_sum_7d` | Core | `telemetry` | `reboot_cnt` | 7d $[T-7\text{d}, T)$ | $\sum \texttt{reboot\_cnt}$ | None ($t < T$) | Handled (returns 0) | Incremental | High (Gate) | **YES** | HIGH | **READY** | Incremental hourly count (max 32); direct sum is mathematically valid. |
| **F10** | `reboot_cnt_sum_28d` | Supporting | `telemetry` | `reboot_cnt` | 28d $[T-28\text{d}, T)$ | $\sum \texttt{reboot\_cnt}$ | None ($t < T$) | Handled (returns 0) | Incremental | High (Gate) | **YES** | HIGH | **READY** | Stable chronic reboot baseline (note: $r = 0.99$ collinearity with F09). |
| **F11** | `reboot_intensity_ratio` | Supporting | `telemetry` | `reboot_cnt` | 28d $[T-28\text{d}, T)$ | $\text{F09} / \max(1, \text{F10}/4)$ | None ($t < T$) | Small denominator noise | Ratio | High (Gate) | **CONDITIONAL** | MEDIUM | **CONDITIONAL** | Constructible, but requires smoothing parameter to prevent $0 	o 1$ explosion. |
| **F12** | `disconnection_cnt_sum_7d` | Core | `telemetry` | `disconnection_cnt` | 7d $[T-7\text{d}, T)$ | $\sum \texttt{disconnection\_cnt}$ | None ($t < T$) | Handled (returns 0) | Incremental | High (Gate) | **YES** | HIGH | **READY** | Incremental hourly count (max 55); direct sum is valid. |
| **F13** | `disconn_to_offline_ratio` | Context | `telemetry` | `disconnection_cnt`, `offline_sec` | 7d $[T-7\text{d}, T)$ | $\text{F12} / \max(1, \text{F06}/3600)$ | None ($t < T$) | Unstable when F06 small | Ratio | High (Gate) | **CONDITIONAL** | LOW | **DEFERRED** | High numerical volatility; weak diagnostic separation in initial tests. |
| **F14** | `reboot_and_offline_syndrome` | Supporting | `telemetry` | `reboot_cnt`, `offline_sec` | 7d $[T-7\text{d}, T)$ | $\mathbb{I}(\text{F09} \ge \theta_r) \cdot \mathbb{I}(\text{F06} \ge \theta_o)$ | None ($t < T$) | Handled (returns 0) | Dual Thresh. | High (Gate) | **CONDITIONAL** | MEDIUM | **CONDITIONAL** | Constructible, but parameters ($\theta_r, \theta_o$) must be calibrated in Phase 6. |
| **F15** | `flapping_and_offline_syndrome`| Supporting | `telemetry` | `disconnection`, `offline_sec` | 7d $[T-7\text{d}, T)$ | $\mathbb{I}(\text{F12} \ge \theta_d) \cdot \mathbb{I}(\text{F06} \ge \theta_o)$ | None ($t < T$) | Handled (returns 0) | Dual Thresh. | High (Gate) | **CONDITIONAL** | MEDIUM | **CONDITIONAL** | Constructible, but parameters ($\theta_d, \theta_o$) require empirical tuning. |
| **F16** | `acute_chronic_divergence` | Core | `telemetry` | `gateway_id`, `ts_utc` | 28d $[T-28\text{d}, T)$ | Prior 21d ratio minus recent 7d | None ($t < T$) | Handled (returns 0) | None | High (Gate) | **YES** | HIGH | **READY** | Clean capture of sudden acute operational collapse ($r = 0.07$ with reboots). |
| **F17** | `hist_meter_success_pre_feb` | Context | `meter_reads` | `meters_read`, `meters_expected` | Pre-Feb static ($\le \text{Jan 26}$) | $\sum \texttt{read} / \sum \texttt{expected}$ | None ($t \le \text{Jan 26}$) | 33 gateways missing in meter log | None | Medium | **YES** | HIGH | **READY (Static)** | Constructible strictly as a static pre-February prior; 0 live signal in Feb/Mar. |
| **F18** | `hist_meter_outage_freq` | Context | `meter_reads` | `meters_read` | Pre-Feb static ($\le \text{Jan 26}$) | Fraction of 0-read weeks | None ($t \le \text{Jan 26}$) | 33 gateways missing in meter log | None | Medium | **YES** | HIGH | **READY (Static)** | Constructible strictly as a static pre-February prior. |
| **F19** | `is_lifecycle_active` | Core | `gateway_master`| `installed_on`, `decommissioned_on` | Snapshot evaluated at $T$ | $\mathbb{I}(\text{inst} \le T \land (\text{decom} > T \lor \text{null}))$ | None ($t \le T$) | No missing dates in installed_on | None | Master Gate | **YES** | HIGH | **READY (Gate)** | Mandatory gating filter; dynamically screens 290 to 308 active gateways. |
| **F20** | `installed_age_days` | Context | `gateway_master`| `installed_on` | Evaluated at $T$ | $(T - \texttt{installed\_on}) / 1\text{d}$ | None ($t \le T$) | 100% populated in master | None | Low | **YES** | HIGH | **READY** | Simple secondary tie-breaker measuring physical installation age. |

---

## 6. Data Availability & Schema Verification

Programmatic inspection of raw datasets confirmed exact types, column names, and row volumes:

### 6.1 `telemetry/` Parquet Partitions
- **Storage & Partitions:** 8 monthly partitions (`month=2025-08` through `month=2026-03`).
- **Total Records:** 1,433,387 raw rows; **1,426,840 deduplicated rows**.
- **Verified Column Types:**
  - `gateway_id`: `string` (12-character bare uppercase hex, e.g. `0639EA5602C1`).
  - `ts_utc`: `string` (ISO-8601 UTC timestamp, parseable via `pd.to_datetime(ts_utc, utc=True)`).
  - `offline_duration_sec`: `int64` (values from 0 to 726,642 seconds).
  - `reboot_duration_sec`: `int64` (values from 0 to 439,061 seconds).
  - `reboot_cnt`: `int64` (values from 0 to 32 events per hour).
  - `disconnection_cnt`: `int64` (values from 0 to 55 events per hour).
- **Explicit Missingness:** Exactly **0 nulls** across all 57 columns in telemetry.

### 6.2 `gateway_master.csv`
- **Encoding:** Must be read explicitly with `encoding='latin1'` (or Windows-1252) due to byte `0xDF` (`ß` in `Großkunden`).
- **Verified Columns:**
  - `gateway_id`: `string` (17-character colon-delimited hex, e.g. `06:39:EA:56:02:C1`).
  - `installed_on`: `string` (ISO date `YYYY-MM-DD`, 100% populated across all 332 rows).
  - `decommissioned_on`: `string` (ISO date `YYYY-MM-DD`, 12 rows populated, 320 rows null).

### 6.3 `meter_read_success.csv`
- **Rows & Grain:** 7,226 rows; Gateway × Week grain.
- **Temporal Boundary:** Exactly 26 weeks, starting `2025-08-04` and terminating `2026-01-26`.
- **Gateway Identifiers:** 12-character bare hex (`0202CB0A6B1F`), covering 299 unique gateways. Exactly 33 gateways in Master have zero records in the meter log.

---

## 7. Gateway Coverage & Fleet Dynamics

A rigorous cross-table census revealed critical dynamic fleet behavior across the 8 scored prediction Mondays:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        FLEET LIFECYCLE DYNAMICS ACROSS SCORED WEEKS                    │
├────────────┬────────────────┬──────────────────────┬─────────────────┬─────────────────┤
│ Scored     │ Active Master  │ Future Commissioned  │ Decommissioned  │ Observed 7d     │
│ Monday (T) │ Gateways (F19) │ (installed_on > T)   │ (decom_on <= T) │ Telemetry Fleet │
├────────────┼────────────────┼──────────────────────┼─────────────────┼─────────────────┤
│ 2026-02-02 │      290       │          33          │        9        │       290       │
│ 2026-02-09 │      291       │          30          │       11        │       292       │
│ 2026-02-16 │      294       │          27          │       11        │       294       │
│ 2026-02-23 │      298       │          23          │       11        │       298       │
│ 2026-03-02 │      300       │          20          │       12        │       300       │
│ 2026-03-09 │      304       │          16          │       12        │       303       │
│ 2026-03-16 │      308       │          12          │       12        │       308       │
│ 2026-03-23 │      308       │          12          │       12        │       308       │
└────────────┴────────────────┴──────────────────────┴─────────────────┴─────────────────┘
```

### 7.1 Key Empirical Discoveries
1. **Dynamic Fleet Expansion:** Between Feb 2 and Mar 23, 2026, 18 new gateways are commissioned mid-period (e.g. `installed_on = '2026-02-05'`), expanding the active fleet from 290 to 308 gateways.
2. **Decommissioning Transitions (e.g. Week 2, 2026-02-09):**
   - On 2026-02-09, exactly 291 gateways are active in Master, but 292 gateways appear in the 7-day telemetry window.
   - Investigation confirmed that gateways `02EBC6CD4398` and `0259991BA036` were decommissioned on `2026-02-04`. They emitted telemetry on Feb 2–3 before decommissioning.
   - Without `is_lifecycle_active` ($F19$), an algorithm would evaluate their pre-decommissioning distress and potentially dispatch a technician to a retired asset!
3. **Same-Day Commissioning (e.g. Gateway `0EA061007895`):**
   - Installed on `2026-02-09` (Monday of Week 2). It is active at cutoff ($F19 = 1$), but has zero telemetry rows in the trailing 7 days.
   - A naive silence detector would flag it as 168 hours missing. Lifecycle awareness prevents penalizing an asset that was just commissioned on Monday morning.

---

## 8. Deduplication Impact & Invariant

Direct empirical analysis across all 8 Parquet partitions verified:
- **Total Duplicate Rows:** Exactly **6,547 duplicates** on `(gateway_id, ts_utc)`.
- **Identity of Clones:** 100% of these 6,547 rows are identical full-row clones across all 57 columns.
- **Partition Concentration:**
  - `month=2025-09`: **2,185 duplicates**
  - `month=2025-11`: **2,124 duplicates**
  - `month=2026-01`: **2,238 duplicates**
  - All even months (Aug, Oct, Dec, Feb, Mar): **0 duplicates**.

### 8.1 Impact on Candidate Features
If aggregations are run on raw telemetry without deduplication:
- **F01 (`reported_hours_7d`):** Protected if using `nunique('ts_utc')`, but distorted if using raw `count()`.
- **F09 (`reboot_cnt_sum_7d`) & F12 (`disconnection_cnt_sum_7d`):** Artificially inflated by ~1.2% to 1.3% during odd-month baseline calculations.
- **Differencing ($\Delta t$):** Consecutive time differences produce spurious 0-second intervals ($t_k - t_{k-1} = 0$).
- **The Invariant:** All feature extraction logic must execute `.drop_duplicates(subset=['gateway_id', 'ts_utc'], keep='first')` immediately upon loading raw partitions.

---

## 9. Counter Feature Feasibility & Gap Mechanics

An empirical audit of consecutive hourly transitions in August 2025 (181,484 rows) revealed critical firmware counter behaviors:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        COUNTER TRANSITION DYNAMICS IN AUGUST TELEMETRY                 │
├──────────────────────────────────────┬──────────────────┬──────────────────────────────┤
│ Metric / Transition Type             │ Row Count        │ Percentage of Total Rows     │
├──────────────────────────────────────┼──────────────────┼──────────────────────────────┤
│ Total Telemetry Rows                 │ 181,484          │ 100.0%                       │
│ Zero offline_diff (Stationary)       │ 123,271          │ 67.92%                       │
│ Positive offline_diff (Accumulating) │ 28,993           │ 15.98% (Max jump: 716,110s)  │
│ Negative offline_diff (Reset/Drop)   │ 28,940           │ 15.95%                       │
│ Gaps > 1 Hour Between Readings       │ 18,722 gaps      │ —                            │
│ ├─ Gap where diff > 0 (Accumulated)  │ 5,318 gaps       │ 28.4% of gaps                │
│ ├─ Gap where diff < 0 (Reset)        │ 5,357 gaps       │ 28.6% of gaps                │
│ └─ Gap where offline_sec == 0        │ 10,287 gaps      │ 54.9% of gaps                │
└──────────────────────────────────────┴──────────────────┴──────────────────────────────┘
```

### 9.1 Technical Implications
1. **F06 (`offline_duration_max_7d`) is READY:**  
   Because $F06$ computes $\max_{t \in W} (\texttt{offline\_duration\_sec})$, it measures the **peak reported offline-duration counter value within the 7-day window**. It is mathematically immune to whether intermediate gaps reset or accumulated.  
   *Caveat (Observed Evidence vs Interpretation):* While $F06$ captures the maximum counter value recorded in the window, unresolved firmware-counter semantics mean this measures the highest reported counter state rather than definitively proving an uninterrupted single outage.
2. **F07 (`offline_duration_delta_7d`) is CONDITIONAL:**  
   *Observed Evidence:* In August telemetry across 18,722 multi-hour gaps, the observed transition across the gap was positive in 28.4% of gaps (counter value increased), negative in 28.6% of gaps (counter value dropped), and reported 0 on the first post-gap reading in 54.9% of gaps.  
   *Interpretation vs Assumption:* Summing positive differences ($\sum \max(0, \Delta C)$) requires an explicit convention for how to treat the transition following a multi-hour gap. Distinguishing true firmware resets from ongoing accumulation across unobserved intervals remains an unresolved firmware semantic requiring calibration.
3. **F08 (`offline_hours_gt_3600_7d`) is READY:**  
   Bypasses cumulative arithmetic by counting observations where the **reported offline-duration counter is $\ge 3600\text{ seconds}$**.  
   *Caveat (Observed Evidence vs Interpretation):* An observation with $C \ge 3600\text{s}$ indicates that the counter has accumulated to at least one hour; it does not prove that the specific observation hour itself represented a continuous one-hour outage.

---

## 10. Silence Feature Feasibility

Phase 5.1 confirms that silence-related features are **fully constructible and represent the highest-value operational signals**:

### 10.1 Constructibility via Master Outer Join
Because dead gateways produce zero rows in `telemetry`, silence cannot be computed by grouping telemetry alone. The feature engine must execute an **outer join / map** against the active universe in `gateway_master.csv`:
```python
# Fully verified vectorized construction:
hours_7d = w7.groupby('gateway_id')['ts'].nunique().to_dict()
active_df['F01_reported_hours_7d'] = active_df['gateway_id'].map(hours_7d).fillna(0)
active_df['F04_consec_missing'] = (monday - active_df['latest_ts']).dt.total_seconds() / 3600.0
active_df['F04_consec_missing'] = active_df['F04_consec_missing'].fillna(672.0) # 28d cap
active_df['F05_is_silent_7d'] = (active_df['F01_reported_hours_7d'] == 0).astype(int)
```

### 10.2 Communication Loss vs Hardware Failure
Silence measures **severe packet delivery failure**. While root causes remain physically ambiguous (power blackout, carrier tower failure, SIM failure, internal board fault), an active gateway emitting zero packets is causing 100% downstream meter collection loss. It addresses a major blind spot in `baseline_3sigma.py`: gateways with no telemetry observations cannot generate observed-telemetry anomalies.

---

## 11. Meter-Read Feature Feasibility

### 11.1 The Stale Data Reality
- **Dataset Horizon:** Terminates on `2026-01-26`.
- **Scored Window Horizon:** February 2 to March 23, 2026.
- **Feasibility Verdict:**  
  - Dynamic weekly meter features: **IMPOSSIBLE / DEFERRED** (0 records exist).
  - Static historical pre-February prior ($F17, F18$): **READY**.
  - Historical meter success rate ($F17$) can be computed strictly on $t < \text{2026-01-26}$ as a static contextual prior. Gateways with historically poor collection rates ($< 80\%$) represent compromised RF environments.

---

## 12. Lifecycle Feasibility

Feature **F19 (`is_lifecycle_active`)** is verified as a **READY Hard Operational Gate**:
- `installed_on` is 100% populated across all 332 Master gateways.
- Comparing `installed_on <= T` and `(decommissioned_on > T or null)` correctly screens the active candidate universe from 290 gateways in Week 1 to 308 gateways in Week 8.
- Assets failing $F19$ are masked with score $-\infty$, preventing guaranteed €380 false alarm penalties.

---

## 13. Initial Feature Redundancy Findings

A pairwise Pearson correlation matrix was computed across the 290 active gateways for Week 1 (`2026-02-02`):

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                    PAIRWISE CORRELATION MATRIX (WEEK 1, 290 ACTIVE GATEWAYS)             │
├──────┬───────┬───────┬───────┬───────┬───────┬───────┬───────┬───────┬───────┬──────────┤
│      │ F01   │ F02   │ F04   │ F06   │ F08   │ F09   │ F10   │ F12   │ F16   │ F17      │
├──────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┼───────┼──────────┤
│ F01  │  1.00 │ -1.00 │ -0.38 │ -0.57 │ -0.64 │ -0.26 │ -0.28 │ -0.61 │ -0.48 │  0.48    │
│ F02  │ -1.00 │  1.00 │  0.38 │  0.57 │  0.64 │  0.26 │  0.28 │  0.61 │  0.48 │ -0.48    │
│ F04  │ -0.38 │  0.38 │  1.00 │  0.17 │  0.26 │  0.12 │  0.10 │  0.27 │  0.33 │ -0.24    │
│ F06  │ -0.57 │  0.57 │  0.17 │  1.00 │  0.65 │  0.52 │  0.53 │  0.75 │  0.22 │ -0.34    │
│ F08  │ -0.64 │  0.64 │  0.26 │  0.65 │  1.00 │  0.42 │  0.44 │  0.67 │  0.39 │ -0.36    │
│ F09  │ -0.26 │  0.26 │  0.12 │  0.52 │  0.42 │  1.00 │  0.99 │  0.30 │  0.07 │ -0.11    │
│ F10  │ -0.28 │  0.28 │  0.10 │  0.53 │  0.44 │  0.99 │  1.00 │  0.31 │  0.06 │ -0.14    │
│ F12  │ -0.61 │  0.61 │  0.27 │  0.75 │  0.67 │  0.30 │  0.31 │  1.00 │  0.22 │ -0.39    │
│ F16  │ -0.48 │  0.48 │  0.33 │  0.22 │  0.39 │  0.07 │  0.06 │  0.22 │  1.00 │ -0.18    │
│ F17  │  0.48 │ -0.48 │ -0.24 │ -0.34 │ -0.36 │ -0.11 │ -0.14 │ -0.39 │ -0.18 │  1.00    │
└──────┴───────┴───────┴───────┴───────┴───────┴───────┴───────┴───────┴───────┴──────────┘
```

### 13.1 Key Redundancy Insights
1. **Exact Collinearity ($F01$ vs $F02$):** $r = -1.00$. $F02$ (`missing_hours_7d`) is strictly $168 - F01$. Both do not need to be in the same linear scoring model, though $F02$ is more intuitive for deficit scoring.
2. **Extreme Collinearity ($F09$ vs $F10$):** $r = 0.99$. Weekly reboot volume and 28-day reboot volume are nearly identical in ranking order. $F10$ should serve as a baseline normalization denominator ($F11$) rather than an independent additive feature.
3. **High Correlation ($F06$ vs $F12$):** $r = 0.75$. Peak offline duration correlates strongly with disconnection volume.
4. **Low Correlation / High Orthogonality ($F04$ & $F16$):**
   - $F04$ (`consecutive_missing_at_cutoff`) has $r = 0.17$ with $F06$ and $r = 0.12$ with $F09$. Ongoing silence provides completely distinct operational information from internal sensor metrics.
   - $F16$ (`acute_chronic_divergence`) has $r = 0.07$ with reboots and $r = 0.22$ with disconnections, providing an orthogonal signal of sudden operational collapse.

---

## 14. Actionable Feature Categorization

Based on data availability, mathematical constructibility, and parameter dependencies, the 20 candidate features are classified into three operational categories:

### 14.1 READY (15 Features)
*Features that can be immediately implemented in vectorized Python code without unresolved dependencies or tuning blockers:*
1. **F01** (`reported_hours_7d`)
2. **F02** (`missing_hours_7d`)
3. **F03** (`reporting_ratio_7d`)
4. **F04** (`consecutive_missing_at_cutoff`)
5. **F05** (`is_completely_silent_7d`)
6. **F06** (`offline_duration_max_7d`)
7. **F08** (`offline_hours_gt_3600_7d`)
8. **F09** (`reboot_cnt_sum_7d`)
9. **F10** (`reboot_cnt_sum_28d`)
10. **F12** (`disconnection_cnt_sum_7d`)
11. **F16** (`acute_chronic_divergence`)
12. **F17** (`hist_meter_success_pre_feb` — static prior)
13. **F18** (`hist_meter_outage_freq` — static prior)
14. **F19** (`is_lifecycle_active` — hard gating filter)
15. **F20** (`installed_age_days` — secondary tie-breaker)

*(Total: 15 constructible features).*

### 14.2 CONDITIONAL (4 Features)
*Features that are technically constructible but require empirical parameter calibration or specific gap-handling conventions:*
1. **F07** (`offline_duration_delta_7d`): Dependent on post-gap reconnection counter conventions.
2. **F11** (`reboot_intensity_ratio`): Requires small-denominator smoothing to prevent explosive ratios on small baseline counts.
3. **F14** (`reboot_and_offline_syndrome`): Requires threshold tuning for $\theta_{\text{reboot}}$ and $\theta_{\text{offline}}$.
4. **F15** (`flapping_and_offline_syndrome`): Requires threshold tuning for $\theta_{\text{disconn}}$ and $\theta_{\text{offline}}$.

### 14.3 DEFERRED (1 Feature)
*Features exhibiting high numerical instability, extreme volatility, or lack of diagnostic value:*
1. **F13** (`disconn_to_offline_ratio`): Extreme volatility when offline duration is small; redundant with $F06$ and $F12$. Deferred from initial ranking engine.

---

## 15. Operational Assumptions

1. **UTC Date Alignment:** We assume all timestamps in telemetry (`ts_utc`) and metadata (`installed_on`, `decommissioned_on`) represent UTC calendar boundaries.
2. **First Packet Reset Independence:** We assume that using Peak Envelope ($F06$) provides sufficient outage severity information without requiring exact resolution of post-gap counter resets.
3. **Static Prior Aging:** We assume historical meter collection rates prior to January 26, 2026 remain informative baseline proxies through March 2026.
4. **Candidate Universe Definition:** We assume the ranking universe for each Monday $T$ consists of all gateways satisfying $F19=1$ (290 to 308 gateways).

---

## 16. Unresolved Questions for Phase 5.2 / Phase 6

1. **Reconnection Counter Semantics:** During Phase 5.2 pipeline construction, test whether resetting negative deltas to zero introduces cumulative drift compared to peak envelope.
2. **Optimal Parameter Tuning:** Candidate thresholds will be proposed in Phase 5 and empirically evaluated during Phase 6 backtesting (e.g. calibrating cutoffs for $F04$ at $\theta = 48\text{h}$ vs $72\text{h}$, and $F14$ at $\theta_r = 5, \theta_o = 7200\text{s}$) to minimize total financial loss.
3. **Collinear Feature Pruning:** Determine whether retaining both $F09$ and $F10$ harms ranking precision, or if taking the ratio ($F11$) is superior.

---

## 17. What Phase 5.2 Should Do Next

With feature feasibility verified, Phase 5.2 will execute:
1. **Pipeline Implementation:** Construct a clean, vectorized Python class (`FeatureExtractor`) implementing all 15 **READY** features.
2. **Outer-Join Silence Engine:** Implement the master metadata mapping ensuring completely silent gateways receive accurate silence features ($F04, F05$).
3. **Reproducibility Verification:** Validate that extracted feature matrices for all 8 scored weeks match verified distributions and execute in under 30 seconds.

---

## 18. Interview Defense Notes

### Q1: Why are you testing feature feasibility before scoring?
> *"In applied machine learning, teams often design mathematical scoring formulas before verifying whether the required data actually exists. In NEXORA, doing that would lead to disaster: `meter_read_success.csv` abruptly ends on January 26, 2026, and the engineer review is dated February 15. If we had built a ranking formula assuming live weekly meter reads or engineer reviews, the pipeline would produce 100% missing data or severe lookahead leakage during the scored window. Testing feasibility first ensures every signal is verified against data reality."*

### Q2: Why can't every Phase 4 feature automatically be used?
> *"Some candidate features depend on unresolved firmware semantics or uncalibrated parameters. For example, `offline_duration_delta_7d` requires knowing how counters behave after multi-day blackouts, and interaction syndromes require tuning specific thresholds. By classifying features into READY, CONDITIONAL, and DEFERRED, we can build a robust, reproducible core pipeline immediately while deferring experimental features to empirical backtesting."*

### Q3: How do you know a feature does not leak future information?
> *"We enforced a strict right-open temporal boundary: for any prediction Monday $T$ at 00:00:00 UTC, features consume data strictly from $t < T$. Furthermore, we verified dataset-specific cutoff horizons: meter data is frozen as a pre-February static prior, and the February 15 engineer review is physically excluded from Weeks 1 and 2."*

### Q4: Why is ID normalization part of feature engineering?
> *"Gateway identifiers appear in two incompatible representations: 17-character colon-delimited strings (`06:39:EA:56:02:C1`) in Master metadata and 12-character bare hex strings (`0639EA5602C1`) in Telemetry Parquet. A standard inner join yields exactly 0 matching records. Standardizing on a canonical 12-character bare uppercase hex format is an architectural necessity to prevent silent join failure."*

### Q5: Why must duplicates be handled before aggregation?
> *"We proved that telemetry contains exactly 6,547 full-row duplicate records concentrated in odd months. If aggregations like hourly reboot sums or time differences are calculated before deduplication, metrics are double-counted, artificially inflating anomaly scores and distorting variance calculations."*

### Q6: Why are cumulative counters difficult?
> *"`offline_duration_sec` is a cumulative counter reaching 726,642 seconds (~8.4 days). Naively summing raw hourly readings squares the true downtime—an asset offline for 5 hours reporting $[3600, 7200, 10800, 14400, 18000]$ would yield 15 hours of computed downtime. In Phase 5.1, we proved that Peak Window Envelope ($F06$), representing the peak reported offline-duration counter value within the window, is constructible and robust because it bypasses compounding entirely (while respecting the caveat that counter semantics reflect reported state rather than verified physical continuity)."*

### Q7: Why is silence useful but not proof of hardware failure?
> *"Silence indicates a complete absence of telemetry packets reaching the broker. While it can be caused by site power cuts, SIM deactivation, or carrier outages, an active gateway that is completely silent cannot relay utility meter readings, generating an immediate €600/week unaddressed outage loss. It addresses a major blind spot in `baseline_3sigma.py`: gateways with no telemetry observations cannot generate observed-telemetry anomalies, making silence a major operational signal."*

### Q8: Why is meter-read history treated differently?
> *"Because `meter_read_success.csv` ends on January 26, 2026, exactly zero meter records exist during the February–March scored window. It cannot serve as a live dynamic indicator. It can only be utilized as a static pre-February prior reflecting baseline RF collection quality."*

### Q9: What does READY vs CONDITIONAL mean?
> *"READY features have verified raw column availability, well-defined mathematical transformations, and zero tuning blockers, making them suitable for immediate production implementation. CONDITIONAL features are constructible but depend on empirical parameter calibration (such as threshold cutoffs) or unresolved counter-gap semantics that must be evaluated in Phase 6 backtesting."*

### Q10: Why haven't you removed correlated features yet?
> *"Phase 5.1 is an exploratory feasibility audit, not final feature selection. While we discovered extreme collinearity between 7-day and 28-day reboots ($r = 0.99$) and inverse identity between reported and missing hours ($r = -1.00$), removing features prematurely without testing their empirical ranking impact would be unscientific. Feature pruning and weight optimization belong to Phase 5.2 and Phase 6."*

---

> Phase 5.1 status: FEATURE FEASIBILITY VERIFIED & CLASSIFIED — READY FOR PHASE 5.2
