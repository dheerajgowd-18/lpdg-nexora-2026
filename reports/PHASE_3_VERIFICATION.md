# Phase 3 Verification

**Project:** LPDG Innovation Hub Selection Challenge 2026 (NEXORA 2026)  
**Author:** Candidate Engineering Team  
**Review Type:** Micro-Phase 3.1 — Independent Empirical Verification  
**Date:** September 2026  
**Reference Document:** [PHASE_3_DEEP_DATA_INVESTIGATION.md](PHASE_3_DEEP_DATA_INVESTIGATION.md)  
**Investigation Notebook:** [01_deep_data_investigation.ipynb](../notebooks/01_deep_data_investigation.ipynb)

---

## 1. Verification Summary

This document presents an independent, cell-by-cell empirical audit of the quantitative claims, statistical calculations, and domain conclusions set forth in the Phase 3 Deep Data Investigation report. Every claim was recalculated directly from the raw data files (`data/telemetry/**/*.parquet`, `data/gateway_master.csv`, `data/meter_read_success.csv`, `data/field_visits.csv`, and `data/engineer_review_2026-02.xlsx`).

| # | Topic / Claim | Reported Value | Verified Value | Verification Status | Key Audit Finding / Caveat |
| :- | :--- | :--- | :--- | :--- | :--- |
| **1** | **Telemetry Implicit Missingness** | ~23.2% missing hourly reports (432,853 missing rows) | 23.19% (unconditioned); 13.12%–13.52% (active lifetime) | **VERIFIED WITH CAVEAT** | Arithmetic verified under unconditioned denominator (`320 × 5,832`). ~10% is structural (future commissioning / past decommissioning); ~13.5% is true operational downtime. |
| **2** | **Exact Telemetry Duplicates** | Exactly 6,547 duplicates across 57 columns in odd months | Exactly 6,547 duplicate pairs (100% full-row identical) | **VERIFIED** | Verified across all columns. Exactly 2,185 (Sep 2025), 2,124 (Nov 2025), 2,238 (Jan 2026). Overcounts unadjusted aggregations by ~1.2%. |
| **3** | **Gateway ID Format Inconsistency** | 2 formats: colon-delimited (`06:39:...`) vs. bare hex (`0639...`) | Verified: 17-char colon hex vs. 12-char bare hex | **VERIFIED** | Raw inner join yields exactly 0 matches. Normalization to bare uppercase hex is strictly mandatory. |
| **4** | **Cumulative Firmware Counters** | `offline_duration_sec` and `reboot_duration_sec` accumulate across hours | Verified: values reach 726,642s (offline) and 439,061s (reboot) | **VERIFIED** | Values exceed 3,600s in 4.6% of August rows. Firmware accumulates across outage intervals without hourly clamping. |
| **5** | **Historical Field Visit Outcomes** | 60.7% no-fault rate (`Kein Fehler gefunden`, 390 / 642) | 60.75% (390 / 642); 34.74% fixed (223); 4.52% no access (29) | **VERIFIED** | Verified on exact 642 work orders. Strongly supports the €380 false-dispatch penalty concern. |
| **6** | **Meter-Read Temporal Coverage** | Ends on `2026-01-26`; 0 overlap with scored window | Min: `2025-08-04`, Max: `2026-01-26` (26 weeks); 0 scored overlap | **VERIFIED** | Cannot be used as live trailing feature during Feb–Mar 2026. Serves strictly as historical asset baseline. |
| **7** | **Engineer Review Leakage Boundary** | Conducted `2026-02-15`; lookahead for Weeks 1 and 2 | Exactly 1 date (`2026-02-15`), 120 gateways, 60/60 split | **VERIFIED** | Weeks 1 (`2026-02-02`) and 2 (`2026-02-09`) precede review. Using it prior to Feb 15 constitutes severe lookahead leakage. |
| **8** | **Gateways with No Telemetry** | Exactly 12 gateways in Master have zero telemetry rows | Exactly 12 gateways; all installed May–July 2026 | **VERIFIED** | Commissioning dates are in the future relative to the data window. Must be masked from prediction sets. |
| **9** | **Hours Reported vs. Meter Success Correlation** | Correlation of approximately +0.742 | +0.742 (3-month sample); +0.786 (full 6-month overlap) | **VERIFIED WITH EXTENSION** | Reported value matched 3-month sample. Full 26-week overlap yields an even stronger +0.786 correlation. |
| **10**| **Fault vs. Normal Telemetry Ratios** | ~4.7× higher offline time and ~6.1× higher reboots in true faults | 4.71× offline mean ratio (1.91M vs. 406k); 6.17× reboot mean ratio (47.2 vs. 7.7) | **VERIFIED WITH CAVEAT** | Arithmetic verified on 313 windowed visits. Skewed tails mean medians differ even more dramatically (38.8× offline ratio). |
| **11**| **Engineer Review Telemetry Separation** | 13.6× higher offline duration; 9.0× higher disconnections | 13.64× offline ratio (1.18M vs. 86.3k); 8.99× disconnection ratio (348.9 vs. 38.8) | **VERIFIED WITH CAVEAT** | Computed on 107 reporting gateways. 13 audited gateways reported 0 hours in the trailing 7 days and were excluded by standard mean. |

