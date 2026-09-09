# Phase 7.3 — Production Edge-Case Audit: Silent Active Gateways

**Author:** NEXORA Operational Engineering Team  
**Date:** 2026-09-08  
**Status:** COMPLETE (Edge-Case Audit & Policy Recommendation)  
**Selected Strategy:** `Baseline_3Sigma` (Preserved Without Modification)  
**Analyzed Window:** 8 Scored Mondays (`2026-02-02` through `2026-03-23`)  

---

## 1. Purpose

This document provides an **authoritative, evidence-based edge-case audit** evaluating how the production pipeline should handle active gateways that have **zero telemetry records** during the recent 7-day scoring window $[T-7\text{d}, T)$.

In Phase 7.2 ([`reports/PHASE_7_2_PRODUCTION_STRATEGY_CONTRACT.md`](PHASE_7_2_PRODUCTION_STRATEGY_CONTRACT.md)), Section 21 explicitly bounded this investigation:
> *"Phase 7.3 is authorized to audit edge cases and recommend production handling for silent gateways. However, Phase 7.3 is NOT authorized to casually introduce a new ranking model, add unvalidated heuristics (such as Candidate F's $+10.0$ silence bonus), or alter the baseline 3-sigma scoring formulation."*

This audit directly answers:
1. Exactly how many active gateways are completely silent in the recent 7-day window across the eight scored Mondays?
2. What is the physical origin and history of these silent gateways?
3. How many positive-score vs. zero-score gateways exist in each scored week?
4. Can completely silent gateways enter the weekly Top-15 recommendations under the selected `Baseline_3Sigma` strategy?
5. Does the treatment of silent gateways (omission vs. retention with score 0) alter the final submission artifact `predictions.csv`?
6. Which operational policy (Option A, Option B, or Option C) should be frozen for Phase 8 implementation?

---

## 2. Scope

The audit is strictly bounded by the following parameters:
- **Scored Mondays:** Exactly the eight forward challenge evaluation dates:
  - `2026-02-02`, `2026-02-09`, `2026-02-16`, `2026-02-23`
  - `2026-03-02`, `2026-03-09`, `2026-03-16`, `2026-03-23`
- **Ranking Strategy:** Exclusively `Baseline_3Sigma`. The mathematical scoring formulation is frozen and remains unmodified.
- **No New Heuristics:** No silence bonuses (+10 bonus from Candidate F is strictly forbidden), no penalties, no machine learning, and no composite weighting.
- **Implementation Status:** Audit only; no production Python code is deployed or modified during this phase.

---

## 3. Data and Temporal Contract

All calculations follow the validated data contracts established in earlier phases:

1. **Eligibility Universe:** Sourced strictly from `data/gateway_master.csv` (Latin-1 encoded). An asset is eligible at decision Monday $T$ if and only if:
   $$\text{Eligible}(i, T) \iff \Big(\texttt{installed\_on}_i \le T\Big) \;\land\; \Big(\texttt{decommissioned\_on}_i > T \;\;\lor\;\; \texttt{decommissioned\_on}_i \text{ is null}\Big)$$
   *Telemetry presence does not determine eligibility.*
2. **Identifier Canonicalization:** All identifiers are normalized to 12-character uppercase bare hexadecimal strings (`^[0-9A-F]{12}$`) via `normalize_gateway_id()`.
3. **Telemetry Deduplication:** Exact full-row duplicate records (6,547 verified records on `(gateway_id, ts_utc)`) are removed using `drop_duplicates(subset=["gateway_id", "ts_utc"], keep="first")` prior to computing window statistics.
4. **Temporal Windows:**
   - **Baseline History:** Trailing 28 days strictly before $T$: $[T - 28\text{d}, T)$.
   - **Recent Evaluation:** Trailing 7 days strictly before $T$: $[T - 7\text{d}, T)$.
   - **Anti-Leakage Cutoff:** Strict $\text{timestamp} < T$. Zero telemetry with $\text{timestamp} \ge T$ is accessed.
5. **No Evaluative Inputs in Production:** `field_visits.csv`, `engineer_review_2026-02.xlsx`, and `meter_read_success.csv` are strictly excluded from ranking calculations.

---

## 4. Silent-Gateway Definition

In this audit, a **completely silent active gateway** is defined strictly and observationally as:

> **An asset that is lifecycle-eligible on decision Monday $T$, but has exactly zero telemetry records in the trailing 7-day scoring window $[T-7\text{d}, T)$.**

