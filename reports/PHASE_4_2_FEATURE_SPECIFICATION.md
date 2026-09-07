# Phase 4.2 — Candidate Feature Specification

**Project:** LPDG Innovation Hub Selection Challenge 2026 (NEXORA 2026)  
**Author:** Candidate Engineering Team  
**Phase Status:** Micro-Phase 4.2 — Candidate Feature Specification (Audited & Factually Verified)  
**Date:** September 2026  
**Reference Documents:**  
- [PHASE_3_DEEP_DATA_INVESTIGATION.md](PHASE_3_DEEP_DATA_INVESTIGATION.md)  
- [PHASE_3_VERIFICATION.md](PHASE_3_VERIFICATION.md)  
- [PHASE_3_EXPLAINED.md](PHASE_3_EXPLAINED.md)  
- [PHASE_4_1_OPERATIONAL_DEFINITION.md](PHASE_4_1_OPERATIONAL_DEFINITION.md)  
- `baseline_3sigma.py`  
- Challenge Brief & Data Dictionary  

---

## 1. Objective

The objective of Micro-Phase 4.2 is to translate the qualitative operational framework established in Phase 4.1 into a rigorous, mathematically sound, leak-free, and factually verified **Candidate Feature Specification**.

In Phase 4.1, we conceptualized what "Gateway Needs a Visit" means in an operational utility IoT network: a persistent operational condition that halts downstream packet relay, cannot be resolved remotely, and carries sufficient business urgency to warrant one of the 15 available weekly technician dispatches. In Phase 4.2, we formalize **what can be measured** from the local historical data and **how those candidate features must be computed** prior to any ranking or model training.

### Explicit Micro-Phase Boundaries
To preserve absolute engineering rigor and prevent premature assumptions, the following boundaries are strictly enforced:
- **NO final ranking formulas:** We do not define composite ranking equations or scoring weights.
- **NO arbitrary feature weights:** We do not assign subjective weights ($w_1, w_2, \dots$).
- **NO machine learning training:** No classifiers, regressors, or unsupervised models are fitted.
- **NO premature threshold tuning:** Numerical cutoffs (e.g. 48h vs 72h silence, 5 vs 10 reboots) are explicitly designated as **Candidate Parameters** to be empirically calibrated during Phase 6 backtesting.
- **NO code or baseline changes:** `baseline_3sigma.py`, `validate_submission.py`, and Git history remain completely untouched.

This document serves as the architectural specification for Phase 5 (Feature Store Implementation) and Phase 6 (Empirical Backtesting & Validation).

---

## 2. Feature Design Principles

Every candidate feature specified in this document adheres to eight foundational design principles:

1. **Grounded Operational Meaning:** The feature must correspond to an observable operational condition (e.g. communication blackout, reboot instability, prolonged offline duration, or chronic packet deficit). It must not be an ungrounded statistical abstraction.
2. **Strict Temporal Integrity (Leak-Free):** Features evaluated for prediction Monday $T$ must consume data strictly from $t < T$. No information timestamped at or after $T$ may enter the computation.
3. **Robustness to Implicit Missingness:** Because dead gateways emit zero telemetry rows, features must explicitly account for absent records rather than computing aggregations solely over surviving rows.
4. **Empirically Verified Counter Semantics:** Features utilizing counters (`offline_duration_sec`, `reboot_duration_sec`) must account for cumulative accumulation and counter resets rather than naively summing raw values.
5. **Deduplication Precedence:** Exact telemetry duplicate records verified in Phase 3 (exactly 6,547 rows) must be eliminated prior to any aggregation.
6. **Lifecycle Awareness:** Features must recognize when an asset is inactive or not yet commissioned, preventing false alarm dispatches on non-operational assets.
7. **Sensitivity vs. Specificity Trade-Off:** Each feature is explicitly evaluated for its potential failure modes—what external benign conditions could mimic a fault (e.g. carrier network outages, scheduled power maintenance).
8. **Multi-Dimensional Validation:** Candidate features will not be evaluated or eliminated based on a single statistical test (such as a p-value threshold). They will be validated across multiple dimensions: statistical separability, repair precision on historical visits, false positive penalty (€380), unaddressed outage penalty (€600), and incremental ranking utility under a 15-visit capacity cap.

---

## 3. Temporal Contract

To guarantee that the ranking pipeline remains completely leak-free and production-viable, we establish a strict **Temporal Information Contract**.

```
                           Information Horizon: Monday 00:00:00 UTC (T)
                                              |
[===== Historical Window: t < T =====)       |  [===== Future Scored Week: t >= T =====)
---------------------------------------------+------------------------------------------
Trailing 28-day window: [T - 28d, T)         |  Technician dispatches executed
Trailing 7-day window:  [T - 7d,  T)         |  Outage penalties accrue if unvisited
                                             |  NO TELEMETRY OR METER DATA PERMITTED
```

### 3.1 Strict Right-Open Window Definition
For any prediction Monday $T$ (where $T \in \{	ext{2026-02-02}, 	ext{2026-02-09}, \dots, 	ext{2026-03-23}\}$):
$$	ext{Window}_{	ext{trailing\_7d}} = [T - 7	ext{ days}, T) \equiv \{t \mid T - 7	ext{ days} \le t < T\}$$
$$	ext{Window}_{	ext{trailing\_28d}} = [T - 28	ext{ days}, T) \equiv \{t \mid T - 28	ext{ days} \le t < T\}$$

- **Right-Open Interval:** The upper boundary is strictly $t < T$, NOT $t \le T$. Any telemetry packet timestamped at exactly $T$ (e.g. `2026-02-02 00:00:00 UTC`) or later belongs to the upcoming week and is strictly forbidden during feature generation.
- **Operational Reality:** In production, the optimization pipeline runs at midnight on Monday morning to generate work orders for the field technician crew arriving at 07:00. Telemetry generated after 00:00:00 UTC is physically unavailable to the scheduling system.

### 3.2 Information Cutoff Across Challenge Datasets

| Dataset | Raw Time Range | Usable Range for Prediction Monday $T$ | Temporal Restrictions & Safeguards |
| :--- | :--- | :--- | :--- |
| `telemetry/` | 2025-08-01 00:00:00Z to 2026-03-31 23:00:00Z | $[T - 28	ext{d}, T)$ | Filter strictly on `ts < T`. Never inspect $t \ge T$. |
| `gateway_master.csv` | Asset register (static snapshot) | Static properties + temporal filter | Assets must satisfy $	ext{installed\_on} \le T$ and $(	ext{decommissioned\_on} > T 	ext{ or null})$. |
| `meter_read_success.csv` | 2025-08-04 to 2026-01-26 (26 weekly Mondays) | $[T - 28	ext{d}, \min(T, 	ext{2026-01-26})]$ | **Data Cliff:** Concludes on Jan 26, 2026. Zero records exist during February and March 2026. Can only serve as a static pre-February prior, never a live weekly indicator. |
| `field_visits.csv` | 2025-02-03 to 2026-01-30 (work orders); visits to 2026-02-14 | Work orders with $	ext{created\_at} < T$ | Historical outcomes inform priors; future work orders must not leak into early weeks. |
| `engineer_review_2026-02.xlsx` | 2026-02-15 (single audit date) | Entries where $	ext{review\_date} < T$ | Conducted on 2026-02-15. Cannot be used for Week 1 (Feb 2) or Week 2 (Feb 9). |

