# Phase 7.2 — Production Strategy Contract: Baseline 3-Sigma Pipeline Specification

**Author:** NEXORA Operational Engineering Team  
**Date:** 2026-09-08  
**Status:** Authoritative Technical Specification (Frozen for Phase 8)  
**Selected Strategy:** `Baseline_3Sigma` (3-Sigma Anomaly Baseline)  
**Target Artifact:** `predictions.csv` (Part 1 Submission)  

---

## 1. Purpose and Scope

This document establishes the **authoritative production strategy contract** for Part 1 of the LPDG Innovation Hub Selection Challenge 2026 (NEXORA 2026). It translates the empirical findings and strategy selection from Phase 6 into an explicit, implementable engineering specification.

### 1.1 Scope
The contract defines the end-to-end operational pipeline that produces `predictions.csv` for the eight challenge-scored Mondays:
- **Coverage:** Exactly eight scored Mondays from `2026-02-02` through `2026-03-23`.
- **Weekly Output:** Exactly 15 prioritized gateway recommendations per scored Monday.
- **Total Output:** Exactly $8 \times 15 = 120$ rows conforming to the submission schema.

### 1.2 Specification vs. Implementation
This document is a **contract and specification**, not an implementation phase:
- **Phase 7.2 (This Document):** Freezes the algorithmic definition, temporal boundaries, mathematical rules, eligibility gates, tie-breaking procedures, and schema contracts.
- **Phase 7.3:** Audits production edge cases (specifically, the handling of completely silent active gateways during the scored period).
- **Phase 8:** Implements the finalized production code, runs the pipeline, and generates the final submission artifact.

---

## 2. Selected Strategy

The selected Part 1 ranking strategy is:

$$\mathbf{Baseline\_3Sigma}$$

This strategy was selected and retained after rigorous evaluation over 26 historical decision Mondays (`2025-08-04` through `2026-01-26`), capturing 116 confirmed historical repairs across 390 dispatch recommendations:

| Metric | `Baseline_3Sigma` | `Candidate_C_SevereOffline` | Net Delta ($\text{Cand C} - \text{Baseline}$) |
| :--- | :---: | :---: | :---: |
| **Repairs Captured** | **41 / 116** | 42 / 116 | **+1 repair** (+0.86% capture) |
| **False Alarms** | **14** | 22 | **+8 false alarms** (+57.1% increase) |
| **False Alarm Rate** | **3.59%** | 5.64% | +2.05% absolute increase |
| **Missed Repairs** | 75 | **74** | **-1 missed repair** |
| **False Alarm Cost Proxy (€380)** | **€5,320** | €8,360 | +€3,040 added wasted cost |
| **Missed Repair Proxy (€600)** | €45,000 | **€44,400** | -€600 saved proxy cost |
| **Combined Standardized Proxy (€)** | **€50,320** | €52,760 | **+€2,440 worse** (net penalty) |

Phase 6.3 established that Candidate C gained 1 additional repair at the cost of 8 additional false alarms—an 8:1 penalty trade-off that resulted in a €2,440 higher standardized economic penalty. Furthermore, paired statistical testing confirmed:
- No statistically significant difference in weekly repair capture ($t = 0.161, p = 0.8732$).
- A statistically significant increase in weekly false alarms for Candidate C ($t = 2.133, p = 0.0430$).

Phase 7.2 does **NOT** reopen strategy selection. The production contract is strictly constructed around the verified `Baseline_3Sigma` architecture. No composite feature scoring (F02/F09/F16), machine learning models, or arbitrary heuristics from rejected candidates are permitted.

### 2.1 Reference Baseline vs. Production Contract Layer
It is critical to distinguish the reference baseline code from the surrounding production pipeline:

- **Reference ranking logic:**  
  `baseline_3sigma.py` defines the selected 3-sigma scoring formulation (computing 28-day historical means and standard deviations, flagging 3-sigma breaches in the recent 7 days, summing metric breaches, and sorting descending).
- **Production contract layer:**  
  `baseline_3sigma.py` does not itself perform lifecycle filtering on `gateway_master.csv`, deduplicate telemetry records, normalize divergent gateway ID representations, enforce retention of the entire active universe, or apply deterministic tie-breaking. These controls were introduced and validated in our surrounding pipeline and Phase 6 backtesting wrapper (`Baseline3SigmaStrategy.rank`).

