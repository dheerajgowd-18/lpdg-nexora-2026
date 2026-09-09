# NEXORA 2026 — Project Overview

**LPDG Innovation Hub Selection Challenge 2026 (NEXORA 2026)**  
**Document Type:** Master Architectural Overview & Executive Engineering Summary  
**Audience:** Technical Reviewers, Engineering Leadership, Evaluators, and Collaborating Engineers  
**Project Status:** Phase 8 Complete — Part 1 Production Pipeline Verified & Grader-Compliant  
**Primary Artifact Produced:** `predictions.csv` (120 rows, 8 scored weeks $\times$ 15 recommendations)  
**Production CLI Entrypoint:** `python -m nexora.pipeline --data data/ --out predictions.csv`

---

## 1. Executive Summary

NEXORA 2026 is an operational engineering solution developed for the **LPDG Innovation Hub Selection Challenge 2026**. 

The operational challenge is straightforward but constrained: LPDG operates a fixed radio network of roughly 320 active LoRaWAN gateways across Germany, relaying hourly meter readings for 40 to 900 downstream utility meters per gateway. When a gateway degrades or fails, connected meters cannot be billed automatically. To service this infrastructure, LPDG deploys physical field crews, but dispatch capacity is strictly limited to a **maximum of 15 site visits per week**. Historically, sites were selected through manual spreadsheet reviews and technician intuition, resulting in a **60.7% historical false alarm rate** (unnecessary inspections where no equipment defect was found).

To solve this, our system executes a weekly prioritization decision:
> *"Given strictly the telemetry and metadata recorded prior to Monday morning, which 15 gateways should field technicians visit to maximize physical repair yield while minimizing wasted inspections?"*

Through rigorous empirical investigation, multi-feature analysis, and 26 weeks of historical backtesting, we evaluated seven distinct ranking strategies under strict temporal anti-leakage conditions. Although multi-feature composite candidates captured marginal additional repairs, they caused a disproportionate surge in false alarms (+57% false alarms for +2.4% repair gain), incurring higher net standardized economic penalties. 

Consequently, **`Baseline_3Sigma`** was selected and locked as the production strategy. It evaluates trailing 28-day operating baselines across three core distress metrics (`offline_duration_sec`, `disconnection_cnt`, `reboot_cnt`), counts individual 3-sigma metric breaches over the trailing 7 days, and ranks the fleet deterministically.

In Phase 8, we engineered a clean, modular, 12-stage production pipeline (`src/nexora/`) incorporating defensive data controls: Latin-1 safe master loading, 12-character uppercase hexadecimal identifier normalization, exact duplicate telemetry removal (6,547 duplicate clones eliminated), lifecycle fleet gating, Option B silent-gateway universe retention (assigning score=0 to unobserved active assets), and non-causal reason generation. The entire pipeline executes across all 8 challenge-scored Mondays in **~7 seconds**, passes all internal regression tests, and achieves **100% acceptance (exit code 0)** from the official challenge submission validator.

---

## 2. The Problem We Are Solving

LPDG's smart metering infrastructure relies on physical gateway assets installed on building rooftops, industrial plants, and utility towers.

### 2.1 The Operational Context
- **Asset Register:** 332 total gateways recorded in the master asset database, with 290 to 308 actively commissioned during the challenge evaluation window.
- **Data Volume:** Over 1.43 million hourly telemetry readings capturing operating state, radio packets, CPU loads, memory, and network dropouts.
- **Physical Bandwidth:** A hard physical ceiling of **15 inspection visits per week** across Germany.
- **Target Horizon:** 8 forward scored Mondays spanning `2026-02-02` through `2026-03-23` ($8 \times 15 = 120$ total inspection recommendations).

### 2.2 Asymmetric Operational Economics
The challenge establishes an explicit, asymmetric economic cost proxy to evaluate dispatch quality:
- **False Visit Penalty (€380):** Incurred whenever a field crew is dispatched to a gateway in the Top 15, inspects the installation, and discovers normal operation (`Kein Fehler gefunden`). A false dispatch wastes €380 in direct proxy labor and displaces another degraded gateway from receiving service.
- **Missed Broken Gateway Penalty (€600/week):** Incurred for every week a faulty gateway requiring physical maintenance (`Fehler behoben`) remains unaddressed.
- **Standardized Proxy Nature:** The values of €380 and €600 are standardized decision-analysis proxies established by the challenge to evaluate strategy trade-offs on equal terms across historical data. They do not represent measured historical company ledger expenses or contractual liabilities.

### 2.3 The Core Operational Question
The problem is not an abstract machine learning competition or unconstrained anomaly detection exercise. It is a **constrained operational decision problem**:
> *"How do we allocate exactly 15 scarce field inspection slots each Monday morning to maximize the capture of genuine equipment failures without burning resources on false alarms?"*

---

## 3. Challenge Constraints

The challenge brief enforces strict operational, temporal, and technical boundaries that govern our solution:

1. **Strict Pre-$T$ Information Boundary:** Predictions for decision Monday $T$ must rely strictly on data timestamped prior to $T$ ($\text{timestamp} < T$). Accessing data recorded on or after Monday morning constitutes fatal temporal lookahead leakage.
2. **Fixed Recommendation Cardinality:** The output must contain **exactly 15 recommendations per scored week** (120 total rows across the 8 scored weeks), with contiguous ranks strictly numbered $1, 2, \dots, 15$ and zero duplicate gateway IDs within any week.
3. **No Future Commissioning:** Gateways whose installation date is in the future relative to decision Monday $T$ (e.g., assets installed in May–July 2026) must never enter the candidate recommendation list.
4. **Decommissioned Asset Gating:** Retired gateways (decommissioned prior to or on Monday $T$) must never be recommended for inspection.
5. **Deterministic & Reproducible Execution:** Output orderings must be 100% reproducible across repeated runs without reliance on random seeds, stochastic sampling, or platform-dependent sort behavior.
6. **Submission Formatting Acceptance:** The exported `predictions.csv` file must pass `validate_submission.py` with exit code 0.
7. **Two-Part Architecture:** Part 1 (this production pipeline) provides the authoritative predictive ranking engine. Part 2 builds the production software engineering delivery (API, CLI, containerization, and test harnesses). Part 1 correctness is the mandatory foundation for Part 2.

---

## 4. Data We Were Given

The challenge provided five core datasets covering network operations, physical asset metadata, field tickets, and downstream metering:

| Dataset | Storage Format | Temporal Span | Row Count | Primary Key | Role in Project | Used in Production Pipeline? |
| :--- | :--- | :--- | :---: | :--- | :--- | :---: |
| **`gateway_master.csv`** | CSV (`latin1`) | Static snapshot | 332 assets | `gateway_id` | Asset register: installation dates, decommission dates, region, site type. | **YES** (Defines eligible fleet) |
| **`telemetry/`** | Parquet (8 monthly partitions) | 2025-08-01 to 2026-03-31 | 1,433,387 rows | `(gateway_id, ts_utc)` | Hourly operating metrics: offline durations, disconnections, reboots, radio packets, load, memory. | **YES** (Core scoring signals) |
| **`field_visits.csv`** | CSV (`utf-8`) | 2025-02-03 to 2026-02-14 | 642 work orders | `visit_id` | Historical ground-truth field tickets: work order reasons, visit dates, technician outcome findings. | **NO** (Evaluation / backtesting only) |
| **`meter_read_success.csv`** | CSV (`utf-8`) | 2025-08-04 to 2026-01-26 | 7,226 weekly rows | `(week_start, gateway_id)` | Weekly downstream meter-reading counts (`meters_read`, `meters_expected`). Stops on 2026-01-26. | **NO** (Exploratory analysis only) |
| **`engineer_review_2026-02.xlsx`** | Excel OpenXML | 2026-02-15 (Single audit) | 120 reviews | `gateway_id` | Expert engineering audit sample by M. Hoffmann during week 2 of the scored window. | **NO** (Validation reference only) |

### Scale and Data Separation
- The raw telemetry comprises **1,433,387 rows** across 57 telemetry columns.
- We maintain strict architectural separation between **production operational inputs** (`gateway_master.csv`, `telemetry/`) and **evaluative ground truth** (`field_visits.csv`, `meter_read_success.csv`, `engineer_review_2026-02.xlsx`). The production pipeline never touches evaluative files, preventing any risk of target leakage.

---

## 5. Data Investigation — What We Discovered

In Phase 3 ([`reports/PHASE_3_DEEP_DATA_INVESTIGATION.md`](PHASE_3_DEEP_DATA_INVESTIGATION.md)), we conducted an exhaustive empirical audit of all supplied datasets. The findings directly shaped our production safeguards:

### 1. Character Encoding Vulnerability
- **Finding:** Reading `gateway_master.csv` using default UTF-8 triggers a fatal `UnicodeDecodeError` on byte `0xDF` (German sharp S `ß` in `Großkunden`).
- **Why It Mattered:** A standard python script would crash immediately in production.
- **Decision:** All master loading enforces explicit `encoding="latin1"`.

### 2. Dual Gateway Identifier Representations
- **Finding:** Master metadata, field visits, and engineer reviews use colon-delimited MAC-style strings (`06:39:EA:56:02:C1`), whereas telemetry Parquet partitions use bare 12-character hex strings (`0639EA5602C1`).
- **Why It Mattered:** Naive joins between telemetry and master metadata resulted in **0 matching rows**.
- **Decision:** Built `normalize_gateway_id()` to canonicalize all IDs across the system to uppercase 12-character bare hex (`^[0-9A-F]{12}$`).

### 3. Exact Row Duplication in Telemetry
- **Finding:** Exactly **6,547 duplicate records** on `(gateway_id, ts_utc)` were discovered across odd monthly partitions (Sep 2025: 2,185; Nov 2025: 2,124; Jan 2026: 2,238). All 6,547 are 100% full-row identical network retry clones.
- **Why It Mattered:** Raw aggregations artificially inflate downtime sums and distort sample standard deviations ($\sigma$) by double-counting downtime.
- **Decision:** Telemetry is deterministically deduplicated (`drop_duplicates(subset=['gateway_id', 'ts_utc'], keep='first')`) prior to baseline calculation.