---

## 4. Gateway ID Contract

Phase 3 uncovered an exact formatting divergence across project files that causes naive cross-table joins to fail completely.

### 4.1 Actual ID Formats Discovered in Phase 3
Empirical verification confirmed two distinct representations of 6-byte gateway MAC identifiers:
1. **Colon-delimited 17-character hexadecimal string** (`XX:XX:XX:XX:XX:XX`, uppercase):
   - `gateway_master.csv` (e.g. `06:39:EA:56:02:C1`, `0A:56:03:8B:20:D0`, `0E:5D:FC:F6:5A:D4`)
   - `field_visits.csv` (e.g. `02:30:EE:F7:24:35`)
   - `engineer_review_2026-02.xlsx` (e.g. `06:5B:92:87:16:CD`)
2. **Bare 12-character hexadecimal string** (`XXXXXXXXXXXX`, uppercase):
   - `telemetry` Parquet partitions (e.g. `0639EA5602C1`)
   - `meter_read_success.csv` (e.g. `0202CB0A6B1F`)

An unnormalized SQL or Pandas inner join between `gateway_master.csv` and `telemetry` yields **exactly 0 matching rows**.

### 4.2 Canonical Representation & Normalization Rules
To prevent silent join failures, we establish the **Canonical Gateway ID Standard**:

$$	ext{Canonical ID Format: 12-character bare uppercase hex } (	exttt{0639EA5602C1})$$

The canonical normalization function is:
$$	ext{normalize\_id}(s) = s	ext{.strip}().	ext{replace}(':', '').	ext{upper}()$$

- **Contract Invariant:** All internal joins, merges, lookups, and feature keys must operate strictly on the 12-character canonical bare hex ID.
- **Submission Output:** `validate_submission.py` accepts either format in `predictions.csv`. However, internal pipeline integrity requires uniform canonical keys.

---

## 5. Duplicate Handling Contract

In Phase 3 and Phase 3.1, direct data verification established the exact properties of duplicate records in the telemetry dataset:

### 5.1 Verified Duplicate Statistics
- **Duplicate Key Count:** Grouping by the primary business key `(gateway_id, ts_utc)` reveals **exactly 6,547 duplicate records** across the 1,433,387 total rows.
- **Full-Row Duplicate Count:** Evaluating duplicates across all 57 columns simultaneously reveals **exactly the same 6,547 duplicate records**.
- **Population Identity:** The duplicate business keys and full-row duplicates are **identically the same rows**. There are no conflicting timestamp collisions (where the same gateway and timestamp have divergent sensor values).
- **Temporal Distribution:** Duplicates occur exclusively in odd-month partitions:
  - `month=2025-08`: 0 duplicates
  - `month=2025-09`: **2,185 duplicates**
  - `month=2025-10`: 0 duplicates
  - `month=2025-11`: **2,124 duplicates**
  - `month=2025-12`: 0 duplicates
  - `month=2026-01`: **2,238 duplicates**
  - `month=2026-02`: 0 duplicates
  - `month=2026-03`: 0 duplicates

### 5.2 Deduplication Invariant
Before any temporal slicing, window aggregation, differencing, or feature extraction, the raw telemetry partition must undergo deduplication:

$$\mathcal{D}_{	ext{clean}} = \mathcal{D}_{	ext{raw}}.	ext{drop\_duplicates}(	ext{subset}=[	exttt{"gateway\_id"}, 	exttt{"ts\_utc"}], 	ext{keep}=	exttt{"first"})$$

**Why Aggregation Must Happen After Deduplication:**
If aggregations are executed prior to deduplication, hourly metrics in odd months are counted twice for duplicate timestamps, overcounting unadjusted sums by ~1.2% to 1.3% and producing artificial zero-second consecutive timestamp intervals ($\Delta t = 0$).

---

## 6. Cumulative Counter Handling Contract

Phase 3 and Data Dictionary verification established an essential distinction in telemetry column semantics: **some columns are incremental hourly event counts, while others behave as cumulative counters accumulating across multi-hour or multi-day intervals.**

### 6.1 Verified Metric Semantics

| Column | Data Dictionary Definition | Empirical Behavior & Extremes | Nature |
| :--- | :--- | :--- | :--- |
| `reboot_cnt` | "Reboots during the hour." | Max: 32 reboots/hour. 3,778 rows $>0$ in Aug 2025. | **Incremental hourly count** |
| `disconnection_cnt` | "Backhaul disconnection events during the hour." | Max: 55 events/hour. 40,199 rows $>0$ in Aug 2025. | **Incremental hourly count** |
| `offline_duration_sec` | "Backhaul offline time counter, seconds." | Max: **726,642 seconds** (~201.8h / 8.4d). 8,354 rows $> 3,600	ext{s}$ (4.60%) in Aug. | **Cumulative firmware counter** |
| `reboot_duration_sec` | "Total time spent rebooting during the hour, seconds." | Max: **439,061 seconds** (~121.9h / 5.1d). 921 rows $> 3,600	ext{s}$ (0.51%) in Aug. | **Cumulative firmware counter** |

### 6.2 The Danger of Naive Summation on Cumulative Counters
Because `offline_duration_sec` accumulates over consecutive outage hours, naively summing raw values:
$$	ext{Naive Sum} = \sum_{t} 	exttt{offline\_duration\_sec}_t$$
artificially squares the outage impact. For example, if a gateway is offline for 5 consecutive hours reporting cumulative values $[3600, 7200, 10800, 14400, 18000]$, the naive sum is $54,000	ext{ seconds}$ (15 hours), whereas the physical elapsed downtime was only $18,000	ext{ seconds}$ (5 hours).

### 6.3 Candidate Counter Transformation Approaches

To handle cumulative counters rigorously, we specify candidate transformations:

#### Approach 1: Consecutive Positive Differencing ($\Delta C$)
For consecutive telemetry rows sorted by timestamp:
$$\Delta C_i = egin{cases} 
C_i - C_{i-1} & 	ext{if } C_i \ge C_{i-1} \
C_i & 	ext{if } C_i < C_{i-1} 	ext{ (counter reset)}
\end{cases}$$
$$	ext{Total Incremental Offline} = \sum_{i} \Delta C_i$$