**The production system preserves the baseline scoring formulation while adding validated engineering controls required for a complete and reproducible submission.**

---

## 3. Production Inputs

The production pipeline requires only the minimal set of raw datasets necessary to execute `Baseline_3Sigma` and validate its submission format.

### 3.1 Required Production Datasets

| Dataset | File / Path | Format | Role in Production Pipeline |
| :--- | :--- | :---: | :--- |
| **Gateway Master** | `data/gateway_master.csv` | CSV (Latin-1) | Determines asset lifecycle eligibility (`installed_on`, `decommissioned_on`). |
| **Telemetry** | `data/telemetry/month=YYYY-MM/` | Parquet (Snappy) | Hourly sensor observations across 28-day baseline and 7-day scoring windows. |

### 3.2 Auxiliary / Tooling Scripts
- **`validate_submission.py`**: Shipped grader-validation script. Used strictly as post-generation acceptance tooling to verify schema and contract compliance. It is **NOT** a prediction input.

### 3.3 Explicitly Excluded Datasets
The selected `Baseline_3Sigma` strategy does **NOT** use, require, or depend upon the following datasets:
- **`data/field_visits.csv`**: Historical target and dispatch ledger. Used exclusively for backtest evaluation, not for forward operational prediction.
- **`data/engineer_review_2026-02.xlsx`**: Qualitative audit spreadsheet. Forbidden from automated prediction pipelines to prevent leakage.
- **`data/meter_read_success.csv`**: Weekly meter reading aggregation. Not utilized in the 3-sigma baseline algorithm.

Excluding these datasets enforces pipeline simplicity and eliminates potential channels for accidental target leakage.

---

## 4. Prediction Schedule

The production pipeline generates predictions for exactly **eight scored Mondays** in calendar year 2026:

1. `2026-02-02` (Scored Week 1)
2. `2026-02-09` (Scored Week 2)
3. `2026-02-16` (Scored Week 3)
4. `2026-02-23` (Scored Week 4)
5. `2026-03-02` (Scored Week 5)
6. `2026-03-09` (Scored Week 6)
7. `2026-03-16` (Scored Week 7)
8. `2026-03-23` (Scored Week 8)

### 4.1 Temporal Boundary Definition
The scored decision is identified by the challenge-specified Monday date T. Telemetry timestamps are normalized to UTC for comparison, and the implementation preserves the validated cutoff convention used by the reference baseline and backtesting pipeline.
- **Strict Pre-$T$ Boundary:** All prediction information must strictly satisfy:
  $$\text{timestamp} < T$$
- **Absolute Anti-Leakage Guard:** Zero telemetry records with $\text{timestamp} \ge T$ may be loaded, parsed, or processed when generating rankings for week $T$.

### 4.2 Standard Observation Windows
For each scored Monday $T$:
- **Trailing 28-Day Baseline Window:**
  $$W_{\text{base}}(T) = [T - 28\text{ days}, T)$$
- **Trailing 7-Day Scoring Window:**
  $$W_{\text{recent}}(T) = [T - 7\text{ days}, T)$$

Note that $W_{\text{recent}}(T) \subset W_{\text{base}}(T)$. Both windows share the exact same strict pre-$T$ cutoff convention.

---

## 5. Gateway Identity Contract

A single canonical identifier format must be enforced across all stages of data loading, processing, ranking, and export.

### 5.1 Canonical Format
- **Format:** Exactly 12-character uppercase hexadecimal string.
- **Pattern:** `^[0-9A-F]{12}$`
- **Example:** `0639EA5602C1`

### 5.2 Source Discrepancies and Normalization
Raw files provide identifiers in divergent formats:
- **Master Dataset (`gateway_master.csv`):** 17-character colon-delimited uppercase hex (e.g., `06:39:EA:56:02:C1`).
- **Telemetry Parquet:** 12-character bare hex strings (e.g., `0639EA5602C1`).

### 5.3 Normalization Logic
Production code must apply the verified normalization logic:
```python
def normalize_gateway_id(gateway_id: str) -> str:
    # Canonicalizes gateway identifiers to 12-character uppercase bare hex.
    if not isinstance(gateway_id, str):
        return str(gateway_id)
    return gateway_id.strip().replace(":", "").upper()
```
**Contract Rule:** Normalization must be executed immediately upon loading `gateway_master.csv` and telemetry partitions. Mixed or colon-delimited identifiers must never enter the ranking engine or `predictions.csv`.

