# Phase 7.4 — Production Architecture & Comprehensive Test Plan

**Author:** NEXORA Operational Engineering Team  
**Date:** 2026-09-08  
**Status:** COMPLETE (Architecture Specification & Test Plan Frozen for Phase 8)  
**Selected Strategy:** `Baseline_3Sigma` (LOCKED)  
**Silent-Gateway Policy:** Option B — Universe Retention with Score 0 (LOCKED)  
**Target Submission Artifact:** `predictions.csv` (Part 1 Grader Output)  

---

## 1. Production Objective

The primary objective of the production system is to generate the authoritative, grader-compliant `predictions.csv` submission file for **Part 1 of the LPDG Innovation Hub Selection Challenge 2026 (NEXORA 2026)**.

The production pipeline must:
1. **Strict Temporal Integrity:** Utilize only information strictly available before each decision cutoff Monday $T$ ($\text{timestamp} < T$). Zero future information may influence predictions.
2. **Strategy Preservation:** Preserve the exact mathematical scoring formulation of the locked `Baseline_3Sigma` strategy without alteration.
3. **Lifecycle-Governed Fleet Universe:** Construct the candidate pool strictly from `gateway_master.csv` lifecycle dates ($\texttt{installed\_on} \le T \land (\texttt{decommissioned\_on} > T \lor \text{null})$). Telemetry presence must never define asset eligibility.
4. **Deterministic Identifier Normalization:** Canonicalize all gateway identifiers to 12-character uppercase bare hexadecimal format before processing.
5. **Deterministic Deduplication:** Eliminate exact telemetry duplicate records before computing baseline variance or anomaly breaches.
6. **Locked Silent-Gateway Handling (Option B):** Retain all lifecycle-eligible active gateways that have zero recent telemetry rows within the candidate universe with $\text{score} = 0.0$ and $\text{worst\_metric} = \text{"no\_telemetry"}$.
7. **Fixed Weekly Recommendation Cardinality:** Produce **exactly 15 unique gateway recommendations** per scored Monday, ranked strictly $1, 2, \dots, 15$.
8. **Explainable, Non-Causal Reasons:** Generate factual, understandable explanation strings ($\le 300$ characters) grounded strictly in observed statistical deviations.
9. **Execution Reproducibility:** Guarantee deterministic output for identical inputs and code without reliance on random seeds.
10. **One-Command Portability:** Enable an external evaluator to clone the repository, install dependencies, and execute the entire end-to-end pipeline with a single documented shell command.

> [!IMPORTANT]
> The production system operates as an **operational prioritization tool**, not a definitive hardware diagnostics engine. It ranks assets exhibiting extreme statistical deviations from historical operating norms; it does **not** claim to predict physical failure modes with certainty.

---

## 2. End-to-End Production Architecture

The production architecture enforces a clean, linear, 12-stage dataflow designed to eliminate coupling between raw ingestion, mathematical scoring, operational decision rules, and output serialization:

```
┌────────────────────────────────────────────────────────┐
│ 1. Raw Data Ingestion                                  │
│    Load gateway_master.csv and telemetry partitions    │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 2. Schema Validation & Input Guards                    │
│    Verify required columns, data types, and non-emptiness │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 3. Gateway Identifier Normalization                    │
│    Canonicalize master & telemetry IDs to 12-char hex  │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 4. Telemetry Deduplication                             │
│    Eliminate exact duplicate clones on (gateway, ts)   │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 5. Lifecycle Eligibility Gating                        │
│    Construct active fleet universe at Monday T         │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 6. Temporal Cutoff Enforcement                         │
│    Enforce strict right-open boundary (t < T)          │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 7. Baseline_3Sigma Metric-Breach Scoring               │
│    Compute 28-day baseline; accumulate 7-day breaches  │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 8. Silent-Gateway Universe Alignment (Option B)        │
│    Retain silent active assets with score = 0.0        │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 9. Deterministic Ranking & Tie-Breaking                │
│    Sort by (score desc, canonical gateway_id asc)      │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 10. Top-15 Selection & Fleet Capacity Guard            │
│     Extract top 15; assert fleet capacity >= 15        │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 11. Reason String Generation                           │
│     Construct factual, non-causal reason <= 300 chars  │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 12. Output Validation & CSV Serialization              │
│     Assert validate_submission.py checks; write CSV    │
└────────────────────────────────────────────────────────┘
```

