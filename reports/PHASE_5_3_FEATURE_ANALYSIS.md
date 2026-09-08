# Phase 5.3 — Feature Correlation, Distribution Analysis & Pruning Recommendations

**LPDG Innovation Hub Selection Challenge 2026 (NEXORA 2026)**  
**Author:** Candidate Engineering Team  
**Status:** Complete & Validated across all 8 Scored Mondays ($N=2,393$ Gateway-Weeks)  
**Parent Contract:** `reports/PHASE_5_1_FEATURE_FEASIBILITY.md`  
**Pipeline Implementation:** `reports/PHASE_5_2_FEATURE_EXTRACTION.md`, `src/nexora/feature_extractor.py`  
**Executable Companion Artifact:** `notebooks/03_feature_analysis.ipynb`  

---

## 1. Executive Summary & Scope Boundaries

### 1.1 Objective
Micro-Phase 5.3 conducts an empirical statistical investigation of the **15 approved READY features** extracted by the validated Phase 5.2 pipeline across all 8 scored prediction Mondays (`2026-02-02` through `2026-03-23`, $N=2,393$ total gateway-week instances).

The objective is to establish:
1. **Empirical Distribution Properties:** Full quantile profiles (1%, 5%, 25%, 50%, 75%, 95%, 99%), standard deviations, and skewness.
2. **Sparsity & Constant Behavior:** Identification of zero-inflated signals, near-constant distributions, and clarification of the architectural role of $F19$.
3. **Outlier & Counter Characteristics:** Assessment of heavy right tails and cumulative firmware counter artifacts ($F06 > 700,000\text{s}$).
4. **Redundancy & Multicollinearity:** Rigorous Pearson (linear) and Spearman (rank) correlation matrices to detect mathematical duplicates and collinear feature pairs.
5. **Gateway-Level Retrospective Association Analysis:** Methodologically sound retrospective comparisons against historical work orders in `field_visits.csv` and categories in `engineer_review_2026-02.xlsx`.
6. **Defensible Feature Pruning Recommendations:** Assigning every feature an evidence-backed categorization (`KEEP`, `KEEP_WITH_TRANSFORMATION`, `DROP_FOR_RANKING`, `DEFER_TO_BACKTEST`, or `KEEP — AS ELIGIBILITY GATE, NOT RANKING SIGNAL`).

### 1.2 Strict Micro-Phase Boundaries
- **NO final ranking formulas** or composite risk score implementations.
- **NO feature weights** ($w_1, w_2, \dots$) or optimization.
- **NO machine learning training** (classifiers, regressors, or clustering).
- **NO modifications** to `baseline_3sigma.py`, `validate_submission.py`, `predictions.csv`, or raw `data/`.
- **NO Git commits** performed.

---

## 2. Feature Inventory & Panel Dimensions

The analyzed dataset comprises **2,393 rows** representing 100% of the active gateway universe across all 8 evaluation Mondays ($290 \to 308$ active nodes per week).

The 15 analyzed features span 6 operational families:
1. **Availability:** $F01$ (`reported_hours_7d`), $F02$ (`missing_hours_7d`), $F03$ (`reporting_ratio_7d`), $F04$ (`consecutive_missing_at_cutoff`), $F05$ (`is_completely_silent_7d`), $F16$ (`acute_chronic_divergence`)
2. **Offline Behavior:** $F06$ (`offline_duration_max_7d`), $F08$ (`offline_hours_gt_3600_7d`)
3. **Reboot Behavior:** $F09$ (`reboot_cnt_sum_7d`), $F10$ (`reboot_cnt_sum_28d`)
4. **Connectivity Drops:** $F12$ (`disconnection_cnt_sum_7d`)
5. **Historical Meter Reliability:** $F17$ (`hist_meter_success_pre_feb`), $F18$ (`hist_meter_outage_freq`)
6. **Lifecycle Eligibility:** $F19$ (`is_lifecycle_active`), $F20$ (`installed_age_days`)

---

## 3. Comprehensive Distribution Analysis

Across all $N=2,393$ observations, zero explicit nulls exist due to deterministic extraction rules:

| ID | Feature Name | Missing | N Unique | Top Val % | Min | Q01 | Q05 | Q25 | Median | Mean | Q75 | Q95 | Q99 | Max | Std | Skewness | Distribution Shape |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **F01** | `reported_hours_7d` | 0 | 145 | 5.2% | 0.0 | 29.0 | 79.0 | 140.0 | 155.0 | 143.82 | 161.0 | 166.0 | 167.0 | 168.0 | 28.47 | -2.40 | Left-skewed (healthy peak) |
| **F02** | `missing_hours_7d` | 0 | 145 | 5.2% | 0.0 | 1.0 | 2.0 | 7.0 | 13.0 | 24.18 | 28.0 | 89.0 | 139.0 | 168.0 | 28.47 | +2.40 | Right-skewed deficit |
| **F03** | `reporting_ratio_7d` | 0 | 145 | 5.2% | 0.00 | 0.17 | 0.47 | 0.83 | 0.92 | 0.86 | 0.96 | 0.99 | 0.99 | 1.00 | 0.17 | -2.40 | Left-skewed ratio $[0, 1]$ |
| **F04** | `consecutive_missing_at_cutoff`| 0 | 36 | 86.2% | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 2.53 | 1.0 | 2.0 | 21.0 | 672.0 | 24.31 | +26.38 | Point-mass at 1.0h, heavy tail |
| **F05** | `is_completely_silent_7d` | 0 | 2 | 99.9% | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.00 | 0.0 | 0.0 | 0.0 | 1.0 | 0.04 | +28.21 | Binary sparse (3 events) |
| **F06** | `offline_duration_max_7d` | 0 | 2074 | 3.8% | 0.0 | 0.0 | 473.0 | 1908.0 | 4500.0 | 34239.64 | 11686.0 | 137834.0 | 726642.0 | 726642.0 | 116733.53 | +5.02 | Extreme right tail (counters) |
| **F08** | `offline_hours_gt_3600_7d` | 0 | 88 | 43.2% | 0 | 0 | 0 | 0 | 1.0 | 6.60 | 3.0 | 43.0 | 73.0 | 108.0 | 15.22 | +3.10 | Right-skewed count |
| **F09** | `reboot_cnt_sum_7d` | 0 | 79 | 79.9% | 0 | 0 | 0 | 0 | 0.0 | 4.61 | 0.0 | 24.0 | 94.0 | 928.0 | 39.62 | +17.20 | Zero-inflated (79.9% 0) |
| **F10** | `reboot_cnt_sum_28d` | 0 | 138 | 69.4% | 0 | 0 | 0 | 0 | 0.0 | 16.32 | 1.0 | 85.0 | 303.8 | 3275.0 | 128.88 | +17.50 | Zero-inflated (69.4% 0) |
| **F12** | `disconnection_cnt_sum_7d` | 0 | 424 | 4.4% | 0 | 0 | 1.0 | 6.0 | 20.0 | 112.64 | 73.0 | 639.4 | 1714.8 | 2662.0 | 294.07 | +4.89 | Right-skewed count |
| **F16** | `acute_chronic_divergence` | 0 | 199 | 55.3% | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.02 | 0.02 | 0.12 | 0.28 | 0.45 | 0.05 | +4.33 | Zero-inflated (55.3% 0) |
| **F17** | `hist_meter_success_pre_feb` | 0 | 290 | 3.8% | 0.00 | 0.00 | 0.22 | 0.78 | 0.89 | 0.82 | 0.93 | 0.96 | 0.97 | 1.00 | 0.20 | -2.92 | Left-skewed $[0, 1]$ |
| **F18** | `hist_meter_outage_freq` | 0 | 2 | 99.3% | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.04 | 0.00 | +12.11 | Near-constant (99.3% 0) |
| **F19** | `is_lifecycle_active` | 0 | 1 | 100.0% | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.00 | 1.0 | 1.0 | 1.0 | 1.0 | 0.00 | 0.00 | Perfectly constant (1.0) |
| **F20** | `installed_age_days` | 0 | 1441 | 0.3% | 0.0 | 6.0 | 31.0 | 629.0 | 1116.0 | 1198.83 | 1890.0 | 2471.0 | 2541.0 | 2576.0 | 737.74 | +0.13 | Multimodal installation cohorts |