#### Approach 2: Windowed Peak Envelope ($\max C$)
Within trailing window $W$:
$$	ext{Peak\_Offline}_W = \max_{t \in W} (	exttt{offline\_duration\_sec}_{i, t})$$
- **Operational Meaning:** Represents the single longest continuous outage spell reported by the gateway during the window.
- **Advantage:** Completely immune to packet sampling rates or intermediate resets.

#### Approach 3: Severe State Indicator Count
$$	ext{Severe\_Offline\_Hours}_W = \sum_{t \in W} \mathbb{I}(	exttt{offline\_duration\_sec}_{i, t} \ge 3600)$$
- **Operational Meaning:** Counts the number of hours where the device reported an accumulated offline spell exceeding 1 hour.

### 6.4 Unresolved Counter-Gap Semantics (To Validate in Phase 5)
When a gateway experiences a multi-day silent gap and subsequently reconnects:
- *Scenario A:* The first post-reconnection packet reports the total accumulated offline seconds elapsed during the blackout.
- *Scenario B:* The counter reset to zero upon reboot, reporting only post-boot offline seconds.
- *Specification Decision:* Rather than assuming Scenario A or B, the feature store will compute both **Observed Peak Envelope** and **Differenced Delta**, keeping observed counter values strictly separate from inferred silence duration. The exact empirical behavior across reconnection events will be validated directly in Phase 5.

---

## 7. Telemetry Completeness Features (Silence & Communication Loss)

In Phase 3, we observed that catastrophic failure modes often result in complete absence of telemetry records. The provided baseline is completely blind to silent gateways because it filters strictly on rows present in the recent window.

### 7.1 Interpretation of Silence
Silence indicates a **severe loss of communication between the gateway and the central telemetry ingestion server**. It does not inherently prove that the gateway motherboard is physically destroyed. Silence can stem from multiple operational causes:
1. Complete loss of site AC power (utility power cut or building maintenance);
2. Internal power supply or component failure (requiring `Netzteil` or `Gateway getauscht`);
3. Cellular network outage or SIM card deactivation (`SIM-Karte`);
4. Severe antenna / RF cable disconnection (`Antenne`, `Kabel`);
5. Asset de-installation or decommissioning.

Regardless of cause, an active, commissioned gateway that goes completely silent cannot relay utility meter readings. If the silence persists, it warrants operational investigation.

### 7.2 Feature Specifications

#### F01: `reported_hours_7d`
- **Operational Meaning:** Total hours in trailing 7 days with at least one reported telemetry packet.
- **Raw Columns Used:** `gateway_id`, `ts_utc`.
- **Transformation:** Count of unique hourly timestamps in $[T - 7	ext{d}, T)$:
  $$F01_i = |\mathcal{H}_i(W_7)|$$
- **Window:** Trailing 7 days, $[T - 7	ext{d}, T)$.
- **Temporal Safety:** Safe ($t < T$).
- **Potential Failure Mode:** Does not differentiate between an asset that reported 1 hour every day vs an asset that died 5 days ago.
- **Validation Method:** Correlate with historical work orders requiring hardware replacement.
- **Candidate Priority:** **HIGH**

#### F02: `missing_hours_7d`
- **Operational Meaning:** Hourly telemetry packet deficit relative to continuous 168-hour operation.
- **Raw Columns Used:** `gateway_id`, `ts_utc`.
- **Transformation:**
  $$F02_i = 168 - |\mathcal{H}_i(W_7)|$$
- **Window:** Trailing 7 days, $[T - 7	ext{d}, T)$.
- **Temporal Safety:** Safe ($t < T$).
- **Potential Failure Mode:** Normal active gateways exhibit baseline missingness (~13.5% active drop-out rate). Benign intermittent reporting can be mistaken for failure without baseline comparison.
- **Validation Method:** Evaluate separability between healthy baseline missingness and failure missingness.
- **Candidate Priority:** **HIGH**

#### F03: `reporting_ratio_7d`
- **Operational Meaning:** Normalized telemetry availability fraction.
- **Raw Columns Used:** `reported_hours_7d`.
- **Transformation:**
  $$F03_i = rac{|\mathcal{H}_i(W_7)|}{168.0} \in [0.0, 1.0]$$
- **Window:** Trailing 7 days, $[T - 7	ext{d}, T)$.
- **Temporal Safety:** Safe ($t < T$).
- **Potential Failure Mode:** Collinear with F01, but scale-invariant across variable window lengths.
- **Validation Method:** Distributional check across active vs decommissioned assets.
- **Candidate Priority:** **MEDIUM**

#### F04: `consecutive_missing_at_cutoff`
- **Operational Meaning:** Duration of ongoing communication silence leading directly up to prediction Monday $T$.
- **Raw Columns Used:** `ts_utc` relative to $T$.
- **Transformation:** Elapsed hours between $T$ and the latest reported packet timestamp prior to $T$:
  $$F04_i = rac{T - \max \{t \in \mathcal{H}_i \mid t < T\}}{3600	ext{ seconds}}$$
  *(If zero packets exist in the trailing 28 days, bounded at $F04_i = 672	ext{ hours}$)*.
- **Window:** Trailing 28 days evaluated relative to $T$.
- **Temporal Safety:** Safe ($t < T$).
- **Potential Failure Mode:** A transient cell-tower outage occurring 2 hours before cutoff ($F04 = 2	ext{h}$) could appear alarming. Requires candidate persistence parameter (e.g. candidate cutoff $\ge 48	ext{h}$ or $72	ext{h}$, to be tuned in Phase 6).
- **Validation Method:** Compare against `Keine Verbindung` work orders that resulted in physical repairs.
- **Candidate Priority:** **HIGH**

#### F05: `is_completely_silent_7d`
- **Operational Meaning:** Binary indicator of zero telemetry packets throughout the entire trailing 7-day window.
- **Raw Columns Used:** `reported_hours_7d`.
- **Transformation:**
  $$F05_i = \mathbb{I}(|\mathcal{H}_i(W_7)| == 0)$$
- **Window:** Trailing 7 days, $[T - 7	ext{d}, T)$.
- **Temporal Safety:** Safe ($t < T$).
- **Potential Failure Mode:** Identifies assets completely invisible to `baseline_3sigma.py`. However, if evaluated without lifecycle filtering, it flags uninstalled or decommissioned gateways.
- **Validation Method:** Cross-reference silent gateways against subsequent meter-read loss and field visits.
- **Candidate Priority:** **HIGH**

---

## 8. Offline Features

These features measure downtime reported by gateways that are actively communicating but experiencing internal or backhaul outages.