### Component Responsibilities:
- **Stages 1–4 (Data Preparation Layer):** Ensure data integrity, character encoding resilience (Latin-1), uniform identifier semantics, and removal of ingestion retries (6,547 duplicate records).
- **Stages 5–6 (Temporal & Fleet Universe Layer):** Establish the exact candidate population eligible for work orders on decision Monday $T$ and seal the temporal boundary to prevent future leakage.
- **Stage 7 (Algorithmic Scoring Layer):** Execute the frozen mathematical formulation of `Baseline_3Sigma`.
- **Stages 8–10 (Operational Decision Layer):** Align candidate scores with the complete active universe (Option B), apply deterministic tie-breaking, and select exactly 15 recommendations.
- **Stages 11–12 (Serialization & Compliance Layer):** Formulate human-readable justifications and verify submission formatting against the official grader contract.

---

## 3. Proposed Module Boundaries (`src/nexora/`)

To balance modular testability with engineering simplicity, Phase 8 will organize the production logic into dedicated modules within `src/nexora/`:

```
src/nexora/
├── __init__.py
├── data_loader.py         # Ingestion, Latin-1 parsing, ID canonicalization, deduplication
├── eligibility.py         # Lifecycle universe construction from gateway_master.csv
├── scoring.py             # Baseline_3Sigma 28-day statistics and 7-day breach accumulation
├── ranking.py             # Option B universe alignment, deterministic sorting, Top-15 selection
├── reasons.py             # Explainable, non-causal reason string synthesis
├── validation.py          # Pre-flight data checks and post-generation submission audit
└── pipeline.py            # Orchestrator and entry point for one-command execution
```

### Architectural Layer Separation:
1. **Layer A: Data Preparation (`data_loader.py`, `eligibility.py`)**
   - Pure data transformations: reads raw files, normalizes keys, drops identical timestamp clones, and filters active assets.
   - Completely agnostic to anomaly scoring algorithms.
2. **Layer B: Scoring Formulation (`scoring.py`)**
   - Implements the mathematical scoring interface: accepts preprocessed telemetry and returns gateway anomaly scores.
   - Strictly isolated: can be swapped for alternative research algorithms without touching universe gating or CSV output logic.
3. **Layer C: Operational Decision & Ranking (`ranking.py`, `reasons.py`)**
   - Handles operational constraints: fixed visit budget ($K=15$), silent-gateway retention (Option B), secondary tie-breaking on `gateway_id`, and reason formatting.
4. **Layer D: Output & Validation Layer (`validation.py`, `pipeline.py`)**
   - Orchestrates the loop over the eight scored weeks, verifies intermediate data invariants, runs submission validation, and exports `predictions.csv`.

---

## 4. Reference Baseline vs. Production Safety Layer

A foundational principle of Phase 7 is the formal distinction between the raw reference algorithm and the production safety controls wrapped around it:

### 4.1 Reference Ranking Logic (`baseline_3sigma.py`)
The reference logic shipped by the challenge organizers implements the mathematical core:
- Evaluates exactly three monitored metrics: `offline_duration_sec`, `disconnection_cnt`, and `reboot_cnt`.
- Computes each gateway's trailing 28-day baseline mean ($\mu$) and sample standard deviation ($\sigma$) using pandas default sample variance (`ddof=1`).
- Evaluates recent 7-day hourly observations against individual thresholds: $x > \mu + 3.0\sigma$.
- Accumulates breaches across metrics within each observation:
  ```python
  flags = flags + exceeded.astype(int)
  ```
- Groups by gateway to compute the aggregate score:
  ```python
  flagged_hours=("flagged", "sum")
  ```

#### Authoritative Score Definition:
> **$\text{score}_i(T)$ is the sum of all individual 3-sigma metric breaches across telemetry observations in $[T-7\text{d}, T)$ for the three monitored metrics. A single telemetry observation can contribute 0, 1, 2, or 3 to the score.**

*Technical Note:* While `flagged_hours` is the historical variable name inherited from `baseline_3sigma.py`, it mathematically represents an **aggregate count of individual 3-sigma metric breaches**, not a binary count of unique calendar hours.

