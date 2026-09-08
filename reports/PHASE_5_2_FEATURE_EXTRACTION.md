# Phase 5.2 — Deterministic Feature Extraction Pipeline

**LPDG Innovation Hub Selection Challenge 2026 (NEXORA)**  
**Author:** Candidate Engineering Team  
**Status:** Complete & Fully Validated against Phase 5.1 Contract across all 8 Scored Mondays  
**Execution Timestamp:** 2026-03-24 (Simulated Evaluation Run)  
**Parent Specification:** `reports/PHASE_5_1_FEATURE_FEASIBILITY.md`  
**Reference Specification:** `reports/PHASE_4_2_FEATURE_SPECIFICATION.md`  
**Companion Artifacts:**
- Core Library: `src/nexora/data_loader.py`, `src/nexora/feature_extractor.py`, `src/nexora/__init__.py`
- Executable Verification Notebook: `notebooks/02_feature_extraction_validation.ipynb`
- Verification Suite: `scratch/validate_20_checks.py`

---

## 1. Executive Summary & Scope Boundaries

### 1.1 Objective
Micro-Phase 5.2 implements a reusable, strictly deterministic, leak-free feature-extraction layer in pure Python/Pandas (`src/nexora/`). It operationalizes the **exact 15 READY features** defined in the authoritative Phase 5.1 contract (`reports/PHASE_5_1_FEATURE_FEASIBILITY.md`) without modifying raw data, inventing heuristic ranking formulas, or assigning predictive weights.

### 1.2 Strict Scope Boundaries Enforced
- **NO ranking formulas or composite risk scores:** No candidate scores or heuristic weights ($w_1, w_2, \dots$) are computed.
- **NO machine learning models:** No classifiers, clustering algorithms, or regression models are fitted.
- **NO hyperparameter optimization:** Threshold tuning is deferred to historical backtesting in Phase 6.
- **NO modification of challenge files:** `baseline_3sigma.py`, `validate_submission.py`, `predictions.csv`, and source files in `data/` remain strictly unmodified.
- **NO Git commits:** All changes are maintained in the working tree for explicit review.

---

## 2. Authoritative Feature Contract Mapping (15 READY Features)

Every implemented feature corresponds directly to the approved Phase 5.1 specification:

| Feature ID | Feature Name | Exact Operational Definition | Data Source | Window ($T = 	ext{Monday 00:00:00Z}$) | Validation Status |
|:---|:---|:---|:---|:---|:---:|
| **F01** | `reported_hours_7d` | Count of unique observed hourly timestamps: $\|\mathcal{H}_i(W_7)\| = \|\{ t \in [T-7\text{d}, T) \mid \text{telemetry exists} \}\|$. | `telemetry` (`ts_utc`) | $[T - 7\text{d}, T)$ | **VALIDATED** |
| **F02** | `missing_hours_7d` | Hourly packet deficit relative to 168-hour continuous operation: $168 - F01$. Exactly verifies $F02 == 168 - F01$. | `telemetry` (`ts_utc`) | $[T - 7\text{d}, T)$ | **VALIDATED** |
| **F03** | `reporting_ratio_7d` | Normalized reporting availability fraction: $F01 / 168.0 \in [0.0, 1.0]$. | `telemetry` (`ts_utc`) | $[T - 7\text{d}, T)$ | **VALIDATED** |
| **F04** | `consecutive_missing_at_cutoff` | Elapsed hours from $T$ to the latest reported packet timestamp before $T$: $(T - \max(t < T)) / 3600\text{s}$. If no telemetry exists in $[T-28\text{d}, T)$, capped at 672.0 hours. | `telemetry` (`ts_utc`) | $[T - 28\text{d}, T)$ | **VALIDATED** |
| **F05** | `is_completely_silent_7d` | Complete weekly blackout indicator: $1 \text{ if } F01 == 0 \text{ else } 0$. | `telemetry` (`ts_utc`) | $[T - 7\text{d}, T)$ | **VALIDATED** |
| **F06** | `offline_duration_max_7d` | Peak reported counter value of `offline_duration_sec` within $[T-7\text{d}, T)$: $\max_{t \in W_7}(\texttt{offline\_duration\_sec})$. Evaluated without differencing. | `telemetry` (`offline_duration_sec`) | $[T - 7\text{d}, T)$ | **VALIDATED** |
| **F08** | `offline_hours_gt_3600_7d` | Count of telemetry observations where reported counter is $\ge 3,600$ seconds: $\sum_{t \in W_7} \mathbf{1}_{\{\texttt{offline\_duration\_sec} \ge 3600\}}$. | `telemetry` (`offline_duration_sec`) | $[T - 7\text{d}, T)$ | **VALIDATED** |
| **F09** | `reboot_cnt_sum_7d` | Sum of incremental hourly reboot events in the trailing 7 days: $\sum_{t \in W_7} \texttt{reboot\_cnt}$. | `telemetry` (`reboot_cnt`) | $[T - 7\text{d}, T)$ | **VALIDATED** |
| **F10** | `reboot_cnt_sum_28d` | Sum of incremental hourly reboot events in the trailing 28 days: $\sum_{t \in W_{28}} \texttt{reboot\_cnt}$. Chronic reboot baseline. | `telemetry` (`reboot_cnt`) | $[T - 28\text{d}, T)$ | **VALIDATED** |
| **F12** | `disconnection_cnt_sum_7d` | Sum of incremental hourly backhaul disconnection events in trailing 7 days: $\sum_{t \in W_7} \texttt{disconnection\_cnt}$. | `telemetry` (`disconnection_cnt`) | $[T - 7\text{d}, T)$ | **VALIDATED** |
| **F16** | `acute_chronic_divergence` | Sudden collapse in availability: drop from prior 21-day average availability to recent 7-day availability: $\max\left(0, \frac{\|\mathcal{H}_i(W_{21})\|}{21 \times 24} - \frac{\|\mathcal{H}_i(W_7)\|}{7 \times 24}\right)$. | `telemetry` (`ts_utc`) | $[T - 28\text{d}, T)$ vs $[T - 7\text{d}, T)$ | **VALIDATED** |
| **F17** | `hist_meter_success_pre_feb` | Static historical collection success rate prior to February: $\frac{\sum \texttt{meters\_read}}{\sum \texttt{meters\_expected}}$ for $t \le \text{2026-01-26}$. | `meter_read_success.csv` | Static ($t \le \text{2026-01-26}$) | **VALIDATED** |
| **F18** | `hist_meter_outage_freq` | Static historical fraction of zero-read weeks prior to February: $\frac{1}{N_{\text{weeks}}} \sum \mathbf{1}_{\{\texttt{meters\_read} == 0\}}$ for $t \le \text{2026-01-26}$. | `meter_read_success.csv` | Static ($t \le \text{2026-01-26}$) | **VALIDATED** |
| **F19** | `is_lifecycle_active` | Asset operational status at $T$: $\mathbf{1}_{\{\texttt{installed\_on} \le T \;\land\; (\texttt{decommissioned\_on} > T \;\lor\; \text{null})\}}$. Hard gating filter; identically 1 for all returned rows. | `gateway_master.csv` | Evaluated at $T$ | **VALIDATED** |
| **F20** | `installed_age_days` | Operational lifespan exposure: $(T - \texttt{installed\_on}) / 86,400\text{s}$, measured in elapsed decimal days. | `gateway_master.csv` | Evaluated at $T$ | **VALIDATED** |

---

## 3. Implementation Details & Architectural Invariants

### 3.1 Gateway ID Canonicalization (`normalize_gateway_id`)
Raw datasets store gateway identifiers in two incompatible formats:
- `gateway_master.csv`: 17-character colon-delimited hex (e.g. `06:39:EA:56:02:C1`).
- `telemetry/` Parquet partitions & `meter_read_success.csv`: 12-character bare hex (e.g. `0639EA5602C1`).

`DataLoader` applies `normalize_gateway_id` uniformly upon load, converting all keys to bare, 12-character uppercase hexadecimal strings.

### 3.2 Deduplication Invariant
Across the 8 monthly telemetry partitions, exactly **6,547 full-row duplicate records** exist (concentrated in odd months: September 2025, November 2025, and January 2026).  
`DataLoader.load_telemetry()` executes:
```python
df = df.drop_duplicates(subset=['gateway_id', 'ts_utc'], keep='first')
```
This guarantees that no observation key contributes more than once to any feature aggregation.