### Critical Observational Distinction
We maintain strict engineering discipline regarding observational language:
- Silence means **only** that zero telemetry packets were observed during the 7-day evaluation window.
- Silence does **NOT** prove "physical hardware failure", "power grid outage", "lightning damage", or "broken gateway".
- A gateway may emit zero telemetry because it was newly installed on Monday $T$ itself, because of cellular network maintenance, or because of a local power disconnect.
- The pipeline observes only the absence of telemetry; root causes are unobserved.

---

## 5. Audit Methodology

For each of the eight scored Mondays $T$:
1. **Universe Extraction:** Filter `gateway_master.csv` to identify all gateways active on Monday $T$.
2. **Telemetry Cross-Referencing:** Query the deduplicated telemetry corpus to identify:
   - Eligible gateways with $\ge 1$ telemetry observation in $[T-7\text{d}, T)$ (telemetry-present).
   - Eligible gateways with 0 telemetry observations in $[T-7\text{d}, T)$ (silent gateways).
3. **Baseline History Auditing:** For each silent gateway, query the 28-day historical window $[T-28\text{d}, T)$ to determine whether prior telemetry exists.
4. **Baseline 3-Sigma Execution:** Run the reference 3-sigma anomaly scoring logic across the fleet. Calculate:
   - The number of gateways with $\text{score} > 0$ (accumulated 3-sigma breaches).
   - The number of gateways with $\text{score} == 0$ (both reporting gateways with no breaches and silent gateways).
5. **Top-15 Boundary Simulation:** Rank the fleet under:
   - **Option A:** Omitting silent gateways from the ranking universe (raw `baseline_3sigma.py` behavior).
   - **Option B:** Retaining silent gateways with $\text{score} = 0$ (Phase 6 backtester universe-aligned wrapper).
   - Compare the Top-15 recommendations, ranks, scores, and reasons between Option A and Option B.

---

## 6. Eight-Week Empirical Results Table

The audit was executed across all 1.43 million telemetry records and 332 master gateway records. The measured results across the eight scored Mondays are presented below:

| Week | Eligible | Telemetry-present | Silent | Silent with 28d history | Silent with no 28d history | Positive-score gateways | Zero-score gateways | Silent enters Top-15? |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| 2026-02-02 | 290 | 290 | 0 | 0 | 0 | 260 | 30 | No |
| 2026-02-09 | 291 | 290 | 1 | 0 | 1 | 262 | 29 | No |
| 2026-02-16 | 294 | 294 | 0 | 0 | 0 | 266 | 28 | No |
| 2026-02-23 | 298 | 298 | 0 | 0 | 0 | 277 | 21 | No |
| 2026-03-02 | 300 | 299 | 1 | 0 | 1 | 269 | 31 | No |
| 2026-03-09 | 304 | 303 | 1 | 0 | 1 | 268 | 36 | No |
| 2026-03-16 | 308 | 308 | 0 | 0 | 0 | 270 | 38 | No |
| 2026-03-23 | 308 | 308 | 0 | 0 | 0 | 275 | 33 | No |

*Note: All counts are derived from actual execution against repository datasets.*

---

## 7. Silent-Gateway Details and Investigation

Across the eight scored Mondays ($8 \times \approx 300 = 2,405$ total asset-evaluations), there are **exactly three instances** of completely silent active gateways:

1. **Week 2 (`2026-02-09`): Gateway `0EA061007895`**
   - **Installation Date:** `2026-02-09`
   - **Decommissioned Date:** `NaN` (Active)
   - **Telemetry in $[T-7\text{d}, T)$:** 0 rows.
   - **Telemetry in $[T-28\text{d}, T)$:** 0 rows.
   - **First Telemetry Timestamp:** `2026-02-09 00:00:00+00:00`.
   - **Analysis:** This gateway was installed on the exact Monday of decision week 2. Because the temporal horizon strictly requires $\text{timestamp} < T$ (pre-Monday 00:00 UTC), zero telemetry existed prior to the decision point. Subsequent telemetry confirms normal operation starting at installation.

2. **Week 5 (`2026-03-02`): Gateway `0EE587927263`**
   - **Installation Date:** `2026-03-02`
   - **Decommissioned Date:** `NaN` (Active)
   - **Telemetry in $[T-7\text{d}, T)$:** 0 rows.
   - **Telemetry in $[T-28\text{d}, T)$:** 0 rows.
   - **First Telemetry Timestamp:** `2026-03-02 00:00:00+00:00`.
   - **Analysis:** Installed on the exact Monday of decision week 5. Zero historical telemetry existed prior to Monday 00:00 UTC. Subsequent telemetry demonstrates active reporting.

