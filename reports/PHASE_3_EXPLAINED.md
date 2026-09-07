# Phase 3 — Deep Data Investigation Explained

> This document is a study and interview-defense guide. The technical reports remain the source of record.

---

## 1. Phase 3 in One Minute

### What was the problem?
LPDG operates a fixed LoRaWAN radio network across Germany where approximately 320 gateways relay utility meter readings (each serving 40 to 900 meters). When a gateway degrades or fails, connected utility meters stop being read, leading to unbilled energy and customer complaints. The field operations team has a strict capacity limit of **15 physical site visits per week**. The economic stakes are asymmetric and severe:
- **Wasted visit penalty:** €380 when a technician arrives on-site and finds nothing wrong (false alarm).
- **Unaddressed failure penalty:** €600 per week for every week a broken gateway is left unattended.

Today, those 15 visits are picked through spreadsheets and intuition. The challenge task is to build an automated, defensible ranking service that tells the team which 15 gateways to visit each week.

### Why couldn't we immediately build a ranking formula or ML model?
The challenge prompt deliberately leaves the definition of *"needs a visit"* under-specified. Jumping straight into heuristic weighting or machine learning without understanding the physical data semantics would be reckless engineering:
1. We did not know how clean the data was.
2. We did not know if telemetry dropouts were recorded as explicit zeros or missing rows.
3. We did not know what units firmware counters were reporting.
4. We did not know whether historical dispatches were actually effective.
5. We did not know the temporal boundaries or data horizons of our tables.

Building a ranking algorithm before understanding the data guarantees building the wrong thing.

### What did we investigate?
Across 8 Parquet partitions and 4 tabular datasets (1.43 million telemetry rows), we audited data schemas, character encodings, primary keys, identifier formats, implicit and explicit missingness, exact row duplications, cumulative counter dynamics, field visit work-order outcomes, weekly meter-reading performance, expert engineer audits, and temporal leakage boundaries.

### What was the major outcome?
We uncovered critical physical realities:
- Historical field dispatches had a **60.75% false alarm rate** (€148,200 in wasted visits), with statistical anomaly dispatches achieving a **0.0% repair rate**.
- Completely silent gateways (missing telemetry hours) are the single strongest predictor of meter reading failure ($r = +0.786$), yet the provided 3-sigma baseline is completely blind to them.
- Meter read data stops on January 26, 2026, creating a hard data cliff before the scored window.
- Firmware counters accumulate downtime across multi-day outages (up to 726,000s in an hourly row).
- Parquet telemetry contains 6,547 identical duplicate rows in odd months.

### One-sentence interview answer:
> "Before designing any scoring model, Phase 3 conducted an empirical investigation of 1.43 million telemetry rows and auxiliary operational logs, proving that completely silent gateways and persistent multi-day dropouts drive true meter failures, whereas the 3-sigma baseline's reliance on reported statistical outliers mirrors a historical dispatch practice that suffered a 60.7% false alarm rate."

---

## 2. Where Phase 3 Fits in the Overall Project

To build an engineering solution that survives executive and technical scrutiny, development follows a disciplined, evidence-based progression:

```
[Phase 0: Setup & Environment]
          ↓
[Phase 1: Baseline Implementation & Validation Checkpoint]
  - Run baseline_3sigma.py (creates predictions_baseline.csv)
  - Verify compliance with validate_submission.py
          ↓
[Phase 2: Dataset Inventory & Initial Orientation]
  - Identify physical files, schema structures, and basic grains
          ↓
★ [PHASE 3: DEEP DATA INVESTIGATION & VERIFICATION] ★  <-- (WE ARE HERE)
  - Uncover physical semantics, anomalies, missingness, duplicates, and leakage boundaries
  - Formulate empirical candidate signals without guessing formulas
          ↓
[Phase 4: Operational Definition of "Needs a Visit"]
  - Synthesize Phase 3 evidence into a formal mathematical & business definition
  - Balance the €380 false alarm cost against the €600/week unaddressed outage penalty
          ↓
[Phase 5: Ranking Strategy & Feature Engineering]
  - Implement silence detectors, counter differencing, and persistent degradation filters
          ↓
[Phase 6: Backtesting, Error Analysis & Validation]
  - Evaluate against baseline across the 8 scored weeks (Feb 2 to Mar 23, 2026)
          ↓
[Phase 7: Production Service & Packaging (Part 1 & Part 2)]
  - FastAPI / CLI / Containerization / Automated testing
```

### Why Phase 3 MUST happen before Phase 4 & 5:
If you define *"needs a visit"* in Phase 4 before doing Phase 3, you are defining it based on assumptions. Phase 3 provides the empirical ground truth: it tells you what actually broke in the past, what physical parts were replaced, what technicians found on-site, how sensors actually report during outages, and where data traps exist. Phase 4 translates Phase 3 evidence into an operational decision policy.

---

## 3. What Data We Had

We investigated 5 primary datasets (spanning 6 physical files) covering network telemetry, asset registers, metering logs, maintenance tickets, and expert audits:

| Dataset | Operational Purpose | Key Fields Analyzed | Temporal Coverage | How It May Eventually Be Used | Important Limitations / Traps |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`telemetry/`** (Parquet) | Hourly sensor, radio, and backhaul health logs per gateway. | `gateway_id`, `ts_utc`, `offline_duration_sec`, `disconnection_cnt`, `reboot_cnt`, `rx_nr_pkts`, `rx_crc_bad`. | 2025-08-01 00:00:00Z to 2026-03-31 23:00:00Z (8 calendar months). | Primary real-time dynamic signal for weekly gateway health scoring. | Non-reporting when offline (silent dropouts); cumulative counters; 6,547 duplicate rows in odd months. |
| **`gateway_master.csv`** | Asset register and site configuration metadata. | `gateway_id`, `installed_on`, `decommissioned_on`, `n_meters_installed`, `site_type`, `hw_model`. | Static asset snapshot. | Lifecycle masking (filter out decommissioned or uninstalled gateways); baseline meter capacity. | Encoded in Latin-1 (crashes UTF-8 parsers); 12 gateways have future installation dates in mid-2026. |
| **`meter_read_success.csv`** | Weekly utility billing meter reading counts. | `week_start`, `gateway_id`, `meters_expected`, `meters_read`. | 2025-08-04 to 2026-01-26 (26 weekly reporting cycles). | Historical asset-level baseline / prior risk factor for meter read reliability. | **Data cliff:** Stops on 2026-01-26. Zero records exist during the scored window (Feb–Mar 2026). |
| **`field_visits.csv`** | Historical maintenance work orders and site findings. | `visit_id`, `gateway_id`, `requested_on`, `visited_on`, `reason_reported`, `outcome`, `parts_replaced`. | Work orders: Feb 2025 – Jan 2026; Attendance: Feb 2025 – Feb 2026. | Ground-truth benchmark of physical failure modes and past diagnostic dispatch accuracy. | 60.75% of past visits found no fault; visits prior to Aug 2025 lack corresponding telemetry. |
| **`engineer_review_2026-02.xlsx`** | Expert audit evaluating 120 gateways as Normal vs Bad. | `gateway_id`, `Kategorie` (`Normal`/`Schlecht`), `reviewed_on`, `Bemerkung`. | Single audit date: **2026-02-15**. | Qualitative validation benchmark and post-hoc sanity check. | **Lookahead leakage risk:** Conducted on Feb 15; cannot be used for Weeks 1 & 2 predictions. |

---

## 4. The Investigation Process

Our investigation followed a rigorous 12-step engineering workflow. At each stage, we documented what we did, why we did it, and what we learned:

### Step 1: Inventory the Data
- **What we did:** Audited the directory structure, verified file sizes, identified storage formats (Parquet partitions, CSV, Excel), and checked file accessibility.
- **Why we did it:** To ensure all expected assets existed, check storage volume (~105 MB total), and determine memory footprints.
- **What we learned:** Telemetry is split across 8 monthly Parquet partitions (`month=YYYY-MM`), while auxiliary tables are standalone CSVs and an `.xlsx` workbook.

### Step 2: Inspect Schemas and Data Types
- **What we did:** Inspected column headers, PyArrow physical schemas, and Pandas data types across all tables.
- **Why we did it:** To prevent silent type coercion bugs, identify integer vs float representations, and verify timestamp string formats.
- **What we learned:** Telemetry has 57 physical columns (58 with partition key). `gateway_master.csv` threw a `UnicodeDecodeError` under default UTF-8 due to German umlauts encoded in `latin1`.