### 8.1 Feature Specifications

#### F06: `offline_duration_max_7d` (Observed Peak Outage Envelope)
- **Operational Meaning:** Longest continuous offline spell reported by the gateway during the trailing 7 days.
- **Raw Columns Used:** `offline_duration_sec`.
- **Transformation:**
  $$F06_i = \max_{t \in W_7, 	ext{observed}} (	exttt{offline\_duration\_sec}_{i, t})$$
  *(Note: Strictly computed over observed packets. Not imputed from silence).*
- **Window:** Trailing 7 days, $[T - 7	ext{d}, T)$.
- **Temporal Safety:** Safe ($t < T$).
- **Potential Failure Mode:** Undefined (null) if the device is 100% silent (silence is tracked separately by F04/F05).
- **Validation Method:** Measure separation on historical visits where components were replaced vs no fault found.
- **Candidate Priority:** **HIGH**

#### F07: `offline_duration_delta_7d` (Differenced Incremental Downtime)
- **Operational Meaning:** Sum of incremental downtime advances across the trailing 7 days, neutralizing cumulative counter compounding.
- **Raw Columns Used:** `offline_duration_sec`, sorted by timestamp.
- **Transformation:** Positive consecutive differencing with reset handling:
  $$F07_i = \sum_{k} \max(0, \Delta 	exttt{offline\_duration\_sec}_{i, k})$$
- **Window:** Trailing 7 days, $[T - 7	ext{d}, T)$.
- **Temporal Safety:** Safe ($t < T$).
- **Potential Failure Mode:** Dependent on counter behavior across resets; sensitive to missing intermediate packets.
- **Validation Method:** Test whether differenced offline time correlates more strongly with downstream meter loss than raw peak envelope.
- **Candidate Priority:** **MEDIUM**

#### F08: `offline_hours_gt_3600_7d` (Severe Downtime Hour Count)
- **Operational Meaning:** Frequency of reporting hours where accumulated offline duration exceeded 1 hour (3,600 seconds).
- **Raw Columns Used:** `offline_duration_sec`.
- **Transformation:**
  $$F08_i = \sum_{t \in W_7} \mathbb{I}(	exttt{offline\_duration\_sec}_{i, t} \ge 3600)$$
- **Window:** Trailing 7 days, $[T - 7	ext{d}, T)$.
- **Temporal Safety:** Safe ($t < T$).
- **Potential Failure Mode:** A single multi-day outage will flag every hour that reports upon reconnection, potentially compounding the score.
- **Validation Method:** Cross-tabulate with work orders logged under `Keine Verbindung` and `Haeufige Neustarts`.
- **Candidate Priority:** **MEDIUM**

---

## 9. Reboot Features

Reboot features identify power supply instability, watchdog timer resets, and firmware crash loops.

### 9.1 Feature Specifications

#### F09: `reboot_cnt_sum_7d` (Weekly Reboot Volume)
- **Operational Meaning:** Total reboot events initiated in the trailing 7 days.
- **Raw Columns Used:** `reboot_cnt`.
- **Transformation:** Sum of hourly reboot increments:
  $$F09_i = \sum_{t \in W_7} 	exttt{reboot\_cnt}_{i, t}$$
  *(Verified in Section 6: `reboot_cnt` is an incremental hourly count, max 32).*
- **Window:** Trailing 7 days, $[T - 7	ext{d}, T)$.
- **Temporal Safety:** Safe ($t < T$).
- **Potential Failure Mode:** A benign scheduled remote firmware update can cause 1–2 reboots across multiple gateways simultaneously.
- **Validation Method:** Precision on historical `Haeufige Neustarts` visits (historically 56.4% physical repair rate).
- **Candidate Priority:** **HIGH**

#### F10: `reboot_cnt_sum_28d` (Chronic Reboot Baseline)
- **Operational Meaning:** Long-term chronic reboot instability across a 4-week window.
- **Raw Columns Used:** `reboot_cnt`.
- **Transformation:** Sum over 28-day trailing window:
  $$F10_i = \sum_{t \in W_{28}} 	exttt{reboot\_cnt}_{i, t}$$
- **Window:** Trailing 28 days, $[T - 28	ext{d}, T)$.
- **Temporal Safety:** Safe ($t < T$).
- **Potential Failure Mode:** May dilute the operational urgency of an acute reboot storm that started 48 hours ago.
- **Validation Method:** Test whether combining 28d and 7d metrics improves ranking stability.
- **Candidate Priority:** **MEDIUM**

#### F11: `reboot_intensity_ratio` (Acute Reboot Acceleration)
- **Operational Meaning:** Ratio of recent 7-day reboot volume relative to weekly average over trailing 28 days.
- **Raw Columns Used:** `reboot_cnt_sum_7d`, `reboot_cnt_sum_28d`.
- **Transformation:**
  $$F11_i = rac{F09_i}{\max(1.0, F10_i / 4.0)}$$
- **Window:** 7-day vs 28-day trailing comparison prior to $T$.
- **Temporal Safety:** Safe ($t < T$).
- **Potential Failure Mode:** High variance when baseline reboot counts are small (e.g. $0 	o 2$ reboots yields a high ratio). Requires candidate volume threshold.
- **Validation Method:** Evaluate ranking precision when paired with a minimum count candidate parameter ($F09 \ge 5$).
- **Candidate Priority:** **MEDIUM**

---

## 10. Disconnection Features

Disconnection features measure backhaul cellular bearer drops and connectivity instability.

### 10.1 Feature Specifications

#### F12: `disconnection_cnt_sum_7d` (Total Connection Drops)
- **Operational Meaning:** Total backhaul connection drops in the trailing 7 days.
- **Raw Columns Used:** `disconnection_cnt`.
- **Transformation:** Sum of hourly disconnection increments:
  $$F12_i = \sum_{t \in W_7} 	exttt{disconnection\_cnt}_{i, t}$$
  *(Verified in Section 6: `disconnection_cnt` is an incremental hourly count, max 55).*
- **Window:** Trailing 7 days, $[T - 7	ext{d}, T)$.
- **Temporal Safety:** Safe ($t < T$).
- **Potential Failure Mode:** Cellular carrier cell-tower maintenance can induce temporary connection drops across many gateways without physical fault.
- **Validation Method:** Measure correlation with historical antenna and cable replacements in `field_visits.csv`.
- **Candidate Priority:** **MEDIUM**

#### F13: `disconn_to_offline_ratio` (Connection Flapping vs Stagnation)
- **Operational Meaning:** Ratio of disconnection events per offline hour, distinguishing connection flapping from continuous stagnation.
- **Raw Columns Used:** `disconnection_cnt_sum_7d`, `offline_duration_max_7d`.
- **Transformation:**
  $$F13_i = rac{F12_i}{\max(1.0, F06_i / 3600.0)}$$