---

## 6. Gateway Eligibility Contract

The set of candidate gateways eligible for ranking and selection on scored Monday $T$ is governed strictly by physical asset lifecycle dates.

### 6.1 Lifecycle Eligibility Definition
A gateway $i$ is **eligible for ranking on Monday $T$** if and only if it was installed on or before $T$ and was not decommissioned on or before $T$:

$$\text{Eligible}(i, T) \iff \Big(\texttt{installed\_on}_i \le T\Big) \;\land\; \Big(\texttt{decommissioned\_on}_i > T \;\;\lor\;\; \texttt{decommissioned\_on}_i \text{ is null}\Big)$$

### 6.2 Precedence of Eligibility
- **Lifecycle Gating Before Ranking:** Eligibility must be established from `gateway_master.csv` **prior** to running baseline calculations or anomaly scoring.
- **Independence from Telemetry:** Telemetry presence must **never** define the eligible universe. An active asset that suffered a severe power outage and emitted zero telemetry rows remains fully eligible. Silently dropping active gateways due to lack of telemetry violates the fleet universe contract.
- **Verified Active Fleet Size:** In the eight scored weeks of 2026, the active eligible universe ranges between 290 and 308 gateways (e.g., 290 on 2026-02-02, 308 on 2026-03-23).

---

## 7. Telemetry Preparation Contract

Telemetry preprocessing must guarantee consistent time representations, valid identifiers, deduplicated records, and required sensor columns.

### 7.1 Timestamp Handling
- Parse `ts_utc` into timezone-aware UTC timestamps (`pd.to_datetime(ts_utc, utc=True)`).
- Filter strictly by the right-open window: $[T - 28\text{d}, T)$.

### 7.2 Gateway ID Canonicalization
- Apply `normalize_gateway_id` to the `gateway_id` column before indexing, joining, or aggregating.

### 7.3 Exact Duplicate Handling
- **Data Reality:** Micro-Phase 3.1 verified that raw telemetry contains **exactly 6,547 duplicate records** on `(gateway_id, ts_utc)` (100% full-row clones located in odd-month partitions: 2,185 in Sep 2025; 2,124 in Nov 2025; 2,238 in Jan 2026).
- **Deduplication Policy:** Production preprocessing must execute the validated deduplication rule used in Phase 5.2 and `DataLoader`:
  ```python
  telemetry = telemetry.drop_duplicates(subset=["gateway_id", "ts_utc"], keep="first")
  ```
  Deduplication must occur before calculating window statistics to prevent artificial inflation of baseline variance.

### 7.4 Required Metrics
`Baseline_3Sigma` strictly uses exactly three telemetry columns:
1. `offline_duration_sec`: Duration offline reported by firmware (seconds).
2. `disconnection_cnt`: Count of cellular/network disconnections.
3. `reboot_cnt`: Count of hardware reboot events.

**Contract Rule:** Do not substitute or append alternative telemetry signals (e.g., RSSI, CRC error counts, packet metrics). The baseline is defined exclusively over these three metrics.

---

## 8. 28-Day Baseline Calculation

For each eligible gateway $i$ and scored Monday $T$, establish individual historical reference baselines using telemetry in the right-open window $t \in [T - 28\text{d}, T)$.

### 8.1 Summary Statistics
Compute the per-gateway mean ($\mu_{i,m}$) and standard deviation ($\sigma_{i,m}$) for each metric $m \in \{\text{offline\_duration\_sec}, \text{disconnection\_cnt}, \text{reboot\_cnt}\}$:

$$\mu_{i,m} = \frac{1}{N_{i}} \sum_{t \in W_{\text{base}}} x_{i,t}^{(m)}$$

$$\sigma_{i,m} = \sqrt{\frac{1}{N_{i} - 1} \sum_{t \in W_{\text{base}}} \left(x_{i,t}^{(m)} - \mu_{i,m}\right)^2}$$