### 3.3 Strict Temporal Cutoff ($t < T$)
For any evaluation Monday $T$:
- Trailing 7-day window: $[T - 7\text{d}, T) = [T - 168\text{h}, T)$.
- Trailing 28-day window: $[T - 28\text{d}, T) = [T - 672\text{h}, T)$.
- Prior 21-day baseline: $[T - 28\text{d}, T - 7\text{d}) = [T - 672\text{h}, T - 168\text{h})$.
- Strict Invariant: Every timestamp $\ge T$ is unconditionally dropped before feature extraction. Zero lookahead leakage is possible.

### 3.4 Active Universe & Silence Retention (Outer Join)
Dead gateways emit zero rows in telemetry. Grouping telemetry alone would omit silent units—a severe failure mode present in `baseline_3sigma.py`.  
`FeatureExtractor` begins with `get_active_universe(T)` from `gateway_master.csv` (filtering $\text{installed\_on} \le T$ and $\text{decommissioned\_on} > T$), and maps telemetry features onto this active register via dictionaries. Active gateways with zero telemetry in $[T-7\text{d}, T)$ are preserved with:
- $F01 = 0$
- $F02 = 168$
- $F03 = 0.0$
- $F05 = 1$
- $F06 = 0.0$
- $F08 = 0$
- $F09 = 0$
- $F10 = 0$ (or historical 28d sum if observed in $[T-28\text{d}, T-7\text{d})$)
- $F12 = 0$
- $F04 = 672.0$ hours (if no telemetry in 28 days) or elapsed hours to latest packet in 28d

---

## 4. Multi-Week Verification & Test Suite (20/20 Checks Passed)

The complete 20-check invariant test suite was executed across all 8 scored prediction Mondays. All checks passed without a single failure or warning.

### 4.1 Fleet Dynamics & Runtime Summary Across All 8 Weeks

| Week | Prediction Monday ($T$) | Active Master Universe ($N$) | Silent Gateways ($F05=1$) | Extraction Time (s) | 20-Check Invariant Status |
|:---:|:---:|:---:|:---:|:---:|:---:|
| **Week 1** | `2026-02-02 00:00:00Z` | **290** | 0 | 1.256 s | **ALL PASS** |
| **Week 2** | `2026-02-09 00:00:00Z` | **291** | 1 (`0EA061007895`) | 0.280 s | **ALL PASS** |
| **Week 3** | `2026-02-16 00:00:00Z` | **294** | 0 | 0.279 s | **ALL PASS** |
| **Week 4** | `2026-02-23 00:00:00Z` | **298** | 0 | 0.274 s | **ALL PASS** |
| **Week 5** | `2026-03-02 00:00:00Z` | **300** | 1 (`0EE587927263`) | 0.740 s | **ALL PASS** |
| **Week 6** | `2026-03-09 00:00:00Z` | **304** | 1 (`02D3289B907C`) | 0.456 s | **ALL PASS** |
| **Week 7** | `2026-03-16 00:00:00Z` | **308** | 0 | 0.407 s | **ALL PASS** |
| **Week 8** | `2026-03-23 00:00:00Z` | **308** | 0 | 0.468 s | **ALL PASS** |

**Total Validation Runtime:** **7.03 seconds** for all 8 weeks combined (substantially beating the < 30s requirement).

### 4.2 Invariant Verification Check Results

1. **Expected Active Count:** 100% match ($290, 291, 294, 298, 300, 304, 308, 308$).
2. **Entity Uniqueness:** Exactly one row per active gateway; zero duplicate `gateway_id` keys.
3. **Lifecycle Validity ($F19$):** $F19 == 1$ and `is_lifecycle_active == 1` for all rows.
4. **$F01$ Bounds & Type:** Strictly integer, $0 \le F01 \le 168$.
5. **$F02$ Linear Complement:** $F02 == 168 - F01$ verified identically across all 2,393 gateway-week rows.
6. **$F03$ Ratio Identity:** $F03 == F01 / 168.0$ verified within floating-point tolerance.
7. **$F05$ Silence Identity:** $F05 == (F01 == 0)$ verified for every row.
8. **$F04$ Bounds:** $0.0 \le F04 \le 672.0$ hours; capped at 672.0 for assets with zero telemetry in 28d.
9. **$F06$ Peak Envelope:** Strictly non-negative; reflects the highest observed `offline_duration_sec` reading.
10. **$F08$ Counter Threshold:** Integer count of observations with `offline_duration_sec` $\ge 3600\text{s}$.
11. **$F09$ 7d Reboot Sum:** Non-negative integer sum of incremental reboot events.
12. **$F10$ 28d Reboot Sum:** Non-negative integer sum; $F10 \ge F09$ verified across all active gateways.
13. **$F12$ Disconnection Sum:** Non-negative integer sum of incremental backhaul drop events.
14. **$F17$ & $F18$ Static Pre-February Bounds:** $0.0 \le F17 \le 1.0$, $0.0 \le F18 \le 1.0$.
15. **$F19$ Master Lifecycle Alignment:** Active ID set matches master lifecycle condition identically.
16. **$F20$ Installation Age:** Non-negative float; matches $(T - \texttt{installed\_on})$ in days.
17. **Temporal Leakage Prevention:** Verified zero telemetry records with $t \ge T$ accessed.
18. **Deduplication Invariant:** Zero duplicate `(gateway_id, ts_utc)` pairs contribute to feature sums.
19. **Silent Asset Retention:** Silent gateways ($F05=1$) retained with exact fallback values.
20. **Deterministic Reproducibility:** `assert_frame_equal(df, df_rerun)` passes identically.

