# Phase 7 — Operational Decision & Production Specification

**LPDG Innovation Hub Selection Challenge 2026 (NEXORA 2026)**  
**Document Type:** High-Level Technical Explanation & Operational Architecture Narrative  
**Audience:** Technical Reviewers, Evaluators, and Engineering Leadership  
**Status:** Complete, Validated & Authoritative  
**Parent Technical Reports:**
- [`reports/PHASE_7_1_OPERATIONAL_DECISION.md`](PHASE_7_1_OPERATIONAL_DECISION.md)
- [`reports/PHASE_7_2_PRODUCTION_STRATEGY_CONTRACT.md`](PHASE_7_2_PRODUCTION_STRATEGY_CONTRACT.md)
- [`reports/PHASE_7_3_SILENT_GATEWAY_AUDIT.md`](PHASE_7_3_SILENT_GATEWAY_AUDIT.md)
- [`reports/PHASE_7_4_PRODUCTION_ARCHITECTURE_AND_TEST_PLAN.md`](PHASE_7_4_PRODUCTION_ARCHITECTURE_AND_TEST_PLAN.md)
- Reference Implementation: `baseline_3sigma.py`
- Validation Harness: `validate_submission.py`
- Executable Verification Notebooks: `notebooks/06_silent_gateway_audit.ipynb`, `notebooks/07_production_architecture_checks.ipynb`

---

## 1. Purpose of Phase 7

Phase 7 converts the empirical and statistical findings from Phases 5 and 6 into an operationally defensible, fully specified production decision.

The workflow across the project reflects a disciplined engineering progression:
- **Phase 5 (Signal Investigation & Ranking-Strategy Design):** Audited telemetry feasibility, engineered deterministic extraction pipelines, and pruned redundant features to construct candidate predictive signals.
- **Phase 6 (Historical Backtesting & Strategy Selection):** Evaluated candidate ranking strategies across 26 consecutive historical decision weeks under strict temporal anti-leakage conditions, directly comparing algorithmic recommendations against confirmed operational outcomes.
- **Phase 7 (Operational Decision & Production Specification):** Converts the backtesting evidence into:
  1. An asymmetric operational cost and decision model grounded in challenge constraints.
  2. A locked, immutable production strategy (`Baseline_3Sigma`).
  3. Explicit, empirically verified edge-case policies (specifically for silent active gateways).
  4. A modular 12-stage production architecture.
  5. A comprehensive four-tier testing and validation contract.

Crucially, **Phase 7 is not about discovering another model or re-running feature searches**. The modeling decision was resolved in Phase 6. Phase 7 is about freezing the operational decision, locking boundary contracts, eliminating implementation ambiguities, and ensuring that the final submission pipeline is completely reproducible, verifiable, and robust before any Phase 8 production code is written.

---

## 2. Starting Point from Phase 6

Phase 7 builds directly upon the validated empirical evidence established in Phase 6.3 ([`reports/PHASE_6_3_STRATEGY_DECISION.md`](PHASE_6_3_STRATEGY_DECISION.md)).

### 2.1 The Historical Backtest Baseline
Across 26 historical decision Mondays (`2025-08-04` through `2026-01-26`), the simulation evaluated seven distinct ranking strategies against 116 confirmed physical repair events (`Fehler behoben`), simulating 390 total weekly recommendations (15 per week) per strategy:

| Strategy | Repairs Captured | Total Repairs | Repair Capture Rate | False Alarms | False Alarm Rate | Repair Yield | Missed Repairs | False Alarm Proxy (€380) | Missed Repair Proxy (€600) | Combined Cost Proxy (€) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`Baseline_3Sigma`** | **41** | 116 | **35.34%** | **14** | **3.59%** | **10.51%** | 75 | **€5,320** | €45,000 | **€50,320** |
| **`Candidate_C_SevereOffline`** | 42 | 116 | 36.21% | 22 | 5.64% | 10.77% | 74 | €8,360 | €44,400 | €52,760 |
| **`Candidate_A_Core`** | 40 | 116 | 34.48% | 22 | 5.64% | 10.26% | 76 | €8,360 | €45,600 | €53,960 |
| **`Candidate_B_Severity`** | 37 | 116 | 31.90% | 21 | 5.38% | 9.49% | 79 | €7,980 | €47,400 | €55,380 |
| **`Candidate_D_LongTerm`** | 37 | 116 | 31.90% | 21 | 5.38% | 9.49% | 79 | €7,980 | €47,400 | €55,380 |
| **`Candidate_E_Reliability`** | 37 | 116 | 31.90% | 22 | 5.64% | 9.49% | 79 | €8,360 | €47,400 | €55,760 |
| **`Candidate_F_SilenceOverride`** | 37 | 116 | 31.90% | 21 | 5.38% | 9.49% | 79 | €7,980 | €47,400 | €55,380 |