---

## 4. Sparsity & Constant Feature Analysis

### 4.1 $F19$ (`is_lifecycle_active`) — Hard Gate vs Ranking Signal
- **Observed Fact:** Across all 2,393 panel observations, $F19 \equiv 1.0$ with standard deviation $0.00$ and zero variance.
- **Architectural Role:** $F19$ is evaluated *during* universe filtering: assets failing $	ext{installed\_on} \le T \land (	ext{decommissioned\_on} > T \lor 	ext{null})$ are completely excluded from the candidate pool.
- **Decision:** $F19$ provides **zero ranking variance**. It must never be assigned a ranking weight ($w_{19} \cdot F19$) because adding a constant to all assets shifts scores identically without altering rank order. It is retained strictly as an **eligibility gate**.

### 4.2 $F18$ (`hist_meter_outage_freq`) — Fleet-Wide Near-Zero Variance
- **Observed Fact:** Across the 7,226 rows in `meter_read_success.csv` (covering 299 gateways across 26 weeks), exactly **2 rows** report zero meters read (`02C0F45F31E7` on 2025-11-03 and `0A568E79FEF6` on 2025-12-15).
- **Interpretation:** Across the active fleet, 99.3% of gateways have $F18 = 0.000$, and exactly two gateways have $F18 = 1/26 pprox 0.038$.
- **Recommendation:** **`DROP_FOR_RANKING`**. $F18$ lacks the variation required to distinguish candidate failure across a 300-gateway fleet.

### 4.3 $F05$ (`is_completely_silent_7d`) — Rare Catastrophic Signal & Conditional Status
- **Observed Fact:** Across 2,393 gateway-weeks, $F05=1$ occurs exactly **3 times**:
  - `0EA061007895` on `2026-02-09` (same-day commissioning asset; age 0 days).
  - `0EE587927263` on `2026-03-02` (same-day commissioning asset; age 0 days).
  - `02D3289B907C` on `2026-03-09` (same-day commissioning asset; age 0 days).
- **Critical Semantic Finding:** All 3 observed cases in the scored sample occurred on **newly commissioned gateways with age 0 days**, rather than sudden failures of established units.
- **Recommendation:** **`KEEP — CONDITIONAL OVERRIDE CANDIDATE`**. Complete silence is operationally critical (addressing the baseline blind spot on zero-row dead nodes), but because all observed cases in the evaluation window represent newly commissioned assets, an automatic failure override is not yet justified. Phase 6 must test silence among established gateways ($F20 > 7	ext{d}$) and determine whether it improves top-15 precision. No override is implemented in Phase 5.3.

---

## 5. Outliers & Cumulative Counter Behavior

### 5.1 The $F06$ (`offline_duration_max_7d`) Counter Scale
- **Observed Fact:** The median $F06$ is 4,500 seconds (1.25 hours), but the 95th percentile is 137,834 seconds (38.3 hours), and the maximum reaches **726,642 seconds (~8.41 days / 201.8 hours)**.
- **Root Cause:** As established in Phase 3 and Phase 5.1, `offline_duration_sec` is an accumulating hardware timer that rolls over across observation weeks unless reset by firmware or connection restoration.
- **Operational Risk:** If raw $F06$ is fed directly into an additive linear scoring model, a single gateway reporting $726,642	ext{s}$ will mathematically overwhelm all other signals ($F02 \le 168$, $F09 \le 50$) by orders of magnitude.
- **Recommendation:** **`KEEP_WITH_TRANSFORMATION`**. Apply $\log(1 + F06)$ or min-max normalization against a physical lookback ceiling ($168 	imes 3600 = 604,800	ext{s}$).