---

## 2. Detailed Verification

### Claim 1: Telemetry Implicit Missingness
- **Claim:** Telemetry exhibits approximately 23.2% implicit missingness (432,853 missing hourly records).
- **Reported Value:** ~23.2% missingness (`432,853 / 1,866,240`).
- **Verified Value:**
  - Unconditioned observation window: 243 calendar days × 24 hours = 5,832 expected hours.
  - Total observed gateways in telemetry: 320.
  - Theoretical maximum records: `320 × 5,832 = 1,866,240`.
  - Actual records in Parquet: 1,433,387.
  - Unconditioned missing records: `1,866,240 - 1,433,387 = 432,853` (**23.1938%**, exactly matching reported arithmetic).
  - Deduplicated records in Parquet: 1,426,840 (`439,400` missing rows, **23.5443%**).
  - Active-lifetime conditioned expected hours (accounting for gateways installed mid-period in Feb/Mar 2026 and decommissioned mid-period between Sep 2025 and Feb 2026): **1,649,940 expected hours**.
  - Active-lifetime missingness: `(1,649,940 - 1,433,387) / 1,649,940` = **13.12%** (or **13.52%** deduplicated).
- **Status:** **VERIFIED WITH CAVEAT**
- **Method:** Evaluated full timestamp boundaries across all 8 Parquet files using PyArrow metadata and Pandas aggregation, comparing simple fixed-box expectation against gateway active operational lifetime derived from `gateway_master.csv`.
- **Important Caveat:** The reported 23.2% figure represents an unconditioned network-level missingness against a static 320-gateway assumption. In reality, **~9.7% of this missingness is structural** (8 gateways installed in Feb/Mar 2026 had not yet been deployed, and 12 gateways were decommissioned before March 2026). The true operational drop-out rate during active deployment is **~13.5%**. Both figures are operationally meaningful, but must be distinguished.

---

### Claim 2: Exact Telemetry Duplicates
- **Claim:** Telemetry contains exactly 6,547 duplicate records on `(gateway_id, ts_utc)`, all of which are 100% identical full-row duplicates concentrated in odd-month partitions.
- **Reported Value:** 6,547 duplicate records (2,185 in Sep 2025; 2,124 in Nov 2025; 2,238 in Jan 2026).
- **Verified Value:**
  - `(gateway_id, ts_utc)` duplicate count: **6,547**.
  - Full-row duplicate count across all 57 columns: **6,547**.
  - Monthly distribution:
    - `month=2025-08`: 0
    - `month=2025-09`: **2,185**
    - `month=2025-10`: 0
    - `month=2025-11`: **2,124**
    - `month=2025-12`: 0
    - `month=2026-01`: **2,238**
    - `month=2026-02`: 0
    - `month=2026-03`: 0
- **Status:** **VERIFIED**
- **Method:** Iterated over all Parquet partitions, evaluating `.duplicated(subset=['gateway_id', 'ts_utc'])` against `.duplicated()` across all dataframe columns.
- **Important Caveat:** Because these 6,547 rows are 100% identical clones of existing rows within the same partition, unweighted cumulative metrics (`SUM(offline_duration_sec)`) will double-count downtime for duplicated hours unless deduplicated prior to window aggregation.

---