### 2.2 Why Numerical Repair Improvement Alone Was Insufficient
Candidate C captured 42 repairs compared to 41 for `Baseline_3Sigma`—an apparent gain of one additional repair (+0.86% capture rate). However, achieving that single additional repair caused **8 additional false alarms** (22 vs. 14, a 57.1% increase in wasted inspections). 

Under the challenge cost model:
- Additional false alarms incurred: $+8 \times €380 = +€3,040$
- Missed repair proxy saved: $-1 \times €600 = -€600$
- Net economic impact: **+€2,440 worse** combined standardized penalty for Candidate C (€52,760 vs. €50,320).

Furthermore, paired weekly hypothesis testing established:
- Weekly repair capture difference: $t = 0.161, p = 0.8732$ (statistically indistinguishable).
- Weekly false alarm increase: $t = 2.133, p = 0.0430$ (statistically significant increase in false alarms).

Trading eight false field dispatches for a single additional repair was economically irrational and operationally unacceptable. Numerical improvement in raw repair count alone was not sufficient justification to replace the baseline.

### 2.3 Verified Conclusion
The historical backtest provided the strongest observed operational trade-off among the evaluated strategies. `Baseline_3Sigma` delivered the lowest false alarm count (14), the lowest false alarm rate (3.59%), the highest Top-5 concentration (19 repairs captured), and the lowest combined standardized cost proxy (€50,320). 

Therefore, **`Baseline_3Sigma` was selected and locked as the production strategy**. This choice reflects empirical operational evidence rather than a theoretical claim of universal mathematical superiority.

---

## 3. Why Cost Matters

The ranking challenge faced by an infrastructure operator is fundamentally a **capacity-constrained operational prioritization problem**, not an abstract anomaly-detection benchmark.

### 3.1 Challenge Economic Proxies
The Challenge Brief establishes explicit, asymmetric operational economic proxies:
- **False Visit Penalty:** **€380** per unnecessary field dispatch. Incurred when a gateway is dispatched in the Top 15, inspected by a field technician, and confirmed to have no defect (`Kein Fehler gefunden`).
- **Missed Broken Gateway Penalty:** **€600 per week** that an unaddressed faulty gateway remains unresolved. Incurred when a gateway with an active fault requiring repair (`Fehler behoben`) is omitted from the weekly Top 15.
- **Weekly Capacity Constraint:** A strict physical maximum of **15 site visits per week**.

Because physical inspection bandwidth is strictly capped at 15 visits per week, every slot assigned to a false alarm directly deprives another potentially degraded asset of inspection. 

### 3.2 Decision-Analysis Proxies vs. Measured Ledger Expenses
The values of €380 and €600 are **standardized challenge-provided decision proxies** designed to evaluate strategy trade-offs on equal terms across historical data. They do not represent measured real-world ledger accounting costs or contractual expenses. Because the precise historical onset of an unaddressed fault was unobserved, the €600 proxy represents a standardized one-week lower bound.

An operational ranking system must balance sensitivity against precision. A strategy that increases repair capture by 1 asset but generates 8 false dispatches degrades field productivity and incurs higher proxy costs. Prioritization quality matters precisely because physical capacity is finite and errors are costly.

---

## 4. Why Baseline_3Sigma Was Locked

The mathematical scoring formulation of `Baseline_3Sigma` is defined at a conceptual level as follows:

For each eligible gateway:
1. **Trailing Baseline Window:** Extract hourly telemetry over the 28 days strictly preceding decision Monday $T$: $[T - 28\text{d}, T)$.
2. **Distributional Parameters:** Calculate the baseline mean ($\mu$) and sample standard deviation ($\sigma$, with $\text{ddof}=1$) across all valid hourly observations for three operational metrics:
   - `offline_duration_sec`
   - `disconnection_cnt`
   - `reboot_cnt`
