# Phase 4.2 — Verification & Audit Report

**Project:** LPDG Innovation Hub Selection Challenge 2026 (NEXORA 2026)  
**Author:** Candidate Engineering Team  
**Review Type:** Independent Audit & Empirical Correction Pass  
**Phase Status:** Micro-Phase 4.2 — Verification Complete  
**Date:** September 2026  
**Reference Documents:**  
- [PHASE_4_2_FEATURE_SPECIFICATION.md](PHASE_4_2_FEATURE_SPECIFICATION.md)  
- [PHASE_4_1_OPERATIONAL_DEFINITION.md](PHASE_4_1_OPERATIONAL_DEFINITION.md)  
- [PHASE_3_DEEP_DATA_INVESTIGATION.md](PHASE_3_DEEP_DATA_INVESTIGATION.md)  
- [PHASE_3_VERIFICATION.md](PHASE_3_VERIFICATION.md)  
- `baseline_3sigma.py`  
- `validate_submission.py`  
- Challenge Brief & Data Dictionary  

---

## 1. Executive Summary

This report documents the rigorous audit and correction pass conducted on **Micro-Phase 4.2 (Candidate Feature Specification)**.

The audit verified every factual claim, statistical figure, schema representation, and causal hypothesis in `reports/PHASE_4_2_FEATURE_SPECIFICATION.md` against the actual challenge dataset and the empirically verified findings from Phase 3. 

All 14 audit categories specified in the review mandate were thoroughly examined and corrected. No final features, weights, ranking formulas, or machine learning models were chosen, preserving strict phase boundaries.

**Final Audit Status:** **PASS WITH ASSUMPTIONS**  
*(All factual errors and speculative causal claims corrected; remaining assumptions regarding post-gap counter resets and candidate parameter thresholds are explicitly cataloged for empirical validation in Phase 5 and Phase 6).*

---

## 2. Corrections Made by Category

The following table summarizes the 14 audit categories, the original defects identified, and the specific corrections applied to `reports/PHASE_4_2_FEATURE_SPECIFICATION.md`:

| # | Audit Category | Original Defect / Inaccuracy | Applied Correction |
| :- | :--- | :--- | :--- |
| **1** | **Gateway ID Formats** | Invented synthetic ID examples (`GW_001`–`GW_120`, `GW_0001`). | Replaced with actual verified ID formats: 17-char colon hex (`06:39:EA:56:02:C1`) in Master, Visits, Review; 12-char bare hex (`0639EA5602C1`) in Parquet and Meter Reads. Canonical form standardized to 12-char uppercase bare hex. |
| **2** | **Duplicate Counts & Semantics** | Ambiguous phrasing suggested duplicate keys and full-row duplicates were two separate populations. | Clarified that the 6,547 duplicates on `(gateway_id, ts_utc)` and the 6,547 full-row duplicates are **identically the same records**. Documented exact monthly breakdown (0 in Aug/Oct/Dec/Feb/Mar; 2,185 in Sep, 2,124 in Nov, 2,238 in Jan). |
| **3** | **Cumulative Counter Statistics** | General statements about counter extremes without empirical grounding. | Verified exact extremes from Phase 3: max `offline_duration_sec` is **726,642s** (8,354 rows $> 3600\text{s}$ in August); max `reboot_duration_sec` is **439,061s** (921 rows $> 3600\text{s}$ in August). |
| **4** | **Counter Semantics** | Incomplete separation of incremental counts vs cumulative counters. | Clarified that `reboot_cnt` (max 32) and `disconnection_cnt` (max 55) are incremental hourly event counts (summing supported), whereas `offline_duration_sec` and `reboot_duration_sec` are cumulative firmware counters (differencing/peak envelope required). |
| **5** | **Silence Interpretation** | Unqualified assertions that silence proves physical hardware death. | Replaced with grounded operational definition: silence is a severe communication-loss signal with multiple possible root causes (power loss, carrier outage, hardware failure, SIM deactivation, uninstalled asset). |
| **6** | **Physical Failure Explanations** | Speculative claims regarding "drying capacitors", "lightning surge protectors", or "water ingress". | Replaced with qualified engineering hypotheses and aligned directly with actual recorded parts in `field_visits.csv` (`Netzteil`, `Antenne`, `Kabel`, `Gateway getauscht`, `SIM-Karte`). |
| **7** | **F06/F07 Counter Features** | Confusingly stated that F06 would impute offline duration from silence duration if no packets exist. | Strictly decoupled observed counter metrics from inferred silence metrics. F06 is strictly null/undefined when zero packets are reported. Silence is tracked separately by F04/F05. Unresolved counter-gap semantics explicitly documented. |
| **8** | **Lifecycle Semantics** | High-level summary of commissioning dates. | Verified exact schema: `installed_on` (populated for all 332 gateways) and `decommissioned_on` (populated for 12 gateways; null for 320). Confirmed the 12 future-installed gateways (May–July 2026) and exact UTC date comparison rule. |
| **9** | **Validation Methodology** | Prescribed eliminating candidate features solely if $p > 0.01$. | Removed single p-value elimination rule. Implemented multi-dimensional evaluation: statistical separability (Mann-Whitney U), precision/repair yield on historical visits, false positive penalty (€380), unaddressed outage penalty (€600), and incremental ranking utility. |
| **10**| **Thresholds & Cutoffs** | Presented specific values (48h, 72h, 5 reboots, 24h offline) as established thresholds. | Explicitly re-labeled all numerical cutoffs as **Candidate Parameters** ($\theta$) to be empirically calibrated during Phase 6 backtesting. |
| **11**| **Historical Meter Data** | Implied meter data could be rolling or partially available in February. | Confirmed strict data cliff: `meter_read_success.csv` spans exactly 26 weeks from `2025-08-04` to `2026-01-26`. Zero records exist in February or March 2026. Designated strictly as a static pre-February prior. |
| **12**| **Rejected Features** | Included broad statements about environmental noise. | Grounded rejections strictly in Phase 3 empirical data: `Signal schwach` (79 visits, 0.0% fixed); `Auffaellige Statistik` (87 visits, 0.0% fixed); raw CRC ratios (atmospheric noise without packet relay disruption). |
| **13**| **Feature Table Synchronization** | Minor column discrepancies between text and summary table. | Fully synchronized all 20 features across ID, Name, Meaning, Raw Columns, Transformation, Window, Temporal Safety, Failure Mode, Validation Method, and Priority. |
| **14**| **Interview Explanation** | Contained over-confident claims that physical hardware failure was fully captured. | Revised spoken interview defense to reflect an empirically grounded, leak-free feature engineering workflow without premature claims of problem resolution. |