### 4. Future Commissioned Gateways
- **Finding:** Exactly 12 gateways in `gateway_master.csv` have zero telemetry rows because their commissioning dates are in May, June, or July 2026.
- **Why It Mattered:** If not filtered, uninstalled hardware could be mistakenly queued for field inspection.
- **Decision:** Lifecycle eligibility filtering ($	exttt{installed\_on} \le T$) strictly excludes future assets.

### 5. Decommissioned Asset Persistence
- **Finding:** 12 gateways were decommissioned between Sep 2025 and Feb 2026. Telemetry ceases exactly on their decommission dates.
- **Why It Mattered:** Disagreeing dispatch queues might recommend retired hardware.
- **Decision:** Lifecycle gating drops assets where $	exttt{decommissioned\_on} \le T$.

### 6. Cumulative Firmware Counters
- **Finding:** Metrics like `offline_duration_sec` accumulate downtime across multi-hour dropouts, with values reaching up to 726,642 seconds (8.4 days) in a single hourly row.
- **Why It Mattered:** Values cannot be interpreted as simple 0–3,600 second hourly slices.
- **Decision:** Monitored metrics are evaluated as statistical deviations against a gateway's own baseline rather than absolute fixed thresholds.

### 7. Historical False Alarm Baseline
- **Finding:** Of 642 historical field tickets, **60.7% (390 visits)** resulted in `Kein Fehler gefunden` (no fault found), while only 34.7% (223 visits) resulted in physical repairs (`Fehler behoben`).
- **Why It Mattered:** Confirmed that historical human dispatching was plagued by false alarms.
- **Decision:** Ranking strategy selection must penalize false alarms heavily rather than chasing raw recall.

### 8. The Meter-Read Data Cliff
- **Finding:** `meter_read_success.csv` ends abruptly on `2026-01-26`. Zero meter reads exist for the 8-week scored period (Feb–Mar 2026).
- **Why It Mattered:** Any production model relying on recent meter-reading features would fail or suffer massive feature staleness.
- **Decision:** Meter read data was rejected as an input for the production scoring pipeline.

---

## 6. Operational Definition — What Does "Needs a Visit" Mean?

The challenge brief intentionally left "needs a visit" under-specified. In Phase 4 ([`reports/PHASE_4_1_OPERATIONAL_DEFINITION.md`](PHASE_4_1_OPERATIONAL_DEFINITION.md)), we established an empirical operational definition:

### 6.1 The Operational Spectrum
A gateway exhibits behavior across a spectrum:
1. **Normal Operation:** Stable telemetry, periodic keep-alives, low disconnections, minimal reboots.
2. **Transient Noise:** Occasional RF packet collisions or brief cellular re-attachments that resolve autonomously without physical human intervention.
3. **Statistical Anomaly:** Telemetry observations that deviate significantly from historical distributions.
4. **Persistent Operational Distress:** Ongoing, severe breakdown in communication (extended downtime, repeated reboot loops, flapping network connections).
5. **Actionable Hardware Fault:** A persistent defect requiring on-site technician attendance to resolve (`Fehler behoben`: antenna realignment, power supply replacement, hardware swap).

### 6.2 Crucial Boundary Principles
- **We Detect Statistical Anomaly, Not Physical Causation:** Telemetry records network and hardware symptoms, not physical causes. A high anomaly score indicates acute operational distress; it does **not** prove a specific physical root cause (such as a severed cable or blown fuse).
- **Not Every Anomaly Requires a Truck Roll:** Many network fluctuations clear remotely. Dispatches are only justifiable when distress is severe enough to warrant consuming one of the 15 scarce weekly visit slots.
- **Distinguishing Outcomes:** In backtesting, we categorize historical field visits into **Repairs Captured** (`Fehler behoben`), **False Alarms** (`Kein Fehler gefunden`), and **Inconclusive** (`Kein Zugang`).

---

## 7. Feature Investigation

In Phase 5 ([`reports/PHASE_5_1_FEATURE_FEASIBILITY.md`](PHASE_5_1_FEATURE_FEASIBILITY.md) through [`reports/PHASE_5_3_FEATURE_ANALYSIS.md`](PHASE_5_3_FEATURE_ANALYSIS.md)), we evaluated dozens of candidate telemetry features across seven functional families:

1. **Reporting & Silence:** Missing hours count, transmission gap lengths, reporting completeness.
2. **Offline Duration:** Total offline seconds, maximum offline run, weekly offline delta.
3. **Disconnection Frequency:** Reconnection count, network flapping rate.
4. **Reboot Cycles:** Hourly reboots, reboot duration, rapid reboot loops.
5. **Volatilities & Ratios:** Packet-to-error ratios, RSSI/SNR volatility.
6. **Downstream Meter Read Success:** Trailing read ratios, missing meter deltas (abandoned due to the 2026-01-26 data cliff).
7. **Asset Lifecycle:** Operational age, installation tenure, firmware age.