### 8.2 Standard Deviation Convention
- **Sample Standard Deviation:** The calculation uses pandas default sample standard deviation (`ddof=1`), exactly as implemented in `baseline_3sigma.py` via `.groupby("gateway_id")[METRICS].agg(["mean", "std"])`.
- **Zero Variance & Insufficient Data:** If $\sigma_{i,m} = 0$, or if $N_i < 2$ (rendering $\sigma_{i,m}$ undefined/NaN), the standard deviation is treated as NaN (`replace(0, np.nan)`). Under this condition, $(x - \mu) > 3\sigma$ evaluates to `False` (via `.fillna(False)`). Constant or unvarying telemetry never triggers a false anomaly breach.

---

## 9. Recent 7-Day Anomaly Detection

Evaluate telemetry records observed in the recent 7-day evaluation window $t \in [T - 7\text{d}, T)$.

### 9.1 Breach Condition
For each hourly observation record $t$ of gateway $i$, test each metric against the gateway's own 28-day baseline:

$$\text{Exceeded}_{i,t}^{(m)} \iff x_{i,t}^{(m)} - \mu_{i,m} > 3.0 \cdot \sigma_{i,m}$$

### 9.2 Observation-Level Flag Accumulation
In `baseline_3sigma.py`, flags are evaluated across all three metrics and accumulated within each observation:
```python
flags = pd.Series(0, index=recent.index, dtype=int)
worst = pd.Series("", index=recent.index, dtype=object)
for metric in METRICS:
    mean = recent["gateway_id"].map(stats[(metric, "mean")])
    std = recent["gateway_id"].map(stats[(metric, "std")]).replace(0, np.nan)
    exceeded = (recent[metric] - mean) > SIGMA * std
    exceeded = exceeded.fillna(False)
    flags = flags + exceeded.astype(int)
    worst = worst.where(~exceeded | (worst != ""), metric)

recent["flagged"] = flags
recent["worst_metric"] = worst
```
Because `flags` is incremented by each breaching metric independently, a single hourly observation can contribute **0, 1, 2, or 3** to the gateway's metric-breach total. The observation also records `worst_metric` (the first metric to breach the 3-sigma threshold in that record).

---

## 10. Gateway Score Definition

The operational score for gateway $i$ on scored Monday $T$ is defined authoritatively as:

> "score_i(T) is the sum of all individual 3-sigma metric breaches across telemetry observations in [T-7d, T) for the three monitored metrics. A single telemetry observation can contribute 0, 1, 2, or 3 to the score."

Mathematically:
$$\text{score}_i(T) = \sum_{t \in W_{\text{recent}}} \text{flagged}_{i,t} = \sum_{t \in W_{\text{recent}}} \sum_{m \in \text{METRICS}} \mathbf{1}\left(x_{i,t}^{(m)} > \mu_{i,m} + 3\sigma_{i,m}\right)$$

### 10.1 Technical Clarification on `flagged_hours`
In `baseline_3sigma.py`, the aggregation is performed as:
```python
grouped = recent.groupby("gateway_id").agg(
    flagged_hours=("flagged", "sum"),
    worst_metric=("worst_metric", lambda s: next((v for v in s if v), "")),
)
```
- **Historical Variable Name:** `flagged_hours` is the historical column name inherited from the reference script.
- **True Mathematical Meaning:** Technically, it is an **aggregate count of individual 3-sigma metric breaches**, not necessarily a count of unique hours. If a gateway simultaneously breaches 3-sigma on both `offline_duration_sec` and `disconnection_cnt` during the same hour, that hour increments `flagged_hours` by 2.
- **Contract Rule:** The production pipeline must preserve this exact accumulation logic without collapsing breaches into binary per-hour flags.

### 10.2 Interpretation and Scope
- **Directionality:** Higher scores indicate greater aggregate deviation across the monitored metrics and receive higher inspection priority.
- **Explicit Negative Scope:**
  - The score is **NOT** a calibrated probability of hardware breakdown.
  - The score is **NOT** a likelihood of repair.
  - The score is **NOT** a projected financial loss in Euros.
  - The score is an **ordinal metric-breach prioritization signal**.

---

## 11. Missing Telemetry Contract

The pipeline must handle varying degrees of telemetry availability across the eligible fleet:

### 11.1 Case A: Gateway With Regular Telemetry
- Gateway has active records in both the 28-day baseline and 7-day scoring windows.
- Baseline statistics ($\mu, \sigma$) and recent metric breaches are calculated normally.