### Step 3: Check Temporal Coverage
- **What we did:** Computed minimum and maximum timestamps across all tables, cross-referencing against the 8 scored Mondays (`2026-02-02` to `2026-03-23`).
- **Why we did it:** To establish which data is available at each prediction cutoff and identify lookahead boundaries.
- **What we learned:** A critical data cliff was discovered: `meter_read_success.csv` terminates on `2026-01-26`, providing zero live visibility during the scored period.

### Step 4: Check Gateway Coverage
- **What we did:** Extracted distinct gateway identifiers from each table and performed cross-table set intersections.
- **Why we did it:** To verify if all gateways exist everywhere and identify unobserved entities.
- **What we learned:** Master has 332 gateways, but Telemetry has only 320. Exactly 12 gateways in Master have zero telemetry rows because their commissioning dates are in mid-2026 (May–July 2026).

### Step 5: Check Missingness (Explicit and Implicit)
- **What we did:** Audited explicit nulls (`NaN`/`None`) in all columns, and calculated expected vs actual hourly telemetry rows per gateway.
- **Why we did it:** To detect data corruption and determine if offline gateways report zero values or emit no records.
- **What we learned:** Telemetry has **0 explicit nulls** across all 1.43M rows, but suffers **23.19% implicit missingness** (432,853 missing hourly records). Dead gateways stop transmitting rather than writing zeros.

### Step 6: Check Duplicate Records
- **What we did:** Evaluated duplicate keys `(gateway_id, ts_utc)` in telemetry and full-row equality across all 57 columns.
- **Why we did it:** To prevent double-counting downtime and inflating aggregation statistics.
- **What we learned:** Exactly **6,547 identical full-row duplicate records** exist, concentrated strictly within odd months (Sep 2025, Nov 2025, Jan 2026).

### Step 7: Check Identifier Consistency
- **What we did:** Inspected string formats of `gateway_id` across datasets and tested inner joins.
- **Why we did it:** To ensure join integrity across relational entities.
- **What we learned:** Master, Visits, and Review use colon-separated 17-char hex (`06:39:EA:56:02:C1`), while Telemetry and Meter Reads use bare 12-char hex (`0639EA5602C1`). Unnormalized joins produce **0 matches**. Normalization is mandatory.

### Step 8: Understand Telemetry Semantics & Units
- **What we did:** Profiled distributions, minimums, maximums, and time-series sequences of core numerical metrics.
- **Why we did it:** To verify whether columns conform to hourly rates or cumulative registers.
- **What we learned:** `offline_duration_sec` reaches 726,642 seconds (~201.8 hours) in a single hourly row. It is a cumulative firmware counter that accumulates across multi-day outages rather than an hourly rate clamped to 3,600s.

### Step 9: Compare Telemetry Against Historical Outcomes
- **What we did:** Matched 313 field visits attended between Aug 2025 and Feb 2026 with trailing 7-day pre-visit and post-visit telemetry.
- **Why we did it:** To physically verify whether technician visits fixed anything and what true hardware failure looks like in telemetry.
- **What we learned:** When faults were resolved, offline duration dropped by 47.1% and reboots dropped by 34.5%. True faults had 4.71× higher mean offline time and 38.8× higher median offline time than false alarms.

### Step 10: Investigate Possible Predictive Signals
- **What we did:** Aligned weekly telemetry aggregations with weekly meter-reading success rates to assess empirical relationships.
- **Why we did it:** To evaluate which sensor measurements correlate with the primary business failure mode (unread meters).
- **What we learned:** Telemetry completeness (`hours_reported`) has the strongest positive correlation with meter success ($r = +0.786$), while raw packet count has zero correlation ($r = -0.005$).

### Step 11: Check Temporal Leakage Boundaries
- **What we did:** Evaluated the date of `engineer_review_2026-02.xlsx` against the scored prediction timeline.
- **Why we did it:** To prevent training on or using features that would not have existed at prediction time.
- **What we learned:** The review occurred on `2026-02-15`. Using it for Week 1 (`2026-02-02`) or Week 2 (`2026-02-09`) is strict lookahead leakage.

### Step 12: Verify Important Claims Independently
- **What we did:** Recalculated every metric, denominator, ratio, and percentage from raw source data in Micro-Phase 3.1.
- **Why we did it:** To ensure the investigation was mathematically sound and defensible before freezing Phase 3.
- **What we learned:** All 11 core claims were verified. Crucial refinements were established: differentiating structural from operational missingness, and noting the extreme median separation in downtime.

---

## 5. Finding 1 — Telemetry Missingness

### Observation:
When querying `data/telemetry/**/*.parquet`, there are **0 explicit null values** in any column. However, across the 243 calendar days (August 1, 2025 to March 31, 2026), a fully reporting gateway should emit 5,832 hourly records ($243 	imes 24$). For the 320 gateways observed in telemetry, the expected total is $1,866,240$ rows. The actual row count is $1,433,387$, leaving **432,853 missing hourly records (23.19%)**.

### Interpretation:
This is **implicit missingness** (silent non-reporting). In an IoT sensor network, when a gateway suffers a complete power loss or backhaul severing, it cannot construct or transmit a telemetry packet to the ingestion server. Instead of writing a row with `offline_duration_sec = 3600`, the system receives **no record at all**.

### Conditioning on Operational Lifetime:
Our verification audit uncovered that this 23.19% network missingness consists of two components:
1. **Structural Missingness (~9.7%):** 8 gateways were commissioned mid-period in February/March 2026 (they could not report before being installed), and 12 gateways were decommissioned between September 2025 and February 2026 (they stopped reporting upon decommissioning).
2. **True Operational Missingness (~13.5%):** Accounting strictly for active lifetimes ($1,649,940$ expected active hours), gateways failed to report during **13.12% (raw) to 13.52% (deduplicated)** of their active deployment.

### Why this matters for the ranking system:
The supplied 3-sigma baseline (`baseline_3sigma.py`) computes statistics *only on rows present in the recent 7-day window*:
```python
recent = window[window["ts"] >= end - dt.timedelta(days=RECENT_DAYS)].copy()
grouped = recent.groupby("gateway_id").agg(flagged_hours=("flagged", "sum"))
```
If a gateway was active and suffered a fatal hardware death (zero rows in the last 7 days), `recent` contains **0 rows** for that gateway. It receives **0 flagged hours** and completely disappears from the candidate list! In an operational utility network, a completely silent gateway is the most catastrophic failure (€600/week ongoing penalty). The baseline is 100% blind to it.

```
Active Gateway Dies Completely → Emits 0 Telemetry Rows → 0 Rows in Recent Window → 0 Breaches Flagged by 3-Sigma → Ignored by Operations (€600/wk Penalty Accumulates)
```

### Interview Question & Answer:
**Q: "Why did you care about missing telemetry, and how did you measure it?"**  
> *"We cared because missing telemetry in an IoT network is not random missingness (MCAR)—it is the primary physical signature of total gateway failure. A dead or unpowered gateway cannot report an error; it simply stops transmitting. We discovered zero explicit nulls in the Parquet files, but calculated an unconditioned 23.19% implicit missingness against the 5,832 expected hourly slots. More importantly, when conditioned on active gateway lifetime, active gateways were silent 13.5% of the time. This revealed a fatal flaw in the provided 3-sigma baseline: because it only aggregates over rows that exist in the recent window, a completely dead gateway receives zero flagged hours and evades detection entirely."*

---

## 6. Finding 2 — Duplicate Telemetry

### Observation:
Evaluating duplicate keys on `(gateway_id, ts_utc)` revealed exactly **6,547 duplicate records** across the 1,433,387 telemetry rows. Checking all 57 columns confirmed that 100% of these records are exact full-row clones residing within the same monthly Parquet partition:
- `month=2025-08`: 0 duplicates
- `month=2025-09`: **2,185 duplicates**
- `month=2025-10`: 0 duplicates
- `month=2025-11`: **2,124 duplicates**
- `month=2025-12`: 0 duplicates
- `month=2026-01`: **2,238 duplicates**
- `month=2026-02`: 0 duplicates
- `month=2026-03`: 0 duplicates