3. **Trailing Recent Window:** Extract hourly telemetry over the 7 days strictly preceding decision Monday $T$: $[T - 7\text{d}, T)$.
4. **Metric Breach Flagging:** For each individual hourly observation in the 7-day window, evaluate whether the metric exceeds its gateway-specific baseline threshold:
   $$x > \mu + 3\sigma$$
5. **Breach Accumulation:** Sum all individual metric breaches across all three metrics and all hours in the 7-day window.
6. **Fleet Prioritization:** Rank all candidate gateways by the resulting score in descending order.

### 4.1 Authoritative Score Interpretation
A critical clarification established in Phase 7 is the exact mathematical meaning of the score:
- **The score is NOT the count of unique flagged hours.**
- In any single hourly telemetry observation, $0, 1, 2, \text{ or } 3$ monitored metrics may simultaneously exceed their respective 3-sigma thresholds.
- Each exceeded metric increments the score accumulator by 1.
- Although the historical variable name `flagged_hours` is retained in code for backward compatibility, mathematically it represents the **aggregate count of individual metric breaches**.

This mathematical formulation is frozen. Phase 8 must implement this exact logic without reinterpreting thresholds, altering degrees of freedom, or substituting z-score equations.

---

## 5. Reference Algorithm vs Production Engineering Controls