### 5.2 $F04$ (`consecutive_missing_at_cutoff`) Distribution
- **Observed Fact:** 86.2% of active gateways report $F04 = 1.0	ext{h}$ (normal hourly cadence). Only 5% report $F04 \ge 2.0	ext{h}$, and only 1% report $F04 \ge 21.0	ext{h}$. The 3 silent new assets hit the 672.0-hour cap.
- **Recommendation:** **`KEEP_WITH_TRANSFORMATION`**. Cap at a sensible persistence threshold (e.g. $\min(F04, 72.0	ext{h})$) or apply non-linear scaling to prevent the 672h cap from distorting score distributions.

---

## 6. Correlation & Multicollinearity Analysis

Pairwise Pearson (linear) and Spearman (rank) correlation matrices across the 14 varying features ($N=2,393$):

### 6.1 Pearson Correlation Matrix (Linear)
```
      F01   F02   F03   F04   F05   F06   F08   F09   F10   F12   F16   F17   F18   F20
F01  1.00 -1.00  1.00 -0.25 -0.18 -0.66 -0.69 -0.32 -0.31 -0.67 -0.50  0.34 -0.28  0.02
F02 -1.00  1.00 -1.00  0.25  0.18  0.66  0.69  0.32  0.31  0.67  0.50 -0.34  0.28 -0.02
F03  1.00 -1.00  1.00 -0.25 -0.18 -0.66 -0.69 -0.32 -0.31 -0.67 -0.50  0.34 -0.28  0.02
F04 -0.25  0.25 -0.25  1.00  0.98  0.03  0.03  0.01  0.01  0.02  0.04 -0.16  0.04 -0.05
F05 -0.18  0.18 -0.18  0.98  1.00 -0.01 -0.02 -0.00 -0.00 -0.01 -0.01 -0.15 -0.00 -0.06
F06 -0.66  0.66 -0.66  0.03 -0.01  1.00  0.65  0.44  0.41  0.78  0.35 -0.11  0.23  0.05
F08 -0.69  0.69 -0.69  0.03 -0.02  0.65  1.00  0.40  0.38  0.69  0.41 -0.14  0.05  0.04
F09 -0.32  0.32 -0.32  0.01 -0.00  0.44  0.40  1.00  0.93  0.33  0.15 -0.02 -0.01 -0.01
F10 -0.31  0.31 -0.31  0.01 -0.00  0.41  0.38  0.93  1.00  0.32  0.08 -0.03 -0.01 -0.00
F12 -0.67  0.67 -0.67  0.02 -0.01  0.78  0.69  0.33  0.32  1.00  0.27 -0.16  0.20  0.04
F16 -0.50  0.50 -0.50  0.04 -0.01  0.35  0.41  0.15  0.08  0.27  1.00  0.02  0.04  0.01
F17  0.34 -0.34  0.34 -0.16 -0.15 -0.11 -0.14 -0.02 -0.03 -0.16  0.02  1.00 -0.19  0.21
F18 -0.28  0.28 -0.28  0.04 -0.00  0.23  0.05 -0.01 -0.01  0.20  0.04 -0.19  1.00  0.09
F20  0.02 -0.02  0.02 -0.05 -0.06  0.05  0.04 -0.01 -0.00  0.04  0.01  0.21  0.09  1.00
```

