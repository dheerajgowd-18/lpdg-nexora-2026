# Phase 7.1 — Operational Cost & Decision Model

**LPDG Innovation Hub Selection Challenge 2026 (NEXORA 2026)**  
**Document Type:** Technical Specification & Operational Decision Contract  
**Audience:** Technical Reviewers, Evaluators, and Engineering Leadership  
**Status:** Complete & Validated  
**Parent Contract:** `reports/PHASE_6_3_STRATEGY_DECISION.md` (Strategy Selection)  
**Reference Technical Reports:**
- [`reports/PHASE_4_1_OPERATIONAL_DEFINITION.md`](PHASE_4_1_OPERATIONAL_DEFINITION.md)
- [`reports/PHASE_6_1_BACKTEST_TARGET.md`](PHASE_6_1_BACKTEST_TARGET.md)
- [`reports/PHASE_6_2_BACKTEST_ENGINE.md`](PHASE_6_2_BACKTEST_ENGINE.md)
- [`reports/PHASE_6_3_STRATEGY_DECISION.md`](PHASE_6_3_STRATEGY_DECISION.md)
- [`reports/backtest/strategy_comparison.csv`](backtest/strategy_comparison.csv)

---

## 1. Objective

Phase 6 concluded with an evidence-based decision: across 26 consecutive historical decision weeks, **`Baseline_3Sigma` was selected as the ranking strategy for the final Part 1 pipeline**.

The purpose of Phase 7.1 is to establish the **Operational Cost & Decision Model** that bridges that strategy selection into the production submission pipeline.

The central systems question Phase 7.1 answers is:
> **"If our system can recommend only 15 gateways per week, how should those recommendations be interpreted, prioritized, and evaluated under operational constraints?"**

In an operational deployment under the challenge rules:
- Physical field inspection capacity is strictly limited to a maximum of **15 site visits per week**.
- Therefore, ranking quality matters directly: every recommendation consumes one limited visit slot.
- A false visit consumes limited visit capacity and incurs a **€380 standardized proxy cost**.
- A missed broken gateway leaves an active fault unaddressed and incurs a **€600/week standardized proxy cost**.
- The ranking system is fundamentally a **constrained operational prioritization system**, not an unconstrained, guaranteed physical failure detector.

---

## 2. Operational Economics

The Challenge Brief establishes an explicit, asymmetric economic cost model for evaluating field dispatch decisions:

| Event | Operational Classification | Standardized Challenge Cost | Nature of Cost |
| :--- | :--- | :---: | :--- |
| **False Visit** | Type I Error / False Alarm / False Positive | **€380** | Standardized cost proxy per unnecessary inspection visit |
| **Missed Broken Gateway** | Type II Error / Missed Outage / False Negative | **€600 per week** | Standardized weekly proxy for an unaddressed faulty gateway |

### 2.1 The Meaning of the False-Visit Penalty (€380)
When a gateway is selected in the weekly Top 15, a physical inspection work order is created. If the technician inspects the gateway and finds normal operation (`Kein Fehler gefunden`):
- The €380 standardized false-visit cost proxy is incurred.
- That visit consumed one of the 15 available slots for the week, displacing other potentially faulty gateways.

### 2.2 The Meaning of the Missed-Gateway Penalty (€600 per week)
When a gateway has an operational fault that subsequently required physical repair (`Fehler behoben`), but was not included in the weekly Top 15:
- The challenge specifies a €600/week standardized proxy for a missed broken gateway.
- This figure represents a continuing weekly proxy associated with unaddressed equipment faults during the evaluation.

### 2.3 Decision-Analysis Proxies vs. Actual Business Costs
In the Phase 6 historical backtest, the combined economic metric was formulated as:
$$\text{Combined Cost Proxy} = (\text{False Alarms} \times €380) + (\text{Missed Repairs} \times €600)$$

> [!IMPORTANT]
> The €380 false-alarm cost and €600 missed-repair cost are **standardized decision-analysis proxies** established by the challenge to compare strategy trade-offs on equal footing. They do not represent measured historical company ledger expenses, contractually binding penalty figures, or proven ongoing physical damage. In the historical data, the exact duration of each unaddressed failure was unobserved; therefore, the €600 figure represents a standardized one-week lower-bound evaluation proxy.

---

## 3. Why the Top 15 Constraint Matters

The challenge requires submitting **exactly 15 gateway recommendations** for each scored Monday. This hard capacity constraint transforms the problem from an open-ended classification model into a constrained resource-allocation problem:

1. **Every Selection Displaces Another:**  
   Because capacity is fixed at 15, selecting one gateway automatically displaces another candidate from inspection.
2. **A Ranking Is Not Merely a "Bad List":**  
   In a fleet of active gateways, multiple units may exhibit statistical variations or communication dropouts. Ranking determines which 15 assets exhibit the strongest evidence of severe telemetry deviation.