### Why full-row equality matters:
If duplicates had different sensor values for the same hour, we would face a conflicting update problem (which record is authoritative?). Because they are exact 100% clones across all 57 columns, this is a clean data pipeline ingestion artifact (e.g. an ETL batch job retried or appended data twice in odd months).

### How duplicates distort aggregation (Concrete Example):
Suppose gateway `A` experienced an unstable hour with 1,800 seconds of downtime and 5 disconnects.
- In a clean partition, a 7-day sum yields: $	ext{Offline} = 1,800	ext{s}$, $	ext{Disconnects} = 5$.
- In `month=2025-09`, where that hour is duplicated: $	ext{Offline} = 3,600	ext{s}$, $	ext{Disconnects} = 10$.
A naive rolling aggregation over odd months artificially inflates total downtime, reboot counts, and breach frequencies by 1.2% to 1.3%, potentially promoting healthy gateways above broken ones purely due to duplicate duplication.

### Engineering Implication:
Deduplication (`df.drop_duplicates(subset=['gateway_id', 'ts_utc'])`) must be applied as a mandatory first-stage transformation before any feature extraction or rolling window calculation.

### Interview Question & Answer:
**Q: "How did you identify and handle duplicates?"**  
> *"We audited primary key uniqueness on `(gateway_id, ts_utc)` per partition and across the full dataset. We found exactly 6,547 duplicate records, isolated entirely to odd-numbered months (September, November, January), with roughly 2,100 to 2,200 duplicates in each. By checking all 57 columns, we proved they were 100% identical row clones caused by pipeline ingestion retries. We established that deduplication must occur upstream of feature computation; otherwise, rolling sums of downtime or reboots would double-count duplicate hours and distort weekly rankings."*

---

## 7. Finding 3 — Gateway ID Inconsistency

### Observation:
The repository uses two incompatible string formatting standards for gateway identifiers:
- **Colon-delimited 6-byte hex (17 chars):** e.g., `06:39:EA:56:02:C1` (used in `gateway_master.csv`, `field_visits.csv`, and `engineer_review_2026-02.xlsx`).
- **Bare 12-char hex (12 chars):** e.g., `0639EA5602C1` (used in `telemetry` Parquet partitions and `meter_read_success.csv`).

### Engineering Impact:
If a developer executes a standard Pandas merge or SQL join:
```python
# FAILS: Produces 0 rows!
merged = pd.merge(telemetry, gateway_master, on="gateway_id")
```
The inner join produces **exactly 0 matching rows**. A software engineer unfamiliar with the underlying data would assume the asset register was completely disconnected from telemetry.

### Normalization Solution:
We implemented an explicit normalization function adhering to the logic in `validate_submission.py`:
```python
def normalise_gateway_id(v: str) -> str:
  return re.sub(r"[^0-9A-Fa-f]", "", str(v)).upper()
```
Applying this function standardizes all identifiers to 12-character uppercase bare hex strings, immediately resolving the join and yielding all **320 active telemetry gateways** and **299 meter-read gateways**.

### Interview Question & Answer:
**Q: "Why didn't your joins work initially, and how did you resolve it?"**  
> *"Our initial relational joins between the asset register and telemetry returned zero matches because the source systems used two different serialization conventions: the physical hardware register and work orders used standard colon-delimited MAC-style hex strings (17 characters), whereas the telemetry ingestion pipeline stripped delimiters into bare 12-character hex strings. We wrote a defensive normalization helper that strips non-hexadecimal characters and enforces uppercase formatting. This reconciled all datasets, allowing seamless joins across asset metadata, sensor telemetry, and maintenance history."*

---

## 8. Finding 4 — Cumulative Counters

### Observation:
Profiling numerical ranges in telemetry revealed values in `offline_duration_sec` reaching up to **726,642 seconds (~201.8 hours / 8.4 days)** and `reboot_duration_sec` reaching **439,061 seconds (~121.9 hours)** in a single 1-hour reporting row. Across August 2025 alone, **8,354 hourly records (4.60%)** had `offline_duration_sec > 3,600`.

### Time-Series Behavior:
Tracking individual gateways over consecutive timestamps revealed that these columns do not reset to zero at the start of each hour. When a gateway disconnects, the firmware register increments continuously across hours. When connection is re-established, the cumulative downtime is emitted in the next successful transmission, after which the counter resets or rolls over.

```
Hour 01:00 → offline = 0s
Hour 02:00 → offline = 3,372s
Hour 03:00 → [SILENCE: Gateway disconnected, no packet emitted]
Hour 04:00 → [SILENCE: Gateway disconnected, no packet emitted]
Hour 05:00 → offline = 19,440s (Emits 5.4 hours of accumulated outage!)
Hour 06:00 → offline = 0s (Connection restored, counter resets)
```

### Data Dictionary Confirmation:
The Data Dictionary explicitly notes:
> *"offline_duration_sec: Backhaul offline time counter, seconds. A note on units: Several of these columns are counters read straight off the gateway firmware... Where the column name says the unit... you can rely on it. Where it does not, this dictionary says 'as the gateway reports it' rather than guessing."*

### How a wrong interpretation could damage the model:
If an engineer assumes `offline_duration_sec` is an hourly rate bounded between 0 and 3,600:
1. They might treat a single row of 726,000s as a corrupt data anomaly and clip or delete it.
2. They might sum the column across 7 days: $726,000	ext{s} + 726,000	ext{s} = 1,452,000	ext{s}$, falsely calculating 400 hours of downtime in a 168-hour week!
3. They would fail to recognize that the single large number represents a multi-day sustained blackout.

### Engineering Implication:
In Phase 5, features derived from cumulative counters must be carefully transformed: using threshold exceedance flags (e.g. hours where offline counter $> 0$), first-order diffing ($\Delta 	ext{counter}$), or max-duration capping per event.

### Interview Question & Answer:
**Q: "How could a wrong interpretation of `offline_duration_sec` damage your model?"**  
> *"If you interpret `offline_duration_sec` as an instantaneous hourly rate, you would assume values cannot exceed 3,600 seconds. In reality, we observed values up to 726,642 seconds because the firmware accumulates downtime across ongoing disconnection periods. If you naively sum these values over a 7-day window, you would severely double-count multi-hour outages and create impossible totals (e.g. 300 hours of downtime in a 168-hour week). Conversely, if you treated values over 3,600 as outliers and clipped them, you would discard the exact signal indicating a catastrophic multi-day outage. In Phase 5, this requires feature transformation via event diffing or threshold exceedance rather than raw summation."*

---

## 9. Finding 5 — Historical Field Visits

### Observation:
Auditing all 642 work orders in `field_visits.csv` revealed the following outcome distribution:
- **`Kein Fehler gefunden` (No fault found / False Alarm): 390 visits (60.75%)**
- **`Fehler behoben` (Fault resolved / True Positive): 223 visits (34.74%)**
- **`Kein Zugang` (Access denied / Inconclusive): 29 visits (4.52%)**

### Dispatch Reason Disparities:
Cross-tabulating outcomes against the initial dispatch reason exposed an alarming reality:
- **`Auffaellige Statistik` (Statistical Anomaly):** 87 visits $ightarrow$ **0.0% fault resolution rate** (88.5% no fault found, 11.5% no access).
- **`Signal schwach` (Weak Signal):** 79 visits $ightarrow$ **0.0% fault resolution rate** (92.4% no fault found).
- **`Routinepruefung` (Routine Check):** 79 visits $ightarrow$ **0.0% fault resolution rate** (92.4% no fault found).
- **`Keine Verbindung` (No Connection / Outage):** 100 visits $ightarrow$ **65.0% fault resolution rate**.
- **`Haeufige Neustarts` (Frequent Reboots):** 110 visits $ightarrow$ **56.4% fault resolution rate**.
- **`Kunde meldet Ausfall` (Customer Reported):** 101 visits $ightarrow$ **53.5% fault resolution rate**.

```
Historical Dispatch Reasons vs Actual Physical Repair Rate:
[Keine Verbindung (Offline)]     ============================> 65.0% Fixed
[Haeufige Neustarts (Reboots)]   ========================> 56.4% Fixed
[Kunde meldet Ausfall (Outage)]  =======================> 53.5% Fixed
[Zaehler nicht gelesen (Meters)] =====================> 48.8% Fixed
[Auffaellige Statistik (Anomaly)]| 0.0% Fixed (100% Wasted Visits!)
[Signal schwach (Weak RF)]       | 0.0% Fixed (100% Wasted Visits!)
[Routinepruefung (Routine)]      | 0.0% Fixed (100% Wasted Visits!)
```