---

## 3. Factual Checks Performed

The following programmatic checks were executed directly against the local challenge datasets in `data/`:

### 3.1 Telemetry Partitions & Duplicates
```python
# Executed across all 8 Parquet partitions:
total_rows = 1,433,387
duplicate_keys = 6,547  # df.duplicated(subset=['gateway_id', 'ts_utc'])
duplicate_full = 6,547  # df.duplicated() across all 57 columns
# Exact partition counts:
# month=2025-09: 2,185
# month=2025-11: 2,124
# month=2026-01: 2,238
# All other months: 0
```
- **Conclusion:** Factual claim verified with 100% precision. The duplicate keys and full-row duplicates represent the exact same rows.

### 3.2 Gateway ID String Representations
```python
# Raw samples extracted:
gateway_master['gateway_id']: ['06:39:EA:56:02:C1', '0A:56:03:8B:20:D0', '0E:5D:FC:F6:5A:D4']
field_visits['gateway_id']:   ['02:30:EE:F7:24:35', ...]
telemetry['gateway_id']:      ['0639EA5602C1', ...]
meter_reads['gateway_id']:    ['0202CB0A6B1F', ...]
```
- **Conclusion:** Verified. `replace(':', '').upper()` normalization is strictly required to join metadata with telemetry.

### 3.3 Counter Statistics & Extremes
```python
# August 2025 telemetry partition (181,484 rows):
offline_duration_sec: max = 726,642s (~201.8h), count(> 3600) = 8,354 (4.60%)
reboot_duration_sec:  max = 439,061s (~121.9h), count(> 3600) = 921 (0.51%)
reboot_cnt:           max = 32,                 count(> 0)    = 3,778
disconnection_cnt:    max = 55,                 count(> 0)    = 40,199
```
- **Conclusion:** Verified. Counters are non-hourly cumulative values, while counts are incremental hourly frequencies.