3. **Week 6 (`2026-03-09`): Gateway `02D3289B907C`**
   - **Installation Date:** `2026-03-09`
   - **Decommissioned Date:** `NaN` (Active)
   - **Telemetry in $[T-7\text{d}, T)$:** 0 rows.
   - **Telemetry in $[T-28\text{d}, T)$:** 0 rows.
   - **First Telemetry Timestamp:** `2026-03-09 00:00:00+00:00`.
   - **Analysis:** Installed on the exact Monday of decision week 6. Zero historical telemetry existed prior to Monday 00:00 UTC. Subsequent telemetry demonstrates active reporting.

### Core Empirical Finding:
**100% of completely silent active gateways during the scored period are newly commissioned assets installed on the decision Monday itself.**  
There is **not a single instance** in the eight scored weeks where an existing, previously operational gateway suffered a total communication blackout and became silent.

---

## 8. Positive-Score vs. Zero-Score Analysis

A vital consideration for ranking behavior is the volume of gateways that accumulate positive metric-breach scores:

- **Abundance of Positive-Score Assets:** In every scored week, between **260 and 277 active gateways** have $\text{score} > 0$ (representing 88.2% to 93.0% of the active fleet).
- **Small Zero-Score Population:** Gateways with $\text{score} == 0$ comprise only 21 to 38 assets per week.
- **High Anomaly Density at Rank 15:**
  - `2026-02-02`: Rank 15 score = 18.0
  - `2026-02-09`: Rank 15 score = 16.0
  - `2026-02-16`: Rank 15 score = 19.0
  - `2026-02-23`: Rank 15 score = 20.0
  - `2026-03-02`: Rank 15 score = 17.0
  - `2026-03-09`: Rank 15 score = 17.0
  - `2026-03-16`: Rank 15 score = 15.0
  - `2026-03-23`: Rank 15 score = 15.0

Across all eight weeks, the cutoff threshold to enter the Top-15 is at least **15 to 20 metric breaches**. Gateways with $\text{score} = 0$ are ranked between positions **261 and 308**, separated from the Top-15 cutoff by more than **245 higher-scoring candidates**.

---

## 9. Top-15 Impact Analysis

To rigorously test whether silent-gateway handling impacts the final submission, we simulated both options side-by-side:

- **Option A (Omit Silent Gateways):** Gateways with zero recent telemetry are omitted from the ranking list (producing a ranked list of 290 to 308 items).
- **Option B (Retain Silent Gateways with Score 0):** Silent gateways are included in the ranked list with $\text{score} = 0.0$ and secondary sort by `gateway_id` ascending (producing a ranked list of exactly 290 to 308 items).

### Mathematical Verification:
In all eight scored weeks:
1. **Top-15 Gateway IDs:** Exactly identical between Option A and Option B ($15/15$ matches for all 8 weeks).
2. **Top-15 Ranks:** Ranks $1, 2, \dots, 15$ match identically.
3. **Top-15 Scores:** Scores match identically.
4. **Top-15 Reasons:** Reasons match identically.

**Empirical Result:** Completely silent gateways are **never selected into the Top-15** under either policy. Handling silent active gateways by assigning them $\text{score} = 0.0$ has **zero impact** on the final 120-row submission artifact `predictions.csv`.

---

## 10. Retrospective Historical Field-Visit Analysis

To determine whether silent gateways historically correlated with confirmed repairs, we conducted a retrospective observational query against `data/field_visits.csv`.

> [!IMPORTANT]
> This analysis is retrospective and descriptive only. Field visit data is strictly forbidden from the forward prediction pipeline.

### Findings:
1. **Scored-Period Gateways:** None of the three silent gateways (`0EA061007895`, `0EE587927263`, `02D3289B907C`) ever appeared in `field_visits.csv`. No technician visits or repairs were ever requested or executed for them.
2. **26 Historical Backtest Weeks (`2025-08-04` to `2026-01-26`):**
   Across the 26 historical decision Mondays, there were only **4 instances** of silent active gateways:
   - Three were newly installed gateways on decision day (`0A58FAD26D9D` on 2026-01-05; `02817D5E40EE` and `069FB4585F6E` on 2026-01-19). None had field visits.
   - One was an existing gateway (`0A568E79FEF6` on `2025-12-22`, installed in 2021). Its subsequent field visit on `2026-01-26` resulted in:
     $$\texttt{outcome} = \text{"Kein Fehler gefunden" (False Alarm)}$$