3. **List Position Matters (Top-5 vs. Top-10 vs. Top-15):**  
   In field operations where inspection capacity may be constrained or staged, early-rank concentration ensures that the most prominent signals appear at the top of the queue.

### Verified Phase 6 Top-$K$ Evidence:
The 26-week historical backtest demonstrated that cumulative repair capture varied across rank cutoffs:

- Baseline_3Sigma: Top-5 = 19, Top-10 = 28, Top-15 = 41
- Candidate_C_SevereOffline: Top-5 = 14, Top-10 = 27, Top-15 = 42

| Rank Cutoff | `Baseline_3Sigma` Repairs Captured | `Candidate_C_SevereOffline` Repairs Captured | Operational Difference |
| :---: | :---: | :---: | :--- |
| **Top-5** | **19** | 14 | Baseline captured +5 more repairs in the first 5 slots |
| **Top-10** | **28** | 27 | Baseline captured +1 more repair in the first 10 slots |
| **Top-15** | 41 | **42** | Candidate C captured +1 more repair across all 15 slots |

The baseline demonstrated stronger repair concentration in the early portion of the visit list (Top-5 and Top-10). Candidate C only overtook the baseline at the tail of the Top-15 list ($K=13, 14, 15$), where false alarms were also elevated.

---

## 4. Baseline vs. Candidate C — Operational Trade-off

Candidate C was evaluated in Phase 6 as a leading alternative to the baseline. The full operational balance sheet across all 26 historical weeks established:

| Metric | `Baseline_3Sigma` | `Candidate_C_SevereOffline` | Net Delta ($\text{Cand C} - \text{Baseline}$) |
| :--- | :---: | :---: | :---: |
| **Repairs Captured** | 41 / 116 | 42 / 116 | **+1 repair** (+0.86% capture) |
| **False Alarms** | **14** | 22 | **+8 false alarms** (+57.1% increase) |
| **False Alarm Rate** | **3.59%** | 5.64% | +2.05% absolute increase |
| **Missed Repairs** | 75 | **74** | **-1 missed repair** |
| **False Alarm Cost Proxy (€380)** | **€5,320** | €8,360 | +€3,040 added wasted cost |
| **Missed Repair Proxy (€600)** | €45,000 | **€44,400** | -€600 saved proxy cost |
| **Combined Standardized Proxy (€)** | **€50,320** | €52,760 | **+€2,440 worse** (net penalty) |

### The Operational Trade-Off:
- **An 8:1 Penalty Ratio:** To gain 1 additional confirmed repair over 26 weeks of historical evaluation, Candidate C incurred **8 additional false alarms**.
- **Net Economic Loss:** Under the challenge's standardized cost assumptions, spending €3,040 in additional false visits to capture €600 in repair proxy resulted in a net penalty of **+€2,440**.
- **Statistical Significance:**
  - The paired test did not detect a statistically significant difference in weekly repair capture in this historical sample. (Paired $t = 0.161, p = 0.8732$).
  - The paired test detected a statistically significant difference in weekly false-alarm counts at the 0.05 level in this historical sample. (Paired $t = 2.133, p = 0.0430$).

This trade-off did not justify replacing the simpler baseline. Candidate C is not universally inferior, but under the standardized constraints and historical evidence of this challenge, it was not operationally advantageous.

---

## 5. What the Selected Strategy Means

The final Part 1 pipeline is intended to implement Baseline_3Sigma, subject to the production edge-case decisions in Phase 7. It uses the methodology established in `baseline_3sigma.py` and Phase 6.2:

For each scored decision Monday $T$:
1. **Identify the Active Universe:** Filter `gateway_master.csv` for gateways installed on or before $T$ and not decommissioned ($\texttt{installed\_on} \le T \land (\texttt{decommissioned\_on} > T \lor \text{null})$).
2. **Establish Preceding 28-Day Baselines:** Using telemetry strictly before $T$ ($t \in [T-28\text{d}, T)$), compute the mean ($\mu_i$) and standard deviation ($\sigma_i$) per gateway for:
   - `offline_duration_sec`
   - `disconnection_cnt`
   - `reboot_cnt`
3. **Evaluate the Recent 7-Day Window:** For each hourly observation in $[T-7\text{d}, T)$, compare the observed value against the gateway's baseline.
4. **Flag 3-Sigma Anomaly Hours:** Flag an hour if any of the three metrics exceeds its baseline by more than three standard deviations:
   $$\text{Flagged Hour} \iff \exists m \in \{\text{offline, disconn, reboot}\} : x_{i,t}^{(m)} > \mu_i^{(m)} + 3 \cdot \sigma_i^{(m)}$$