### 4.2 Production Engineering Controls Layer
The reference script alone does not provide the engineering controls necessary for robust production execution:
- It does not parse `gateway_master.csv` or verify asset installation/decommissioning dates.
- It does not deduplicate the 6,547 exact telemetry duplicate records in odd months.
- It does not canonicalize mixed gateway identifier representations.
- It omits silent gateways from the ranking rather than tracking the full fleet universe.
- It relies on arbitrary tie-breaking for assets with identical breach counts.

### 4.3 Explicit System Commitment
> **"The production system preserves the baseline scoring formulation while adding validated engineering controls required for a complete and reproducible submission."**

---

## 5. Temporal Contract & Cutoff Specification

The production pipeline enforces an uncompromised temporal boundary to prevent lookahead leakage:

### 5.1 Scored Mondays Schedule
Predictions must be generated for exactly eight calendar dates in 2026:
1. `2026-02-02` (Week 1)
2. `2026-02-09` (Week 2)
3. `2026-02-16` (Week 3)
4. `2026-02-23` (Week 4)
5. `2026-03-02` (Week 5)
6. `2026-03-09` (Week 6)
7. `2026-03-16` (Week 7)
8. `2026-03-23` (Week 8)

### 5.2 Mathematical Observation Windows
For each scored Monday $T$:
- **Trailing 28-Day Baseline Window:**
  $$W_{\text{base}}(T) = [T - 28\text{ days}, T)$$
- **Trailing 7-Day Scoring Window:**
  $$W_{\text{recent}}(T) = [T - 7\text{ days}, T)$$

### 5.3 Strict Pre-$T$ Boundary
All telemetry records participating in predictions for week $T$ must strictly satisfy:
$$\text{timestamp} < T$$
Zero telemetry records with $\text{timestamp} \ge T$ may participate in baseline calculations, anomaly detection, scoring, ranking, or reason generation.

### 5.4 Timezone Alignment
- Challenge decision dates are designated by Monday calendar date $T$.
- Telemetry timestamps are stored in UTC (`ts_utc`).
- The implementation normalizes timestamps to timezone-aware UTC and preserves the validated cutoff convention established in `baseline_3sigma.py` and the Phase 6 backtesting suite. No arbitrary timezone shifts or manual offsets may be introduced.

---

## 6. Gateway Universe & Silent-Gateway Contract

The candidate fleet universe is governed strictly by physical asset lifecycle dates, fully resolving the Phase 7.3 audit findings:

### 6.1 Lifecycle Eligibility Definition
An asset $i$ is eligible for recommendation on decision Monday $T$ if and only if:
$$\text{Eligible}(i, T) \iff \Big(\texttt{installed\_on}_i \le T\Big) \;\land\; \Big(\texttt{decommissioned\_on}_i > T \;\;\lor\;\; \texttt{decommissioned\_on}_i \text{ is null}\Big)$$

- **Precedence:** Eligibility filtering occurs **before** querying telemetry.
- **Independence:** Telemetry absence does **not** disqualify an active gateway.
- **Empirical Universe Size:** The active eligible universe ranges between 290 and 308 gateways across the eight scored weeks (290 on 2026-02-02 up to 308 on 2026-03-23).

### 6.2 Locked Silent-Gateway Policy (Option B)
In Phase 7.3, empirical investigation proved that completely silent active gateways (zero rows in $[T-7\text{d}, T)$) during the scored period are newly commissioned assets installed on decision Monday itself.

The production pipeline locks **Option B**:
- All lifecycle-eligible gateways are retained in the candidate ranking universe.
- Any eligible gateway with zero telemetry records in $[T-7\text{d}, T)$ is assigned:
  - $\text{score} = 0.0$
  - $\text{flagged\_hours} = 0$
  - $\text{worst\_metric} = \text{"no\_telemetry"}$
- Silent gateways receive zero artificial score bonuses (no Candidate F $+10$ bonus) and are not classified as failures.
- In the observed eight-week scored period, silent gateways ranked below all positive-score gateways and therefore did not enter the Top-15. The production rule does not depend on this observed ordering.

---

## 7. Deterministic Telemetry Deduplication