### 6.2 Spearman Rank Correlation Matrix (Monotonic)
```
      F01   F02   F03   F04   F05   F06   F08   F09   F10   F12   F16   F17   F18   F20
F01  1.00 -1.00  1.00 -0.41 -0.06 -0.55 -0.61 -0.41 -0.46 -0.71 -0.36  0.52 -0.13  0.01
F02 -1.00  1.00 -1.00  0.41  0.06  0.55  0.61  0.41  0.46  0.71  0.36 -0.52  0.13 -0.01
F03  1.00 -1.00  1.00 -0.41 -0.06 -0.55 -0.61 -0.41 -0.46 -0.71 -0.36  0.52 -0.13  0.01
F04 -0.41  0.41 -0.41  1.00  0.10  0.32  0.35  0.25  0.27  0.33  0.16 -0.21  0.14  0.06
F05 -0.06  0.06 -0.06  0.10  1.00 -0.06 -0.04 -0.02 -0.02 -0.06 -0.03 -0.06 -0.00 -0.06
F06 -0.55  0.55 -0.55  0.32 -0.06  1.00  0.91  0.33  0.35  0.47  0.18 -0.25  0.00 -0.01
F08 -0.61  0.61 -0.61  0.35 -0.04  0.91  1.00  0.36  0.38  0.54  0.18 -0.29  0.02  0.01
F09 -0.41  0.41 -0.41  0.25 -0.02  0.33  0.36  1.00  0.82  0.38  0.15 -0.25 -0.02  0.08
F10 -0.46  0.46 -0.46  0.27 -0.02  0.35  0.38  0.82  1.00  0.41  0.10 -0.31 -0.00  0.13
F12 -0.71  0.71 -0.71  0.33 -0.06  0.47  0.54  0.38  0.41  1.00  0.15 -0.38  0.00  0.00
F16 -0.36  0.36 -0.36  0.16 -0.03  0.18  0.18  0.15  0.10  0.15  1.00  0.02  0.01  0.04
F17  0.52 -0.52  0.52 -0.21 -0.06 -0.25 -0.29 -0.25 -0.31 -0.38  0.02  1.00 -0.13  0.02
F18 -0.13  0.13 -0.13  0.14 -0.00  0.00  0.02 -0.02 -0.00  0.00  0.01 -0.13  1.00  0.09
F20  0.01 -0.01  0.01  0.06 -0.06 -0.01  0.01  0.08  0.13  0.00  0.04  0.02  0.09  1.00
```

---

## 7. Redundancy & Feature Family Analysis

### 7.1 Mathematical Duplicates: $F01 \leftrightarrow F02 \leftrightarrow F03$
- **Observed Invariants:** $F02 \equiv 168 - F01$ ($r = -1.00$), $F03 \equiv F01 / 168.0$ ($r = +1.00$).
- **Impact:** Retaining all three in an additive formula adds duplicate degrees of freedom with zero added information.
- **Resolution:** **`KEEP F02`**, **`DROP F01 and F03`**. $F02$ (`missing_hours_7d`) directly quantifies the *operational deficit* (0 hours = perfect; 168 hours = complete outage), which scales naturally with penalty weighting.

### 7.2 Chronic Reboot Collinearity: $F09 \leftrightarrow F10$
- **Observed Correlation:** Pearson $r = 0.93$, Spearman $ho = 0.82$.
- **Interpretation:** The 7-day sum ($F09$) and 28-day sum ($F10$) identify nearly identical problematic nodes.
- **Resolution:** **`KEEP F09`** as the primary acute ranking signal. **`DEFER F10 TO BACKTEST`** as a candidate denominator for the reboot intensity ratio ($F11 = F09 / \max(1, F10/4)$).

### 7.3 Offline Redundancy: $F06 \leftrightarrow F08$
- **Observed Correlation:** Spearman rank correlation $ho = 0.91$.
- **Interpretation:** Peak counter duration ($F06$) and the count of observations exceeding 1 hour ($F08$) capture the same underlying downtime.
- **Resolution:** **`KEEP F06 (WITH TRANSFORMATION)`**; **`DEFER F08 TO BACKTEST`** to determine whether peak duration or hour-count yields better backtesting precision in Phase 6.

### 7.4 Orthogonality of Failure Modes: $F04$ & $F16$
- **Observed Fact:** $F04$ has $r \le 0.03$ with reboots and disconnections. $F16$ has $ho = 0.15$ with reboots and disconnections.
- **Interpretation:** Ongoing silence ($F04$) and sudden availability collapse ($F16$) provide completely independent, non-redundant diagnostic information from internal sensor metrics ($F09, F12$). Both must be preserved.

---

## 8. Gateway-Level Retrospective Association Analysis