3. **Descriptive Conclusion:** Historical evidence provides no support for treating complete telemetry silence as a positive repair-priority signal. The silence-boosting Candidate F evaluated in Phase 6.3 produced 21 false alarms versus 14 for Baseline_3Sigma, with a €55,380 combined standardized proxy versus €50,320 for the baseline (+€5,060). Candidate F is therefore rejected.

---

## 11. Reference Baseline vs. Phase 6 Universe-Aligned Behavior

An important architectural nuance exists between the reference script and our Phase 6 backtester:

### Reference Script (`baseline_3sigma.py`)
In `baseline_3sigma.py`, the code filters telemetry on the recent 7-day window:
```python
recent = window[window["ts"] >= end - dt.timedelta(days=RECENT_DAYS)].copy()
grouped = recent.groupby("gateway_id").agg(...)
return grouped.sort_values("flagged_hours", ascending=False).reset_index()
```
If a gateway has no rows in `recent`, it is absent from `recent.groupby("gateway_id")`. The returned DataFrame contains only gateways with telemetry.

### Phase 6 Wrapper (`Baseline3SigmaStrategy.rank`)
In `src/nexora/backtesting/strategies.py`, our backtesting wrapper enforced **universe parity**:
```python
active_ids = set(feature_df["gateway_id"])
ranked = ranked[ranked["gateway_id"].isin(active_ids)].copy()
missing_ids = active_ids - set(ranked["gateway_id"])
if missing_ids:
    missing_df = pd.DataFrame({
        "gateway_id": sorted(missing_ids),
        "flagged_hours": 0,
        "worst_metric": "no_telemetry",
    })
    ranked = pd.concat([ranked, missing_df], ignore_index=True)
```
Silent gateways were explicitly retained with `flagged_hours = 0` and placed at the bottom of the list.

### Impact Comparison:
Because the positive-score fleet is large ($\ge 260$), both implementations produce the **exact same Top-15 recommendations** for all scored weeks. However, the Phase 6 wrapper provides structural safety by maintaining alignment with `gateway_master.csv`.

---

## 12. Evaluation of Decision Options

We evaluated three potential operational policies for handling completely silent active gateways:

### Option A: Omit Completely Silent Active Gateways from Ranking
- **Description:** Allow silent gateways to drop out of the ranking, matching raw `baseline_3sigma.py`.
- **Compatibility:** 100% compatible with the reference baseline script.
- **Top-15 Impact:** Zero difference; identical Top-15 recommendations.
- **Risk:** Breaks the lifecycle universe contract. If a catastrophic network event silenced $> 95\%$ of the fleet, the ranked list could contain fewer than 15 gateways, causing `build_predictions()` to crash or violate the 15-recommendation contract.

### Option B: Retain Completely Silent Active Gateways with Score 0 (Recommended)
- **Description:** Retain all lifecycle-eligible gateways in the ranking. Assign silent gateways $\text{score} = 0.0$, `flagged_hours = 0`, and secondary tie-break by `gateway_id` ascending.
- **Compatibility:** 100% compatible with the Phase 6 verified backtester (`Baseline3SigmaStrategy.rank`).
- **Top-15 Impact:** Zero difference; identical Top-15 recommendations.
- **Advantages:**
  - Preserves the foundational contract that the active universe is defined by `gateway_master.csv` lifecycle dates.
  - Formally guarantees that the ranked list size always equals the eligible fleet size ($N_{\text{active}} \ge 290 > 15$).
  - Does not introduce any arbitrary heuristic bonus or penalty.
  - Fully deterministic and easily explainable.

### Option C: Apply Heuristic Scoring Override (e.g., +10 Silence Bonus)
- **Description:** Artificially elevate silent gateways to force them into the Top-15.
- **Evaluation:** Evaluated in Phase 6.3 as Candidate F. Empirical backtesting proved that Candidate F caused an unacceptable increase in false alarms (21 vs. 14 for the baseline, +7 false alarms; €55,380 vs. €50,320 combined standardized proxy, +€5,060 net penalty).
- **Assessment:** **Strictly Rejected.** Introducing heuristic bonuses violates the strategy freeze and degrades operational efficiency.

---

## 13. Final Policy Recommendation

### Authoritative Decision: **ADOPT OPTION B**