### Connection to Challenge Economics:
The Challenge Brief establishes that:
- Wasted site visit = **€380 penalty**.
- 390 historical false dispatches cost LPDG **€148,200 in wasted technician labor**.
- Initiating dispatches on statistical blips (`Auffaellige Statistik`) or weak cellular coverage (`Signal schwach`) produced zero physical repairs. Cellular coverage in a basement is an environmental property of the building; a technician visiting the site cannot move a cell tower!
- True hardware repairs occurred when there was complete backhaul silence or severe boot loops, resulting in parts replaced: power supplies (`Netzteil`, 39), antennas (`Antenne`, 37), cables (`Kabel`, 35), gateway swaps (`Gateway getauscht`, 30), and SIM cards (`SIM-Karte`, 25).

### Important Boundary:
We have **not** solved the cost optimization problem yet. We have established empirical proof that false alarms are historically rampant and that statistical anomaly triggers fail in the field.

### Interview Question & Answer:
**Q: "What did the historical work-order data tell you about how the operations team currently selects sites?"**  
> *"It confirmed that current operations practice is deeply flawed: 60.75% of past dispatches were wasted false alarms where technicians attended and found nothing wrong, costing nearly €150,000. Crucially, work orders dispatched for 'statistical anomalies' (Auffaellige Statistik) and 'weak signal' had a 0.0% repair rate. Technicians only resolved real faults when there was hard operational evidence: sustained loss of connection (65% true positive rate) or persistent reboot cycles (56% true positive rate). This proved that generic statistical outlier detection—like the provided 3-sigma baseline—directly mimics the worst historical dispatch habits."*

---

## 10. Finding 6 — Meter Read Data Cliff

### Observation:
Evaluating `meter_read_success.csv` showed that it spans 26 reporting weeks from `2025-08-04` through `2026-01-26`. The scored challenge window spans 8 Mondays from `2026-02-02` to `2026-03-23`.
- Direct temporal overlap between `meter_read_success` and the scored window is **exactly 0 weeks**.

### The Subtle Engineering Distinction:
At first glance, a candidate might think: *"Meter reading success is the ultimate business metric, so let's use last week's meter read success rate as our primary feature."*
- On Week 1 (`2026-02-02`), this works: the week ending `2026-01-26` is only 7 days old.
- By Week 4 (`2026-02-23`), that meter-reading data is 4 weeks old.
- By Week 8 (`2026-03-23`), that meter-reading data is **8 weeks old / completely stale**.
If a gateway broke in mid-February, `meter_read_success.csv` has zero records to reflect that failure.

```
August 2025                January 26, 2026        February 2, 2026               March 23, 2026
[===== Meter Read Success Data (26 Weeks) =====]|
                                                [===== Scored Evaluation Window (8 Weeks) =====]
                                                Week 1: Fresh (7d lag)  -->  Week 8: Stale (8-week lag!)
```

### Engineering Implication:
Historical meter reading performance can safely serve as a **static asset-level health prior** (e.g. identifying chronic historically degraded sites), but it **cannot serve as a live updating feature**. Dynamic weekly dispatch decisions must be driven primarily by real-time telemetry proxies.

### Interview Question & Answer:
**Q: "Why didn't you simply use meter-read success as your primary ranking feature?"**  
> *"Because of a critical temporal data cliff: `meter_read_success.csv` terminates on January 26, 2026, exactly 7 days before the scored window begins. While it provides fresh trailing data for Week 1, by Week 8 that data is two months out of date and completely blind to new failures. We concluded that historical meter read success can only serve as a static asset prior, while dynamic weekly dispatch decisions must be driven by real-time telemetry proxies that continue reporting through March 2026."*

---

## 11. Finding 7 — Engineer Review Leakage

### Observation:
`engineer_review_2026-02.xlsx` contains audits for 120 gateways conducted by senior engineer M. Hoffmann on a single date: **`2026-02-15`** (60 `Normal`, 60 `Schlecht`).

### Temporal Leakage Explained Simply:
Temporal data leakage (lookahead bias) occurs when an algorithm uses information that could not have been known at the exact moment a decision was made.
- Scored Week 1 is Monday, **`2026-02-02`**.
- Scored Week 2 is Monday, **`2026-02-09`**.
- Engineer Hoffmann did not perform his inspection until Sunday, **`2026-02-15`**.

If you use Hoffmann's labels (`Schlecht`) to select gateways for Week 1 or Week 2, your model is looking into the future. In a live production setting on February 2, that spreadsheet did not exist.

```
Timeline of Events:
2026-02-02 (Week 1 Prediction Cutoff)  --> Review DOES NOT EXIST (Leakage if used!)
2026-02-09 (Week 2 Prediction Cutoff)  --> Review DOES NOT EXIST (Leakage if used!)
2026-02-15 (Engineer Review Conducted) --> 120 Gateways Audited
2026-02-16 (Week 3 Prediction Cutoff)  --> Review exists (Safe for post-hoc evaluation)
```

### Safe Usage:
The review is strictly quarantined from training or ranking during Weeks 1 and 2. It may be used on Week 3 (`2026-02-16`) or later, or as an external validation benchmark to verify whether telemetry health metrics align with human expert judgment.

### Interview Question & Answer:
**Q: "What is data leakage and how did you prevent it in your investigation?"**  
> *"Data leakage occurs when an algorithm learns from features containing information from the future that would not be available in production at decision time. We identified a prime leakage trap in `engineer_review_2026-02.xlsx`, which was conducted on February 15, 2026. Because scored Weeks 1 and 2 occurred on February 2 and February 9, using this spreadsheet to predict those weeks would be fatal lookahead bias. We strictly quarantined the review from early feature pipelines, restricting its role to post-hoc sanity checking after February 15."*

---

## 12. Finding 8 — Gateways With No Telemetry

### Observation:
`gateway_master.csv` lists 332 gateways. However, `data/telemetry` contains records for only 320 unique gateways. Cross-referencing the 12 missing gateways in the asset register revealed their commissioning dates:
- `0E:40:56:A2:CD:08`: `installed_on = 2026-05-10`
- `06:FE:DE:0E:77:89`: `installed_on = 2026-07-05`
- `02:E1:C7:0E:46:D1`: `installed_on = 2026-07-14`
- ... (all 12 gateways have `installed_on` between `2026-05-07` and `2026-07-14`).

### Operational Reality:
The scored challenge window concludes on `2026-03-23`. These 12 gateways represent future physical capital installations that had not yet been deployed to rooftops or plant rooms during the evaluation window.

### Engineering Implication (Lifecycle Masking):
If an algorithm ranks gateways without filtering by lifecycle dates, it might observe that these 12 gateways have 0 meter reads or 0 reported packets and dispatch technicians to empty rooftops where no gateway has been installed yet (€380 wasted per visit).
- **Rule:** The ranking pipeline must enforce an active lifecycle mask: $	ext{installed\_on} \le T_{	ext{Monday}} \le 	ext{decommissioned\_on}$.

---

## 13. Finding 9 — Candidate Signal Investigation

### Quantitative Correlation Analysis:
Aggregating telemetry into weekly intervals and joining with `meter_read_success.csv` yielded the following empirical correlations across all 7,223 overlapping gateway-weeks (August 2025 to January 2026):

| Aggregated Telemetry Metric | Correlation ($r$) with Meter Read Success | Statistical Interpretation | Operational Reality |
| :--- | :--- | :--- | :--- |
| **`hours_reported`** | **+0.786** (+0.742 on 3-mo sample) | Strong positive linear association. | When a gateway reports all 168 hours in a week, meters are successfully collected. When reporting drops, readings drop proportionally. |
| **`offline_sec_sum`** | **-0.603** (-0.618 on 3-mo sample) | Strong negative association. | Sustained backhaul downtime directly starves downstream meter packet forwarding. |
| **`disc_cnt_sum`** | **-0.557** (-0.580 on 3-mo sample) | Moderate-to-strong negative association. | Connection flapping indicates unstable power supplies or fringe cellular connectivity. |
| **`reboot_cnt_sum`** | **-0.282** (-0.300 on 3-mo sample) | Moderate negative association. | Reboots cause temporary packet loss, but brief isolated reboots are less damaging than prolonged disconnections. |
| **`rx_pkts_sum`** | **-0.005** (-0.001 on 3-mo sample) | **Zero linear association ($r pprox 0$).** | Gateways serve widely varying customer deployments (40 to 900 meters). Raw packet volume reflects site scale, not hardware health. |