---

## 5. Explicit Technical Resolutions & Clarifications

### 5.1 Clarification on $F16$ (`acute_chronic_divergence`)
- **Specification Source:** Phase 4.2 Section 11.1 / Phase 5.1 Section 5 Master Table.
- **Mathematical Formula:**
  $$F16_i = \max\left(0.0, \; \frac{\|\mathcal{H}_i(W_{21})\|}{21 \times 24} - \frac{\|\mathcal{H}_i(W_7)\|}{7 \times 24}\right)$$
  where $W_{21} = [T - 28\text{d}, T - 7\text{d})$ and $W_7 = [T - 7\text{d}, T)$.
- **Operational Logic:** Measures the sudden drop in reporting availability from the prior 3-week chronic baseline to the recent 1-week acute window. It evaluates to $0.0$ for continuously healthy gateways, as well as for chronically dead gateways (which are captured by $F04$ and $F05$).
- **Status:** Fully specified in Phase 4.2/5.1; implemented without ambiguity.

### 5.2 Clarification on Missing Data in Historical Meter Priors ($F17, F18$)
- **Data Reality:** `meter_read_success.csv` ends on January 26, 2026 and covers 299 gateways. Exactly 33 gateways in `gateway_master.csv` have zero records in the historical meter log.
- **Root Cause:** All 33 missing gateways were commissioned in February, March, or mid-2026—**after** the meter read log terminated. Every gateway that was active during 2025 is present in the meter log.
- **Deterministic Handling:** Gateways installed after January 26, 2026 receive $F17 = 0.0$ and $F18 = 0.0$ (no historical baseline).

### 5.3 Clarification on Decommissioned Gateways with Trailing Telemetry
- **Week 2 Example (`2026-02-09`):** Gateways `02EBC6CD4398` and `0259991BA036` emitted telemetry on Feb 2–3 before being decommissioned on Feb 4.
- **Lifecycle Precedence:** The candidate universe is strictly filtered on master lifecycle status at cutoff $T$: $\text{decommissioned\_on} > T$. Decommissioned assets are pruned from the candidate universe regardless of whether they emitted packets prior to retirement.

---

## 6. Verification of Status of Features Not in the 15-Feature Contract

The remaining 5 candidate features from Phase 4.2 were classified as `CONDITIONAL` or `DEFERRED` in Phase 5.1 and are **not** part of the Phase 5.2 extraction pipeline:
- **`F07` (`offline_duration_delta_7d`):** CONDITIONAL — requires post-gap counter reconnection conventions.
- **`F11` (`reboot_intensity_ratio`):** CONDITIONAL — requires small-denominator smoothing parameter.
- **`F13` (`disconn_to_offline_ratio`):** DEFERRED — high volatility, weak diagnostic value.
- **`F14` (`reboot_and_offline_syndrome`):** CONDITIONAL — requires dual-threshold tuning ($	heta_r, 	heta_o$).
- **`F15` (`flapping_and_offline_syndrome`):** CONDITIONAL — requires dual-threshold tuning ($	heta_d, 	heta_o$).

---

## 7. Next Steps: Advancing to Phase 5.3

With the 15-feature extraction engine fully compliant with Phase 5.1 and verified across all 8 scored Mondays, the pipeline is ready for **Phase 5.3 (Feature Correlation, Distribution Analysis & Pruning Recommendations)**.