### 8.1 Explicit Methodology & Temporal Contract
- **Analysis Level:** This comparison is conducted at the **gateway level**, comparing historical maintenance history against feature values extracted for Week 1 (`2026-02-02`, $W_7 = [	ext{2026-01-26}, 	ext{2026-02-02})$).
- **Temporal Alignment:** All historical work orders in `field_visits.csv` occurred strictly before `2026-02-02` (created between `2025-02-03` and `2026-01-30`). The Week 1 features chronologically follow the historical visit period.
- **Aggregation Handling:** Multiple visits for the same gateway are aggregated into cumulative lifetime categories:
  - `Ever Repaired` ($N=144$): Gateways with $\ge 1$ visit resulting in `Fehler behoben` (component replacement/repair).
  - `Only No-Fault` ($N=94$): Gateways visited but where all outcomes were `Kein Fehler gefunden` or `Kein Zugang`.
  - `Never Visited` ($N=52$): Gateways with zero historical work orders logged prior to February 2026.
- **Important Invariant:** **This analysis is retrospective exploratory evidence and does not establish event-level temporal prediction.** It evaluates whether historical problem assets exhibit chronically worse telemetry properties on the eve of the scored evaluation period.

### 8.2 Retrospective Findings against Historical Work Orders (`field_visits.csv`)

| Operational Metric | Ever Repaired Gateways ($N=144$) | Only No-Fault Gateways ($N=94$) | Never Visited Gateways ($N=52$) | Observed Retrospective Association |
|:---|:---:|:---:|:---:|:---|
| **F01 (reported hours)** | Median: 151.0 h | Median: 157.5 h | Median: 159.5 h | Repaired assets have ~7h higher packet deficit |
| **F02 (missing hours)** | Median: 17.0 h | Median: 10.5 h | Median: 8.5 h | Repaired assets have double the missingness |
| **F06 (peak offline sec)** | Median: 5,243 s | Median: 3,359 s | Median: 4,396 s | Repaired assets show higher peak offline durations |
| **F08 (offline hours > 3.6k)** | Median: 1.0 h (Mean: 8.1) | Median: 0.0 h (Mean: 5.8) | Median: 1.0 h (Mean: 1.0) | Repaired assets have higher chronic outage hours |
| **F09 (reboots 7d)** | Mean: 5.72 reboots | Mean: 1.06 reboots | Mean: 0.12 reboots | **Over 5x higher reboot volume in repaired units** |
| **F10 (reboots 28d)** | Mean: 18.57 reboots | Mean: 5.02 reboots | Mean: 0.54 reboots | **Chronic reboot elevation in problem assets** |
| **F12 (disconnections 7d)** | Median: 26.5 drops | Median: 22.5 drops | Median: 6.0 drops | Repaired assets experience 4x drops vs never-visited |
| **F16 (acute divergence)** | Mean: 0.029 | Mean: 0.016 | Mean: 0.005 | **6x higher sudden divergence in repaired units** |
| **F17 (hist meter success)** | Median: 0.816 | Median: 0.921 | Median: 0.932 | **Compromised RF collection rate (<82%) in repaired units** |

### 8.3 Retrospective Alignment with Engineer Review (`2026-02-15`)
Evaluated strictly for Week 3 (`2026-02-16`):

| Feature Code | `Schlecht` (Poor Condition, $N=53$) | `Normal` (Healthy, $N=54$) | Retrospective Separation Observed |
|:---|:---:|:---:|:---|
| **F01 (reported hours)** | Median: 128.5 h | Median: 155.0 h | -26.5 hours reporting deficit in poor units |
| **F02 (missing hours)** | Median: 39.5 h | Median: 13.0 h | **3x higher missingness in poor condition units** |
| **F06 (peak offline sec)** | Median: 14,511 s (~4.0h) | Median: 4,252 s (~1.2h) | **3.4x higher peak offline counter in poor units** |
| **F08 (chronic offline h)** | Median: 6.0 h | Median: 1.0 h | **6x higher chronic offline hours** |
| **F12 (disconnections)** | Median: 142.0 drops | Median: 17.0 drops | **8.3x higher connection drop rate in poor units** |
| **F17 (hist meter success)** | Median: 0.79 | Median: 0.87 | Lower historical read collection in poor units |

*Temporal Warning:* Engineer review occurred on `2026-02-15`. It is strictly invalid as an input for Week 1 (Feb 2) or Week 2 (Feb 9). The above table is purely retrospective exploratory validation of feature diagnostic relevance.