### Crucial Caveat: Correlation $
e$ Causation
These correlations establish strong empirical associations, but they do **not** prove causation:
- Missing telemetry hours do not *cause* meters to fail; rather, an unpowered gateway *simultaneously causes* both telemetry silence and unread meters.
- A high reboot count does not always mean a broken gateway; scheduled firmware updates also cause reboots.
- These numbers guide which physical signals deserve focus, but domain engineering judgment must govern how they are combined.

---

## 14. Finding 10 — Historical Fault vs False Alarm

### Physical Verification of True Outages:
Evaluating the 313 field visits attended between August 15, 2025 and February 15, 2026 (where full 7-day pre-visit and 7-day post-visit telemetry existed):

```
Pre-Visit 7-Day Window Comparison:
[True Fault Fixed (Fehler behoben)]   ==> Mean Offline: 1,913,525s | Median Offline: 895,071s | Reboots: 47.2
[False Alarm (Kein Fehler gefunden)] ==> Mean Offline:   405,962s | Median Offline:  23,042s | Reboots:  7.7
```

### Arithmetic Means vs Skewed Medians:
- **Mean Offline Ratio:** $1,913,525.5	ext{s} / 405,962.1	ext{s} = \mathbf{4.71	imes}$.
- **Mean Reboot Ratio:** $47.2 / 7.65 = \mathbf{6.17	imes}$.
- **Median Offline Ratio:** $895,071.0	ext{s} / 23,042.5	ext{s} = \mathbf{38.84	imes}$!

### Why the median is so revealing:
In `Kein Fehler gefunden`, most healthy gateways experience minimal downtime (median 23,000s across 7 days, or ~6.4 hours cumulative), but a few isolated dropouts pull the mean up to 405,000s. In contrast, gateways with confirmed hardware faults had a median downtime of nearly **900,000 seconds**.
- Furthermore, upon technician repair (`Fehler behoben`), offline duration dropped by **47.1%** and reboots dropped by **34.5%**.
- For false alarms (`Kein Fehler gefunden`), telemetry was low before the visit and remained completely unchanged afterward.

### What this proves:
This is hard physical proof that **persistent, severe operational downtime separates real hardware faults from benign network noise**.

---

## 15. Finding 11 — Engineer Review Separation

### Observation:
Senior Engineer Hoffmann's audit of 120 gateways on `2026-02-15` (60 `Schlecht`, 60 `Normal`) showed extreme separation in the trailing 7 days of telemetry (`2026-02-08` to `2026-02-15`):
- **Mean 7-Day Offline Seconds:**
  - `Schlecht`: **1,176,507.3 seconds** (~326.8 hours cumulative downtime)
  - `Normal`: **86,265.0 seconds** (~24.0 hours)
  - **Separation: 13.64× higher offline duration.**
- **Mean 7-Day Disconnections:**
  - `Schlecht`: **348.9 disconnections**
  - `Normal`: **38.8 disconnections**
  - **Separation: 8.99× higher disconnection frequency.**

### Methodological Caveat (The 13 Silent Gateways):
Our verification audit uncovered that exactly **13 of the 120 audited gateways** (5 `Normal`, 8 `Schlecht`) emitted **0 telemetry rows** during that 7-day window.
- Standard Pandas `.mean()` automatically dropped these 13 non-reporting gateways.
- The reported 13.6× and 9.0× ratios are computed across the **107 reporting gateways**.
- For the 8 silent `Schlecht` gateways, they were completely dark, which aligns with the engineer's assessment of severe failure.

---

## 16. What We Learned Overall

| Empirical Finding | Physical / Domain Meaning | Architectural Importance | Impact on Phase 4/5 Design |
| :--- | :--- | :--- | :--- |
| **Silence is Fatal** | Completely dead gateways stop emitting telemetry. | High: Explains why `baseline_3sigma.py` fails on total outages. | Explicitly count and heavily penalize missing telemetry hours. |
| **Persistence > Spikes** | Real hardware faults exhibit multi-day outages; transient blips are noise. | High: Historical statistical outlier dispatches had 0% success. | Prioritize sustained downtime and cumulative hours over 1-hour 3-sigma spikes. |
| **Counters Accumulate** | `offline_duration_sec` does not clamp to 3,600s; rolls over across days. | Critical: Naive sums double-count downtime. | Transform counters via thresholding ($>0$), capping, or first-order differencing. |
| **Duplicate Row Clones** | 6,547 exact row copies in odd months (Sep, Nov, Jan). | Medium: Inflates aggregations by 1.2% in odd months. | Execute automated deduplication on `(gateway_id, ts_utc)` upstream. |
| **Dual ID Standards** | Colon-separated MAC vs bare hex formatting. | Critical: Unnormalized inner joins drop 100% of data. | Apply universal `normalise_gateway_id()` at all ingestion boundaries. |
| **Lifecycle Masking** | 12 gateways installed mid-2026; 12 decommissioned mid-window. | Critical: Dispatching to uninstalled sites guarantees €380 waste. | Filter candidates by operational lifetime: $	ext{installed} \le T \le 	ext{decommissioned}$. |
| **Meter Data Cliff** | `meter_read_success.csv` halts on January 26, 2026. | High: Cannot be used as live updating feature in Feb/Mar. | Treat historical meter reads as static risk priors; use telemetry as live dynamic driver. |
| **Engineer Review Leakage** | Conducted on Feb 15, 2026; lookahead bias for Weeks 1 and 2. | High: Violates temporal causality if used prior to Feb 15. | Strictly quarantine from early prediction features; use solely for post-hoc validation. |
| **RF CRC Noise is Ubiquitous** | `rx_crc_bad` > `rx_nr_pkts` in 38.5% of hours due to raw RF bursts. | Medium: CRC errors reflect environmental noise, not broken hardware. | Deprioritize raw CRC ratios from dispatch ranking. |
| **False Alarms are Costly** | 60.75% of past visits found no fault (€148,200 wasted). | Critical: €380 false alarm cost dictates conservative thresholding. | Design scoring to suppress false positives on borderline/noisy gateways. |

---

## 17. What We Deliberately DID NOT Do

It is just as important to explain what was **not** done in Phase 3, and why:

1. **We did NOT build a ranking formula or assign scoring weights:**
   - *Why:* Assigning weights (e.g. $0.4 	imes 	ext{offline} + 0.3 	imes 	ext{reboots}$) before defining the operational objective would be pure guesswork.
2. **We did NOT train machine learning models:**
   - *Why:* Training an XGBoost or Random Forest model without clean feature semantics, leakage boundaries, and ground-truth definitions produces unexplainable overfitted models.
3. **We did NOT optimize thresholds:**
   - *Why:* Threshold optimization belongs in backtesting against the €380 vs €600 business cost curve (Phase 5/6).
4. **We did NOT build an API, FastAPI endpoints, or Docker containers:**
   - *Why:* Software engineering wrappers must wrap verified, defensible logic. Packaging unverified code is wasted effort.
5. **We did NOT claim correlation proves causation:**
   - *Why:* High correlation between silence and unread meters proves co-occurrence, not direct mechanistic causality.