The production pipeline implemented in Phase 8 shall implement **Option B**:
1. **Full Universe Alignment:** All gateways verified active via `gateway_master.csv` on decision Monday $T$ are retained in the candidate ranking universe.
2. **Zero Score for Silent Assets:** Any active gateway with zero telemetry in $[T-7\text{d}, T)$ is assigned:
   - $\text{score} = 0.0$
   - $\text{flagged\_hours} = 0$
   - $\text{worst\_metric} = \text{"no\_telemetry"}$
3. **Deterministic Tie-Breaking:** All zero-score gateways are placed at the bottom of the ranked list, sorted by canonical `gateway_id` ascending.
4. **Capacity Guarantee:** Because $\ge 260$ gateways accumulate positive scores in every scored week, silent assets will never enter the Top-15, but their retention ensures that the pipeline structurally guarantees a full candidate pool of $\ge 290$ assets.

---

## 14. Strategy-Preservation Assessment

Option B strictly preserves the frozen `Baseline_3Sigma` strategy:
- **No Mathematical Changes:** The 3-sigma threshold, 28-day baseline mean/std ($\text{ddof}=1$), 7-day scoring window, metric breach accumulation, and deterministic sorting are completely unchanged.
- **No Arbitrary Heuristics:** No artificial score increments or penalties are added.
- **Verifiable Identity:** The resulting predictions are 100% identical to the reference baseline rankings for the Top-15 recommendations.

---

## 15. Operational Limitations

1. **New Asset Artifact:** All 3 silent gateways in the scored period were newly installed assets on decision Monday. Because telemetry begins on Monday at 00:00 UTC, strict pre-$T$ cutoff renders them silent prior to Monday.
2. **Zero Natural Blackouts:** The observed dataset exhibits high cellular reliability across established gateways; zero pre-existing gateways went completely silent during the eight scored weeks.
3. **Sparsity Safety:** In scenarios with extreme telemetry loss, Option B safely falls back to canonical identifier ordering rather than crashing on missing rows.

---

## 16. Verification Checklist

- [x] Exactly 8 scored weeks analyzed (`2026-02-02` to `2026-03-23`).
- [x] Lifecycle eligibility verified from `gateway_master.csv`.
- [x] Gateway IDs canonicalized to 12-char bare uppercase hex.
- [x] Telemetry deduplicated (6,547 duplicates removed).
- [x] Recent window is strictly $[T-7\text{d}, T)$.
- [x] Baseline window is strictly $[T-28\text{d}, T)$.
- [x] Strict $\text{timestamp} < T$ cutoff enforced (zero future leakage).
- [x] Field visits, engineer review, and meter reads excluded from ranking.
- [x] `Baseline_3Sigma` scoring formulation preserved without modification.
- [x] No Candidate F, no +10 silence bonus, no ML, no weight optimization.
- [x] Silent gateways explicitly identified and documented.
- [x] Positive-score vs. zero-score distributions quantified.
- [x] Top-15 identity between Option A and Option B mathematically verified.
- [x] Deterministic execution verified.
- [x] Raw datasets untouched.

---

## 17. Phase 7.4 Boundary

With Phase 7.3 complete:
- **Phase 7.3 Audited and Decided:** The handling of completely silent active gateways (Option B adopted).
- **Phase 7.4 (Production Architecture & Test Plan):** Will specify the modular software architecture, unit test suites, integration test harness, and validation scripts for the final Part 1 pipeline before implementation begins in Phase 8.

---

## Related Documents

- [`reports/PHASE_6_2_BACKTEST_ENGINE.md`](PHASE_6_2_BACKTEST_ENGINE.md) — Backtesting engine and universe-aligned wrapper implementation.
- [`reports/PHASE_6_3_STRATEGY_DECISION.md`](PHASE_6_3_STRATEGY_DECISION.md) — Candidate evaluation and rejection of Candidate F silence bonus.
- [`reports/PHASE_7_1_OPERATIONAL_DECISION.md`](PHASE_7_1_OPERATIONAL_DECISION.md) — Operational cost model and capacity constraints.
- [`reports/PHASE_7_2_PRODUCTION_STRATEGY_CONTRACT.md`](PHASE_7_2_PRODUCTION_STRATEGY_CONTRACT.md) — Production strategy specification and boundary definitions.
- [`notebooks/06_silent_gateway_audit.ipynb`](../notebooks/06_silent_gateway_audit.ipynb) — Executable Jupyter notebook reproducing all audit tables and figures.