### Pruning and Selection Outcomes
- **Multicollinearity:** Many features exhibited near-perfect correlation ($r > 0.95$, e.g., missing hours vs offline duration, raw packet counts vs site size).
- **Core Signal Confirmation:** Three metrics consistently showed the cleanest association with acute distress:
  - `offline_duration_sec` (backhaul connectivity loss)
  - `disconnection_cnt` (cellular link instability)
  - `reboot_cnt` (hardware instability / power cycling)
- **Outcome:** Rather than feeding dozens of noisy, collinear features into an over-parameterized model, feature investigation validated that tracking deviations in these three core distress metrics provided the most robust foundation for ranking.

---

## 8. Strategy Development

In Phase 6 ([`reports/PHASE_6_2_BACKTEST_ENGINE.md`](PHASE_6_2_BACKTEST_ENGINE.md)), we developed and evaluated seven distinct candidate ranking strategies across 26 historical decision weeks:

1. **`Baseline_3Sigma` (Reference Anomaly Benchmark):** Trailing 28-day baseline; flags individual metric breaches exceeding $\mu + 3\sigma$ over the trailing 7 days; ranks by total breach count.
2. **`Candidate_A_Core` (Persistence / Core Trio):** Weighted composite scoring combining normalized offline duration, reboot counts, and disconnection frequency.
3. **`Candidate_B_Severity` (Non-linear Outlier Scaling):** Quadratic penalty scaling on severe offline events to heavily penalize extreme outages.
4. **`Candidate_C_SevereOffline` (Hybrid Composite + Offline Boost):** Blends 3-sigma anomaly counting with an explicit offline severity multiplier.
5. **`Candidate_D_LongTerm` (Multi-Horizon Baseline):** Evaluates multi-week trend divergence comparing 7-day vs. 56-day moving averages.
6. **`Candidate_E_Reliability` (Chronic Degradation Index):** Focuses on chronic, repeated micro-disconnections over extended horizons.
7. **`Candidate_F_SilenceOverride` (Dead Gateway Bonus):** Awards an artificial $+10.0$ score bonus to completely silent gateways to force uncommunicative assets into the Top 15.

---

## 9. Why Baseline_3Sigma Was Selected

Strategy selection was resolved by empirical performance in historical backtesting ([`reports/PHASE_6_3_STRATEGY_DECISION.md`](PHASE_6_3_STRATEGY_DECISION.md)).

### 9.1 The Scoring Formulation
For every candidate gateway on decision Monday $T$:
1. Establish a reference baseline over the trailing 28 days: $[T-28\text{d}, T)$.
2. Calculate sample mean ($\mu$) and sample standard deviation ($\sigma$, with $\text{ddof}=1$) for `offline_duration_sec`, `disconnection_cnt`, and `reboot_cnt`.
3. Evaluate telemetry over the recent 7 days: $[T-7\text{d}, T)$.
4. Flag each individual hourly observation where:
   $$x > \mu + 3\sigma$$
5. Accumulate total breaches: a single hourly observation can contribute **0, 1, 2, or 3 breaches** to the score.
6. Rank gateways by total breach score in descending order.

### 9.2 Historical Backtest Evidence (26 Decision Weeks)
Across 26 historical weeks (390 dispatch recommendations per strategy, 116 available repairs):

| Strategy | Repairs Captured | Repair Capture % | False Alarms | False Alarm Rate | Combined Cost Proxy (€) | Net Delta vs. Baseline |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`Baseline_3Sigma`** | **41** | **35.34%** | **14** | **3.59%** | **€50,320** | **LOCKED (Best Trade-off)** |
| `Candidate_C_SevereOffline` | 42 | 36.21% | 22 | 5.64% | €52,760 | +1 repair, +8 false alarms, +€2,440 penalty |
| `Candidate_A_Core` | 40 | 34.48% | 22 | 5.64% | €53,960 | -1 repair, +8 false alarms, +€3,640 penalty |
| `Candidate_B_Severity` | 37 | 31.90% | 21 | 5.38% | €55,380 | -4 repairs, +7 false alarms, +€5,060 penalty |
| `Candidate_D_LongTerm` | 37 | 31.90% | 21 | 5.38% | €55,380 | -4 repairs, +7 false alarms, +€5,060 penalty |
| `Candidate_E_Reliability` | 37 | 31.90% | 22 | 5.64% | €55,760 | -4 repairs, +8 false alarms, +€5,440 penalty |
| `Candidate_F_SilenceOverride`| 37 | 31.90% | 21 | 5.38% | €55,380 | -4 repairs, +7 false alarms, +€5,060 penalty |