---

## 9. Comprehensive Feature Pruning & Recommendation Table

Every one of the 15 features is assigned an evidence-backed categorization:

| ID | Feature | Family | Variation | Skew / Outliers | Redundancy | Retrospective Evidence | Recommendation | Engineering Rationale |
|:---|:---|:---|:---:|:---:|:---|:---|:---:|:---|
| **F01** | `reported_hours_7d` | Availability | High | Moderate (-2.40) | Exact with F02 ($r=-1.00$) | Median 151h in repaired vs 159.5h in never-visited | **DROP_FOR_RANKING** | Redundant linear inverse of F02; F02 is superior for deficit scoring. |
| **F02** | `missing_hours_7d` | Availability | High | Moderate (+2.40) | Exact with F01/F03 | Median 17h in repaired vs 8.5h in never-visited; 39.5h in Schlecht | **KEEP** | Primary direct measure of weekly operational availability deficit. |
| **F03** | `reporting_ratio_7d` | Availability | High | Moderate (-2.40) | Exact with F01/F02 | Identical rank information to F01 | **DROP_FOR_RANKING** | Redundant scalar multiple ($F01 / 168.0$); omit from ranking model. |
| **F04** | `consecutive_missing_at_cutoff` | Availability | Tail Only | Extreme (skew +26.38) | Low with reboots/disconn | Captures ongoing blackouts leading into dispatch Monday | **KEEP_WITH_TRANSFORMATION** | Primary ongoing blackout signal; apply cap ($\le 72	ext{h}$) or log scaling to handle 672h cap. |
| **F05** | `is_completely_silent_7d` | Availability | Sparse (0.1%) | Binary indicator | High collinearity with extreme F04 | Direct solution to baseline blind spot on zero-row dead nodes | **KEEP — CONDITIONAL OVERRIDE CANDIDATE** | Complete silence is operationally critical, but all 3 observed cases in the scored sample occurred on newly commissioned gateways (age 0d). An automatic failure override is not yet justified; Phase 6 must test silence among established gateways. |
| **F06** | `offline_duration_max_7d` | Offline Behavior | Very High | Extreme spikes (>700k sec) | High with F08 ($ho=0.91$) and F12 ($r=0.78$) | Median 5,243s in repaired vs 3,359s in no-fault; 14.5k in Schlecht | **KEEP_WITH_TRANSFORMATION** | Peak outage duration; apply $\log(1 + F06)$ to stabilize cumulative firmware counter spikes. |
| **F08** | `offline_hours_gt_3600_7d` | Offline Behavior | Moderate | Right-skewed (skew +3.10) | High rank corr with F06 ($ho=0.91$) | 6h median in Schlecht vs 1h in Normal | **DEFER_TO_BACKTEST** | High redundancy with F06; test whether counter duration or threshold count yields better precision in Phase 6. |
| **F09** | `reboot_cnt_sum_7d` | Reboot Behavior | Zero-Inflated (79.9% 0) | Heavy tail (skew +17.20) | High with F10 ($r=0.93$) | Mean 5.72 reboots in repaired vs 0.12 in never-visited | **KEEP** | Direct acute weekly reboot storm indicator; strong empirical association with component failure. |
| **F10** | `reboot_cnt_sum_28d` | Reboot Behavior | Zero-Inflated (69.4% 0) | Heavy tail (skew +17.50) | High with F09 ($r=0.93$) | Chronic baseline elevated in problem assets | **DEFER_TO_BACKTEST** | Collinear with F09; defer to Phase 6 to test as normalization denominator for surge intensity ($F11$). |
| **F12** | `disconnection_cnt_sum_7d` | Connectivity | High | Heavy tail (max 2,662 drops) | Moderate with F06 ($r=0.78$) | Median 142 drops in Schlecht vs 17 in Normal | **KEEP_WITH_TRANSFORMATION** | Backhaul connection drop volume; apply log1p or percentile capping to dampen carrier noise. |
| **F16** | `acute_chronic_divergence` | Availability | Moderate | Right-skewed (skew +4.33) | Low with reboots/disconn ($ho=0.15$) | Mean 0.029 in repaired vs 0.005 in never-visited | **KEEP** | Clean orthogonal signal capturing sudden availability drop relative to 21d chronic baseline. |
| **F17** | `hist_meter_success_pre_feb` | Historical Meter | Moderate | Left-skewed (-2.92) | Low with live telemetry | Median 0.816 in repaired vs 0.932 in never-visited | **DEFER_TO_BACKTEST** | Valuable pre-Feb prior, but requires evaluation of missing baseline handling for post-Jan 26 nodes. |
| **F18** | `hist_meter_outage_freq` | Historical Meter | Near-Zero | 99.3% zeros (only 2 active assets) | Weak | Lacks variation across 99.3% of fleet | **DROP_FOR_RANKING** | Near-constant feature with zero variance across almost entire fleet; omit from candidate scoring. |
| **F19** | `is_lifecycle_active` | Lifecycle | Zero (Constant) | Identically 1.0 across all rows | N/A | Hard eligibility filter | **KEEP — AS ELIGIBILITY GATE, NOT RANKING SIGNAL** | Hard candidate universe gate; zero ranking variance by definition. |
| **F20** | `installed_age_days` | Lifecycle | High | Uniform across cohorts (skew +0.13) | Near-zero with operational distress | Weak direct separation on acute failures | **DROP_FOR_RANKING** | F20 is not used in ranking or tie-breaking. It is retained for lifecycle/context analysis only. |