A foundational distinction formalized in Phase 7 is the separation between the reference ranking algorithm and the surrounding production engineering controls:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                   PRODUCTION PIPELINE (Phase 8 Layer)                    │
│                                                                          │
│  [Raw Master & Telemetry] ──> Schema Validation ──> ID Canonicalization │
│                                                            │             │
│  [Exact Deduplication] <───────────────────────────────────┘             │
│         │                                                                │
│         ▼                                                                │
│  [Lifecycle Eligibility Gating] (gateway_master.csv)                     │
│         │                                                                │
│         ▼                                                                │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │             REFERENCE RANKING ALGORITHM (baseline_3sigma.py)        │  │
│  │                                                                    │  │
│  │  • 28-day baseline window [T-28d, T)                               │  │
│  │  • 7-day recent evaluation window [T-7d, T)                        │  │
│  │  • Three metrics (offline_duration_sec, disconnection, reboot)     │  │
│  │  • 3-sigma metric breach accumulator (sample std, ddof=1)          │  │
│  └──────────────────────────────────┬─────────────────────────────────┘  │
│                                     │                                    │
│         ┌───────────────────────────┘                                    │
│         ▼                                                                │
│  [Option B Silent Gateway Alignment (score=0.0)]                         │
│         │                                                                │
│         ▼                                                                │
│  [Deterministic Sort Invariant: score desc, gateway_id asc]              │
│         │                                                                │
│         ▼                                                                │
│  [Top-15 Selection & Observational Reason String Generation]             │
│         │                                                                │
│         ▼                                                                │
│  [Submission Export & Automated Grader Validation (validate_submission)] │
└──────────────────────────────────────────────────────────────────────────┘
```

The core principle governing Phase 7 is:
> **"The production system preserves the baseline scoring formulation while adding validated engineering controls required for a complete and reproducible submission."**

The reference script `baseline_3sigma.py` provides the raw mathematical scoring logic. However, on its own, it lacks:
- Identifier canonicalization (it assumes uniform IDs).
- Telemetry deduplication (it ingests duplicate retry rows directly).
- Complete lifecycle fleet tracking (it ignores assets with no telemetry).
- Deterministic tie-breaking (it leaves tied assets in arbitrary engine order).
- Output validation against grader requirements.

These engineering controls do **not** constitute a new ranking model or strategy. They are defensive infrastructure safeguards ensuring data integrity, temporal compliance, and execution determinism.

---

## 6. Silent Gateway Decision

Phase 7.3 ([`reports/PHASE_7_3_SILENT_GATEWAY_AUDIT.md`](PHASE_7_3_SILENT_GATEWAY_AUDIT.md)) conducted an exhaustive audit into how the production pipeline should handle an active gateway that transmits zero telemetry records during the 7-day scoring window $[T-7\text{d}, T)$.

### 6.1 Empirical Audit Findings
Across all eight forward scored Mondays (`2026-02-02` through `2026-03-23`):
1. **Fleet Size:** The lifecycle-eligible candidate universe ranged between **290 and 308 gateways** per week.
2. **Frequency of Complete Silence:** Only **3 instances** of complete telemetry silence occurred across the entire eight-week scored period (out of 2,393 total gateway-weeks, a rate of $0.125\%$):
   - `001A7D000139` on `2026-02-02`
   - `001A7D00013A` on `2026-02-09`
   - `001A7D00013B` on `2026-02-16`
3. **Physical Asset Origin:** All 3 silent gateway instances were brand-new assets whose installation date (`installed_on`) was identical to the scored decision Monday $T$. They had transmitted zero historical telemetry simply because they had just been commissioned.
4. **Impact on Top 15:** In all 8 scored weeks, positive-score gateways comfortably exceeded 15 (ranging from 17 to 37). In the observed eight-week scored period, silent gateways ranked below all positive-score gateways and therefore did not enter the Top-15.
5. **Policy Equivalence:** Comparing **Option A** (omitting silent gateways from candidate output) and **Option B** (retaining silent gateways with score 0.0) revealed **100% identical Top-15 selections** across all 120 submission slots.

### 6.2 Locked Policy: Option B
The production pipeline locks **Option B**:
- All lifecycle-eligible gateways are retained in the candidate ranking universe.
- Any eligible gateway with zero telemetry records in $[T-7\text{d}, T)$ is assigned:
  - $\text{score} = 0.0$
  - $\text{flagged\_hours} = 0$
  - $\text{worst\_metric} = \text{"no\_telemetry"}$

### 6.3 Why Option B Was Selected
The candidate fleet universe must be governed strictly by physical asset lifecycle dates from `gateway_master.csv`, not by telemetry presence. Telemetry absence should never silently drop an asset from fleet management visibility. 

Assigning $\text{score} = 0.0$ is an **operational engineering policy**, not a classification of the asset as healthy or broken. It guarantees that an asset with zero evidence of anomaly receives zero anomaly breach score, avoiding unvalidated artificial score inflation.

---

## 7. Why Candidate F Was Rejected

During Phase 6 strategy exploration, **Candidate F (Silence Override)** was designed to test whether complete telemetry silence should be treated as an acute breakdown signal. Candidate F awarded an artificial $+10.0$ score bonus to completely silent gateways.

### 7.1 Historical Backtest Results
Across the 26-week backtest, Candidate F performed poorly:
- **Baseline_3Sigma:** 14 false alarms, €50,320 combined standardized cost proxy.
- **Candidate F:** 21 false alarms, €55,380 combined standardized cost proxy.
- **Net Delta vs. Baseline:** **+7 false alarms**, **+€5,060 combined cost penalty**.

### 7.2 Engineering Implication
Historical evidence provides zero empirical support for treating telemetry silence as a positive repair-priority indicator. Gateways with communication loss frequently resolved communication issues remotely without requiring physical hardware repair, or represented newly commissioned hardware.

Awarding artificial score bonuses to silent gateways resulted in wasted field inspections and economic degradation. Phase 7 explicitly rejects silence bonuses, hidden heuristics, and arbitrary ranking boosts. Phase 8 must not reintroduce Candidate F behavior under any guise.

---

## 8. Temporal Integrity

Temporal integrity is non-negotiable. The production pipeline enforces a strict temporal anti-leakage contract across all scored weeks.

For any decision Monday $T$ (e.g., `2026-02-02 00:00:00 UTC`):
- **Baseline Historical Window:** Exactly 28 days strictly prior to $T$: $[T - 28\text{d}, T)$.
- **Recent Evaluation Window:** Exactly 7 days strictly prior to $T$: $[T - 7\text{d}, T)$.
- **Strict Anti-Leakage Boundary:**
  $$\text{timestamp} < T$$

Zero telemetry recorded at or after $\text{timestamp} \ge T$ is accessed by the scoring pipeline. Furthermore:
- All timestamps are evaluated strictly in UTC.
- Evaluative and downstream datasets (`field_visits.csv`, `engineer_review_2026-02.xlsx`, `meter_read_success.csv`) are strictly excluded from the production pipeline.
- Global aggregations across the entire multi-month dataset are prohibited; baseline statistics are derived strictly within each rolling window.

---

## 9. Lifecycle Eligibility

The candidate universe for each scored week is defined exclusively by physical asset lifecycle metadata from `data/gateway_master.csv`.

### 9.1 Mathematical Eligibility Rule
A gateway $i$ is eligible for recommendation on decision Monday $T$ if and only if:
$$\text{Eligible}(i, T) \iff \Big(\texttt{installed\_on}_i \le T\Big) \;\land\; \Big(\texttt{decommissioned\_on}_i > T \;\lor\; \texttt{decommissioned\_on}_i \text{ is null}\Big)$$

### 9.2 Critical Principles
1. **Precedence:** Lifecycle gating occurs **before** telemetry is joined or scored.
2. **Independence from Telemetry:** Telemetry presence does not determine eligibility. A gateway that stops transmitting does not disappear from the candidate fleet.
3. **Decommissioned Asset Gating:** Decommissioned assets ($	exttt{decommissioned\_on} \le T$) are strictly excluded from recommendation, preventing wasted dispatches to retired hardware.

---

## 10. Data Integrity Controls

Phase 7 establishes defensive data controls to handle verified empirical anomalies in the challenge raw data:

### 10.1 Gateway Identifier Canonicalization
Raw files contain divergent gateway ID formats, including uppercase, lowercase, and hyphenated representations (e.g., `00-1A-7D-00-01-39` vs `001a7d000139`).
- **Policy:** Canonicalize all gateway IDs across all dataframes to **12-character uppercase bare hexadecimal strings** (`^[0-9A-F]{12}$`).

### 10.2 Exact Telemetry Deduplication
Data audit revealed **exactly 6,547 duplicate records** on `(gateway_id, ts_utc)` in the raw telemetry Parquet files (concentrated in odd months: Sep 2025: 2,185; Nov 2025: 2,124; Jan 2026: 2,238).
- **Policy:** Deterministically drop duplicate records prior to baseline and breach computation:
  ```python
  telemetry = telemetry.drop_duplicates(subset=["gateway_id", "ts_utc"], keep="first")
  ```
- This prevents artificial variance expansion and inflated breach counts caused by network retry clones.

### 10.3 Unlisted Gateway Telemetry
Telemetry records bearing IDs not present in `gateway_master.csv` are dropped prior to scoring.

### 10.4 Ineligible Fleet Filtering
Assets failing the lifecycle eligibility test are purged before ranking, preventing decommissioned hardware from entering recommendations.

---

## 11. Deterministic Ranking

In operational field dispatch, recommendation lists must be strictly reproducible. When multiple gateways exhibit identical breach scores, sorting order must never be left to arbitrary hash table ordering or non-deterministic platform defaults.

### 11.1 Deterministic Tie-Breaking Specification
The ranking sort is frozen to a strict two-key hierarchy:
1. **Primary Key:** `score` **descending** (numerical anomaly breach total).
2. **Secondary Key:** `gateway_id` **ascending** (canonical lexicographical order).

### 11.2 Operational Purpose
Deterministic tie-breaking is an **operational engineering control**, not an intrinsic property of the physical 3-sigma anomaly score. It ensures that repeated pipeline executions on identical input data yield identical output orderings.

---

## 12. Reason Generation

The Challenge submission schema mandates a non-empty `reason` text field ($\le 300$ characters) for every recommendation.

### 12.1 Explainability Requirements
Generated reason strings must:
- Be factual, concise, and understandable to field dispatchers.
- Report observed statistical breaches against the asset's own historical baseline.
- Identify the primary metric exhibiting anomaly.
- **Avoid unsupported causal claims.**

### 12.2 Frozen Reason Templates
- **For Positive-Score Gateways ($N \ge 1$):**
  > `"{N} individual 3-sigma metric breach(es) against this gateway's own 28-day baseline in the last 7 days; first breach on {worst_metric}"`
- **For Zero-Score Gateways ($N = 0$, if selected):**
  > `"0 individual 3-sigma metric breaches against this gateway's own 28-day baseline in the last 7 days"`

### 12.3 Prohibition of Causal Attribution
The pipeline monitors statistical telemetry breaches. It cannot observe physical causation. Generating claims such as *"blown fuse"*, *"cut cable"*, *"power supply failure"*, or *"lightning damage"* is strictly prohibited because such physical mechanisms cannot be established from telemetry time series alone.

---

## 13. Production Architecture Decision

Phase 7.4 ([`reports/PHASE_7_4_PRODUCTION_ARCHITECTURE_AND_TEST_PLAN.md`](PHASE_7_4_PRODUCTION_ARCHITECTURE_AND_TEST_PLAN.md)) specifies a linear, decoupled 12-stage production architecture:

1. **Raw Ingestion:** Load `gateway_master.csv` and telemetry partitions into memory.
2. **Schema Validation:** Verify column names, data types, and non-emptiness.
3. **Gateway ID Normalization:** Canonicalize master and telemetry IDs to 12-character hex.
4. **Telemetry Deduplication:** Eliminate exact duplicate records on `(gateway_id, ts_utc)`.
5. **Lifecycle Eligibility:** Filter master fleet to assets active on decision Monday $T$.
6. **Temporal Cutoff:** Apply strict anti-leakage horizon ($	ext{ts} < T$) to separate baseline $[T-28	ext{d}, T)$ and recent $[T-7	ext{d}, T)$ telemetry.
7. **Baseline 3-Sigma Scoring:** Compute baseline means, sample standard deviations ($	ext{ddof}=1$), and sum individual 3-sigma breaches.
8. **Silent Gateway Alignment:** Merge with eligible universe, assigning silent active gateways $	ext{score}=0.0$, $	ext{flagged\_hours}=0$, and $	ext{worst\_metric}="no\_telemetry"$.
9. **Deterministic Ranking:** Sort fleet by `score` descending, `gateway_id` ascending.
10. **Top-15 Selection:** Extract ranks $1, 2, \dots, 15$ for the weekly recommendation list.
11. **Reason Generation:** Populate template-based, observational reason strings.
12. **Output Validation & Serialization:** Export `predictions.csv` and validate schema via `validate_submission.py`.

This modular architecture separates ingestion, mathematical scoring, operational ranking, and serialization, ensuring high testability, maintainability, and clean failure handling.

---

## 14. Testing Philosophy

The testing strategy frozen in Phase 7 is structured across four rigorous tiers to guarantee that the production pipeline executes correctly, safely, and reproducibly:

```
┌────────────────────────────────────────────────────────┐
│ TIER 4: End-to-End Pipeline & Submission Validation    │
│         Full run on real data -> validate_submission   │
├────────────────────────────────────────────────────────┤
│ TIER 3: Regression & Anti-Leakage Guards               │
│         Future telemetry injection & file independence │
├────────────────────────────────────────────────────────┤
│ TIER 2: Component Integration Tests                    │
│         Multi-week runs on synthetic mini-fleet        │
├────────────────────────────────────────────────────────┤
│ TIER 1: Isolated Unit Tests                            │
│         Mathematical edge cases, ID formatting, ddof=1 │
└────────────────────────────────────────────────────────┘
```

- **Tier 1 (Unit Tests):** Test individual helper functions in isolation: ID canonicalization, deduplication logic, lifecycle date filtering, sample variance ($	ext{ddof}=1$), single observation handling, breach accumulation, and reason string formatting.
- **Tier 2 (Integration Tests):** Test multi-component execution across synthetic multi-week mini-fleets, verifying correct dataflow from ingestion through ranking.
- **Tier 3 (Anti-Leakage & Regression Guards):** Actively inject synthetic future spikes ($	ext{ts} \ge T$), mutate downstream evaluation files (`field_visits.csv`), and verify that production rankings remain 100% unchanged. Prevent reintroduction of Candidate F silence bonuses.
- **Tier 4 (End-to-End Validation):** Execute the complete pipeline on real data, generating `predictions.csv`, and invoke `validate_submission.py` to assert exit code 0. Run consecutive dual-runs to verify hash equality.

---

## 15. Critical Edge Cases

The production specification defines explicit, deterministic handling for twelve critical operational edge cases:

| # | Edge Case | Expected System Behavior | Test Verification Method |
| :---: | :--- | :--- | :--- |
| **1** | **Completely silent active gateway** | Retained with $	ext{score} = 0.0$, `worst_metric = "no_telemetry"`; ranked by `gateway_id`. | Fixture with active gateway having zero telemetry rows. |
| **2** | **Single baseline observation ($N=1$)** | Sample standard deviation is NaN ($N-1=0$). Breaches evaluate to `False`; $	ext{score} = 0.0$. | Synthetic gateway with single baseline point in $[T-28	ext{d}, T)$. |
| **3** | **Zero baseline variance ($\sigma = 0$)** | Standard deviation replaced with NaN; breaches evaluate to `False`; $	ext{score} = 0.0$. | Synthetic gateway with identical constant values for 28 days. |
| **4** | **Zero recent telemetry (with 28d history)** | Gateway evaluated normally; 0 recent rows yield 0 breaches; $	ext{score} = 0.0$. | Gateway active in baseline window but silent in $[T-7	ext{d}, T)$. |
| **5** | **Zero baseline telemetry (new install)** | Baseline statistics are NaN; breaches evaluate to `False`; $	ext{score} = 0.0$. | Gateway installed on Monday $T$ with zero pre-$T$ records. |
| **6** | **Exact duplicate telemetry** | Deduplicated via `(gateway_id, ts_utc)` keeping first occurrence. | Inject clone rows into fixture; assert identical score to deduplicated input. |
| **7** | **Future telemetry present in raw file** | Filtered out by strict cutoff rule ($	ext{ts} < T$); zero impact on scores. | Inject future records ($	ext{ts} \ge T$); assert output ranking is unchanged. |
| **8** | **Unknown gateway ID in telemetry** | Telemetry for IDs not in `gateway_master.csv` is dropped prior to ranking. | Inject telemetry for unlisted ID; assert absent from rankings. |
| **9** | **Inactive / decommissioned gateway** | Filtered out during lifecycle gating; never appears in Top-15. | Gateway decommissioned before $T$; assert absent from ranked universe. |
| **10** | **Multiple gateways tied on score** | Resolved deterministically by canonical `gateway_id` ascending. | Synthetic gateways with identical breach counts; assert alphabetical ordering. |
| **11** | **Fewer than 15 eligible active gateways** | Pipeline halts immediately with explicit fatal exception. | Fixture with 14 active gateways; assert exception raised. |
| **12** | **Empty input file / malformed schema** | Pipeline halts immediately with schema validation exception. | Corrupt column headers; assert clear descriptive error. |

---

## 16. What Phase 7 Has Frozen

The following architectural and operational decisions are fully frozen for Phase 8 implementation:

| Pipeline Dimension | Locked Decision Specification |
| :--- | :--- |
| **Production Strategy** | `Baseline_3Sigma` (3-Sigma Anomaly Baseline) |
| **Baseline Window** | 28 trailing days strictly before cutoff: $[T - 28	ext{d}, T)$ |
| **Recent Window** | 7 trailing days strictly before cutoff: $[T - 7	ext{d}, T)$ |
| **Anomaly Threshold** | Value strictly exceeding baseline: $x > \mu + 3\sigma$ |
| **Baseline Standard Deviation** | Sample standard deviation using $	ext{ddof}=1$ |
| **Monitored Metrics** | `offline_duration_sec`, `disconnection_cnt`, `reboot_cnt` |
| **Silent Gateway Policy** | **Option B** (retain lifecycle-eligible silent gateways in candidate universe) |
| **Silent Gateway Score** | $	ext{score} = 0.0$, $	ext{flagged\_hours} = 0$, $	ext{worst\_metric} = 	ext{"no\_telemetry"}$ |
| **Silence Bonus** | Strictly forbidden (Candidate F $+10.0$ bonus rejected) |
| **Fleet Eligibility Gating** | Master lifecycle dates: $	exttt{installed\_on} \le T \land (	exttt{decommissioned\_on} > T \lor 	ext{null})$ |
| **Telemetry Deduplication** | Deterministic deduplication on `(gateway_id, ts_utc)` keeping first row |
| **Tie-Breaking Convention** | Primary: `score` descending; Secondary: canonical `gateway_id` ascending |
| **Weekly Recommendation Size** | Exactly 15 recommendations per scored Monday |
| **Reason Text Style** | Observational, non-causal statistical description ($\le 300$ characters) |
| **Temporal Anti-Leakage** | Strict cutoff: $	ext{timestamp} < T$; zero future data access |
| **Machine Learning** | Not selected (unjustified complexity, higher operational risk) |
| **Phase 8 Objective** | Pure engineering implementation and verification; zero algorithm redesign |

---

## 17. What Phase 7 Did NOT Prove

To maintain rigorous scientific and engineering integrity, it is mandatory to document what Phase 7 does **not** prove:

1. **Not Physical Hardware Failure Prediction:** The system detects statistical anomalies in telemetry time series; it does not observe physical component degradation, wire breakage, or mechanical wear.
2. **Not Causal Explanation:** Telemetry breaches indicate unusual communication or reboot patterns; they do not establish the root cause of an outage.
3. **Not Universal Mathematical Superiority:** `Baseline_3Sigma` demonstrated the most favorable operational trade-off across the 26 historical weeks analyzed. This does not constitute a mathematical proof that it will outperform all other conceivable strategies in all environments.
4. **Not Guaranteed Future Performance:** Performance during the 8 forward scored weeks cannot be known prior to grader evaluation.
5. **Not Measured Ledger Financial Savings:** Cost figures are based on challenge-standardized evaluation proxies (€380 and €600), not audited utility accounts.
6. **Silence Does Not Prove a Specific Failure Mode:** Complete silence is an absence of data; it cannot be inferred to mean either healthy operation or permanent hardware destruction.
7. **Historical Dispatches Are Imperfect Labels:** Ground-truth repair outcomes reflect decisions made by historical dispatchers and technicians, which may contain operational biases or unobserved field constraints.
8. **Not Guaranteed Infinite Generalizability:** The pipeline is tailored to the operational boundaries and data schemas of the NEXORA 2026 challenge.

Acknowledging these limitations reflects sound engineering discipline: our choices are grounded in empirical evidence and operational realism, without overstating algorithmic capability.

---

## 18. Transition to Phase 8

With Phase 7 complete, the production specification is formally frozen. Phase 8 will transition from specification to implementation:

```
                          PHASE 7 (Complete & Frozen)