### 9.3 The Engineering Rationale
Candidate C captured 42 repairs vs. 41 for `Baseline_3Sigma` (+1 repair). However, achieving that single additional repair caused **8 additional false alarms** (22 vs. 14, a 57.1% increase). Under the challenge cost model:
- 8 extra false alarms incurred: $+8 \times €380 = +€3,040$
- 1 saved repair saved: $-1 \times €600 = -€600$
- Net outcome: **+€2,440 higher cost proxy for Candidate C**.

Furthermore, paired statistical testing confirmed:
- Weekly repair capture difference: $t = 0.161, p = 0.8732$ (no statistically significant difference).
- Weekly false alarm increase: $t = 2.133, p = 0.0430$ (Candidate C caused a statistically significant increase in false alarms).

`Baseline_3Sigma` delivered the lowest false alarms (14), lowest false alarm rate (3.59%), highest Top-5 repair concentration (19 repairs), and lowest overall cost proxy (€50,320). It was locked as the production strategy because it demonstrated the strongest observed operational trade-off.

---

## 10. Historical Backtesting

To validate our ranking strategies rigorously without lookahead bias, Phase 6 constructed a leak-free backtesting harness:

- **26 Decision Weeks:** Evaluated every Monday from `2025-08-04` through `2026-01-26`.
- **Target Attribution:** Linked field repairs back to decision Mondays using the ticket creation timestamp (`requested_on`). A repair was attributed to week $T$ if its work order was created during the operational dispatch cycle $[T, T + 7\text{d})$.
- **Delayed Field Outcomes:** Technicians attended sites on average 9.6 days after work order creation (`visited_on`). The evaluation correctly preserved outcomes regardless of field delay.
- **Strict Pre-$T$ Filtering:** Telemetry was strictly sliced to $t < T$, ensuring zero information leakage from future operating hours.
- **Observational Nature:** Backtesting evaluates historical decisions under field conditions; it is not a theoretical claim of future perfection or causal hardware diagnostics.

---

## 11. Production Strategy Contract

In Phase 7 ([`reports/PHASE_7_2_PRODUCTION_STRATEGY_CONTRACT.md`](PHASE_7_2_PRODUCTION_STRATEGY_CONTRACT.md) and [`reports/PHASE_7_3_SILENT_GATEWAY_AUDIT.md`](PHASE_7_3_SILENT_GATEWAY_AUDIT.md)), we froze the production contract before writing code:

1. **Temporal Boundaries:**
   - Baseline window: $[T - 28\text{d}, T)$
   - Recent evaluation window: $[T - 7\text{d}, T)$
   - Strict cutoff: $\text{timestamp} < T$ (strictly pre-Monday)
2. **Lifecycle Eligibility:**
   $$\text{Eligible}(i, T) \iff \Big(\texttt{installed\_on}_i \le T\Big) \;\land\; \Big(\texttt{decommissioned\_on}_i > T \;\lor\; \texttt{decommissioned\_on}_i \text{ is null}\Big)$$
3. **Locked Silent Gateway Policy (Option B):**
   - Active, eligible gateways that transmit zero telemetry in $[T-7\text{d}, T)$ are retained in the candidate universe.
   - Default values assigned: $\text{score} = 0.0$, $\text{flagged\_hours} = 0$, $\text{worst\_metric} = \text{"no\_telemetry"}$.
   - No silence bonuses (Candidate F rejected).
4. **Deterministic Ranking:**
   - Primary sort: `score` **descending**.
   - Secondary tie-breaker: `gateway_id` **ascending** (canonical lexicographical order).
   - Cardinality: Exactly Top 15 recommendations selected.
5. **Observational Reasons:**
   - For score $> 0$: `"{N} individual 3-sigma metric breach(es) against this gateway's own 28-day baseline in the last 7 days; first breach on {worst_metric}"`
   - For score $= 0$: `"0 individual 3-sigma metric breaches against this gateway's own 28-day baseline in the last 7 days"`
   - Length strictly $\le 300$ characters; non-causal.

---

## 12. Production Architecture