### Claim 3: Gateway ID Formats
- **Claim:** Two divergent gateway ID formats exist across datasets, requiring normalization for cross-table joins.
- **Reported Value:** Colon-separated 17-char hex (`06:39:EA:56:02:C1`) in Master, Field Visits, and Review; Bare 12-char hex (`0639EA5602C1`) in Telemetry and Meter Reads.
- **Verified Value:**
  - `gateway_master.csv`: `06:39:EA:56:02:C1`
  - `field_visits.csv`: `02:30:EE:F7:24:35`
  - `engineer_review_2026-02.xlsx`: `06:5B:92:87:16:CD`
  - `telemetry` (Parquet): `0639EA5602C1`
  - `meter_read_success.csv`: `0202CB0A6B1F`
  - Unnormalized inner join between `gateway_master` and `telemetry`: **0 matches**.
  - Normalized inner join (`v.replace(':', '').upper()`): **320 matches**.
- **Status:** **VERIFIED**
- **Method:** Extracted raw string samples from each table and executed unnormalized vs. normalized set intersections.
- **Important Caveat:** The official submission validator (`validate_submission.py`) accepts both formats in `predictions.csv`. However, internal data joins between asset metadata and telemetry require normalization to prevent silent dropouts.

---

### Claim 4: Cumulative Firmware Counters
- **Claim:** `offline_duration_sec` and `reboot_duration_sec` behave as cumulative firmware counters rather than hourly 0–3,600s rates.
- **Reported Value:** Values reach up to 726,642s (`offline_duration_sec`) and 439,061s (`reboot_duration_sec`) in single hourly rows.
- **Verified Value:**
  - Maximum `offline_duration_sec` in August: **726,642 seconds (~201.8 hours / 8.4 days)**.
  - Maximum `reboot_duration_sec` in August: **439,061 seconds (~121.9 hours / 5.1 days)**.
  - Hourly records exceeding 3,600s in August: **8,354 rows (4.60%)** for offline duration; **921 rows (0.51%)** for reboot duration.
  - Time-series inspection confirms values accumulate across consecutive dropouts and reset when connectivity stabilizes.
- **Status:** **VERIFIED**
- **Method:** Inspected distribution quantiles and consecutive hourly sequences for high-downtime gateways (e.g. `0E121B6B8661`, `06B641B75B29`).
- **Important Caveat:** The Data Dictionary explicitly states: *"offline_duration_sec: Backhaul offline time counter, seconds"*. It does not claim values are bounded by 3,600 seconds. Treating this column as a simple hourly rate would distort baseline calculations.

---

### Claim 5: Historical Field Visits (60.7% No-Fault Rate)
- **Claim:** 60.7% of historical field visits concluded with `Kein Fehler gefunden` (€380 wasted per visit).
- **Reported Value:** 60.7% (390 of 642 visits).
- **Verified Value:**
  - Total work orders in `field_visits.csv`: **642**.
  - `Kein Fehler gefunden` (No fault found): **390 (60.7477% -> 60.75%)**.
  - `Fehler behoben` (Fault resolved): **223 (34.7352% -> 34.74%)**.
  - `Kein Zugang` (Access denied): **29 (4.5171% -> 4.52%)**.
- **Status:** **VERIFIED**
- **Method:** Executed frequency value counts on `field_visits['outcome']` across all 642 records.
- **Important Caveat:** This empirical finding confirms that historical dispatch practice was highly inefficient, heavily justifying the Challenge Brief’s cost structure where false dispatches carry a €380 penalty.

---

### Claim 6: Meter-Read Temporal Coverage
- **Claim:** `meter_read_success.csv` ends on `2026-01-26` and has zero overlap with the scored prediction window.
- **Reported Value:** Final week: `2026-01-26`; 26 total weeks; 0 scored weeks overlap.
- **Verified Value:**
  - Earliest `week_start`: `2025-08-04`.
  - Latest `week_start`: `2026-01-26`.
  - Distinct weeks count: **26**.
  - Scored prediction Mondays: `2026-02-02` through `2026-03-23` (8 weeks).
  - Direct overlap between `meter_read_success` and scored window: **0 weeks**.
- **Status:** **VERIFIED**
- **Method:** Checked min/max dates, unique counts, and set intersection against `SCORED_WEEKS` defined in `baseline_3sigma.py`.
- **Important Caveat:** For Week 1 (`2026-02-02`), trailing meter-read data (`2026-01-26`) is fresh. By Week 8 (`2026-03-23`), meter-read data is 8 weeks old. Any ranking model relying on live meter reading updates will suffer severe data staleness.

