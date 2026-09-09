# Phase 9 — Automated Testing & Regression Protection

**LPDG Innovation Hub Selection Challenge 2026 (NEXORA 2026)**  
**Document Type:** Formal Test Suite Architecture & Verification Report  
**Audience:** Technical Reviewers, Evaluators, and Engineering Leadership  
**Status:** PASS WITH CORRECTIONS  

---

## Status

**PASS WITH CORRECTIONS**

All automated tests pass cleanly (59 passed in 5.05 seconds). Two edge-case implementation bugs identified during test design (all-NaT date comparison `TypeError` across pandas versions in `eligibility.py` and empty DataFrame concat deprecation warning in `ranking.py`) were corrected while strictly maintaining the frozen mathematical scoring contract and official submission schema.

---

## 1. Testing Strategy

The test suite enforces a strict dual-tier testing pyramid:
1. **Unit & Behavioral Invariant Tier (Fast / Synthetic):**
   - 100% independent of the full 1.43M-row real dataset.
   - Executes in **5.05 seconds**.
   - Validates mathematical formulations, sample variance ($ddof=1$), threshold strict inequality ($x > \mu + 3\sigma$), zero variance / insufficient sample ($N=1$) handling, lifecycle boundaries, silent gateway Option B retention, reason formatting, and temporal cutoff invariants using deterministic synthetic fixtures.
2. **End-to-End Pipeline & Integration Tier:**
   - Evaluates full multi-stage pipeline flow (`DataLoader` $\rightarrow$ `eligibility` $\rightarrow$ `scoring` $\rightarrow$ `ranking` $\rightarrow$ `reasons` $\rightarrow$ `validation` $\rightarrow$ `predictions.csv`).
   - Verifies dataset isolation (guarantees no dependency on auxiliary competition files).
   - Validates bitwise determinism across duplicate pipeline invocations.
   - Validates structural integrity and official grader acceptance (`validate_submission.py`) on real production outputs.

---

## 2. Test Modules

| Test File | Tests | Core Responsibilities & Protections |
| :--- | :---: | :--- |
| `tests/test_data_loader.py` | 13 | Gateway ID canonicalization (`bare hex`, `colon hex`, `lowercase`, `whitespace`, `invalid IDs`), regex contract validation (`^[0-9A-F]{12}$`), exact duplicate removal on `(gateway_id, ts_utc)`, UTC timezone enforcement, unknown gateway filtering, missing directory/column errors, and dataset isolation. |
| `tests/test_normalization.py` | 3 | Backward-compatible standalone normalization regression suite. |
| `tests/test_eligibility.py` | 10 | Lifecycle boundary tests: $installed \le T$, $installed > T$, $decommissioned < T$, $decommissioned == T$, $decommissioned > T$, $decommissioned \text{ is null}$, telemetry-absent asset retention, deterministic sorting, and flexible date-type handling. |
| `tests/test_scoring.py` | 14 | Direct protection of the frozen `Baseline_3Sigma` scoring formulation: cases A through N (no breaches, 1/2/3 breaches, multi-observation accumulation, strict threshold equality $x == \mu + 3\sigma$ rejection, $std=0 \rightarrow \text{NaN}$, $N=1 \rightarrow \text{NaN}$, omitted silent assets, boundary $T$ exclusion, boundary $T-28\text{d}$ inclusion via Samuelson inequality, boundary $T-7\text{d}$ inclusion, future telemetry injection). |
| `tests/test_ranking.py` | 6 | Deterministic sorting (`score DESC`, `gateway_id ASC`), top-15 selection, rank numbering $1..15$, absence of duplicate IDs within week, Option B silent asset retention ($score=0.0$, $flagged\_hours=0$, $worst\_metric="no\_telemetry"$), prohibition of silence bonus, and insufficient fleet exception handling. |
| `tests/test_reasons.py` | 4 | Positive-score formatting, exact frozen zero-score wording, string length constraint ($\le 300$ chars), exclusion of unsupported causal claims (e.g. blown fuse, hardware fault), determinism, and DataFrame immutability. |
| `tests/test_strategy_integrity.py` | 4 | Regression defense against unauthorized model introduction: strictly approved 3-metric set (`offline_duration_sec`, `disconnection_cnt`, `reboot_cnt`), behavioral invariance when extraneous candidate features or ML predictions are injected into telemetry, unweighted unitary breach increments, and absence of silence bonuses. |
| `tests/test_pipeline_regression.py` | 5 | End-to-end synthetic pipeline execution, dataset isolation (no `field_visits.csv`, `meter_read_success.csv`, or `engineer_review_2026-02.xlsx`), bitwise pipeline reproducibility, official output contract adherence, and real production `predictions.csv` structural verification against `validate_submission.py`. |
| **Total** | **59** | **Full coverage across all 12 pipeline stages.** |