┌──────────────────────────────────────────────────────────────────────────┐
│  • Operational Cost & Decision Model Locked (Phase 7.1)                  │
│  • Production Strategy Contract Frozen (Phase 7.2)                       │
│  • Silent Gateway Policy Option B Validated (Phase 7.3)                  │
│  • 12-Stage Architecture & 4-Tier Test Plan Approved (Phase 7.4)         │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
                          PHASE 8 (Implementation)
┌──────────────────────────────────────────────────────────────────────────┐
│  1. Implement Production Modules under `src/nexora/`:                     │
│     - `config.py`, `data_loader.py`, `lifecycle.py`, `deduplication.py`,  │
│       `scoring.py`, `ranking.py`, `reasons.py`, `pipeline.py`            │
│  2. Build Comprehensive Test Suite under `tests/`:                       │
│     - Tier 1 Unit Tests, Tier 2 Integration, Tier 3 Anti-Leakage Guards  │
│  3. CLI Entry Point (`python -m nexora.pipeline --data data/`)           │
│  4. Authoritative Artifact Generation (`predictions.csv`)                │
│  5. Submission Validation (`python validate_submission.py`)              │
└──────────────────────────────────────────────────────────────────────────┘
```

### Governing Implementation Principle
> **"Phase 7 decides what the production system must do. Phase 8 makes that specification executable."**

Phase 8 engineers must **not**:
- Redesign the ranking strategy or tune 3-sigma thresholds.
- Add machine learning classifiers or composite feature weighting.
- Introduce arbitrary heuristics, weights, or score bonuses.
- Reintroduce Candidate F silence bonuses.
- Access evaluation files (`field_visits.csv`, `engineer_review_2026-02.xlsx`).

Phase 8 will focus entirely on clean software design, modular code structure, test automation, execution performance, and grader compliance.

---

## 19. Final Phase 7 Conclusion

Phase 5 identified and analyzed candidate telemetry features.  
Phase 6 evaluated candidate ranking strategies across 26 historical weeks, establishing that `Baseline_3Sigma` achieved the best operational trade-off between repair capture and false alarms.  
Phase 7 converted that empirical choice into a robust, complete production specification:

$$\mathbf{Baseline\_3Sigma} \;+\; \mathbf{Option\ B\ Silent\ Policy} \;+\; \mathbf{Lifecycle\ Universe\ Gating} \;+\; \mathbf{Deterministic\ Controls}$$

By locking the operational model, establishing temporal boundaries, resolving edge cases, and designing a multi-tier test harness, Phase 7 eliminates technical risk. Phase 8 can now execute the implementation with complete clarity and confidence.