---

### Claim 7: Engineer Review Leakage Boundary
- **Claim:** `engineer_review_2026-02.xlsx` was conducted on `2026-02-15`. Using it for Weeks 1 and 2 is a lookahead leakage violation.
- **Reported Value:** Review date: `2026-02-15` (single date); 120 gateways; 60 Schlecht / 60 Normal.
- **Verified Value:**
  - Unique `reviewed_on` values: `['2026-02-15']` (100% of rows).
  - Total gateways reviewed: **120**.
  - Breakdown: **60 `Schlecht`**, **60 `Normal`**.
  - Week 1 (`2026-02-02`) and Week 2 (`2026-02-09`) occurred strictly before `2026-02-15`.
- **Status:** **VERIFIED**
- **Method:** Analyzed date column in `engineer_review_2026-02.xlsx` and compared chronological boundaries against scored Mondays.
- **Important Caveat:** This review is strictly out-of-bounds for predictive ranking on Weeks 1 and 2. It can only be used as a post-hoc evaluation check on Week 3 (`2026-02-16`) or later.

---

### Claim 8: Gateways with No Telemetry
- **Claim:** Exactly 12 gateways in `gateway_master.csv` have no telemetry because their installation dates are in mid-2026.
- **Reported Value:** 12 gateways; installation dates in May, June, July 2026.
- **Verified Value:**
  - Master gateways count: 332.
  - Telemetry gateways count: 320.
  - Difference: Exactly **12 gateways**.
  - Minimum `installed_on` for these 12: `2026-05-07`.
  - Maximum `installed_on` for these 12: `2026-07-14`.
- **Status:** **VERIFIED**
- **Method:** Set difference between normalized master IDs and telemetry IDs, followed by date inspection in `gateway_master.csv`.
- **Important Caveat:** These 12 gateways represent future network expansion. They must be explicitly masked from ranking consideration in Phase 4.

---

### Claim 9: Hours Reported vs. Meter Success Correlation
- **Claim:** Correlation between weekly `hours_reported` and meter-read success rate is approximately **+0.742**.
- **Reported Value:** +0.742 correlation (reported based on 3,628 aligned gateway-weeks).
- **Verified Value:**
  - On the 3-month sample (Aug–Oct 2025, 3,628 gateway-weeks): **$r = +0.742070$** (matches reported value exactly).
  - On the **full 6-month overlap** (Aug 2025 – Jan 2026, all 26 weeks, 7,223 gateway-weeks): **$r = +0.785934$** (~+0.786).
  - Full-period correlations for all candidate signals:
    - `hours_reported`: **+0.786**
    - `offline_sec_sum`: **-0.603** (vs. -0.618 reported on 3-month sample)
    - `disc_cnt_sum`: **-0.557** (vs. -0.580 reported on 3-month sample)
    - `reboot_cnt_sum`: **-0.282** (vs. -0.300 reported on 3-month sample)
    - `rx_pkts_sum`: **-0.005** (vs. -0.001 reported on 3-month sample)
- **Status:** **VERIFIED WITH EXTENSION**
- **Method:** Aligned telemetry timestamps to Monday week boundaries (`ts - dayofweek`), aggregated weekly sums/counts, and computed Pearson correlation against `meters_read / meters_expected`.
- **Important Caveat:** The Phase 3 report calculated this correlation across a 3-month sample (3,628 rows) to conserve memory. Evaluating across the full 26-week overlapping period (7,223 rows) confirms the relationship is even stronger (+0.786). Methodologically, this correlation is computed on gateway-weeks with at least one reported hour (inner join). Gateways completely dark for the entire week emit 0 rows, so this correlation actually *understates* the impact of complete silence.

---

