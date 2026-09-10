# Engineering Decisions & Rationale

**Project:** NEXORA 2026 — LPDG Innovation Hub Selection Challenge  
**Candidate Area:** B — Software Development  
**Author:** Engineering Team  

---

## Executive Summary

The LPDG utility network operates approximately 320 active LoRaWAN gateways across Germany, with physical field maintenance strictly constrained to **15 site visits per week**. When gateways degrade silently, downstream meter reads fail, leading to delayed billing and estimated €380 false alarm / €600 unaddressed defect proxy penalties.

This document outlines the **five pivotal engineering decisions** made in developing NEXORA 2026, documenting the alternatives considered, empirical trade-offs, and final justifications.

---

## Decision 1: Production Strategy Selection — Baseline_3Sigma vs. Multi-Feature Composite Models

### What We Chose
We selected and locked **`Baseline_3Sigma`** as the production ranking strategy. For each gateway, it establishes a trailing 28-day baseline across three core distress signals (`offline_duration_sec`, `disconnection_cnt`, `reboot_cnt`). During the trailing 7 days, any hour exceeding $\mu + 3\sigma$ (sample std, $ddof=1$) is flagged as a breach. Gateways are ranked strictly by total unweighted breach accumulation across the 7-day window.

### What Else We Considered
1. **Multi-Feature Gradient Boosted Classifier / Random Forest:** Training non-linear models on historical field visit outcomes (`field_visits.csv`) using RF packet counts, SNR, RSSI, temperature, and duty cycles.
2. **Composite Heuristic Candidates (Candidates A through F):** Blended scoring formulas combining packet degradation, radio SNR variance, and silence duration bonuses.

### Why We Did Not Choose the Alternatives
Across 26 weeks of leakage-safe historical backtesting (`reports/PHASE_6_3_STRATEGY_DECISION.md`), composite candidates captured only marginal additional true defect repairs (+2.4%) at the cost of a catastrophic surge in false alarms (+57% false alarms). Under the challenge economic proxy structure:
- Every false dispatch costs €380 in wasted technician labor and displaces a degraded gateway.
- Every unaddressed faulty gateway costs €600/week.
Composite candidates resulted in substantially higher net standardized economic loss (€61,280 vs. €57,600 for Baseline_3Sigma). Machine learning models suffered from severe class imbalance (only 642 total historical work orders over 8 months) and survivorship bias. `Baseline_3Sigma` delivered superior precision, zero overfitting, and transparent explainability.

---

## Decision 2: Silent-Gateway Policy — Option B (Universe Retention) vs. Option A (Disqualification) vs. Candidate F (+10 Bonus)

### What We Chose
We implemented **Option B (Silent-Gateway Universe Retention)**. Any gateway commissioned and active in the master asset registry that produces zero telemetry in the trailing 7 days is retained in the candidate pool with $score = 0.0$, $flagged\_hours = 0$, and $worst\_metric = \text{"no\_telemetry"}$. Silent gateways participate in deterministic secondary tie-breaking by `gateway_id` ascending alongside other zero-breach assets.

### What Else We Considered
1. **Option A (Strict Disqualification):** Drop gateways with zero telemetry entirely from the candidate pool.
2. **Candidate F (Silence Priority Bonus):** Add an arbitrary +10.0 score bonus to any gateway silent for $>48$ hours to force it into the Top 15.

### Why We Did Not Choose the Alternatives
- **Option A** is operationally hazardous: a catastrophic hardware failure (cut power cable, lightning strike) cuts telemetry completely; dropping silent assets blinds operations to total outages.
- **Candidate F** caused severe false alarms during historical evaluation (30 false dispatches). Newly installed gateways awaiting commissioning or assets in cellular dead zones were repeatedly flagged despite having no equipment defects.
- **Option B** strikes the correct balance: unobserved assets remain eligible if the active fleet is small, but telemetry-backed anomalies take precedence without distorting the empirical breach scale.

---

## Decision 3: Lifecycle Universe Gating — Dynamic Master Metadata Evaluation vs. Telemetry Self-Discovery

### What We Chose
We implemented explicit, date-aware lifecycle fleet gating using `gateway_master.csv`:
$$\text{Eligible}(i, T) \iff \Big(\text{installed\_on}_i \le T\Big) \;\land\; \Big(\text{decommissioned\_on}_i > T \;\;\lor\;\;\text{decommissioned\_on}_i \text{ is null}\Big)$$

### What Else We Considered
Inferring the active candidate universe strictly from the gateways present in recent telemetry parquet partitions (the approach used in `baseline_3sigma.py`).