5. **Aggregate Flagged Hours:** Count total flagged hours per gateway over the 7-day window.
6. **Deterministic Ranking:** Order active gateways by `flagged_hours` descending, with deterministic tie-breaking by canonical bare `gateway_id` ascending.
7. **Select Top 15:** Take the top 15 gateways for the weekly submission.

---

## 6. What a Score Means

In this pipeline, a gateway's ranking score represents:
> **The number of hours in the preceding 7 days during which the gateway exhibited extreme statistical deviations ($> 3\sigma$) from its own historical baseline across offline duration, disconnections, or reboots.**

It is vital to state clearly what this score is **NOT**:
- It is **NOT** a calibrated probability of physical failure.
- It is **NOT** a probability of repair.
- It is **NOT** a percentage chance of failure.
- It is **NOT** a predicted monetary loss in Euros.

The score is an **ordinal prioritization signal**. Its sole function is to place gateways in a defensible queue so that the 15 assets with the strongest evidence of severe telemetry deviation are inspected first.

---

## 7. Ranking vs. Decision

Our system enforces a strict architectural boundary between the **ranking layer** and the **decision layer**:

```
┌────────────────────────────────────────────────────────┐
│  RANKING LAYER (Algorithmic)                           │
│  "Which active gateways exhibit the strongest evidence │
│   of abnormal operational degradation?"                │
│  Output: Ordered permutation of eligible gateways      │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│  DECISION LAYER (Operational)                          │
│  "Which gateways shall receive physical work orders    │
│   given a hard budget constraint of 15 visits?"        │
│  Output: Exactly 15 selected gateway IDs for Monday T  │
└────────────────────────────────────────────────────────┘
```

The ranking layer answers: *"Which gateways should be prioritized?"*  
The operational layer answers: *"Which 15 gateways should actually be selected?"*  

Because the challenge specifies a fixed capacity of 15 visits per week, the operational decision rule is straightforward: **select the top 15 eligible assets from the deterministic ranking**.

---

## 8. False Visits and Missed Gateways: Two Operational Failure Modes

Understanding the operational consequences of the two decision error modes guides pipeline verification:

### 8.1 False Visit (Type I Error)
- **Occurrence:** A gateway is selected in the weekly Top 15, but subsequent inspection indicates no fault found (`Kein Fehler gefunden`).
- **Operational Consequence:**
  - Consumes one of the limited 15 weekly inspection slots.
  - Incurs the €380 standardized false-visit cost proxy.
- **Backtest Evidence:** Baseline 3-Sigma achieved a 3.59% false alarm rate (14 false alarms across 390 recommendations in backtesting), outperforming all candidate composites.

### 8.2 Missed Broken Gateway (Type II Error)
- **Occurrence:** A gateway with a repair outcome (`Fehler behoben`) is not selected in the weekly Top 15 (rank $> 15$).
- **Operational Consequence:**
  - Remains unaddressed in the decision analysis for that week.
  - Incurs the standardized €600/week missed-gateway proxy.
- **Backtest Evidence:** Baseline 3-Sigma captured 41 out of 116 available historical repairs (35.34%), essentially matching the 42 repairs captured by Candidate C while avoiding excess false alarms.

---

## 9. Capacity Interpretation & Submission Contract

The challenge mandates strict adherence to submission formatting in `predictions.csv`:

1. **Exact Cardinality:** The pipeline must produce **exactly 15 recommendations per scored Monday**. Submitting 14 or 16 rows for any week constitutes a structural validation failure.
2. **8 Scored Mondays:** Exactly $8 \times 15 = 120$ total rows:
   - `2026-02-02`, `2026-02-09`, `2026-02-16`, `2026-02-23`
   - `2026-03-02`, `2026-03-09`, `2026-03-16`, `2026-03-23`
3. **Unique Recommendations:** Within any scored Monday, the 15 `gateway_id` entries must be strictly unique (no duplicates).
4. **Rank Monotonicity:** Ranks must be integers strictly numbered $1, 2, \dots, 15$.
5. **Universe Eligibility:** Every selected gateway must be verified active on that Monday (installed on or before $T$, not decommissioned).
6. **Canonical ID Format:** Gateway IDs must be formatted in valid canonical bare hex.

---

## 10. Operational Decision Principles

The production pipeline developed in Phase 8 must preserve ten core engineering principles:

1. **Fixed Weekly Capacity:** Always generate exactly 15 recommendations per scored Monday.
2. **Eligibility Before Ranking:** Screen gateways via `gateway_master.csv` lifecycle dates before computing scores. Never rank an inactive or decommissioned asset.
3. **Strict Temporal Boundary:** Evaluate telemetry strictly where $t < T$ (right-open horizon). Never allow future information to influence historical decisions.
4. **No Fabricated Telemetry Semantics:** Respect true field semantics (`reboot_cnt` as incremental events, `offline_duration_sec` as firmware clocks).
5. **Explainable Ranking Reason:** Prioritize gateways based on verified physical anomaly signals that explain why an asset was selected.
6. **Deterministic Execution:** Guarantee deterministic outputs for the same inputs and execution logic. (Enforced via explicit secondary sorting by `gateway_id` ascending).
7. **Consistent Identifier Normalization:** Apply `normalize_gateway_id()` universally across all internal tables.
8. **Same Decision Logic Every Week:** Apply the exact same scoring and ranking logic across all eight scored weeks without manual intervention.
9. **No Silent Strategy Changes:** Do not alter the selected strategy or introduce arbitrary weights after backtesting has concluded.
10. **Preserve Reproducibility:** Verify final outputs against `validate_submission.py` to ensure reproducible pipeline execution.

---

## 11. Known Operational Caveat — Completely Silent Gateways

A critical operational finding from Phase 5 and 6 concerns **completely silent gateways** (gateways that produce zero telemetry packets during the recent 7-day window):

### The Issue
In `baseline_3sigma.py`, the algorithm performs an inner join/filter on recent telemetry observations:
```python
recent = window[window["ts"] >= end - dt.timedelta(days=RECENT_DAYS)].copy()
```
If a gateway was completely silent for the entire 7-day window, it has zero rows in `recent`. As a result, it generates zero flagged hours and is naturally omitted from `recent.groupby("gateway_id")`.

### The Phase 6 Backtesting Precedent
In Phase 6.2 and 6.3, our backtesting wrapper (`Baseline3SigmaStrategy.rank` in `src/nexora/backtesting/strategies.py`) resolved this for fair universe alignment by explicitly reindexing against the active gateway universe:
- Silent active gateways were retained with `flagged_hours = 0` and `worst_metric = "no_telemetry"`.
- This placed silent gateways at the bottom of the anomaly list, ordered by `gateway_id`.

### The Phase 7 Production Contract
We do **NOT** pretend this issue has already been permanently resolved, nor do we automatically inject an arbitrary heuristic override (such as Candidate F's $+10.0$ silence bonus, which backtesting proved increased false alarms).

**Phase 7.3 will explicitly audit and decide how the production pipeline should handle completely silent gateways** in the scored period, ensuring full alignment with challenge expectations and baseline reproducibility.

---

## 12. What Phase 7.1 Decides

Phase 7.1 establishes the following authoritative decisions:

1. **Weekly Capacity:** Fixed at exactly 15 gateways per scored Monday.
2. **Selected Ranking Policy:** Retain `Baseline_3Sigma` as the selected strategy for the final Part 1 pipeline, subject to production edge-case decisions in Phase 7.
3. **Economic Decision Basis:** Standardized evaluation proxies (€380 false visit, €600/week missed broken gateway).
4. **Interpretation of Scores:** Ordinal prioritization signals reflecting extreme multi-signal deviation hours, not calibrated failure probabilities.
5. **Eligibility Sequencing:** Asset lifecycle gating strictly precedes ranking.
6. **Submission Format:** Exactly 120 total rows ($8 \times 15$) conforming to `predictions.csv` specifications.
7. **Silent-Gateway Handling:** Documented as an explicit operational caveat to be audited and finalized in Phase 7.3.

---

## 13. Transition to Phase 7.2

With the operational principles and economic framework formalized:

- **Phase 7.1 defined:** The operational interpretation, capacity constraints, economic proxies, and decision principles.
- **Phase 7.2 will define:** The exact **Production Strategy Contract**, specifying the end-to-end algorithmic pipeline architecture that Phase 8 will implement in code.

```
Phase 7.1: Operational Decision Model (This Document)
       ↓
Phase 7.2: Production Strategy Contract (Architectural Specification)
       ↓
Phase 7.3: Edge-Case Audit (Silent-Gateway Investigation)
       ↓
Phase 8: End-to-End Pipeline Implementation & Submission Generation
```

---

## Related Technical Reports

- [`reports/PHASE_4_1_OPERATIONAL_DEFINITION.md`](PHASE_4_1_OPERATIONAL_DEFINITION.md) — Foundational concept of "needs a visit" and economic asymmetry.
- [`reports/PHASE_6_1_BACKTEST_TARGET.md`](PHASE_6_1_BACKTEST_TARGET.md) — Operational target attribution and dispatch lag realization.
- [`reports/PHASE_6_2_BACKTEST_ENGINE.md`](PHASE_6_2_BACKTEST_ENGINE.md) — Backtesting simulation engine and anti-leakage controls.
- [`reports/PHASE_6_3_STRATEGY_DECISION.md`](PHASE_6_3_STRATEGY_DECISION.md) — Comprehensive comparative analysis and baseline retention justification.
- [`reports/backtest/strategy_comparison.csv`](backtest/strategy_comparison.csv) — Quantitative performance metrics across all seven candidate strategies.