Data exploration and Phase 3 verification established that raw Parquet telemetry contains **exactly 6,547 duplicate records** on `(gateway_id, ts_utc)` (100% full-row identical clones located in odd months: Sep 2025: 2,185; Nov 2025: 2,124; Jan 2026: 2,238).

### 7.1 Production Deduplication Policy
Before calculating rolling baselines or hourly breach flags, telemetry records must be deduplicated deterministically:
```python
telemetry = telemetry.drop_duplicates(subset=["gateway_id", "ts_utc"], keep="first")
```

### 7.2 Safety Invariants:
1. **No Double-Counting:** Prevents artificial inflation of baseline variance ($\sigma$) and metric breach sums.
2. **Non-Duplicate Preservation:** Leaves all legitimate unique hourly records completely intact.
3. **Reproducibility:** Execution is strictly deterministic regardless of compute platform.

---

## 8. Deterministic Ranking & Tie-Breaking

To guarantee reproducible list generation when multiple assets share identical anomaly scores, ranking enforces two lexicographical keys:

### 8.1 Sorting Rule
```python
ranked = ranked.sort_values(
    by=["score", "gateway_id"],
    ascending=[False, True]
).reset_index(drop=True)
```
1. **Primary Sort Key:** `score` descending (higher aggregate 3-sigma metric breaches receive higher priority).
2. **Secondary Sort Key (Tie-Breaker):** Canonical uppercase bare `gateway_id` ascending (lexicographical hex order).

### 8.2 Architectural Nature
Deterministic tie-breaking is an **operational engineering control**, not an intrinsic property of the physical 3-sigma anomaly score. It guarantees that repeated runs on any machine produce identical output orderings.

---

## 9. Reason Generation Contract

The submission format requires an operational `reason` string explaining each recommendation to human fleet dispatchers.

### 9.1 Reason Text Templates
- **For Selected Gateways with $\text{score} > 0$:**
  ```python
  reason = (
      f"{int(score)} individual 3-sigma metric breach(es) against this gateway's own "
      f"28-day baseline in the last 7 days; first breach on {worst_metric}"
  )
  ```
- **For Selected Gateways with $\text{score} == 0$ (if ever selected to fill capacity):**
  ```python
  reason = (
      "0 individual 3-sigma metric breaches against this gateway's own "
      "28-day baseline in the last 7 days"
  )
  ```

### 9.2 Validation Constraints:
- **Length:** Strictly $\le 300$ characters (`len(reason) <= 300`).
- **Non-Empty:** Never empty or null.
- **Non-Causal Discipline:** The text describes **observed statistical anomalies** relative to baseline behavior. It must **never** assert unverified physical root causes (e.g., "power supply failure", "blown fuse", "cut cable", "tampering", "battery dead").

---

## 10. `predictions.csv` Output Contract

The Part 1 pipeline must produce a single CSV file matching the official challenge submission specification:

### 10.1 Schema Definition

| Column Name | Data Type | Permitted Format | Description |
| :--- | :---: | :--- | :--- |
| `week_start` | String | `YYYY-MM-DD` | Date of the scored Monday (e.g., `2026-02-02`). |
| `rank` | Integer | $1, 2, \dots, 15$ | Contiguous integer rank within the week. |
| `gateway_id` | String | 12 uppercase hex chars | Canonical bare gateway identifier. |
| `score` | Float | Numeric $\ge 0.0$ | Aggregate count of 3-sigma metric breaches. |
| `reason` | String | $1 \le \text{length} \le 300$ chars | Non-empty observational explanation text. |

### 10.2 Mandatory Acceptance Criteria:
1. **Total Rows:** Exactly 120 rows ($8 \text{ weeks} \times 15 \text{ recommendations/week}$).
2. **Unique Ranks:** Ranks strictly numbered $1, 2, \dots, 15$ for each week with zero gaps or repeats.
3. **No Duplicate Assets:** Zero duplicate `gateway_id` values within any individual week.
4. **Grader Acceptance:** Must execute `python validate_submission.py predictions.csv` successfully with exit code 0.

---

## 11. Multi-Tier Testing Strategy

Phase 8 implementation will be accompanied by a rigorous, automated test suite structured across four tiers:

```
┌────────────────────────────────────────────────────────┐
│ TIER 4: End-to-End Pipeline & Submission Validation    │
│         Full run on real data -> validate_submission   │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ TIER 3: Regression & Edge-Case Test Harness            │
│         Silent assets, duplicates, zero-variance, ties │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ TIER 2: Integration Tests on Controlled Fixtures       │
│         Multi-week synthetic pipelines, leakage guards │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ TIER 1: Isolated Unit Tests                            │
│         Normalization, ddof=1, breach logic, reasons   │
└────────────────────────────────────────────────────────┘
```

### 11.1 Tier 1: Unit Tests (`tests/test_unit_*.py`)
- **`test_normalize_gateway_id`:** Validates conversion of 17-char colon hex, 12-char bare hex, lowercase strings, and whitespace padding to canonical bare uppercase hex.
- **`test_deduplicate_telemetry`:** Injects synthetic identical timestamp clones; verifies duplicate removal while keeping first occurrence.
- **`test_lifecycle_eligibility`:** Tests assets installed before, on, and after $T$; tests assets decommissioned before, on, and after $T$; verifies null decommissioning handling.
- **`test_temporal_boundaries`:** Verifies that records at $t = T$ are excluded while $t = T - 1\text{s}$ are retained.
- **`test_3sigma_calculation`:** Tests mean and sample std ($\text{ddof}=1$) on known synthetic distributions; verifies $(x - \mu) > 3.0\sigma$ breach logic.
- **`test_breach_accumulation`:** Verifies that an observation with breaches across 0, 1, 2, or 3 metrics correctly increments `flagged` by 0, 1, 2, or 3.
- **`test_silent_gateway_retention`:** Tests active assets with zero telemetry rows; verifies assignment of $\text{score} = 0.0$ and $\text{worst\_metric} = \text{"no\_telemetry"}$.
- **`test_deterministic_tie_breaking`:** Asserts that identical scores are sorted strictly by `gateway_id` ascending.
- **`test_reason_formatting`:** Asserts non-emptiness, length $\le 300$ characters, and absence of causal claims.

### 11.2 Tier 2: Integration Tests (`tests/test_integration_*.py`)
- **`test_pipeline_fixture`:** Runs an end-to-end simulation across a synthetic mini-fleet (20 gateways across 2 weeks) verifying correct intermediate transformations.
- **`test_metric_isolation`:** Verifies that modifying unmonitored metrics (e.g., RSSI, CRC error count) does not alter `Baseline_3Sigma` rankings.

### 11.3 Tier 3: Regression & Anti-Leakage Suite (`tests/test_regression_*.py`)
- Runs the verified Phase 6 anti-leakage test harness (`nexora.backtesting.leakage`).
- Specifically protects against re-introduction of Candidate F's $+10$ silence bonus or unauthorized heuristic overrides.

### 11.4 Tier 4: End-to-End Validation (`tests/test_e2e_submission.py`)
- Executes the production command generating `predictions.csv`.
- Invokes `validate_submission.py` directly via `subprocess` and asserts returncode `0`.

---

## 12. Critical Edge-Case Matrix

The test harness must explicitly validate twelve operational edge cases:

| # | Edge Case | Expected System Behavior | Classification | Test Method |
| :---: | :--- | :--- | :---: | :--- |
| **1** | **Completely silent active gateway** | Retained with $\text{score} = 0.0$, `worst_metric = "no_telemetry"`; ranked by `gateway_id`. | Valid Edge Case | Fixture with active gateway having zero telemetry rows. |
| **2** | **Gateway with 1 baseline observation** | Sample std evaluates to NaN ($N=1 < 2$). Breaches evaluate to `False` (`.fillna(False)`); $\text{score} = 0.0$. | Valid Edge Case | Synthetic gateway with single baseline point in $[T-28\text{d}, T)$. |
| **3** | **Zero baseline variance ($\sigma = 0$)** | Standard deviation replaced with NaN (`replace(0, np.nan)`); breaches evaluate to `False`; $\text{score} = 0.0$. | Valid Edge Case | Synthetic gateway with identical constant values for 28 days. |
| **4** | **Zero recent telemetry (with 28d history)** | Gateway evaluated normally; 0 recent rows yield 0 breaches; $\text{score} = 0.0$. | Valid Edge Case | Gateway active in baseline window but silent in $[T-7\text{d}, T)$. |
| **5** | **Zero baseline telemetry (new installation)** | Baseline statistics are NaN; breaches evaluate to `False`; $\text{score} = 0.0$. | Valid Edge Case | Gateway installed on Monday $T$ with zero pre-$T$ records. |
| **6** | **Exact duplicate telemetry** | Deduplicated via `(gateway_id, ts_utc)` keeping first occurrence. | Valid Edge Case | Inject clone rows into fixture; assert identical score to deduplicated input. |
| **7** | **Future telemetry present in raw file** | Filtered out by strict cutoff rule ($\text{ts} < T$); zero impact on scores. | Fatal if Leaked | Inject future records ($\text{ts} \ge T$); assert output ranking is unchanged. |
| **8** | **Unknown gateway ID in telemetry** | Telemetry for IDs not in `gateway_master.csv` is dropped prior to ranking. | Warning / Filtered | Inject telemetry for unlisted ID; assert absent from rankings. |
| **9** | **Inactive / decommissioned gateway** | Filtered out during lifecycle gating; never appears in Top-15. | Valid Gating | Gateway decommissioned before $T$; assert absent from ranked universe. |
| **10** | **Multiple gateways tied on score** | Resolved deterministically by canonical `gateway_id` ascending. | Valid Edge Case | Synthetic gateways with identical breach counts; assert alphabetical ordering. |
| **11** | **Fewer than 15 eligible active gateways** | Pipeline halts immediately with explicit fatal exception. | **Fatal Error** | Fixture with 14 active gateways; assert exception raised. |
| **12** | **Empty input file / malformed schema** | Pipeline halts immediately with schema validation exception. | **Fatal Error** | Corrupt column headers; assert clear descriptive error. |

---

## 13. Leakage Prevention & Anti-Leakage Test Plan

To maintain temporal and operational validity, automated leakage regression tests must be executed before generating submissions:

```
┌────────────────────────────────────────────────────────┐
│ LEAKAGE TEST 1: Synthetic Telemetry Horizon Guard      │
│ Inject extreme future spikes (ts >= T).                │
│ Assert: Rankings for week T remain 100% identical.     │
├────────────────────────────────────────────────────────┤
│ LEAKAGE TEST 2: Field Visit Independence Guard         │
│ Modify or wipe field_visits.csv.                       │
│ Assert: Pipeline runs without error; output unchanged. │
├────────────────────────────────────────────────────────┤
│ LEAKAGE TEST 3: Engineer Review Temporal Guard         │
│ Mutate engineer_review_2026-02.xlsx.                   │
│ Assert: Zero impact on production ranking logic.       │
├────────────────────────────────────────────────────────┤
│ LEAKAGE TEST 4: Meter-Read Temporal Guard              │
│ Modify post-cutoff meter reads.                        │
│ Assert: Zero impact on ranking outputs.                │
├────────────────────────────────────────────────────────┤
│ LEAKAGE TEST 5: Global Aggregation Isolation           │
│ Assert: Zero whole-dataset summary statistics exist.   │
│ All metrics derived strictly from [T-28d, T).          │
└────────────────────────────────────────────────────────┘
```

### Automated Leakage Test Procedure:
For each scored Monday $T$:
1. Generate baseline ranking $R_{\text{base}}(T)$.
2. Inject synthetic catastrophic telemetry ($10\times$ baseline spikes) at timestamp $T + 1\text{ hour}$.
3. Regenerate ranking $R_{\text{test}}(T)$.
4. Assert $R_{\text{base}}(T) \equiv R_{\text{test}}(T)$ across all ranks, scores, and reasons.

---

## 14. Reproducibility & Determinism Contract

The production pipeline guarantees **deterministic execution**:
- **Zero Stochasticity:** The algorithm contains no random number generators, stochastic gradient descent, sampling passes, or random seeds.
- **Deterministic Sort Invariant:** Every sort operation explicitly specifies secondary keys down to unique canonical identifiers (`gateway_id` ascending).
- **Environment Invariance:** The implementation uses explicit timezone-aware timestamps and fixed sorting conventions to minimize environment-dependent ordering differences.
- **Verification Protocol:** The test suite will execute the complete pipeline twice consecutively into separate temporary directories and assert character-for-character equality:
  $$\text{hash}(\texttt{predictions\_run1.csv}) == \text{hash}(\texttt{predictions\_run2.csv})$$