- **Window:** Trailing 7 days, $[T - 7	ext{d}, T)$.
- **Temporal Safety:** Safe ($t < T$).
- **Potential Failure Mode:** High numerical volatility when offline duration is small.
- **Validation Method:** Evaluate diagnostic utility on distinguishing antenna/cable faults from power supply faults.
- **Candidate Priority:** **LOW**

---

## 11. Combined Operational Degradation Features (Syndromes)

A single sensor metric rarely justifies a €380 technician dispatch. Real-world operational degradation typically manifests as **correlated distress across multiple subsystems** (e.g. repeated reboots accompanied by prolonged downtime).

### 11.1 Feature Specifications

#### F14: `reboot_and_offline_syndrome` (Crash Loop Syndrome)
- **Operational Meaning:** Simultaneous presence of elevated reboots and prolonged downtime.
- **Raw Columns Used:** `reboot_cnt_sum_7d`, `offline_duration_max_7d`.
- **Transformation:** Candidate non-linear interaction indicator:
  $$F14_i = \mathbb{I}(F09_i \ge 	heta_{	ext{reboot}}) 	imes \mathbb{I}(F06_i \ge 	heta_{	ext{offline}})$$
  *(Candidate Parameters to tune: $	heta_{	ext{reboot}} \in [3, 10]$, $	heta_{	ext{offline}} \in [3600	ext{s}, 14400	ext{s}]$)*.
- **Window:** Trailing 7 days, $[T - 7	ext{d}, T)$.
- **Temporal Safety:** Safe ($t < T$).
- **Potential Failure Mode:** Binary indicator does not provide granular ranking among multiple failing units.
- **Validation Method:** Historical repair precision on work orders with both symptoms.
- **Candidate Priority:** **HIGH**

#### F15: `flapping_and_offline_syndrome` (Unstable Link Syndrome)
- **Operational Meaning:** High disconnection frequency combined with elevated downtime.
- **Raw Columns Used:** `disconnection_cnt_sum_7d`, `offline_duration_max_7d`.
- **Transformation:** Candidate interaction indicator:
  $$F15_i = \mathbb{I}(F12_i \ge 	heta_{	ext{disconn}}) 	imes \mathbb{I}(F06_i \ge 	heta_{	ext{offline}})$$
  *(Candidate Parameters: $	heta_{	ext{disconn}} \in [15, 30]$, $	heta_{	ext{offline}} \in [7200	ext{s}, 28800	ext{s}]$)*.
- **Window:** Trailing 7 days, $[T - 7	ext{d}, T)$.
- **Temporal Safety:** Safe ($t < T$).
- **Potential Failure Mode:** May capture external carrier network instability if regional towers are disrupted.
- **Validation Method:** Cross-check against antenna/cable replacement logs.
- **Candidate Priority:** **MEDIUM**

#### F16: `acute_chronic_divergence` (Sudden Operational Collapse)
- **Operational Meaning:** Asset exhibited stable reporting during the prior 3 weeks but suffered sudden collapse in the trailing 7 days.
- **Raw Columns Used:** Telemetry hourly presence in $[T - 28	ext{d}, T - 7	ext{d})$ vs $[T - 7	ext{d}, T)$.
- **Transformation:** Drop in reporting availability:
  $$F16_i = \max\left(0, rac{|\mathcal{H}_i(W_{	ext{prior\_21d}})|}{21 	imes 24} - rac{|\mathcal{H}_i(W_{	ext{trailing\_7d}})|}{7 	imes 24}ight)$$
- **Window:** Trailing 28 days vs trailing 7 days prior to $T$.
- **Temporal Safety:** Safe ($t < T$).
- **Potential Failure Mode:** Gateway that was already dead throughout the entire 28 days will have divergence 0 (handled by F04/F05).
- **Validation Method:** Verify onset timing against ticket creation dates in `field_visits.csv`.
- **Candidate Priority:** **HIGH**

---

## 12. Historical Meter-Read Reliability Features

The Challenge Brief highlights meter-reading reliability as the fundamental business deliverable. However, Phase 3 discovered a critical temporal boundary: **`meter_read_success.csv` ends on January 26, 2026.**

### 12.1 The January 26 Cliff Limitation
- The dataset covers 26 weekly Monday reporting periods: `2025-08-04` through `2026-01-26`.
- Scored evaluation Mondays span `2026-02-02` through `2026-03-23`.
- During the scored evaluation period, **exactly 0 meter-read records exist**.
- Meter success data **cannot be used as a dynamic weekly feature**. It can only function as a **static historical asset baseline prior** computed strictly before January 26, 2026.

### 12.2 Feature Specifications

#### F17: `hist_meter_success_pre_feb` (Historical Collection Baseline)
- **Operational Meaning:** Gateway's historical meter reading success rate prior to the scored period.
- **Raw Columns Used:** `meters_read`, `meters_expected` from `meter_read_success.csv`.
- **Transformation:** Aggregated across all historical records prior to $T$ (and prior to Jan 26):
  $$F17_i = rac{\sum_{t < \min(T, 	ext{2026-01-26})} 	exttt{meters\_read}_{i, t}}{\sum_{t < \min(T, 	ext{2026-01-26})} 	exttt{meters\_expected}_{i, t}}$$
- **Window:** Static pre-February window (`2025-08-04` to `2026-01-26`).
- **Temporal Safety:** Safe ($t \le 	ext{2026-01-26} < T$).
- **Potential Failure Mode:** **Stale during live evaluation.** Cannot detect new acute failures occurring in February or March 2026.
- **Validation Method:** Test whether historical low performers correlate with chronic field visit requirements.
- **Candidate Priority:** **MEDIUM (Static Prior / Secondary Context)**

#### F18: `hist_meter_outage_freq` (Historical Zero-Read Frequency)
- **Operational Meaning:** Fraction of monitored historical weeks where zero meters were successfully read.
- **Raw Columns Used:** `meters_read` from `meter_read_success.csv`.
- **Transformation:**
  $$F18_i = rac{1}{N_{	ext{weeks}}} \sum_{t < \min(T, 	ext{2026-01-26})} \mathbb{I}(	exttt{meters\_read}_{i, t} == 0)$$
- **Window:** Static pre-February window.
- **Temporal Safety:** Safe ($t < T$).
- **Potential Failure Mode:** Stale; does not capture recent state changes.
- **Validation Method:** Regression against total work orders logged in 2025.
- **Candidate Priority:** **LOW**

---

## 13. Lifecycle Eligibility Features