### Why We Did Not Choose the Alternative
Relying on telemetry presence causes two fatal production failure modes:
1. **Ghost Hardware Dispatches:** Gateways decommissioned prior to decision Monday $T$ may still have historical records in the 28-day baseline window. Without lifecycle gating, retired hardware could be dispatched for inspection.
2. **Temporal Leakage:** Future assets installed post-$T$ (e.g., May–July 2026) appear in partitioned files if read naively. Pre-filtering strictly against master asset commissioning timestamps enforces temporal anti-leakage boundaries.

---

## Decision 4: Specialization Track Selection — Area B (Software Development) vs. Other Tracks

### What We Chose
We chose **Area B — Software Development**. We wrapped the verified predictive engine in a production-grade software package featuring:
- A fully decoupled single-week prediction engine (`predict_week`) and CLI orchestrator.
- A high-performance FastAPI REST service (`GET /health`, `GET /predictions/{week_start}`, `GET /gateways/{gateway_id}`, `POST /run`).
- Comprehensive regression protection (123 automated tests across 11 modules).
- Explicit error handling rejecting corrupt schemas, bad dates, duplicate records, and out-of-bounds inputs.
- Clean one-command execution via standard packaging (`pyproject.toml`).

### What Else We Considered
- **Area E (Machine Learning):** Training custom gradient boosting or neural anomaly models.
- **Area D (Data Science):** Focusing primarily on economic cost curves and distribution analysis.

### Why We Did Not Choose the Alternatives
In physical utility operations, an unconstrained or brittle ML model deployed without defensive engineering produces silent schema failures, unmaintainable glue code, and unpredictable dispatches. When dispatch slots are capped at 15 visits/week, the highest engineering value comes from **reliability, determinism, testability, and integration readiness**. Software Development demonstrates that an engineering team can build a maintainable, modular service that another developer can immediately inspect, test, deploy, and modify under live conditions.

---

## Decision 5: Statistical Anomaly Formulation — Individual 28-Day Baseline with Zero-Variance Protection vs. Global / Rolling Z-Scores

### What We Chose
We compute mean and standard deviation per gateway over its own trailing 28-day window $[T-28\text{d}, T)$ using sample standard deviation ($ddof=1$). If a metric is completely invariant ($\sigma = 0$), $\sigma$ is replaced with `NaN`, ensuring constant historical baselines produce zero breaches ($x > \text{NaN} \to \text{False}$). Discrete hourly breaches ($x > \mu + 3\sigma$) are accumulated across trailing 7 days $[T-7\text{d}, T)$.

### What Else We Considered
1. **Global Fleet Standardization:** Pooling all 320 gateways to compute a single fleet-wide mean and standard deviation for each metric.
2. **Rolling Z-Score Accumulator:** Computing dynamic rolling 7-day normalized Z-scores.

### Why We Did Not Choose the Alternatives
- **Global standardization** fails because LoRaWAN gateway environments are radically heterogeneous. A rooftop gateway handling 900 meters naturally experiences high disconnection counts that would be alarming on a quiet basement gateway handling 40 meters. Comparing a gateway to the fleet produces widespread false alarms.
- **Rolling Z-scores** smooth away sustained degradation: if a gateway degrades continuously for 5 days, its rolling baseline elevates, masking the anomaly.
- The **trailing 28-day individual baseline** evaluates each asset against its own historical normal, and the zero-variance safeguard guarantees zero numerical overflow or false-positive breaches.

---

## Summary of Decisions

| Decision | Selected Choice | Rejected Alternatives | Primary Justification |
| :--- | :--- | :--- | :--- |
| **1. Strategy** | `Baseline_3Sigma` | Multi-feature ML, Composite Candidates A–F | +57% false alarm surge in composite models; €3,680 higher economic penalty. |
| **2. Silent Fleet** | Option B (Retain with score=0) | Option A (Drop), Candidate F (+10 bonus) | Avoids ignoring total outages while preventing 30 false alarms from arbitrary bonuses. |
| **3. Fleet Gating** | Master Lifecycle Date Filtering | Telemetry self-discovery | Prevents dispatching retired hardware and eliminates lookahead leakage. |
| **4. Track** | Area B (Software Development) | Area E (Machine Learning), Area D (Data Science) | Maximizes operational reliability, testability, API integration, and code maintainability. |
| **5. Statistics** | Trailing 28d individual baseline, $ddof=1$, zero-variance NaN | Global fleet pooling, rolling Z-score | Accounts for asset heterogeneity; prevents division-by-zero artifacts. |