---

## 15. Performance & Resource Plan

Performance benchmarking from Phase 5 and Phase 6 provides empirical baselines for production resource consumption:

- **Telemetry Scale:** 1,426,840 deduplicated hourly rows across 8 monthly partitions ($\approx 120\text{ MB}$ uncompressed Parquet).
- **Active Fleet Scale:** 290 to 308 gateways per week.
- **Execution Budget:**
  - Engineering target: full pipeline execution across all 8 scored weeks should complete within approximately 60 seconds on a standard developer laptop. This is a performance target, not a challenge requirement, and Phase 8 will benchmark the actual runtime.
- **Performance Guardrails:**
  1. **Partitioned Reading:** Load only required telemetry columns (`gateway_id`, `ts_utc`, `offline_duration_sec`, `disconnection_cnt`, `reboot_cnt`).
  2. **Vectorized Aggregation:** Utilize pandas vectorized `.groupby().agg()` rather than iterative row scans.
  3. **No Redundant Ingestion:** Cache normalized telemetry in memory during multi-week execution rather than reloading Parquet partitions for each scored Monday.

---

## 16. Failure Handling & Pre-Flight Validation

The pipeline enforces defensive pre-flight and in-flight validation. Under no circumstances will it silently produce an invalid or malformed `predictions.csv`:

### 16.1 Pre-Flight Validation Checks
Before executing scoring, the pipeline verifies:
- `data/gateway_master.csv` exists and contains required columns (`gateway_id`, `installed_on`, `decommissioned_on`).
- `data/telemetry/` contains accessible Parquet partitions with required sensor columns.
- The active eligible universe at every scored Monday $T$ satisfies $N_{\text{active}}(T) \ge 15$.

### 16.2 In-Flight Invariant Checks
During weekly ranking:
- Asserts that all selected gateways have valid 12-char canonical IDs.
- Asserts that no NaN scores exist among selected recommendations.
- Asserts that exactly 15 recommendations are generated per week.

### 16.3 Post-Flight Grader Validation
Immediately after writing `predictions.csv`, the pipeline executes an internal equivalent of `validate_submission.py`. If any structural validation fails, the output file is deleted/quarantined and a non-zero exit code is returned.

---

## 17. One-Command Execution Specification

To ensure frictionless reproducibility by external evaluators, Phase 8 will deliver a single, standardized command-line entry point:

```bash
# Intended Phase 8 Single Command Execution
python -m nexora.pipeline --data data/ --out predictions.csv
```

### Planned CLI Behavior:
- **Default Paths:** Defaults to `--data data/` and `--out predictions.csv`.
- **Automated Validation:** Automatically runs `validate_submission.py` upon completion.
- **Informative Logging:** Prints execution progress per week and outputs summary statistics.
- **Zero Configuration:** Requires no environment variables, API keys, or pre-trained model weights.

---

## 18. Architectural Decision Records (ADR Table)

| Decision | Rationale / Evidence | Rejected Alternative & Reason |
| :--- | :--- | :--- |
| **Retain `Baseline_3Sigma` Strategy** | Captured 41 repairs with only 14 false alarms in 26-week backtesting. Produced lowest combined standardized cost proxy (€50,320). | **Candidate C (+1 repair, +8 false alarms, +€2,440 penalty) & Machine Learning:** Machine Learning was not selected because the available historical outcome data and challenge objective did not justify adding a more complex predictive model, while the validated baseline already provided the strongest observed operational trade-off. |
| **Adopt Option B for Silent Gateways** | Preserves active fleet universe from `gateway_master.csv` (empirically observed eligible-universe range of 290–308 candidates across the eight scored weeks); zero distortion of Top-15. | **Candidate F (+10 Silence Bonus):** Caused 21 false alarms vs. 14 for the baseline (+7 false alarms) and a €55,380 vs. €50,320 combined standardized proxy (+€5,060 net penalty) in historical backtesting. |
| **Lifecycle Eligibility Precedes Telemetry** | Prevents active assets experiencing outages from vanishing from the candidate queue. | **Telemetry-Driven Universe:** Dropping silent assets violates the fleet management contract. |
| **Deterministic Tie-Breaking on `gateway_id`** | Guarantees 100% reproducible rankings when scores are identical without introducing stochasticity. | **Arbitrary / Non-Deterministic Ordering:** Causes submission drift between execution runs. |
| **Exact Deduplication on `(gateway_id, ts_utc)`** | Eliminates 6,547 ingestion retry clones that artificially inflate baseline variance and breach counts. | **Raw Ingestion:** Distorts 3-sigma standard deviation in odd months by double-counting downtime. |
| **Strict Pre-$T$ Horizon ($t < T$)** | Prevents lookahead data leakage into operational decision queues. | **Including Monday Telemetry:** Violates the challenge operational dispatch contract. |
| **Modular Component Architecture** | Separates algorithmic scoring from operational ranking and serialization, enabling unit testing. | **Monolithic Script:** Obscures failure modes and prevents clean regression testing. |
| **Automated Submission Validation in Pipeline** | Guarantees zero grader submission formatting failures on export. | **Manual Post-Hoc Checking:** High risk of accidental schema regressions. |