Dispatching a technician to a gateway that is not yet commissioned or has already been decommissioned results in a guaranteed €380 wasted visit. In Phase 3, census analysis proved that 12 gateways in Master were commissioned in mid-2026 (May–July 2026) and 12 were decommissioned before March 2026.

### 13.1 Schema Verification
In `gateway_master.csv`:
- `installed_on` (ISO-8601 string `YYYY-MM-DD`): Date the gateway was commissioned. Populated for all 332 gateways.
- `decommissioned_on` (ISO-8601 string `YYYY-MM-DD`): Date the gateway was taken out of service. Populated for 12 gateways; null for 320 gateways.

### 13.2 Feature Specifications

#### F19: `is_lifecycle_active` (Master Eligibility Filter)
- **Operational Meaning:** Confirms whether the physical asset is actively in service on prediction Monday $T$.
- **Raw Columns Used:** `installed_on`, `decommissioned_on` from `gateway_master.csv`.
- **Transformation:** Strict boolean validity check:
  $$F19_i(T) = \mathbb{I}\Big((	exttt{installed\_on}_i \le T) \;\land\; (	exttt{decommissioned\_on}_i 	ext{ is null} \;\lor\; 	exttt{decommissioned\_on}_i > T)\Big)$$
- **Window:** Evaluated at prediction date $T$.
- **Temporal Safety:** Safe (metadata installation date $t \le T$).
- **Potential Failure Mode:** Date parsing errors or timezone shifts. Must parse strictly as UTC dates.
- **Validation Method:** Verify that none of the 12 future-installed gateways (May–July 2026) are marked active.
- **Candidate Priority:** **HIGH (Hard Operational Precondition / Gate)**

#### F20: `installed_age_days` (Installation Operational Lifespan)
- **Operational Meaning:** Elapsed days since the gateway was commissioned.
- **Raw Columns Used:** `installed_on` relative to $T$.
- **Transformation:**
  $$F20_i(T) = rac{T - 	exttt{installed\_on}_i}{1	ext{ day}}$$
- **Window:** Evaluated at date $T$.
- **Temporal Safety:** Safe ($t \le T$).
- **Potential Failure Mode:** Installation age alone does not prove acute failure in a specific week.
- **Validation Method:** Evaluate survival correlation with component replacement in historical logs.
- **Candidate Priority:** **LOW (Secondary Tie-Breaker)**

---

## 14. Complete Feature Specification Table

The following master table details all 20 candidate features, fully aligned with detailed specifications.  
*(Note: Candidate Priority denotes architectural feasibility and operational importance, NOT final ranking weights).*

| ID | Feature Name | Operational Meaning | Raw Columns Used | Transformation / Logic | Window | Temporal Safety | Potential Failure Mode | Validation Method | Candidate Priority |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **F01** | `reported_hours_7d` | Operational presence / volume | `gateway_id`, `ts_utc` | Count of unique reporting hours | 7d $[T-7	ext{d}, T)$ | Safe ($t < T$) | Blurs acute death vs intermittent reporting | Separability on historical work orders | **HIGH** |
| **F02** | `missing_hours_7d` | Packet deficit relative to continuous | `gateway_id`, `ts_utc` | $168 - 	ext{distinct hours}$ | 7d $[T-7	ext{d}, T)$ | Safe ($t < T$) | Confuses normal sleep with failure | Correlation with unaddressed outage costs | **HIGH** |
| **F03** | `reporting_ratio_7d` | Normalized availability fraction | `reported_hours_7d` | $	ext{hours} / 168.0$ | 7d $[T-7	ext{d}, T)$ | Safe ($t < T$) | Collinear with F01 | Distributional audit across fleet | **MEDIUM** |
| **F04** | `consecutive_missing_at_cutoff` | Active ongoing silence at Monday cutoff | `ts_utc` vs $T$ | $(T - t_{	ext{latest}}) / 3600	ext{s}$ | 28d $[T-28	ext{d}, T)$ | Safe ($t < T$) | Short transient outage ($< 6	ext{h}$) appears alarming | Cross-check with `Keine Verbindung` repairs | **HIGH** |
| **F05** | `is_completely_silent_7d` | Complete blackout indicator | `reported_hours_7d` | $\mathbb{I}(	ext{hours} == 0)$ | 7d $[T-7	ext{d}, T)$ | Safe ($t < T$) | Flags decommissioned assets if unmasked | Audit baseline blind spot on zero-row units | **HIGH** |
| **F06** | `offline_duration_max_7d` | Peak observed continuous outage | `offline_duration_sec` | $\max(	exttt{offline\_sec})$ | 7d $[T-7	ext{d}, T)$ | Safe ($t < T$) | Undefined (null) if device is 100% silent | Threshold calibration against repairs | **HIGH** |
| **F07** | `offline_duration_delta_7d` | Differenced incremental downtime | `offline_duration_sec` | Positive diffing $\sum \max(0, \Delta C)$ | 7d $[T-7	ext{d}, T)$ | Safe ($t < T$) | Sensitive to missing intermediate packets | Correlation with downstream meter loss | **MEDIUM** |
| **F08** | `offline_hours_gt_3600_7d` | Frequency of severe outage hours | `offline_duration_sec` | $\sum \mathbb{I}(C \ge 3600)$ | 7d $[T-7	ext{d}, T)$ | Safe ($t < T$) | Compounding over-count on multi-day outage | Cross-tabulate with work order logs | **MEDIUM** |
| **F09** | `reboot_cnt_sum_7d` | Weekly reboot increment volume | `reboot_cnt` | Sum of hourly increments | 7d $[T-7	ext{d}, T)$ | Safe ($t < T$) | Scheduled remote firmware update induces 1–2 reboots | Precision on `Haeufige Neustarts` | **HIGH** |
| **F10** | `reboot_cnt_sum_28d` | Chronic reboot baseline | `reboot_cnt` | Sum over 28 days | 28d $[T-28	ext{d}, T)$ | Safe ($t < T$) | Dilutes acute sudden failure | Ranking stability testing | **MEDIUM** |
| **F11** | `reboot_intensity_ratio` | Surge in reboot instability | `reboot_cnt_7d`, `28d` | Ratio $7	ext{d} / (28	ext{d}/4)$ | 28d $[T-28	ext{d}, T)$ | Safe ($t < T$) | High variance on small counts ($0 	o 1$) | Precision testing with min volume cutoff | **MEDIUM** |
| **F12** | `disconnection_cnt_sum_7d` | Cellular bearer drop volume | `disconnection_cnt` | Sum of hourly increments | 7d $[T-7	ext{d}, T)$ | Safe ($t < T$) | Cellular carrier network maintenance artifact | Correlation with antenna/cable repairs | **MEDIUM** |
| **F13** | `disconn_to_offline_ratio` | Flapping vs stagnation discriminator | `disconnection_cnt`, `offline` | Drops per offline hour | 7d $[T-7	ext{d}, T)$ | Safe ($t < T$) | High variance on small offline values | Diagnostic separation on failure types | **LOW** |
| **F14** | `reboot_and_offline_syndrome`| Power/watchdog crash loop | `reboot_cnt`, `offline_sec` | Candidate interaction flag | 7d $[T-7	ext{d}, T)$ | Safe ($t < T$) | Binary flag does not provide granular ranking | Precision check on repair rates | **HIGH** |
| **F15** | `flapping_and_offline_syndrome`| Unstable RF link syndrome | `disconnection`, `offline` | Candidate interaction flag | 7d $[T-7	ext{d}, T)$ | Safe ($t < T$) | Sensitive to carrier network drops | Antenna replacement cross-check | **MEDIUM** |
| **F16** | `acute_chronic_divergence` | Sudden operational collapse | Trailing 7d vs prior 21d | Baseline drop magnitude | 28d $[T-28	ext{d}, T)$ | Safe ($t < T$) | Fails if gateway was never operational | Verification against failure onset dates | **HIGH** |
| **F17** | `hist_meter_success_pre_feb`| Historical collection baseline | `meter_read_success.csv` | Total success / expected | Pre-Jan 26, 2026 | Safe ($t < 	ext{Jan 26}$) | **STALE:** Zero signal during Feb–Mar 2026 | Correlation with chronic problem sites | **MEDIUM** |
| **F18** | `hist_meter_outage_freq` | Historical zero-read week rate | `meter_read_success.csv` | Fraction of 0-read weeks | Pre-Jan 26, 2026 | Safe ($t < T$) | Stale during live evaluation | Regression against work orders | **LOW** |
| **F19** | `is_lifecycle_active` | Asset commissioning eligibility | `installed_on`, `decommissioned`| Strict boolean interval check | Evaluated at $T$ | Safe (metadata) | Date parsing/timezone mismatches | Audit against future-commissioned units | **HIGH (Gate)** |
| **F20** | `installed_age_days` | Asset lifespan exposure | `installed_on` | $(T - 	ext{installed}) / 1	ext{d}$ | Evaluated at $T$ | Safe (metadata) | Age alone does not prove failure in week | Correlation with component wear | **LOW** |