### 3.4 Historical Work Order Diagnostic Outcomes
```python
# field_visits.csv (642 total work orders):
Kein Fehler gefunden: 390 (60.75%)
Fehler behoben:       223 (34.74%)
Kein Zugang:          29 (4.52%)

# Breakdowns for key dispatch reasons:
Auffaellige Statistik: 0 fixed / 77 no fault / 10 no access (0.0% fixed across 87 visits)
Signal schwach:        0 fixed / 73 no fault /  6 no access (0.0% fixed across 79 visits)
Haeufige Neustarts:   62 fixed / 47 no fault /  1 no access (56.36% fixed across 110 visits)
Keine Verbindung:     65 fixed / 32 no fault /  3 no access (65.00% fixed across 100 visits)
```
- **Conclusion:** Verified. Empirically validates the rejection of `Signal schwach` and `Auffaellige Statistik`, and justifies high priority for `Keine Verbindung` (silence) and `Haeufige Neustarts` (reboots).

### 3.5 Actual Parts Replaced in Field Visits
```python
# field_visits[outcome == 'Fehler behoben']['parts_replaced']:
NaN (No part replaced / reset): 57
Netzteil (Power Supply):        39
Antenne (Antenna):              37
Kabel (Cable):                  35
Gateway getauscht (Swap):       30
SIM-Karte (SIM Card):           25
```
- **Conclusion:** Verified. Grounded the physical failure discussions strictly in these observed component categories.

---

## 4. Remaining Assumptions

While all factual errors have been eliminated, the following technical assumptions remain in the specification, pending empirical confirmation in Phase 5:

1. **Uniform Firmware Reset Behavior:** We assume that when a gateway undergoes a clean power reboot, its cumulative counter `offline_duration_sec` resets to 0. If firmware variations exist across hardware models (`hw_model`), reset behavior could vary.
2. **Missingness vs Sleep Schedule:** We assume that normal gateways exhibit periodic missingness (~13.5% active drop-out rate) due to environmental or transmission factors, whereas true failures manifest as sustained, multi-day consecutive dropouts.
3. **Static Pre-February Meter Prior Validity:** We assume that historical meter-reading success prior to January 26, 2026 remains a useful static proxy for long-term site RF quality, despite aging over the 8-week scored window.
4. **Independent Dispatch Capacity:** We assume that all 15 weekly dispatches are operationally independent and that travel routing/geographic clustering does not constrain the candidate selection (as confirmed by the Challenge Brief's simple ranking format).

---

## 5. Unresolved Questions for Phase 5 & Phase 6

The following empirical questions cannot be answered by specification alone and are explicitly scheduled for resolution during implementation (Phase 5) and backtesting (Phase 6):

| # | Unresolved Question | Phase to Resolve | Planned Resolution Method |
| :- | :--- | :--- | :--- |
| **Q1** | **Post-Gap Counter Reconnection Semantics:** When a gateway reconnects after a 3-day silent gap, does the first reported packet contain cumulative gap downtime, or does it reset to 0? | Phase 5 (Feature Implementation) | Inspect consecutive row pairs across reconnection boundaries for silent gateways in the training partitions. |
| **Q2** | **Optimal Counter Transformation:** Does Peak Window Envelope ($F06$) or Consecutive Positive Differencing ($F07$) achieve higher separation on true physical repairs? | Phase 6 (Backtesting) | Compare KS-statistics and repair precision yields between $F06$ and $F07$ across historical work orders. |
| **Q3** | **Optimal Silence Persistence Cutoff:** What is the optimal threshold for ongoing silence at Monday cutoff ($	heta_{	ext{silence}} = 24	ext{h}$, $48	ext{h}$, $72	ext{h}$, or $120	ext{h}$)? | Phase 6 (Backtesting) | Financial loss minimization grid search balancing €380 false visits against €600 unaddressed outages. |
| **Q4** | **Candidate Feature Redundancy:** Does combining $F01$ (`reported_hours`) with $F04$ (`consecutive_missing`) introduce harmful collinearity, or do they capture distinct failure phases? | Phase 6 (Backtesting) | Feature correlation matrix analysis and ablation testing on historical ranking performance. |

---

## 6. Audit Conclusion & Sign-Off

Micro-Phase 4.2 has undergone a complete, rigorous verification and correction pass. All factual claims are grounded directly in the local challenge data, schema representations, and Phase 3 empirical findings. No premature decisions regarding final weights, ranking algorithms, or ML models were made.

**Audit Status:** **PASS WITH ASSUMPTIONS**  
*(Ready to proceed to Phase 5: Feature Pipeline Implementation upon authorization).*