---

## 10. Summary of Pruning Impact

```
┌────────────────────────────────────────────────────────────────────────┐
│               PHASE 5.3 CANDIDATE FEATURE PRUNING SUMMARY               │
├───────────────────────────────┬───────┬────────────────────────────────┤
│ Category                      │ Count │ Feature IDs                    │
├───────────────────────────────┼───────┼────────────────────────────────┤
│ KEEP (Direct Candidates)      │   3   │ F02, F09, F16                  │
│ KEEP — CONDITIONAL OVERRIDE   │   1   │ F05 (silence indicator)        │
│ KEEP_WITH_TRANSFORMATION      │   3   │ F04 (capped), F06 (log1p),     │
│                               │       │ F12 (log1p)                    │
│ DEFER_TO_BACKTEST             │   3   │ F08, F10, F17                  │
│ DROP_FOR_RANKING              │   4   │ F01 (collinear), F03 (collinear),│
│                               │       │ F18 (near-constant), F20 (age) │
│ HARD ARCHITECTURAL GATE       │   1   │ F19 (eligibility gate)         │
├───────────────────────────────┼───────┼────────────────────────────────┤
│ Total Features Analyzed       │  15   │ 100% Phase 5.1 READY Features  │
└───────────────────────────────┴───────┴────────────────────────────────┘
```

---

## 11. Known Limitations & Backtesting Guidance for Phase 6

1. **Retrospective Causality Caveat:** Retrospective association with historical field visits does not prove future causality. A high disconnection count ($F12$) may reflect regional cell-tower maintenance rather than a broken antenna.
2. **Post-January 26 Commissioning Imputation:** 33 gateways installed after January 26 have $F17 = 0.0$ and $F18 = 0.0$ because meter history ended. In Phase 6, if $F17$ is included in ranking, post-Jan 26 nodes must be imputed with fleet median (~0.89) rather than penalized as 0% collection sites.
3. **Cumulative Counter Drift:** Firmware counter resets remain unobserved during complete silence. Log-transforming $F06$ dampens the scale but does not eliminate counter ambiguity.

---

## 12. Next Steps: Advancing to Phase 6 — Historical Backtesting

Phase 5.3 successfully reduces the 15 features to a **compact, orthogonal, defensible candidate set** (3 core signals + 1 conditional override + 3 transformed signals + 3 backtest options), eliminating exact collinearities ($F01, F03$), non-varying noise ($F18$), and non-diagnostic age attributes ($F20$).

**Phase 6 — Historical Backtesting** will systematically evaluate candidate transformations, feature subsets, ranking strategies, and net operational utility under the challenge's €380 false alarm vs €600 unaddressed outage cost function.