---

## 15. Baseline Comparison

To demonstrate the structural advantages of this candidate specification over `baseline_3sigma.py`, we evaluate how the baseline handles critical operational scenarios:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                 BASELINE COMPARISON MATRIX                              │
├──────────────────────────────┬─────────────────────────┬────────────────────────────────┤
│ Operational Dimension        │ baseline_3sigma.py      │ Candidate Feature Spec (Ph 4.2)│
├──────────────────────────────┼─────────────────────────┼────────────────────────────────┤
│ 1. Complete Silence          │ COMPLETELY BLIND (0 pts)│ Explicit Silence Features (F04)│
│ 2. Cumulative Counters       │ Naive Mean/Std on Raw   │ Peak Envelope & Diffing (F06/7)│
│ 3. Failure Persistence       │ Isolated 1-Hour Outliers│ Multi-Day Parameters (F04/14)  │
│ 4. Lifecycle Filtering       │ None (All IDs Ingested) │ Hard Eligibility Masking (F19) │
│ 5. Feature Interaction       │ Unweighted Sum of Flags │ Correlated Syndromes (F14/15)  │
│ 6. Duplicate Cleanliness     │ None (Sums Duplicates)  │ Deduplication Invariant Prior  │
└──────────────────────────────┴─────────────────────────┴────────────────────────────────┘
```

### 15.1 Complete Silence (The Baseline Dead-Gateway Blind Spot)
- **In `baseline_3sigma.py`:** The script performs an inner filter: `recent = window[window["ts"] >= end - dt.timedelta(days=7)]`. If a gateway is dead and emitted zero telemetry rows in the trailing 7 days, it produces 0 rows in `recent`. It receives 0 flags and is completely omitted from the candidate ranking.
- **In Phase 4.2 Specification:** Features **F04** (`consecutive_missing_at_cutoff`) and **F05** (`is_completely_silent_7d`) explicitly capture silent gateways via outer-join against `gateway_master.csv`, surfacing dead units.

### 15.2 Cumulative Counters
- **In `baseline_3sigma.py`:** Computes `mean` and `std` directly on raw `offline_duration_sec` values that range up to 726,642 seconds. When an outage accumulates across several days, the mean and standard deviation explode, distorting subsequent $\mu + 3\sigma$ thresholding.
- **In Phase 4.2 Specification:** Counters are converted via **Peak Window Envelope (F06)** and **Consecutive Positive Differencing (F07)**, neutralizing counter inflation.

### 15.3 Persistence vs Isolated 1-Hour Spikes
- **In `baseline_3sigma.py`:** Any single hour exceeding $\mu + 3\sigma$ adds 1 point. A gateway with 3 isolated noisy hours over 7 days receives 3 flags, outranking a gateway experiencing a severe continuous 48-hour outage.
- **In Phase 4.2 Specification:** Requires persistent distress parameters (e.g. continuous silence candidate parameter $\ge 48	ext{h}$, peak downtime $\ge 24	ext{h}$, reboot storms $\ge 5$ reboots).

### 15.4 Lifecycle Filtering
- **In `baseline_3sigma.py`:** Does not load `gateway_master.csv`. If an uninstalled or decommissioned gateway had legacy historical telemetry in Parquet partitions, the baseline could inadvertently rank it.
- **In Phase 4.2 Specification:** Enforces **F19** as a mandatory gating precondition: assets not yet installed or already decommissioned at date $T$ are masked.

---

## 16. Rejected / Low-Value Features

Based on the empirical evidence gathered during Phase 3, several intuitive metrics are **explicitly rejected** from serving as primary dispatch signals:

### 16.1 Raw Cellular Signal Strength (RSSI / RSRP / RSCP)
- **Empirical Evidence:** In `field_visits.csv`, historical work orders raised for `Signal schwach` (weak signal) resulted in **0 physical repairs across 79 dispatches** (73 No Fault Found, 6 Access Denied; exact 0.0% repair rate).
- **Operational Reality:** Cellular attenuation in a concrete basement is an environmental characteristic of the building, not a broken gateway. A visiting technician cannot alter cellular base-station propagation. Dispatching a technician to "fix weak signal" results in a wasted €380 visit.
- **Status:** **REJECTED as primary dispatch feature.**

### 16.2 Raw Cyclic Redundancy Check (CRC) Packet Error Ratios
- **Empirical Evidence:** Telemetry analysis in Phase 3 showed frequent CRC error spikes across healthy gateways during severe weather and atmospheric disturbances without interrupting meter packet relay.
- **Operational Reality:** Transient atmospheric interference causes packet corruption that resolves autonomously without hardware intervention.
- **Status:** **REJECTED as primary dispatch feature.**

### 16.3 Isolated 1-Hour Statistical Outliers
- **Empirical Evidence:** In `field_visits.csv`, historical work orders dispatched for `Auffaellige Statistik` (statistical anomalies) achieved **0 physical repairs across 87 dispatches** (77 No Fault Found, 10 Access Denied; exact 0.0% repair rate).
- **Operational Reality:** Cellular networks routinely undergo scheduled overnight maintenance, routing handovers, or brief reboot cycles that create 1-hour blips. Dispatching on an isolated 1-hour 3-sigma anomaly produces a near-100% false alarm rate.
- **Status:** **REJECTED as standalone dispatch criteria.**

---

## 17. Why We Are Not Choosing Weights Yet

A common failure mode in operational data science is "hyperparameter guessing"—assigning subjective weights to features based on intuition:
$$	ext{Arbitrary Score (DANGEROUS)} = 0.4 	imes F04 + 0.3 	imes F06 + 0.2 	imes F09 + 0.1 	imes F12$$

In Phase 4.2, we **strictly avoid assigning numerical weights or final ranking coefficients**.

### 17.1 The Dangers of Arbitrary Weighting
1. **Uncalibrated Scales:** Feature $F06$ (`offline_duration_max_7d`) ranges from 0 to 604,800 seconds, while $F09$ (`reboot_cnt_sum_7d`) ranges from 0 to 50. Combining them without empirical scaling causes the larger raw magnitude to silently dominate the ranking.
2. **Distorted Economic Asymmetry:** The real-world objective is financial loss minimization under a €380 false alarm penalty and a €600 unaddressed weekly outage loss. Arbitrary weights cannot optimize an asymmetric loss surface.
3. **Capacity Non-Linearity:** Because only exactly 15 gateways are dispatched each week, the relative ordering of rank 15 vs rank 16 is critical, while the absolute score difference between rank 1 and rank 2 carries zero operational difference.

### 17.2 The Defensible Engineering Alternative
Weights and scoring formulas must be derived through **Empirical Backtesting in Phase 6**:
- Evaluating candidate ranking formulations across the historical training period against known maintenance ground truth in `field_visits.csv`.
- Measuring the exact false alarm rate, physical repair yield, and unaddressed outage cost on simulated historical weeks.
- Utilizing optimization or grid calibration to select weights that directly minimize total financial loss.

---

## 18. Validation Plan

In Phase 6, candidate features will undergo rigorous empirical validation across multiple operational dimensions rather than relying on a single statistical test:

### 18.1 Multi-Dimensional Feature Evaluation Framework
1. **Statistical Separability:** Compare empirical distributions between confirmed physical repairs (`Fehler behoben` with component replacements) and false alarms (`Kein Fehler gefunden`) using non-parametric separation tests (Mann-Whitney U statistic).
2. **Precision / Repair Yield:** Measure the proportion of top-15 flagged gateways that correspond to true physical repairs in historical weeks.
3. **Economic Cost Surface:** Calculate net financial impact across candidate rankings:
   $$	ext{Total Cost} = \sum_{	ext{weeks}} \Big(380 	imes N_{	ext{false\_visits}} + 600 	imes N_{	ext{unaddressed\_outages}}\Big)$$
4. **Incremental Ranking Value:** Evaluate whether adding a candidate feature improves the identification of broken units at ranks 1–15, or merely introduces collinear noise.

### 18.2 Synthetic Outage Injection (Sensitivity Testing)
- Simulate known failure scenarios on healthy gateway historical data:
  - Inject 72 hours of complete silence.
  - Inject 20 hourly reboots.
  - Inject cumulative counter resets.
- Verify that candidate features monotonically increase in response to injected degradation without numerical overflow or edge-case collapse.

---

## 19. What This Enables Next

Micro-Phase 4.2 establishes the verified architectural contract for the subsequent implementation phases:

```
[Phase 4.1: Operational Definition] (COMPLETE)
  - Formalized physical failure modes and economic loss asymmetry
           ↓