The production pipeline in `src/nexora/` implements a linear, decoupled 12-stage architecture:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                   NEXORA 12-STAGE PRODUCTION DATAFLOW                    │
│                                                                          │
│  1. Raw Data Ingestion (gateway_master.csv & monthly telemetry Parquets) │
│                             │                                            │
│                             ▼                                            │
│  2. Schema Validation & Input Column Guards                              │
│                             │                                            │
│                             ▼                                            │
│  3. Gateway Identifier Normalization (12-character uppercase bare hex)   │
│                             │                                            │
│                             ▼                                            │
│  4. Deterministic Telemetry Deduplication (drop_duplicates on id, ts)   │
│                             │                                            │
│                             ▼                                            │
│  5. Lifecycle Fleet Eligibility Gating (installed <= T < decommission)   │
│                             │                                            │
│                             ▼                                            │
│  6. Temporal Window Slicing (strictly pre-T: [T-28d, T) and [T-7d, T))   │
│                             │                                            │
│                             ▼                                            │
│  7. Baseline_3Sigma Scoring (sample std ddof=1, metric breach accum)     │
│                             │                                            │
│                             ▼                                            │
│  8. Silent Gateway Universe Alignment (Option B: score=0.0, no_telemetry)│
│                             │                                            │
│                             ▼                                            │
│  9. Deterministic Fleet Ranking (score descending, gateway_id ascending) │
│                             │                                            │
│                             ▼                                            │
│ 10. Top-15 Weekly Selection (ranks 1 to 15 assigned per scored week)     │
│                             │                                            │
│                             ▼                                            │
│ 11. Observational Reason Generation (factual statistical explanations)   │
│                             │                                            │
│                             ▼                                            │
│ 12. Internal Validation & Output Serialization (predictions.csv export)  │
└──────────────────────────────────────────────────────────────────────────┘
```

### Module Responsibilities
- [`src/nexora/data_loader.py`](file:///d:/lpdg-nexora-2026/src/nexora/data_loader.py): Ingestion, Latin-1 decoding, ID canonicalization, Parquet loading, exact telemetry deduplication.
- [`src/nexora/eligibility.py`](file:///d:/lpdg-nexora-2026/src/nexora/eligibility.py): Evaluates lifecycle dates to construct the active candidate fleet independently of telemetry.
- [`src/nexora/scoring.py`](file:///d:/lpdg-nexora-2026/src/nexora/scoring.py): Implements reference `Baseline_3Sigma` scoring (28-day baseline, sample std with $\text{ddof}=1$, 3-sigma thresholds, 0–3 breach accumulation).
- [`src/nexora/ranking.py`](file:///d:/lpdg-nexora-2026/src/nexora/ranking.py): Fleet alignment, Option B retention, deterministic tie-breaking, Top-15 extraction.
- [`src/nexora/reasons.py`](file:///d:/lpdg-nexora-2026/src/nexora/reasons.py): Formats non-causal, observational explanation strings ($\le 300$ chars).
- [`src/nexora/validation.py`](file:///d:/lpdg-nexora-2026/src/nexora/validation.py): Sanity checking of output dataframes and subprocess execution of `validate_submission.py`.
- [`src/nexora/pipeline.py`](file:///d:/lpdg-nexora-2026/src/nexora/pipeline.py): End-to-end orchestrator and CLI entry point.

---

## 13. Engineering Safeguards

The production pipeline wraps the baseline algorithm in defensive engineering safeguards:

1. **Canonical Identifier Invariant:** Eliminates format mismatches by enforcing bare 12-character uppercase hex (`0639EA5602C1`) throughout.
2. **Deduplication Safeguard:** Eliminates 6,547 ingestion retry clones to prevent variance distortion and double-counting.
3. **Strict Temporal Horizon:** Slices data with $\text{timestamp} < T$, mathematically preventing lookahead contamination.
4. **Lifecycle Universe Completeness:** Fleet eligibility is determined strictly by asset metadata; broken gateways that stop reporting remain in the candidate queue.
5. **Option B Silent Asset Handling:** Retains silent active assets with score 0.0, avoiding artificial score bonuses while maintaining full audit visibility.
6. **Deterministic Tie-Breaking:** Enforces secondary sorting on `gateway_id` ascending, preventing execution drift across different platforms or runtime environments.
7. **Fleet Underflow Protection:** Pipeline halts immediately if fewer than 15 active gateways exist, preventing silent padding with decommissioned assets.
8. **Automated Submission Validation:** Integrates internal DataFrame schema validation and automatically invokes `validate_submission.py` upon completion.

---

## 14. Phase 8 Verification Results

In Phase 8 ([`reports/PHASE_8_VERIFICATION.md`](file:///d:/lpdg-nexora-2026/reports/PHASE_8_VERIFICATION.md)), the production pipeline underwent comprehensive verification across 12 criteria:

- **Raw Rows Loaded:** Exactly 1,433,387 rows.
- **Duplicate Records Removed:** Exactly 6,547 rows.
- **Post-Deduplication Rows:** 1,426,840 rows.
- **Master Assets:** 332 gateways.
- **Unknown Telemetry Gateway IDs:** Exactly 0.
- **Output Submission Rows:** Exactly 120 rows (8 weeks $\times$ 15 recommendations).
- **Weekly Recommendations:** Exactly 15 per week, ranked $1, 2, \dots, 15$.
- **Duplicate IDs Within Weeks:** Exactly 0.
- **Missing / Blank Fields:** Exactly 0 NaN scores, 0 empty reasons.
- **Reason Lengths:** Maximum length 139 characters (well below 300 character ceiling).
- **Official Validator Result:** Exit code 0 (`predictions.csv: OK`).
- **Reproducibility Test:** Consecutive dual runs produced identical SHA-256 hashes (`ec8489c8...`) and identical DataFrames.
- **Measured Runtime:** **~7 seconds** total execution time (data loading: 4.37s; scoring and ranking: 1.19s), comfortably beating the ~60-second engineering target.
- **Temporal Leakage Test:** Injected catastrophic future spikes at $T + 1\text{h}$; rankings remained 100% identical.
- **Issues Found:** 0 critical, 0 non-critical.
- **Gate Verdict:** **PASS**.

---

## 15. Current Output

The current production submission artifact is [`predictions.csv`](file:///d:/lpdg-nexora-2026/predictions.csv).

### Submission Schema
| Column | Data Type | Constraint | Description |
| :--- | :---: | :--- | :--- |
| `week_start` | String | `YYYY-MM-DD` | Date of the scored decision Monday (e.g., `2026-02-02`). |
| `rank` | Integer | $1, 2, \dots, 15$ | Contiguous rank within the weekly recommendation list. |
| `gateway_id` | String | 12-char hex | Canonical bare uppercase gateway identifier. |
| `score` | Float | Numeric $\ge 0.0$ | Aggregate count of 3-sigma individual metric breaches. |
| `reason` | String | $\le 300$ chars | Factual, observational explanation of statistical breaches. |

### Score Interpretation
- Scores in the generated Top 15 range between **15.0 and 43.0**.
- **Important:** The score is a count of statistical standard-deviation breaches against historical operating norms. It is **not** a probability of failure, a percentage, or a physical diagnosis.

---

## 16. What We Have Built So Far

| Project Phase | Focus Area | Status | Verified Outcome |
| :---: | :--- | :---: | :--- |
| **Phase 0** | Repository & Environment Setup | **Complete** | Tooling, virtual environment, and challenge assets established. |
| **Phase 1** | Baseline Checkpoint | **Complete** | Executed reference `baseline_3sigma.py` and generated initial baseline. |
| **Phase 2** | Dataset Inventory | **Complete** | Cataloged all 5 challenge datasets and mapped schema definitions. |
| **Phase 3** | Deep Data Investigation | **Complete** | Identified encoding flaws, ID mismatches, 6,547 duplicates, and 60.7% false alarm rate. |
| **Phase 4** | Operational Definition & Features | **Complete** | Formalized operational distress definition and mapped candidate telemetry metrics. |
| **Phase 5** | Feature Extraction & Analysis | **Complete** | Engineered feature extractors; conducted distribution, correlation, and pruning analyses. |
| **Phase 6** | Historical Backtesting | **Complete** | Simulated 26 decision weeks; evaluated 7 strategies; proved `Baseline_3Sigma` superiority. |
| **Phase 7** | Operational & Production Contract | **Complete** | Established cost model, locked Option B silent gateway policy, and froze architecture. |
| **Phase 8** | Production Implementation & Gate | **Complete** | Built `src/nexora/`, generated compliant `predictions.csv`, verified exit code 0 in ~7s. |
| **Phase 9+** | Part 2 Software Development & Delivery | **Pending** | Automated test suites, API service, containerization, and CI/CD. |

---

## 17. What Remains

With the Part 1 predictive pipeline complete and verified, the remaining roadmap turns this engine into an enterprise-grade software solution (Part 2):

- **Phase 9 — Automated Testing & Regression Protection:** Expanding unit, integration, and anti-leakage test suites with automated coverage tracking.
- **Phase 10 — Architecture Refactoring:** Modularizing components for dependency injection and reusable service layers.
- **Phase 11 — FastAPI Service:** Building a REST API providing weekly ranking endpoints, asset history queries, and on-demand explanation services.
- **Phase 12 — Error Handling & Resilience:** Hardening HTTP endpoints with structured error responses, input validation, and logging.
- **Phase 13 — End-to-End Testing:** Live integration testing spanning HTTP request to validated response.
- **Phase 14 — Dockerization:** Creating reproducible multi-stage Docker containers for the pipeline and API service.
- **Phase 15 — CI / GitHub Actions:** Setting up automated linting, type-checking, testing, and submission verification workflows.
- **Phase 16–22 — Final Documentation, Demos, and Submission Audit:** Comprehensive technical documentation, architectural decision records, recorded demo, and final code freeze.

---

## 18. Part 2 Direction

The selected direction for Part 2 is **Software Development**:

### Why Software Development Fits This Problem
Phase 6 proved that attempting to build complex machine learning models on this dataset offered no operational advantage:
- Historical labels are sparse (only 116 repairs across 26 weeks).
- Field visits reflect historical human dispatch bias, not clean failure truths.
- Complex feature composites increased false alarms by 57% for negligible repair gain.

The true operational value lies in **software engineering excellence**:
- Delivering a robust, reliable, and replaceable ranking service.
- Building a high-performance REST API with comprehensive input validation.
- Ensuring deterministic, transparent, and auditable field dispatch recommendations.
- Packaging the system in a lightweight Docker container that can be deployed and verified live in under 10 seconds.

---

## 19. Limitations

Sound engineering requires transparently acknowledging operational limitations:

1. **Observational Backtesting Scope:** Historical backtesting spans 26 weeks (`2025-08-04` to `2026-01-26`). While extensive, it reflects operational conditions specific to that timeframe.
2. **Label Imperfections:** Field tickets (`field_visits.csv`) represent historical technician actions and human dispatches, which carry operational noise and unobserved site constraints.
3. **Absence of Telemetry Does Not Prove Physical Health:** Complete telemetry silence indicates communication loss, but cannot distinguish between a disconnected backhaul, power outage, or destroyed hardware.
4. **Standardized Economic Proxies:** The €380 and €600 cost penalties are challenge-standardized proxies, not measured corporate ledger figures.
5. **No Causal Diagnostics:** The system identifies statistical anomalies; it cannot definitively identify internal hardware failure modes.
6. **Future Generalization:** While the baseline has proven stable, changes in physical network topology or cellular carrier infrastructure could alter baseline distributions.

---

## 20. Reproducibility

An external evaluator can reproduce our exact results with standard Python 3.10+:

### 1. Environment Setup
```bash
# Ensure dependencies are installed
pip install pandas numpy pyarrow pytest
```

### 2. Run the Production Pipeline
```bash
python -m nexora.pipeline --data data/ --out predictions.csv
```
- Loads master and telemetry partitions.
- Normalizes IDs and removes exact duplicates.
- Evaluates lifecycle eligibility across all 8 scored weeks.
- Computes `Baseline_3Sigma` scores and ranks the fleet deterministically.
- Exports `predictions.csv` and verifies output in ~7 seconds.

### 3. Run the Official Validator
```bash
python validate_submission.py predictions.csv
```
Expected output:
```text
predictions.csv: OK
  15 ranked gateways for each of 8 weeks, 2026-02-02 to 2026-03-23