### 11.2 Case B: Gateway With Zero Telemetry in Recent 7 Days (Completely Silent)
- **Original `baseline_3sigma.py` Behavior:** Because `baseline_3sigma.py` filtered on `recent = window[window["ts"] >= end - dt.timedelta(days=7)]`, a completely silent gateway had zero rows in `recent` and was naturally omitted from `recent.groupby("gateway_id")`.
- **Phase 6 Backtest Precedent:** In Phase 6.2 and 6.3 (`Baseline3SigmaStrategy.rank`), the backtester enforced **universe parity** by reindexing against the active universe. Silent active gateways were retained with `flagged_hours = 0` and `worst_metric = "no_telemetry"`, placing them at the bottom of the anomaly list ordered by `gateway_id`.
- **Production Decision Boundary:** **Phase 7.3 is explicitly assigned to audit and decide the production handling of completely silent active gateways.** Phase 7.2 does NOT introduce arbitrary heuristic bonuses (e.g., Candidate F's $+10.0$ bonus) or synthetic anomaly counts.

### 11.3 Case C: Gateway With Insufficient History for Baseline
This case is handled as a direct mathematical consequence of the baseline calculation rather than an arbitrary policy:
- The pandas sample standard deviation calculation uses `ddof=1`.
- If a gateway was newly installed and has fewer than two telemetry records in $[T - 28\text{d}, T)$, $N_i < 2$ produces $\sigma = \text{NaN}$.
- If a gateway has constant telemetry, $\sigma = 0$, which is replaced by NaN (`replace(0, np.nan)`).
- When $\sigma$ is NaN, the breach condition $(x - \mu) > 3\sigma$ evaluates to `False` (`.fillna(False)`).
- Consequently, such a gateway accumulates zero breaches and receives `score = 0.0` within the active production universe.

---

## 12. Ranking and Tie-Breaking Contract

To produce a fully reproducible ordering across the eligible fleet, ranking must follow strict deterministic criteria.

### 12.1 Ranking Keys
Eligible gateways are sorted using two ordered keys:
1. **Primary Sort Key:** `score` descending (aggregate count of 3-sigma metric breaches descending).
2. **Secondary Sort Key (Tie-Breaker):** Canonical `gateway_id` ascending (lexicographical bare hex order).

```python
ranked = ranked.sort_values(
    by=["score", "gateway_id"],
    ascending=[False, True]
).reset_index(drop=True)
```

### 12.2 Determinism Requirement
- Every pair of distinct gateways has unique canonical IDs; therefore, secondary sorting eliminates all ambiguity.
- Unstable, arbitrary, or random sorting is strictly prohibited. Identical inputs must always yield the exact same ordered ranking.

---

## 13. Top-15 Selection Contract

For each scored Monday $T$:

### 13.1 Selection Rules
1. Order all eligible active gateways using the deterministic ranking keys.
2. Select the first 15 gateways ($K=15$).
3. Assign sequential integer ranks:
   $$\text{rank} \in \{1, 2, 3, \dots, 15\}$$
4. Guarantee that all 15 `gateway_id` values within the week are strictly unique.

### 13.2 Fleet Capacity Guard
- **Validation Guard:** The pipeline must assert that the count of eligible active gateways at Monday $T$ is at least 15 ($N_{\text{active}}(T) \ge 15$).
- If $N_{\text{active}}(T) < 15$, the pipeline must raise an immediate fatal exception rather than generating a truncated or corrupted submission.
- *Empirical Verification:* The active universe in the scored weeks exceeds 290 gateways, ensuring abundant capacity.

---

## 14. Reason Generation Contract

The `reason` field provides an explainable operational justification for why each gateway was selected for a field inspection.

### 14.1 Validation Constraints (per `validate_submission.py`)
- **Type:** Non-empty string.
- **Length:** Strictly $\le 300$ characters (`len(reason) <= 300`).
- **Determinism:** The reason string must be constructed deterministically from observed data.

### 14.2 Reason Text Structure
The reason text must be consistent with the baseline evidence:
- **For gateways with $\text{score} > 0$:**
  ```python
  reason = (
      f"{int(score)} hour(s) beyond 3 sigma of this gateway's own 28-day baseline "
      f"in the last 7 days; first breach on {worst_metric}"
  )
  ```
- **For gateways with $\text{score} == 0$ (if selected to fill capacity):**
  ```python
  reason = (
      "0 hour(s) beyond 3 sigma of this gateway's own 28-day baseline "
      "in the last 7 days; no metric over 3 sigma"
  )
  ```

### 14.3 Semantic Guardrails
- **No Fabricated Causal Claims:** The reason must **never** assert unverified physical root causes (e.g., "power supply failed", "battery died", "lightning surge", "tampering").
- **Observational Integrity:** The explanation must strictly describe observed statistical telemetry breaches relative to historical baseline behavior.

---

## 15. `predictions.csv` Submission Contract

The output of the Part 1 pipeline is a single CSV file named `predictions.csv` conforming exactly to the grader specification.

### 15.1 Exact Schema

| Column Name | Data Type | Permitted Values / Format | Description |
| :--- | :---: | :--- | :--- |
| `week_start` | String | `YYYY-MM-DD` | Date of the scored Monday (e.g., `2026-02-02`). |
| `rank` | Integer | $1, 2, \dots, 15$ | Integer rank from 1 to 15 within the week. |
| `gateway_id` | String | 12 hex chars (`^[0-9A-F]{12}$`) | Canonical bare uppercase gateway identifier. |
| `score` | Float | $\ge 0.0$ | Aggregate count of individual 3-sigma metric breaches. |
| `reason` | String | $1 \le \text{length} \le 300$ chars | Non-empty operational explanation string. |

### 15.2 Structural Invariants
1. **Total Row Count:** Exactly 120 rows ($8 \text{ weeks} \times 15 \text{ rows/week}$).
2. **Column Order:** Exactly `["week_start", "rank", "gateway_id", "score", "reason"]`. No extra columns, no missing columns.
3. **Week Set:** Exactly the 8 scored Mondays (`2026-02-02` through `2026-03-23`), each appearing exactly 15 times.
4. **Rank Sequence:** Strictly contiguous integers $1, \dots, 15$ for each week.
5. **ID Uniqueness:** No duplicate `gateway_id` entries within any single week.
6. **Grader Acceptance:** Must pass `python validate_submission.py predictions.csv` with exit code 0.

---

## 16. Determinism Contract

The pipeline must guarantee **deterministic outputs for the same inputs and execution logic**.

### 16.1 Deterministic Elements
- **Explicit Tie-Breaking:** All rankings enforce secondary sorting on canonical bare `gateway_id` ascending.
- **Deterministic ID Normalization:** Stripping colons and capitalizing hex digits is completely deterministic.
- **Deterministic Deduplication:** Deduplicating with `subset=["gateway_id", "ts_utc"]` and `keep="first"` ensures reproducible record selection.
- **Zero Stochasticity:** The pipeline employs no random seeds, pseudo-random generators, or non-deterministic optimization algorithms.
- **No Manual Adjustments:** The exact same pipeline logic executes autonomously across all eight scored weeks.

---

## 17. Leakage Prevention Contract

The production pipeline enforces strict temporal isolation to prevent information leakage from the future into past operational decisions.

### 17.1 Temporal Isolation Rule
For any scored Monday $T$, all computations must adhere to:

$$\text{Telemetry Timestamp} < T$$

### 17.2 Forbidden Data Sources
The following data channels are strictly forbidden during the execution of week $T$:
1. Telemetry records with timestamp $\ge T$.
2. Any field visit records occurring on or after $T$.
3. Any qualitative review or post-hoc engineer spreadsheet entries.
4. Meter reading records published or updated after $T$.
5. Global summary statistics computed over the entire dataset duration (no dataset-wide means or standard deviations).

All baselines and metric breaches must be derived strictly from the trailing historical window $[T - 28\text{d}, T)$.

---

## 18. Ranking Layer vs. Output Layer Architecture

To preserve clean modularity and testability, the production pipeline enforces a strict separation of concerns across nine sequential stages:

```
┌────────────────────────────────────────────────────────┐
│ 1. Data Ingestion & Normalization                      │
│    Load telemetry & gateway master; normalize IDs      │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 2. Telemetry Deduplication                             │
│    Remove exact (gateway_id, ts_utc) duplicate clones  │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 3. Lifecycle Eligibility Gating                        │
│    Construct active fleet universe at Monday T         │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 4. 28-Day Baseline Computation                         │
│    Compute per-gateway (mean, std) for 3 metrics       │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 5. 7-Day Recent Anomaly Detection                      │
│    Identify individual metric observations > 3 sigma   │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 6. Gateway Scoring                                     │
│    Aggregate 3-sigma metric breaches per gateway       │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 7. Deterministic Ranking                               │
│    Sort by (score desc, gateway_id asc)                │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 8. Top-15 Selection & Reason Generation                │
│    Extract top 15; generate compliant explanation text │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 9. CSV Formatting & Grader Validation                  │
│    Write predictions.csv; execute validate_submission  │
└────────────────────────────────────────────────────────┘
```

The ranking engine remains independent from CSV serialization and validation tooling, facilitating automated unit testing and edge-case auditing.

---

## 19. Error Conditions and Operational Exceptions

The production pipeline must explicitly distinguish between fatal validation failures and expected operational data sparsity.

### 19.1 Fatal Validation Errors (Immediate Termination)
The pipeline must raise an immediate exception and halt if any of the following occur:
- **Missing Required Input Files:** `data/gateway_master.csv` or required monthly telemetry Parquet partitions are missing.
- **Missing Columns:** Required columns (`gateway_id`, `ts_utc`, `offline_duration_sec`, `disconnection_cnt`, `reboot_cnt`, `installed_on`, `decommissioned_on`) are missing.
- **Malformed Identifiers:** Any gateway identifier fails normalization (`normalize_gateway_id` returns an invalid format).
- **Insufficient Fleet Capacity:** The active eligible universe at Monday $T$ has fewer than 15 gateways ($N_{\text{active}}(T) < 15$).
- **Output Schema Violation:** The generated output fails any check in `validate_submission.py`.

### 19.2 Expected Data Sparsity (Handled Gracefully)
The pipeline must handle standard operational variations without crashing:
- **Zero Variance in Baseline ($\sigma = 0$):** Handled via `.replace(0, np.nan)` and `.fillna(False)`; generates zero anomaly flags.
- **Missing Recent Telemetry:** Addressed according to the universe contract (documented in Section 11 and audited in Phase 7.3).
- **Newly Installed Assets:** Gateways with insufficient baseline history receive score `0.0`.

---

## 20. Configuration Contract

To avoid magic numbers and ensure complete maintainability, all pipeline operational parameters must be defined as explicit named constants:

```python
# Pipeline Operational Constants
BASELINE_WINDOW_DAYS: int = 28
RECENT_WINDOW_DAYS: int = 7
SIGMA_THRESHOLD: float = 3.0
VISITS_PER_WEEK: int = 15
MAX_REASON_LENGTH: int = 300

# Telemetry Metric Columns
MONITORED_METRICS: list[str] = [
    "offline_duration_sec",
    "disconnection_cnt",
    "reboot_cnt",
]

# Scored Prediction Mondays
SCORED_MONDAYS: list[dt.date] = [
    dt.date(2026, 2, 2),
    dt.date(2026, 2, 9),
    dt.date(2026, 2, 16),
    dt.date(2026, 2, 23),
    dt.date(2026, 3, 2),
    dt.date(2026, 3, 9),
    dt.date(2026, 3, 16),
    dt.date(2026, 3, 23),
]
```

---

## 21. Phase 7.3 Boundary

Phase 7.2 establishes the baseline specification, but explicitly defines the boundary for **Phase 7.3 (Production Edge-Case Audit)**:

### 21.1 Primary Unresolved Issue: Completely Silent Active Gateways
During the scored period, certain active gateways may emit zero telemetry records in the recent 7-day window $[T - 7\text{d}, T)$:
- **Phase 7.3 Investigation Questions:**
  1. How many active gateways are completely silent during each of the eight scored weeks?
  2. Does retaining them with score `0.0` (as done in the Phase 6 backtester) select them into the Top 15 when fewer than 15 gateways have anomaly breaches?
  3. What is the historical repair outcome of silent gateways in the test period?
  4. Can the original baseline behavior be preserved without violating the 15-gateway submission contract?
  5. Would any proposed handling of silent gateways constitute an unauthorized strategy modification?

### 21.2 Boundary Constraint
Phase 7.3 is authorized to audit edge cases and recommend production handling for silent gateways. However, Phase 7.3 is **NOT** authorized to casually introduce a new ranking model, add unvalidated heuristics (such as Candidate F's $+10.0$ silence bonus), or alter the baseline 3-sigma scoring formulation.

---

## 22. Phase 8 Implementation Contract

Phase 8 will implement the production code based directly on this contract. Specifically, Phase 8 will:
1. Construct the production script/module that executes the 9-stage pipeline defined in Section 18.
2. Ingest `gateway_master.csv` and telemetry Parquet partitions.
3. Apply canonical ID normalization and deduplication.
4. Construct the active eligible fleet universe for each scored Monday.
5. Compute 28-day baseline statistics and 7-day anomaly breaches.
6. Score and rank eligible gateways with deterministic tie-breaking.
7. Select the Top 15 recommendations per week and generate compliant reason strings.
8. Incorporate the finalized silent-gateway handling policy established in Phase 7.3.
9. Generate `predictions.csv` and assert clean pass of `validate_submission.py`.

Phase 8 must **NOT** redesign the strategy, tune arbitrary weights, or introduce machine learning models.

---

## 23. Verification Checklist

The following checklist must be validated before Phase 7.2 approval:

- [x] **Selected Strategy:** Strictly `Baseline_3Sigma` (no ML, no composite features).
- [x] **No Redundant Datasets:** Excluded `field_visits.csv`, `engineer_review_2026-02.xlsx`, and `meter_read_success.csv` from prediction inputs.
- [x] **Prediction Schedule:** Exactly eight scored Mondays from `2026-02-02` to `2026-03-23`.
- [x] **Temporal Boundaries:** Strict pre-$T$ cutoff $[T - 28\text{d}, T)$ and $[T - 7\text{d}, T)$ with $\text{timestamp} < T$.
- [x] **Gateway Identity:** Canonical 12-character uppercase bare hex format enforced.
- [x] **Eligibility Contract:** Lifecycle gating (`installed_on` $\le T$, `decommissioned_on` $> T$ or null) precedes ranking.
- [x] **Deduplication:** Enforces deduplication of 6,547 duplicate records before aggregation.
- [x] **Baseline Rule:** Sample standard deviation (`ddof=1`) with zero-variance protection.
- [x] **Scoring Definition:** Aggregate count of individual 3-sigma metric breaches across the 3 monitored metrics; single observation contributes 0, 1, 2, or 3.
- [x] **Ranking Determinism:** Primary `score` desc, secondary canonical `gateway_id` asc.
- [x] **Submission Shape:** Exactly 120 rows (8 weeks $\times$ 15 rows/week).
- [x] **Reason Text:** Non-empty, $\le 300$ characters, no fabricated physical causes.
- [x] **Leakage Guard:** Strictly zero future telemetry or post-$T$ evaluation data.
- [x] **Phase 7.3 Boundary:** Silent-gateway handling explicitly handed off to Phase 7.3 audit.
- [x] **Phase 8 Scope:** Implementation boundaries clearly frozen.

---

## 24. Final Decision

Phase 7.2 freezes the production strategy specification. Phase 8 may implement this contract but may not change the selected ranking policy without reopening the strategy decision and documenting the change.

---

## Related Documents

- [`reports/PHASE_4_1_OPERATIONAL_DEFINITION.md`](PHASE_4_1_OPERATIONAL_DEFINITION.md) — Operational concept of "needs a visit" and cost asymmetry.
- [`reports/PHASE_6_1_BACKTEST_TARGET.md`](PHASE_6_1_BACKTEST_TARGET.md) — Historical repair target construction and dispatch lag.
- [`reports/PHASE_6_2_BACKTEST_ENGINE.md`](PHASE_6_2_BACKTEST_ENGINE.md) — Backtesting engine architecture and anti-leakage guards.
- [`reports/PHASE_6_3_STRATEGY_DECISION.md`](PHASE_6_3_STRATEGY_DECISION.md) — Strategy comparison, selection justification, and statistical tests.
- [`reports/PHASE_7_1_OPERATIONAL_DECISION.md`](PHASE_7_1_OPERATIONAL_DECISION.md) — Operational cost model, Top-15 capacity constraints, and error modes.
- [`baseline_3sigma.py`](../baseline_3sigma.py) — Reference 3-sigma anomaly baseline implementation.
- [`validate_submission.py`](../validate_submission.py) — Grader submission validation script.
