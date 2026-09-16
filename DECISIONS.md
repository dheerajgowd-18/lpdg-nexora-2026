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
We chose **Area B — Software Development**. We wrapped the verified predictive engine in a production-oriented, challenge-ready software package featuring:
- A fully decoupled single-week prediction engine (`predict_week`) and CLI orchestrator.
- A high-performance FastAPI REST service directly implementing the Challenge Brief specifications:
  - `GET /predictions`: ask it for this week's 15 gateways to visit (defaults to current/latest competition week).
  - `GET /predictions/{week_start}`: ask it for any specific competition Monday's 15 gateways.
  - `GET /gateways/{gateway_id}/explanation`: ask it why a particular gateway is where it is (rank, score, breach count, and observational reason).
  - `GET /gateways/{gateway_id}`: retrieve master asset metadata and dynamic lifecycle eligibility.
  - `POST /run`: tell it to run again (reloads mounted data partitions and recomputes recommendations).
  - `GET /health`: liveness probe.
- Comprehensive regression protection (186 automated tests across 14 modules, including dedicated bug regression suite `tests/test_bug_regression.py` and data contract suite `tests/test_data_contracts.py`).
- Explicit error handling rejecting corrupt schemas, bad dates, duplicate records, and out-of-bounds inputs.
- Clean one-command execution via standard packaging (`pyproject.toml`), `Makefile` (`make run`), and `docker-compose.yml` (`docker compose up`).

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

---

## Data Validation & Ingestion Contracts

All data ingestion boundaries enforce deterministic contract handling:

```
    Invalid Input / Malformed Record
                  ↓
       Data Contract Validation
                  ↓
       Explicit Deliberate Failure (ValueError)
```

and for records with repeated keys:

```
    Identical Duplicate (same key, identical measurements)
                  ↓
       Deterministic Deduplication (collapse safely)
```
versus:
```
    Conflicting Duplicate (same logical key, differing values)
                  ↓
       Explicit Failure (ValueError: corruption / collision)
```

- **Gateway IDs:** Canonicalized to 12-character bare uppercase hex (`[0-9A-F]{12}`). Null, empty, or non-hex characters trigger immediate `ValueError`.
- **Telemetry Parquet:** Identical duplicates (e.g. partition overlaps) are collapsed cleanly; conflicting measurements for the same `(gateway_id, ts_utc)` fail fast.
- **Meter Reads:** `meters_expected` and `meters_read` must be strictly non-negative integers (`meters_read <= meters_expected`). Non-numeric strings, nulls, decimals, and negative counts fail fast. Weekly reporting contract enforces Monday `week_start`.
- **Master Lifecycle:** UTC datetime parsing enforces `installed_on <= decommissioned_on`. Duplicate master registrations fail fast.
- **Temporal Anti-Leakage:** Strictly right-open temporal boundaries ($t < T$ and $week\_start < T$) isolate future data.

---

## Bug Regression Mapping (Challenge Requirement)

Challenge Brief Part 2 (Area B) mandates: *"Include one test you wrote because you found a bug."*  
The repository maintains four dedicated bug regression tests in `tests/test_bug_regression.py`:

1. **BUG 1: Silent Masking of Upstream Duplicate Scored Records**
   - *Bug:* An earlier prototype silently dropped duplicate scored records via `.drop_duplicates(subset=['gateway_id'], keep='first')`.
   - *Impact:* Silently masked upstream partition corruption and produced non-deterministic rankings.
   - *Fix:* Replaced with fail-fast validation in `rank_and_select()` raising `ValueError`.
   - *Regression Test:* `test_bug_regression_duplicate_scored_records_raises_valueerror()`.

2. **BUG 2: FastAPI App Lifespan AttributeError on Data Directory State**
   - *Bug:* Lifespan reload accessed `app.state.data_dir` before startup initialization.
   - *Impact:* `AttributeError` crashed the server during test runner invocation.
   - *Fix:* Explicitly initialized `app.state.data_dir` during `create_app()` factory invocation.
   - *Regression Test:* `test_bug_regression_api_state_data_dir_initialization()`.

3. **BUG 3: Observational Reason Length Invariant ($\le 300$ chars)**
   - *Bug:* Extreme breach counts or multi-metric anomalies risked overflowing the 300-character grader limit.
   - *Impact:* Submission disqualification by `validate_submission.py`.
   - *Fix:* Enforced bounded observational reason generation format.
   - *Regression Test:* `test_bug_regression_reason_string_length_within_limit()`.

4. **BUG 4: SyntheticFakeStrategy Non-Unique Gateway IDs via Slicing Truncation**
   - *Bug:* Test mock strategy generated gateway IDs using `f"0080E1FFFFFF{i:02X}"[:12]`. Because the prefix `'0080E1FFFFFF'` was already 12 characters, slicing `[:12]` truncated the variable index `{i:02X}`, yielding the identical ID `'0080E1FFFFFF'` for all 15 rows.
   - *Impact:* Synthetic predictions contained duplicate gateway IDs, causing downstream validation failures in the API.
   - *Fix:* Corrected generator format to `f"0080E1{i:06X}"` with explicit uniqueness validation.
   - *Regression Test:* `test_bug_regression_synthetic_strategy_generates_strictly_unique_ids()`.

---

## Challenge Brief Deliverable Cross-References
- **Part 1 — Requirement 1 (One-Command Execution):** `make run`, `docker compose up`, or `python -m nexora.pipeline --data data --out predictions.csv`.
- **Part 1 — Requirement 2 (predictions.csv):** Generated and verified via `validate_submission.py predictions.csv`.
- **Part 1 — Requirement 3 (DECISIONS.md):** This document.
- **Part 1 — Requirement 4 (What It Cannot Do):** Documented extensively in `README.md` Section 12 ("What It Cannot Do & Operational Limitations" and "What Another Two Weeks Would Fix").
- **Part 1 — Requirement 5 (AI-USAGE.md):** Full disclosure in `AI-USAGE.md`.
- **Part 2 — Area B (Software Development):** Production FastAPI service in `src/nexora/api.py`, 186 automated tests in `tests/`, clean decoupled architecture, and interactive demo frontend in `frontend/`.