```

### 4. Execute the Test Suite
```bash
pytest -v
```
All unit tests pass in ~1.2 seconds.

---

## 21. Repository Map

```text
lpdg-nexora-2026/
├── data/                                 # Raw challenge datasets (read-only)
│   ├── gateway_master.csv                # Physical asset register
│   ├── telemetry/                        # Monthly Parquet telemetry partitions
│   ├── field_visits.csv                  # Historical field work orders
│   ├── meter_read_success.csv            # Historical weekly meter reads
│   └── engineer_review_2026-02.xlsx      # Expert engineering audit sample
├── src/
│   └── nexora/                           # Production pipeline package
│       ├── __init__.py                   # Package exports
│       ├── data_loader.py                # Ingestion, ID normalization, deduplication
│       ├── eligibility.py                # Master lifecycle fleet gating
│       ├── scoring.py                    # Reference Baseline_3Sigma scoring
│       ├── ranking.py                    # Option B alignment, deterministic ranking, Top 15
│       ├── reasons.py                    # Observational reason generation
│       ├── validation.py                 # Output schema validation & grader runner
│       └── pipeline.py                   # 12-stage pipeline orchestrator & CLI
├── tests/                                # Test suite
│   ├── test_normalization.py             # ID canonicalization tests
│   ├── test_eligibility.py               # Lifecycle boundary tests
│   ├── test_scoring.py                   # ddof=1, breach accumulation tests
│   ├── test_ranking.py                   # Option B retention & tie-break tests
│   └── test_reasons.py                   # Reason string formatting tests
├── reports/                              # Authoritative engineering documentation
│   ├── PROJECT_OVERVIEW.md               # Master project overview (this document)
│   ├── PHASE_3_DEEP_DATA_INVESTIGATION.md# Data quality & empirical findings
│   ├── PHASE_4_1_OPERATIONAL_DEFINITION.md# Operational distress definition
│   ├── PHASE_5_EXPLANATION.md            # Feature feasibility & pruning narrative
│   ├── PHASE_6_EXPLANATION.md            # Backtest engine & strategy selection narrative
│   ├── PHASE_7_EXPLANATION.md            # Production contract & architecture narrative
│   └── PHASE_8_VERIFICATION.md           # Formal verification gate report
├── baseline_3sigma.py                    # Challenge reference baseline script
├── validate_submission.py                # Official challenge submission validator
├── predictions.csv                       # Verified Part 1 submission artifact
├── pytest.ini                            # Test runner configuration
└── reference/                            # Challenge brief and data dictionary PDFs
```

---

## 22. Final Takeaway

We built a leak-free, deterministic weekly gateway ranking pipeline that converts raw IoT telemetry into verified, high-yield field inspection recommendations under strict operational capacity constraints.

Faced with a 60.7% historical false alarm rate and an asymmetric economic cost proxy (€380 false visit penalty vs. €600/week missed broken gateway proxy), we resisted the temptation to deploy fragile, over-parameterized machine learning models that increase false dispatches. Instead, 26 weeks of historical backtesting proved that `Baseline_3Sigma` delivered the best operational trade-off—capturing 41 repairs with only 14 false alarms and the lowest combined cost proxy (€50,320). 

We engineered production controls around this baseline: robust ID canonicalization, deterministic deduplication, lifecycle fleet gating, Option B silent-gateway retention, and non-causal reason generation. The resulting pipeline runs in ~7 seconds, is 100% reproducible, and passes official validation without errors. With Part 1 complete and verified, the project now advances to Part 2 to deliver a robust, containerized software service.