### Claim 10: Fault vs. Normal Telemetry Ratios
- **Claim:** Confirmed component fixes (`Fehler behoben`) had ~4.7× higher offline duration and ~6.1× higher reboot counts prior to visits than false-alarm visits (`Kein Fehler gefunden`).
- **Reported Value:** 4.71× offline mean ratio (1,913,525.5s vs. 405,962.1s); 6.17× reboot mean ratio (47.2 vs. 7.7).
- **Verified Value:**
  - Evaluated sample: 313 visits attended between `2025-08-15` and `2026-02-15` (117 `Fehler behoben`, 182 `Kein Fehler gefunden`, 14 `Kein Zugang`).
  - Pre-visit Mean Offline Seconds:
    - `Fehler behoben`: **1,913,525.5 seconds**
    - `Kein Fehler gefunden`: **405,962.1 seconds**
    - Mean Ratio: `1,913,525.5 / 405,962.1` = **4.7135× (~4.7×)**.
  - Pre-visit Mean Reboots:
    - `Fehler behoben`: **47.2 reboots**
    - `Kein Fehler gefunden`: **7.65 reboots**
    - Mean Ratio: `47.2 / 7.65` = **6.1699× (~6.1×)**.
  - Pre-visit Median Offline Seconds:
    - `Fehler behoben`: **895,071.0 seconds**
    - `Kein Fehler gefunden`: **23,042.5 seconds**
    - Median Ratio: `895,071.0 / 23,042.5` = **38.84×**!
- **Status:** **VERIFIED WITH CAVEAT**
- **Method:** Grouped telemetry by gateway, isolated 7-day windows strictly preceding each work order's `visited_on` timestamp, and aggregated sums by outcome category.
- **Important Caveat:** The arithmetic means match the report exactly. However, looking only at the 4.7× mean ratio obscures how clean the separation truly is: because false alarms contain a few outlier dropouts, their mean is inflated to 405k seconds, but their *median* is only 23k seconds. True faults have a median offline time of nearly 900k seconds (a **38.8× median separation**).

---

### Claim 11: Engineer Review Telemetry Separation
- **Claim:** Gateways classified as `Schlecht` exhibited 13.6× higher offline duration and 9.0× higher disconnections in the 7 days prior to review.
- **Reported Value:** 13.6× offline ratio (1,176,507s vs. 86,265s); 9.0× disconnection ratio (348.9 vs. 38.8).
- **Verified Value:**
  - Window: 7 days strictly before `2026-02-15 00:00:00Z` (`2026-02-08` to `2026-02-15`).
  - Audited gateways reporting telemetry in this window: 107 (55 `Normal`, 52 `Schlecht`).
  - Mean Offline Seconds:
    - `Schlecht`: **1,176,507.3 seconds**
    - `Normal`: **86,265.0 seconds**
    - Ratio: `1,176,507.3 / 86,265.0` = **13.638× (~13.6×)**.
  - Mean Disconnections:
    - `Schlecht`: **348.9 disconnections**
    - `Normal`: **38.8 disconnections**
    - Ratio: `348.94 / 38.80` = **8.993× (~9.0×)**.
- **Status:** **VERIFIED WITH CAVEAT**
- **Method:** Filtered telemetry for the 7-day window prior to Feb 15, joined with `engineer_review_2026-02.xlsx`, and computed category averages.
- **Important Caveat:** Exactly 13 of the 120 audited gateways (5 `Normal`, 8 `Schlecht`) emitted **0 telemetry rows** during the trailing 7 days prior to Feb 15. The standard Pandas `.mean()` calculation automatically dropped these 13 non-reporting gateways. If those 8 silent `Schlecht` gateways were dark due to complete power failure, their offline duration was technically 100%, further supporting the engineer's verdict.

---

## 3. Corrections

The following methodological clarifications and sample adjustments should be recorded:

1. **Missingness Denominator Distinction:**
   - *Reported formulation:* 23.2% missingness across `320 gateways × 5,832 hours = 1,866,240` expected records.
   - *Correction:* Approximately **9.7 percentage points** of this missingness is structural (gateways not yet commissioned or already decommissioned). The true operational drop-out rate during active deployment is **~13.5%**.
2. **Correlation Sample Horizon:**
   - *Reported formulation:* $r = +0.742$ between `hours_reported` and meter success based on a 3-month sample (3,628 rows).
   - *Correction / Extension:* Evaluating across the full 26-week overlapping period (7,223 rows) yields an even stronger positive correlation: **$r = +0.786$**.
3. **Pre-Visit Telemetry Sample Window:**
   - *Reported formulation:* General statements regarding field visits.
   - *Clarification:* Pre-visit telemetry verification is strictly valid only for the **313 visits** attended between August 15, 2025 and February 15, 2026. The 329 visits prior to August 1, 2025 lack telemetry and cannot be verified with sensor data.