6. **We did NOT modify the supplied baseline or submission validator:**
   - *Why:* [`baseline_3sigma.py`](file:///d:/lpdg-nexora-2026/baseline_3sigma.py) and [`validate_submission.py`](file:///d:/lpdg-nexora-2026/validate_submission.py) are official reference benchmarks and must remain untouched.

---

## 18. How Phase 3 Changes Phase 4

Phase 3 evidence directly dictates the design choices of Phase 4 (Operational Definition of *"Needs a Visit"*):

1. **Phase 3 Discovery:** Completely silent active gateways emit zero telemetry rows and disappear from `baseline_3sigma.py`.  
   $ightarrow$ **Phase 4 Implication:** Phase 4 must define *"needs a visit"* to include total communication silence as a tier-1 critical failure mode.
2. **Phase 3 Discovery:** `Auffaellige Statistik` (statistical anomaly flags) historically yielded a 0.0% repair rate.  
   $ightarrow$ **Phase 4 Implication:** Phase 4 must reject generic statistical distance ($\mu + 3\sigma$) as a definition of failure, defining failure instead around sustained physical operational incapacitation.
3. **Phase 3 Discovery:** True component repairs show 38.8× higher median offline seconds and drop 47% upon repair.  
   $ightarrow$ **Phase 4 Implication:** Phase 4 must define severity based on multi-day cumulative downtime and boot loops rather than 1-hour blips.
4. **Phase 3 Discovery:** `offline_duration_sec` accumulates across hours and reaches >700,000s.  
   $ightarrow$ **Phase 4 Implication:** Phase 4 must define metrics using threshold exceedance hours or event diffs to avoid double-counting.
5. **Phase 3 Discovery:** Meter reading logs terminate on January 26, 2026.  
   $ightarrow$ **Phase 4 Implication:** Phase 4 must decouple dynamic real-time health scoring from live meter reads, using meter reads solely as an asset-level susceptibility prior.
6. **Phase 3 Discovery:** 12 master gateways were installed in mid-2026 and 12 were decommissioned mid-window.  
   $ightarrow$ **Phase 4 Implication:** Phase 4 must enforce strict operational filtering so that only active, commissioned assets are eligible for site visit dispatch.
7. **Phase 3 Discovery:** 60.75% of past visits were false alarms (€380 wasted each).  
   $ightarrow$ **Phase 4 Implication:** The definition of "needs a visit" must incorporate a high-confidence threshold that minimizes false dispatches on ambiguous, noisy sites.

---

## 19. The Engineering Story

*Use this narrative for a 2-to-3 minute spoken response in an interview:*

> "When approaching the NEXORA challenge, our objective was to decide which 15 gateways to visit each week under a strict €380 false alarm cost and a €600 unaddressed outage penalty. Rather than immediately jumping into machine learning or guessing ranking formulas, we recognized that the definition of 'needs a visit' was intentionally underspecified. We executed Phase 3 as a deep data investigation to establish empirical ground truth across 1.43 million telemetry rows and all historical maintenance records.
>
> We started by auditing data quality and immediately uncovered several critical traps: `gateway_master.csv` was encoded in Latin-1, causing UTF-8 parsers to crash; gateway IDs used two incompatible formats that caused relational joins to return zero rows; and odd-month telemetry contained exactly 6,547 identical duplicate rows that distorted aggregations.
>
> When we investigated telemetry semantics, we discovered that `offline_duration_sec` was not an hourly rate clamped to 3,600 seconds, but a cumulative firmware register accumulating up to 726,000 seconds across multi-day outages. More importantly, we proved that completely unpowered or disconnected gateways do not emit error rows—they simply emit zero records, resulting in a 13.5% active operational missingness. This exposed a fatal flaw in the provided 3-sigma baseline: because it only computes statistics on rows present in the recent window, a completely dead gateway receives zero flagged hours and is totally ignored by operations.
>
> We then cross-referenced sensor data with historical work orders and discovered that 60.75% of past technician dispatches were wasted false alarms where nothing was wrong on-site. Crucially, work orders dispatched for 'statistical anomalies' had a 0.0% repair rate, whereas true physical component fixes occurred during sustained blackouts and boot loops, showing a 38.8× median separation in downtime. Finally, we identified a hard data cliff: meter-reading logs terminate on January 26, 2026, proving that live dispatch decisions in February and March must rely on real-time telemetry proxies.
>
> By grounding our work in empirical evidence, Phase 3 prevented us from building an overfitted model that mimics historical false alarms, giving us the exact physical criteria required to design a robust, defensible ranking strategy in Phase 4."

---

## 20. Interview Questions and Answers

### Q1: Why did you perform a deep data investigation before building a ranking model?
**Strong Answer:**  
Because building a model or heuristic without understanding data semantics guarantees optimizing for the wrong objective. In this challenge, the definition of *"needs a visit"* was left underspecified, and we faced a steep €380 false alarm penalty. We needed to know what physical hardware failures look like in sensor data, what caused past false dispatches, whether data contained duplicates or leakage traps, and whether the provided baseline had structural blind spots. Phase 3 provided empirical proof of what matters before writing a single line of scoring logic.  
*Key Points:* Prevented premature optimization; discovered 60.7% false alarm rate; uncovered baseline blind spot.

### Q2: What was the biggest data quality issue you discovered?
**Strong Answer:**  
The dual identifier format and the Latin-1 character encoding were the most immediate pipeline blockers. `gateway_master.csv` used colon-separated 17-character hex strings, while telemetry used bare 12-character hex strings. An unnormalized inner join yielded exactly zero matches. Additionally, Latin-1 encoding in `gateway_master.csv` crashed standard UTF-8 parsers due to German sharp S characters. Normalization and defensive encoding were mandatory to connect asset metadata with sensor logs.  
*Key Points:* Colon vs bare hex; 0 join matches without normalization; Latin-1 encoding crash.

### Q3: How did you calculate telemetry missingness, and why is implicit missingness important?
**Strong Answer:**  
We evaluated the full observation window of 243 calendar days (5,832 expected hours) across 320 observed gateways ($1,866,240$ expected rows). We found zero explicit nulls in any column, but 432,853 expected hourly rows were missing entirely (23.19% unconditioned missingness). When conditioning on active gateway lifetime (accounting for mid-period installations and decommissionings), active gateways were silent 13.5% of the time. Implicit missingness is critical because IoT devices that suffer fatal power loss cannot report; silence itself is the failure signal.  
*Key Points:* 0 explicit nulls; 23.2% unconditioned vs 13.5% active lifetime; silence is the physical failure signature.

### Q4: What is the biggest weakness of the provided 3-sigma baseline?
**Strong Answer:**  
The baseline filters telemetry strictly on rows that exist in the recent 7-day window: `recent = window[window["ts"] >= end - dt.timedelta(days=7)]`. If a gateway suffers a catastrophic power outage or severed backhaul and goes 100% silent for the entire week, it produces zero rows in `recent`. As a result, `grouped.agg(flagged_hours=("flagged", "sum"))` contains zero rows for that gateway. It receives zero flagged hours and is completely omitted from dispatch consideration, allowing a €600/week unaddressed outage penalty to accumulate.  
*Key Points:* Only evaluates existing rows; completely blind to 100% silent dead gateways; allows €600/week penalty.

### Q5: How did you detect duplicates and why were they dangerous?
**Strong Answer:**  
We checked uniqueness on `(gateway_id, ts_utc)` and discovered exactly 6,547 duplicate records, isolated strictly to odd-numbered months (Sep 2025: 2,185; Nov 2025: 2,124; Jan 2026: 2,238). By checking all 57 columns, we verified they were 100% identical row clones caused by ingestion retries. They were dangerous because any rolling sum of downtime or reboots would double-count duplicate hours, artificially inflating downtime by over 1% in odd months and promoting healthy gateways above broken ones.  
*Key Points:* Exactly 6,547 duplicates in odd months; 100% identical clones; distorts rolling window sums.

### Q6: What is a cumulative counter and how did you verify its behavior?
**Strong Answer:**  
A cumulative counter is a firmware register that increments continuously across ongoing events rather than resetting to zero each hour. We observed values in `offline_duration_sec` exceeding 726,000 seconds (~200 hours) in a single hourly row, with 4.6% of August records exceeding 3,600 seconds. Longitudinal time-series tracking confirmed that during multi-day disconnections, the gateway accumulates downtime and transmits the total upon reconnecting. This matches the Data Dictionary definition of a 'counter'. Summing it naively would produce impossible numbers, requiring event diffing or threshold exceedance in feature engineering.  
*Key Points:* Values up to 726k sec; exceeds 3,600s in 4.6% of rows; requires event diffing or thresholding.

### Q7: What did the historical field visit data tell you about dispatch effectiveness?
**Strong Answer:**  
It proved that historical dispatching was deeply inefficient: 60.75% of past visits (390 of 642) concluded with `Kein Fehler gefunden` (€380 wasted each). More importantly, work orders dispatched for 'statistical anomalies' (`Auffaellige Statistik`) or 'weak signal' had a 0.0% repair rate. Technicians only resolved physical faults when there was sustained disconnection (65% true positive rate) or severe rebooting (56% true positive rate). This proved that generic statistical anomaly detection directly replicates past false alarms.  
*Key Points:* 60.75% false alarms (€148k wasted); statistical anomalies had 0% fix rate; sustained outages drove true fixes.

### Q8: What did parts replacement data reveal about physical failure modes?
**Strong Answer:**  
In the 166 work orders where physical components were replaced, failures were dominated by power supplies (`Netzteil`, 39), antennas (`Antenne`, 37), cables (`Kabel`, 35), full gateway swaps (`Gateway getauscht`, 30), and SIM cards (`SIM-Karte`, 25). This aligns directly with our telemetry findings: power supply decay causes reboot boot-loops; antenna/cable damage causes RF loss; and SIM degradation causes disconnection flapping.  
*Key Points:* 166 component replacements; power supplies, antennas, and gateway swaps dominate; aligns with telemetry.

### Q9: Why didn't you use meter-read success as your primary ranking feature?
**Strong Answer:**  
Because of a hard data cliff: `meter_read_success.csv` ends on January 26, 2026, exactly 7 days before the scored window begins on February 2, 2026. While fresh for Week 1, by Week 8 that data is two months out of date and completely blind to new failures. We concluded that historical meter reads must be treated as a static asset health prior, while dynamic weekly dispatch ranking must be driven by live telemetry proxies.  
*Key Points:* Stops on Jan 26, 2026; 0 overlap with scored window; 8-week stale lag by Week 8.

### Q10: What is data leakage and how did you prevent it with the engineer review?
**Strong Answer:**  
Data leakage occurs when a model uses information from the future that would not be available at decision time. Senior engineer Hoffmann's review of 120 gateways took place on February 15, 2026. Scored Weeks 1 and 2 occurred on February 2 and February 9. Using Hoffmann's verdicts (`Schlecht`) to predict Weeks 1 and 2 would be illegal lookahead bias. We strictly quarantined the review from early feature pipelines, reserving it as an evaluation check after February 15.  
*Key Points:* Review conducted Feb 15; Weeks 1 & 2 precede it; strictly quarantined to prevent lookahead bias.

### Q11: What did you discover about gateways in Master that had no telemetry?
**Strong Answer:**  
`gateway_master.csv` has 332 gateways, but telemetry only contains 320. We inspected the 12 missing gateways and discovered that all 12 have `installed_on` dates between May and July 2026. Because our evaluation window ends in March 2026, these are future network installations that did not yet physically exist. We established lifecycle masking to ensure an algorithm never dispatches a technician to an uninstalled site.  
*Key Points:* 12 gateways; commissioning dates in mid-2026; lifecycle masking prevents false dispatches.

### Q12: What did your correlation analysis reveal between telemetry and meter reading?
**Strong Answer:**  
Across all 7,223 overlapping gateway-weeks, telemetry completeness (`hours_reported`) had the single strongest positive correlation with meter reading success ($r = +0.786$), while total offline duration had a strong negative correlation ($r = -0.603$) and disconnections had $r = -0.557$. In contrast, raw packet count had zero correlation ($r = -0.005$) because packet volume reflects the size of the customer deployment (40 to 900 meters), not hardware health.  
*Key Points:* `hours_reported` $r = +0.786$; `offline_sec` $r = -0.603$; raw packet count $r pprox 0$.

### Q13: Does correlation prove causation in this context?
**Strong Answer:**  
No, correlation does not prove causation. Missing telemetry hours do not mechanically cause meters to fail; rather, an unpowered gateway simultaneously causes both telemetry silence and dropped meter packets. Similarly, a reboot does not inherently mean hardware failure; routine firmware updates also trigger restarts. We treat correlations as evidence of co-occurrence to identify candidate signals, not as proof of mechanistic causality.  
*Key Points:* Common-cause confounding; silence and meter drops share an underlying root cause (power loss).

### Q14: How did true faults separate from false alarms in pre-visit telemetry?
**Strong Answer:**  
Across 313 field visits, gateways where faults were genuinely fixed exhibited a 4.71× higher mean offline duration and 6.17× higher mean reboots than false-alarm visits. More dramatically, medians showed a 38.8× separation in offline duration (895,000s for true faults vs. 23,000s for false alarms). Furthermore, upon repair, offline duration dropped by 47% and reboots dropped by 35%, whereas false-alarm telemetry remained unchanged. This proves that persistent operational downtime cleanly separates real faults from noise.  
*Key Points:* 4.71× mean ratio; 38.8× median ratio; 47% downtime drop upon physical repair.

### Q15: Why did the engineer review separate so strongly on telemetry?
**Strong Answer:**  
In the 7 days prior to Hoffmann's audit, gateways labeled `Schlecht` exhibited 13.6× higher offline duration and 9.0× higher disconnections than `Normal` gateways. However, our verification audit revealed a key caveat: 13 of the 120 gateways reported zero telemetry hours during that week and were dropped from the arithmetic mean. 8 of those 13 were `Schlecht`, indicating that Hoffmann correctly flagged completely dark gateways that standard aggregations might drop.  
*Key Points:* 13.6× offline ratio; 9.0× disconnect ratio; 13 silent gateways omitted by standard mean.

### Q16: What surprised you most during Phase 3?
**Strong Answer:**  
The most surprising discovery was that historical work orders dispatched for 'statistical anomalies' (`Auffaellige Statistik`) had an exact 0.0% true positive repair rate across 87 visits. That was a profound revelation because the provided baseline (`baseline_3sigma.py`) is literally a statistical anomaly detector. It proved that building a mathematically clever anomaly detector directly replicates the exact operational failure that cost the company €148,000 in wasted visits.  
*Key Points:* 0.0% repair rate on statistical anomalies; baseline mimics this exact failure mode.

### Q17: Why didn't you train an ML model immediately in Phase 3?
**Strong Answer:**  
Because machine learning is an optimization tool, not a data discovery tool. If we had trained a model on historical work orders, it would have learned to predict past dispatch decisions, which were 60.7% false alarms. If we had evaluated it against meter-reading success, it would have failed after January 26 due to the data cliff. Performing Phase 3 first ensured we understood ground-truth physical failure modes before designing features or training models.  
*Key Points:* Training on historical dispatches trains on 60.7% noise; avoids premature optimization.

### Q18: What is lifecycle masking and how does it work?
**Strong Answer:**  
Lifecycle masking is an operational filter that enforces temporal asset validity: a gateway is only eligible for ranking on Monday $T$ if $	ext{installed\_on} \le T \le 	ext{decommissioned\_on}$. In Phase 3, we proved that 12 gateways in Master were commissioned in mid-2026 and 12 were decommissioned between September 2025 and February 2026. Without lifecycle masking, an algorithm might dispatch visits to decommissioned units or empty rooftops, guaranteeing a €380 penalty.  
*Key Points:* Filters candidate gateways by commissioning and decommissioning dates; prevents €380 wasted visits.

### Q19: How did you verify the claims in your report?
**Strong Answer:**  
In Micro-Phase 3.1, we executed an independent audit where every claim, ratio, and percentage was recalculated directly from raw data. We verified that the 6,547 duplicates were 100% full-row identical across all 57 columns, confirmed the 60.75% false alarm rate, and verified the 4.71× offline ratio. We also refined the missingness claim by proving that 9.7% was structural lifecycle missingness and 13.5% was operational downtime.  
*Key Points:* Recalculated from raw source; refined structural vs operational missingness; verified all 11 claims.

### Q20: How does Phase 3 directly inform your Phase 4 ranking design?
**Strong Answer:**  
Phase 3 established four non-negotiable architectural pillars for Phase 4:
1. An explicit silence penalty to catch dead gateways missed by the baseline.
2. Prioritizing persistent multi-day downtime and boot loops over transient statistical blips.
3. Event diffing and thresholding to handle cumulative firmware counters without distortion.
4. Asset lifecycle masking to filter uninstalled and decommissioned units.  
*Key Points:* Silence penalty; persistence over blips; counter diffing; lifecycle masking.

---

## 21. 30-Second Version

> "In Phase 3, we audited 1.43 million telemetry rows and auxiliary records to understand data quality and physical failure modes before designing a ranking model. We discovered that historical field dispatches had a 60.7% false alarm rate, with statistical anomaly dispatches achieving a 0.0% repair rate. We proved that completely silent gateways are the strongest predictor of meter reading failure ($r = +0.786$), yet the 3-sigma baseline is 100% blind to them. We also resolved critical data traps: Latin-1 encoding crashes, incompatible gateway ID formats, 6,547 duplicate records, cumulative firmware counters, and a hard meter-read data cliff on January 26, 2026. This empirical foundation directly guides our Phase 4 ranking strategy."

---

## 22. 2-Minute Version

> "The objective of the NEXORA challenge is to select 15 gateways per week for maintenance, balancing a €380 wasted visit penalty against a €600/week unaddressed outage cost. The challenge left 'needs a visit' underspecified, so Phase 3 executed a deep empirical investigation to establish ground truth.
>
> We audited all 5 datasets and immediately resolved critical pipeline blockers: `gateway_master.csv` was Latin-1 encoded, causing UTF-8 parsers to crash; gateway IDs used two incompatible formats (colon-delimited vs bare hex) that caused joins to fail completely; and odd-month telemetry contained 6,547 identical duplicate rows that distorted downtime aggregations.
>
> When profiling telemetry, we discovered that `offline_duration_sec` is not an hourly rate clamped to 3,600s, but a cumulative firmware register accumulating up to 726,000 seconds across multi-day outages. More importantly, unpowered gateways do not emit error logs—they go completely silent, resulting in a 13.5% operational missingness. This exposed a fatal flaw in the provided 3-sigma baseline: because it only aggregates over rows present in the recent window, a completely dead gateway receives zero flagged hours and is ignored.
>
> Cross-referencing 642 historical field visits revealed that 60.75% were false alarms where no fault was found. Dispatches initiated for 'statistical anomalies' had a 0.0% repair rate, whereas true component fixes occurred during sustained blackouts and boot loops (showing a 38.8× median separation in offline time). Finally, we identified a data cliff: meter-reading logs stop on January 26, 2026, meaning live dispatch decisions in February and March must rely on real-time telemetry proxies.
>
> In summary, Phase 3 proved that persistent downtime and silence drive true failures, preventing us from building an overfitted model that mimics historical false alarms."

---

## 23. 5-Minute Deep-Dive Version

> "To build an internship-winning solution for the NEXORA challenge, we treated Phase 3 as an exhaustive engineering audit. The business context requires dispatching up to 15 site visits per week. With a €380 penalty for false alarms and €600/week for unaddressed failures, selecting the wrong sites is extremely costly. Because the prompt left 'needs a visit' open, we investigated 1.43 million telemetry rows, asset registers, work orders, meter logs, and expert audits before designing any scoring formula.
>
> We began with pipeline integrity. We discovered that `gateway_master.csv` threw fatal `UnicodeDecodeErrors` under UTF-8 due to German sharp S characters encoded in Latin-1. We resolved incompatible gateway ID formats: Master and Work Orders used 17-character colon-delimited hex, while Telemetry used 12-character bare hex. An unnormalized join dropped 100% of data. We also uncovered 6,547 duplicate records concentrated strictly in September 2025, November 2025, and January 2026. Because these were 100% full-row identical clones, unadjusted rolling sums would overcount downtime by over 1% in odd months.
>
> Next, we investigated telemetry semantics. We discovered that `offline_duration_sec` reached 726,642 seconds (~200 hours) in single hourly rows. The Data Dictionary confirms this is an accumulated firmware counter. Treating it as an hourly rate clamped to 3,600s would either discard severe outages as outliers or double-count rolling sums. More critically, we audited missingness: while there were zero explicit nulls, 432,853 hourly records were absent. Differentiating structural missingness (future installs and decommissioned units) revealed that active gateways experienced a 13.5% operational dropout rate. This exposed the primary structural flaw of `baseline_3sigma.py`: because it only computes statistics on rows present in the recent 7-day window, a completely dead gateway emits zero rows, receives zero flagged hours, and completely escapes detection.
>
> We then evaluated maintenance ground truth. Across 642 historical field visits, 60.75% concluded with `Kein Fehler gefunden`, costing nearly €150,000 in wasted visits. When analyzing dispatch reasons, work orders initiated for 'statistical anomalies' (`Auffaellige Statistik`) or 'weak signal' had a 0.0% repair rate. True component repairs occurred during severe sustained outages and boot loops, where physical parts like power supplies and antennas were replaced. In pre-visit telemetry, true faults exhibited 4.71× higher mean offline time and a 38.8× higher median offline time (895k seconds vs. 23k seconds), dropping by 47% post-repair.
>
> Finally, we evaluated temporal boundaries. We discovered a hard data cliff: `meter_read_success.csv` ends on January 26, 2026, offering zero live coverage during the scored February–March window. We also quarantined Senior Engineer Hoffmann's February 15 audit from Weeks 1 and 2 to prevent lookahead leakage.
>
> In Micro-Phase 3.1, we independently verified all 11 quantitative claims against raw source data. This empirical foundation establishes four pillars for Phase 4: an explicit silence penalty, prioritizing persistent downtime over transient blips, event diffing for cumulative counters, and lifecycle masking to prevent false dispatches."

---

## 24. Personal Study Checklist

Before walking into the technical interview, verify that you can explain each of these concepts without looking at your notes:

- [ ] **The Economic Asymmetry:** I can explain the €380 false alarm cost vs. the €600/week unaddressed outage penalty.
- [ ] **The Five Datasets:** I know the purpose, grain, and temporal coverage of telemetry, master, meter reads, visits, and review.
- [ ] **Implicit Missingness:** I can explain why dead gateways emit zero rows rather than explicit nulls, and differentiate the 23.2% unconditioned from the 13.5% active-lifetime rate.
- [ ] **The 3-Sigma Blind Spot:** I can explain why `baseline_3sigma.py` fails on completely silent dead gateways.
- [ ] **Duplicate Telemetry:** I can explain why 6,547 exact row clones in odd months distort unadjusted rolling sums.
- [ ] **ID Normalization:** I can explain why raw joins produce 0 matches and how stripping colons resolves it.
- [ ] **Cumulative Counters:** I can explain why values exceed 3,600s and why event diffing/thresholding is required.
- [ ] **Field Visit Outcome Ratios:** I know that 60.75% were false alarms and that statistical anomaly dispatches had a 0.0% repair rate.
- [ ] **The Meter-Read Cliff:** I can explain why meter reads cannot be used as a live feature after January 26, 2026.
- [ ] **Temporal Leakage:** I can explain why using the February 15 engineer review on Weeks 1 & 2 is lookahead bias.
- [ ] **Lifecycle Masking:** I know that 12 master gateways were installed in mid-2026 and must be filtered out.
- [ ] **Correlation vs. Causation:** I can explain why $r = +0.786$ between silence and meter drops indicates co-occurrence, not mechanistic causation.
- [ ] **What We Did NOT Do:** I can explain why we deliberately avoided building ranking formulas or ML models in Phase 3.

---

## 25. Final Takeaway

1. **Do not memorize the numbers only. Understand the engineering reason behind each number.**  
   *Knowing that downtime reached 726,000s is good; explaining that it behaves as a cumulative firmware counter that accumulates across multi-day blackouts is what gets you hired.*
2. **Silence is the deadliest failure mode.**  
   *A dead IoT device cannot send an alarm; it simply stops transmitting. Catching silent gateways is the single biggest operational improvement over the baseline.*
3. **Statistical anomalies are not physical faults.**  
   *Past dispatches based on statistical outlier blips had a 0.0% true positive rate. True physical faults require sustained operational downtime.*
4. **Data engineering precedes modeling.**  
   *Fixing Latin-1 encoding, normalizing IDs, deduplicating records, and handling cumulative counters are prerequisites for any model to work.*
5. **Respect the temporal arrow of time.**  
   *Quarantining the February 15 review and accounting for the January 26 meter-read cliff proves you understand production data integrity.*
6. **Economics dictate algorithm design.**  
   *Because a false alarm costs €380, the ranking system must suppress borderline noise and only dispatch when there is high-confidence physical evidence.*

---

> Phase 3 status: VERIFIED WITH CORRECTIONS — READY FOR PHASE 4