---

## 3. Coverage of Production Contract

| Frozen Contract Component | Protected In | Verified Behavior |
| :--- | :--- | :--- |
| **Baseline Window** | `test_scoring.py` | Exactly $[T-28\text{d}, T)$. Boundary $T-28\text{d}$ is included; boundary $T$ is strictly excluded. |
| **Recent Window** | `test_scoring.py` | Exactly $[T-7\text{d}, T)$. Boundary $T-7\text{d}$ is included; boundary $T$ is strictly excluded. |
| **Sample Standard Deviation** | `test_scoring.py` | Uses pandas sample standard deviation ($ddof=1$). |
| **Breach Inequality** | `test_scoring.py` | Strict inequality ($x > \mu + 3\sigma$). Exact equality $x == \mu + 3\sigma$ produces 0 breaches. |
| **Breach Accumulation** | `test_scoring.py` | Each observation contributes $0, 1, 2,$ or $3$ breaches across the 3 metrics; breaches accumulate linearly without capping. |
| **Degenerate Variance** | `test_scoring.py` | Zero baseline variance ($std=0$) is replaced by $\text{NaN}$, yielding 0 breaches. Single observation ($N=1$) yields $\text{NaN}$ std and 0 breaches. |
| **Lifecycle Eligibility** | `test_eligibility.py` | $installed \le T \land (decommissioned > T \lor decommissioned \text{ is null})$. Assets installed on $T$ are eligible; assets decommissioned on $T$ are ineligible. Telemetry absence does not disqualify. |
| **Option B Silent Gateways** | `test_ranking.py` | Eligible assets with no recent telemetry are retained in the ranking universe with $score=0.0$, $flagged\_hours=0$, $worst\_metric="no\_telemetry"$. No artificial silence bonus is awarded. |
| **Tie-Breaking** | `test_ranking.py` | Sorted by $score \text{ descending}$, tie-broken by $gateway\_id \text{ ascending}$. |
| **Official Schema** | `test_pipeline_regression.py` | Output columns: `week_start`, `rank`, `gateway_id`, `score`, `reason`. Exactly 15 rows per week. Ranks $1..15$. Canonical 12-char hex IDs. Non-empty reasons $\le 300$ chars. |

---

## 4. Edge Cases Tested

1. **$N \le 10$ Samuelson Boundary Invariant:**
   - In any sample of size $N$, the maximum theoretical z-score is $\frac{N-1}{\sqrt{N}}$.
   - For $N=10$, $\frac{9}{\sqrt{10}} \approx 2.846 < 3.0$ (a 3-sigma breach is mathematically impossible).
   - For $N=11$, $\frac{10}{\sqrt{11}} \approx 3.015 > 3.0$ (a 3-sigma breach becomes possible).
   - Tested that an observation at boundary $T-28\text{d}$ converting $N=10$ to $N=11$ allows breach detection, proving boundary inclusion.
2. **Exact Boundary at $T$:**
   - Telemetry recorded at $T$ (`2026-02-02 00:00:00+00:00`) is excluded from both baseline and recent evaluation windows.
3. **All-NaT Decommissioned Dates:**
   - Master fleet records where `decommissioned_on` is entirely null/NaT are safely evaluated across pandas versions without raising `TypeError`.
4. **Empty Scored Gateway Fleet:**
   - In extreme edge cases where zero gateways have telemetry breaches, Option B correctly populates all 15 ranks with silent assets without concatenation warnings.
5. **Insufficient Fleet Cardinality:**
   - If the total active fleet is strictly fewer than 15 assets, `rank_and_select` raises an explicit `ValueError`.
6. **Corrupt Identifier Formats:**
   - Non-hex characters, invalid lengths (6, 13 chars), wrong octet counts (5, 7 octets), and malformed delimiters are rejected with `ValueError`.

---

## 5. Leakage Tests

Temporal anti-leakage was verified using a deliberate future telemetry injection fixture (`test_case_n_future_telemetry_injection_leakage_safe`):
- A baseline and recent telemetry profile was evaluated for decision Monday $T$.
- Catastrophic telemetry observations ($offline = 999,999$, $disconnection = 999,999$, $reboot = 999,999$) were injected at $T + 1\text{ hour}$.
- Result: Clean and contaminated scored DataFrames were bitwise identical (`pd.testing.assert_frame_equal`). The right-open cutoff ($ts < T$) completely insulates scoring from future data.

---

## 6. Determinism Tests