4. **Engineer Review Zero-Hour Gateway Exclusions:**
   - *Reported formulation:* Category averages presented without sample-size qualifier.
   - *Clarification:* 13 of the 120 gateways had zero telemetry rows in the 7-day window and were dropped from the arithmetic mean.

---

## 4. Evidence That Can Safely Influence Ranking

To prevent noise and false dispatches in Phase 4, empirical evidence is categorized by robustness:

### Strong Evidence (High Operational Confidence)
- **Silence Penalty (Missing Telemetry Hours):** Strongest positive correlate with meter-reading performance ($r = +0.786$). Unpowered/dead gateways stop transmitting entirely.
- **Persistent Cumulative Offline Duration:** True hardware faults exhibit 38.8× higher median offline seconds than false alarms; strongly separates engineer audit ($13.6×$).
- **Boot Loop Intensity (`reboot_cnt`):** Reboots drop by 35% following physical repair. Identifies failing power supplies and firmware crashes.
- **Asset Lifecycle Masking:** Excluding the 12 future-commissioned gateways (installed May–July 2026) and masking decommissioned units prior to scored Mondays prevents guaranteed false dispatches.
- **Telemetry Deduplication:** Deduplicating the 6,547 identical row clones in odd-month partitions prevents skewed downtime aggregations.

### Moderate Evidence (Useful as Prior or Secondary Filter)
- **Historical Meter-Read Deficit (`success_rate` up to Jan 26):** Excellent historical asset-level health indicator, but cannot be used as an updating dynamic feature during the scored window due to the data cliff.
- **Parts Replaced Distribution:** Hardware swaps, power supplies, and antennas account for the majority of physical fixes; confirms physical failure modes.
- **Disconnection Flapping (`disconnection_cnt`):** Useful indicator of degraded cellular/power stability, but must be paired with offline duration to avoid flagging benign cellular handovers.

### Weak / Unproven / Unsafe Evidence (Do NOT Base Ranking On)
- **Statistical Anomaly Scores Alone (`Auffaellige Statistik`):** Initiating visits based on statistical outlier flags produced a **0.0% fault resolution rate** historically (100% false alarms/no access). Naive 3-sigma scoring directly mimics this failure.
- **Radio Packet CRC Ratio (`rx_crc_bad / rx_nr_pkts`):** Bad CRC packets exceed valid packets in 38.5% of hours network-wide due to raw RF background noise. Does not indicate gateway hardware failure.
- **Cellular Signal Strength Bands (`rssi_bad`, `rscp_rsrp_bad`):** `Signal schwach` dispatches yielded **0% component repairs**. Cellular coverage is an environmental property of the building/basement that technician visits cannot remedy.
- **Engineer Review Labels for Early Scored Weeks:** Direct temporal lookahead leakage for Weeks 1 and 2.

---

## 5. Data Risks Relevant to Phase 4/5

1. **The Meter-Read Data Cliff:** Zero meter-read data exists after `2026-01-26`. The ranking engine must rely primarily on live telemetry for dynamic weekly ranking.
2. **The 3-Sigma Dead Gateway Blind Spot:** `baseline_3sigma.py` filters strictly on reported hours, completely blinding it to gateways that go 100% silent during the evaluation week.
3. **Cumulative Counter Differencing:** `offline_duration_sec` does not clamp to 3,600s/hour. Scoring must use thresholding, diffing, or duration clipping rather than treating it as an instantaneous rate.
4. **Encoding Fragility:** `gateway_master.csv` requires Latin-1 encoding in production pipelines.
5. **Lookahead Bias:** Strictly enforce $t < T_{	ext{Monday}}$ temporal masking on all feature generation pipelines.

---

## 6. Final Phase 3 Status

**VERIFIED WITH CORRECTIONS — READY FOR PHASE 4**

### Justification:
All 11 primary quantitative claims, ratios, and domain insights from Phase 3 were successfully verified against the raw datasets. The minor corrections (differentiating structural from operational missingness, extending the correlation calculation to the full 26-week horizon, and noting median vs. mean skewness) enhance the engineering defensibility of the findings. 

The empirical foundation is solid, reproducible, and ready to freeze before entering Phase 4 (Ranking Strategy & Scoring Design).