---

## 19. Phase 8 Implementation Boundary

Phase 7.4 freezes the production specification. The implementation boundary for Phase 8 is strictly demarcated:

### Phase 8 WILL Implement:
1. Production modules under `src/nexora/` conforming to Section 3.
2. Automated test suite under `tests/` conforming to Section 11.
3. One-command pipeline entry point (`python -m nexora.pipeline`).
4. Production generation of the authoritative `predictions.csv` artifact.
5. Verification via `python validate_submission.py predictions.csv`.

### Phase 8 WILL NOT:
- Redesign or tweak the `Baseline_3Sigma` scoring formulation.
- Introduce machine learning models, classifiers, or regressors.
- Add new feature columns or telemetry signals.
- Optimize arbitrary weights or anomaly thresholds.
- Modify the locked Option B silent-gateway retention policy.
- Access future telemetry or forbidden evaluation datasets.

---

## 20. Verification Checklist & Self-Review

- [x] **Strategy Locked:** `Baseline_3Sigma` strictly preserved.
- [x] **Silent-Gateway Policy Locked:** Option B enforced (score 0.0, worst_metric "no_telemetry").
- [x] **Observational Language:** Zero claims of physical failure certainty or root causes.
- [x] **Input Integrity:** Only `gateway_master.csv` and telemetry partitions required.
- [x] **Temporal Boundaries:** Strict pre-$T$ cutoff ($t < T$); UTC normalization preserved.
- [x] **Deduplication:** 6,547 duplicate records handled before variance calculation.
- [x] **Deterministic Ranking:** Primary score desc, secondary canonical `gateway_id` asc.
- [x] **Output Schema:** Exact 120 rows ($8 \times 15$), ranks 1–15, reasons $\le 300$ chars.
- [x] **Multi-Tier Testing:** Unit, integration, regression, and end-to-end tiers specified.
- [x] **Edge-Case Coverage:** All 12 critical operational edge cases fully analyzed.
- [x] **Leakage Test Plan:** 5 automated anti-leakage guards defined.
- [x] **Performance Plan:** Sub-60 second local execution target defined.
- [x] **Phase 8 Scope:** Implementation boundaries explicitly frozen.

---

## Related Documents

- [`reports/PHASE_6_3_STRATEGY_DECISION.md`](PHASE_6_3_STRATEGY_DECISION.md) — Strategy comparison, baseline retention justification, and Candidate F rejection.
- [`reports/PHASE_7_1_OPERATIONAL_DECISION.md`](PHASE_7_1_OPERATIONAL_DECISION.md) — Operational cost model and capacity constraints.
- [`reports/PHASE_7_2_PRODUCTION_STRATEGY_CONTRACT.md`](PHASE_7_2_PRODUCTION_STRATEGY_CONTRACT.md) — Technical production contract and scoring definitions.
- [`reports/PHASE_7_3_SILENT_GATEWAY_AUDIT.md`](PHASE_7_3_SILENT_GATEWAY_AUDIT.md) — Empirical audit and locked Option B policy recommendation.
- [`baseline_3sigma.py`](../baseline_3sigma.py) — Reference 3-sigma anomaly baseline implementation.
- [`validate_submission.py`](../validate_submission.py) — Grader submission validation script.