[Phase 4.2: Candidate Feature Specification] (COMPLETE & AUDITED)
  - Defined 20 mathematically sound, verified candidate features
  - Established temporal, ID, duplicate, and counter handling contracts
  - Rejected non-predictive sensor metrics (RSSI, CRC, isolated 3-sigma)
           ↓
[Phase 5: Feature Pipeline Implementation]
  - Construct clean, vectorized Python / Pandas pipeline
  - Build feature extraction module respecting strict t < T cutoff
  - Implement counter differencing and outer-join silence tracking
           ↓
[Phase 6: Backtesting, Weight Optimization & Validation]
  - Empirically tune scoring weights against historical cost function
  - Benchmark financial yield against baseline_3sigma.py
```

---

## 20. Interview Explanation

*When asked in a technical interview: "How did you go from raw telemetry to candidate features?", deliver this 1-to-2 minute structured response:*

> "Rather than jumping straight from raw files into a machine learning model or throwing arbitrary statistical aggregations at the data, we followed a disciplined, six-step engineering workflow.
>
> First, our Phase 3 investigation revealed critical operational facts: dispatches on generic statistical anomalies resulted in an exact 0.0% physical repair rate, while multi-day outages and reboot loops achieved 56% to 65% repair yields. We also discovered that offline duration was an accumulating counter reaching over 700,000 seconds, and that the provided 3-sigma baseline was completely blind to dead gateways emitting zero telemetry rows.
>
> In Phase 4.1 and 4.2, we translated these operational findings into formal candidate feature specifications. We established strict contracts: an absolute right-open temporal cutoff strictly before Monday midnight to eliminate lookahead leakage; a canonical gateway ID normalization standard to prevent silent join dropouts; an enforced deduplication step to remove exactly 6,547 duplicate records; and explicit counter-differencing logic to prevent artificial compounding of cumulative downtime.
>
> We defined 20 candidate features targeting distinct operational conditions: communication silence, chronic downtime, reboot instability, and multi-subsystem degradation syndromes, while explicitly rejecting uninformative signals like raw signal strength and transient CRC noise based on historical work-order evidence.
>
> Crucially, we deliberately avoided picking arbitrary feature weights at this stage. In an operational setting governed by a hard 15-visit weekly cap and an asymmetric cost structure—balancing a €380 false alarm against a €600 weekly unaddressed outage—feature weights and parameters must be calibrated empirically through historical backtesting, which we execute in our validation phase."

---

> Phase 4.2 status: CANDIDATE FEATURE SPECIFICATION AUDITED & VERIFIED — READY FOR PHASE 5