Pipeline reproducibility was validated in `test_pipeline_determinism`:
- Two consecutive pipeline runs were executed on identical synthetic inputs with randomized gateway order.
- In-memory DataFrames and serialized CSV files were compared.
- Result: Exact match (`df1.equals(df2) == True`), identical ranks, identical floating-point scores, identical reason strings, and identical file bytes.

---

## 7. Strategy Integrity Tests

To guard against unauthorized model shifts (e.g. accidental addition of Candidate C, Candidate F, learned weights, silence bonuses, or ML classifiers):
- `test_metrics_set_strictly_three_approved_signals`: Confirms `METRICS` contains exactly the three approved strings.
- `test_extraneous_telemetry_columns_ignored`: Injects extraneous columns (`meter_read_success_rate`, `rssi_dbm`, `candidate_c_score`, `candidate_f_score`, `silence_bonus`, `ml_probability`) with extreme values into telemetry. Confirms scored results are strictly identical to clean results.
- `test_unweighted_individual_breach_accumulation`: Confirms each metric breach produces an exact unitary score increment ($1.0$), verifying that no feature weighting or scaling is active.
- `test_no_silence_bonus_in_ranking`: Confirms silent gateways receive strictly score $0.0$.

---

## 8. Production Regression

A dedicated integration test (`test_real_dataset_predictions_structure`) validates the generated Phase 8 production output (`predictions.csv`):
- Exactly **120 rows** across **8 distinct Mondays** ($8 \times 15 = 120$).
- Consecutive ranks $1..15$ per week.
- Zero duplicate gateway IDs within any week.
- All scores are non-negative numeric floats.
- All reason strings are non-empty and $\le 300$ characters.
- Passes official `validate_submission.py` with exit code **0**.

---

## 9. Test Results

```
============================= test session starts =============================
platform win32 -- Python 3.10.8, pytest-8.4.2, pluggy-1.6.0
rootdir: D:\lpdg-nexora-2026
configfile: pytest.ini
collected 59 items

tests\test_data_loader.py .............                                  [ 22%]
tests\test_eligibility.py ..........                                     [ 38%]
tests\test_normalization.py ...                                          [ 44%]
tests\test_pipeline_regression.py .....                                  [ 52%]
tests\test_ranking.py ......                                             [ 62%]
tests\test_reasons.py ....                                               [ 69%]
tests\test_scoring.py ..............                                     [ 93%]
tests\test_strategy_integrity.py ....                                    [100%]

============================== 59 passed in 5.05s ==============================
```

- **Total Tests:** 59
- **Passed:** 59
- **Failed:** 0
- **Skipped:** 0
- **Runtime:** 5.05 seconds

---

## 10. Production Pipeline Result

Execution of production command:
```bash
python -m nexora.pipeline --data data/ --out predictions.csv
```

- **Output Rows:** Exactly 120 rows
- **Data Loading Time:** 3.80s
- **Scoring & Ranking Time:** 1.11s
- **Total Runtime:** 5.89s
- **Official Validator (`validate_submission.py`):**
  ```
  predictions.csv: OK
    15 ranked gateways for each of 8 weeks, 2026-02-02 to 2026-03-23
  ```
- **Validator Exit Code:** 0 (PASS)

---

## 11. Issues Found & Resolved

1. **Issue: `TypeError: Invalid comparison between dtype=datetime64[ns] and date` in `eligibility.py`**
   - *Cause:* When master metadata contains all-null `decommissioned_on` values, pandas retains dtype `datetime64[ns]` on `.dt.date`. Direct inequality comparison against a `datetime.date` object raised `TypeError`.
   - *Correction:* Updated `eligibility.py` to inspect dtype and perform comparisons against `pd.Timestamp(target_date)` when `datetime64` is present, or element-wise date comparison otherwise.
2. **Issue: Deprecated empty DataFrame concatenation in `ranking.py`**
   - *Cause:* When no gateways had telemetry scores, concatenating empty `valid_scores` with `silent_df` triggered pandas `FutureWarning`.
   - *Correction:* Replaced unconditional concatenation with conditional assignment (`complete_universe = silent_df` if `valid_scores.empty`).
3. **Issue: Deprecated `pd.api.types.is_datetime64tz_dtype` in `test_data_loader.py`**
   - *Cause:* Triggered pandas `DeprecationWarning`.
   - *Correction:* Replaced with standard `isinstance(df["ts"].dtype, pd.DatetimeTZDtype)`.

---

## 12. Final Verdict

**PHASE 9 STRICTLY VERIFIED AND COMPLETE.**

The automated test suite provides comprehensive, fast (5.05s), and deterministic regression protection for the frozen Baseline_3Sigma production pipeline across all lifecycle, scoring, ranking, explainability, and submission constraints.
