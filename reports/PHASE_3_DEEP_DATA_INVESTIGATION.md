# Phase 3 — Deep Data Investigation

**Project:** LPDG Innovation Hub Selection Challenge 2026 (NEXORA 2026)  
**Author:** Candidate Engineering Team  
**Phase Status:** Phase 3 — Complete  
**Date:** September 2026  
**Artifact Link:** [01_deep_data_investigation.ipynb](../notebooks/01_deep_data_investigation.ipynb)

---

## 1. Objective

The objective of Phase 3 is to execute a rigorous, empirical, and deep data investigation across all supplied datasets in the NEXORA 2026 challenge before committing to any ranking heuristics, feature sets, scoring models, or system architecture.

The Challenge Brief presents an operational problem:
LPDG operates a fixed radio data network across Germany. About 320 LoRaWAN gateways collect meter readings for utility customers (relaying for 40 to 900 meters per gateway). When a gateway degrades or fails, connected utility meters stop being read. The operations team can dispatch up to **15 field technician visits per week** (a hard upper constraint). Today, these sites are chosen through ad-hoc spreadsheets and intuition.
- **Wasted visit penalty:** €380 when a technician is dispatched and nothing is wrong (false alarm / false positive).
- **Unaddressed failure penalty:** €600 per week for every week a broken gateway remains unattended (false negative / delayed detection).

The Challenge Brief intentionally leaves the operational definition of *"needs a visit"* under-specified. The purpose of this investigation is to answer the fundamental questions:
1. What data is actually available, and how reliable is each source?
2. What are the temporal boundaries, granularities, and data horizons?
3. How many gateways exist and how consistently are they represented across tables?
4. How complete is the telemetry, and what forms does missingness take?
5. What data quality defects, anomalies, duplicate records, or format divergences exist?
6. How do historical field visits inform past failure modes, dispatch accuracy, and true positive rates?
7. What is the relationship between gateway telemetry degradation and downstream meter-reading success?
8. What does the February 2026 expert review reveal, and what temporal leakage constraints does it impose?
9. Which operational signals demonstrate persistent, physically grounded degradation versus transient noise?
10. What engineering implications arise for Phase 4 (Ranking Strategy & Scoring Design)?

**Strict Phase Boundary:** No final ranking formula, scoring weights, or predictive models are defined in this phase. All insights are grounded directly in empirical evidence from the supplied data.

---

## 2. Data Sources Investigated

Five primary datasets were inventoried, validated, and investigated:

| Dataset | Storage Format | Temporal Span | Spatial / Entity Grain | Row Count | Primary Key / Natural Key | Size on Disk |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`telemetry`** | Parquet (8 monthly partitions: `month=2025-08` to `2026-03`) | 2025-08-01 00:00:00Z to 2026-03-31 23:00:00Z | Gateway × Hour | 1,433,387 | `(gateway_id, ts_utc)` | ~104 MB |
| **`telemetry_sample_2025-08.csv`** | CSV (`utf-8`) | 2025-08-01 to 2025-08-31 | Gateway × Hour | 181,484 | `(gateway_id, ts_utc)` | 40.1 MB |
| **`gateway_master.csv`** | CSV (`latin1` / `ISO-8859-1`) | Asset register (static snapshot) | Gateway (Asset entity) | 332 | `gateway_id` | 31.9 KB |
| **`meter_read_success.csv`** | CSV (`utf-8`) | 2025-08-04 to 2026-01-26 (26 reporting weeks) | Gateway × Week (Monday grain) | 7,226 | `(week_start, gateway_id)` | 222.4 KB |
| **`field_visits.csv`** | CSV (`utf-8`) | Work orders: 2025-02-03 to 2026-01-30; Visits: 2025-02-05 to 2026-02-14 | Work Order (Event log) | 642 | `visit_id` | 62.6 KB |
| **`engineer_review_2026-02.xlsx`** | Excel OpenXML (`.xlsx`) | 2026-02-15 (single audit date) | Gateway (Audit sample) | 120 | `gateway_id` | 9.5 KB |

---

## 3. Data Quality Findings

### 3.1 Character Encoding Vulnerability in `gateway_master.csv`
Attempting to read `gateway_master.csv` using standard UTF-8 parsing triggers a fatal `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xdf in position 161`. Byte `0xDF` corresponds to the German sharp S (`ß`, as in `Großkunden`) or umlauts under Latin-1 / Windows-1252 encoding.
- **Finding:** The asset register must be read explicitly with `encoding='latin1'` (or `cp1252`). Pipelines assuming universal UTF-8 will crash in production.
- **Affected fields:** `tenant`, `site_type`, and `region`.

### 3.2 Dual Gateway Identifier Representation
Two conflicting formatting standards for `gateway_id` coexist across the project:
1. **Colon-delimited 6-byte hexadecimal format** (`XX:XX:XX:XX:XX:XX`, 17 characters), used in:
   - `gateway_master.csv` (e.g. `06:39:EA:56:02:C1`)
   - `field_visits.csv` (e.g. `02:30:EE:F7:24:35`)
   - `engineer_review_2026-02.xlsx` (e.g. `06:5B:92:87:16:CD`)
2. **Bare 12-character hexadecimal format** (`XXXXXXXXXXXX`, uppercase bare hex), used in:
   - `telemetry` Parquet partitions (e.g. `0639EA5602C1`)
   - `telemetry_sample_2025-08.csv`
   - `meter_read_success.csv` (e.g. `0202CB0A6B1F`)
- **Finding:** A naive SQL or pandas inner join between `telemetry` and `gateway_master` on raw `gateway_id` results in **0 matching rows**. An explicit normalization step (`normalise_gateway_id`) stripping colons and whitespace while converting to uppercase 12-character hex is mandatory.

### 3.3 Exact Row Duplication in Telemetry Partitions
Across the 1,433,387 telemetry rows, exactly **6,547 duplicate records** were detected on `(gateway_id, ts_utc)`.
- **Partition Distribution:**
  - `month=2025-08`: 0 duplicates (181,484 rows)
  - `month=2025-09`: **2,185 duplicates** (177,308 rows)
  - `month=2025-10`: 0 duplicates (178,698 rows)
  - `month=2025-11`: **2,124 duplicates** (172,421 rows)
  - `month=2025-12`: 0 duplicates (175,850 rows)
  - `month=2026-01`: **2,238 duplicates** (181,470 rows)
  - `month=2026-02`: 0 duplicates (170,151 rows)
  - `month=2026-03`: 0 duplicates (196,005 rows)
- **Nature of Duplicates:** Deep inspection across all 57 columns confirmed that 100% of these duplicates are **exact identical row clones** residing within the same monthly Parquet file.
- **Operational Risk:** Naive aggregations (`SUM(offline_duration_sec)`, `SUM(reboot_cnt)`) in odd months will overcount metrics by 1.2% to 1.3% unless deduplication is applied prior to feature calculation.

### 3.4 Explicit vs. Implicit Missingness
1. **Explicit Missingness:**
   - `telemetry`: Exactly **0 nulls** across all 58 columns and 1,433,387 records. No column contains `NaN`, `None`, or unpopulated values.
   - `gateway_master.csv`: `decommissioned_on` is null for 320 gateways (96.4%, meaning active), and populated for 12 gateways. `fw_updated_on` is null for 180 gateways (54.2%, meaning original factory firmware).
   - `field_visits.csv`: `parts_replaced` is null for 476 records (74.1%), representing visits where no physical parts were replaced.
   - `engineer_review_2026-02.xlsx`: `Bemerkung` is null for 46 records (38.3%).
2. **Implicit Missingness (Silent Dropouts):**
   - The observation window spans 243 calendar days (5,832 expected hours per gateway).
   - For 320 unique gateways present in telemetry, expected volume is `320 × 5,832 = 1,866,240` rows.
   - The actual row count is 1,433,387 (or 1,426,840 deduplicated).
   - **432,853 hourly gateway records are completely missing (23.2% implicit missingness)**.
   - Crucially, zero gateways reported all 5,832 hours (maximum reported was 5,752 hours; minimum was 261 hours; median was 5,165 hours).

---

## 4. Temporal Findings

### 4.1 Chronological Map & Granularity
```
August 2025        October 2025       December 2025      February 2026       March 2026
[-------------------------- TELEMETRY (Hourly, 8 Months) -----------------------------]
      [----------------- METER READ SUCCESS (Weekly) ------------| (STOPS Jan 26!)
[--------- HISTORICAL FIELD VISITS (Work Orders) ------------]
                                                            | (Single audit: 2026-02-15)
                                                            * ENGINEER REVIEW
                                                      [==== SCORED PREDICTION WINDOW ====]
                                                      (8 Mondays: 2026-02-02 to 2026-03-23)
```

### 4.2 The Meter-Read Data Cliff
The meter-reading dataset (`meter_read_success.csv`) covers 26 weekly reporting periods from `2025-08-04` through `2026-01-26`.
- **Finding:** The final recorded meter-reading week is `2026-01-26`. There are **zero meter read records for February or March 2026**.
- **Implication:** The scored challenge evaluation window begins on `2026-02-02` (Week 1) and ends on `2026-03-23` (Week 8). On Week 1, meter-reading data is fresh (lag of 7 days). By Week 8, meter-reading data is **8 weeks out of date**. Any scoring pipeline that assumes live trailing-7-day meter reads will fail during the scored window. Meter reading data can serve as a historical baseline / prior, but live telemetry must serve as the primary operational real-time proxy.

### 4.3 Field Visit Temporal Range
Work orders in `field_visits.csv` range from `2025-02-03` to `2026-01-30`, with technician attendance (`visited_on`) ranging from `2025-02-05` to `2026-02-14`.
- **Finding:** The first 6 months of field visits (February 2025 to July 2025, 329 visits) predate the telemetry record (which begins August 1, 2025). Pre-visit and post-visit telemetry analysis is only possible for the 313 visits attended between `2025-08-15` and `2026-02-14`.
- **Lead Time:** The time between a ticket being raised (`requested_on`) and technician attendance (`visited_on`) has a mean of 9.6 days (min 2 days, median 9 days, max 17 days).

### 4.4 Engineer Review Single-Moment Audit
`engineer_review_2026-02.xlsx` contains exactly 120 reviews conducted on a single day: **`2026-02-15`** by a single engineer (`M. Hoffmann`).

---

## 5. Gateway Coverage Findings

### 5.1 Cross-Dataset Gateway Overlap
A census across all datasets after identifier normalization revealed:
- **`gateway_master.csv`:** 332 total gateways
- **`telemetry`:** 320 unique gateways
- **`meter_read_success.csv`:** 299 unique gateways
- **`field_visits.csv`:** 247 unique gateways
- **`engineer_review_2026-02.xlsx`:** 120 unique gateways

### 5.2 The 12 "Missing" Master Gateways
Exactly 12 gateways present in `gateway_master.csv` have zero rows in `telemetry`:
- `0E:40:56:A2:CD:08` (installed 2026-05-10)
- `06:FE:DE:0E:77:89` (installed 2026-07-05)
- `02:E1:C7:0E:46:D1` (installed 2026-07-14)
- `06:86:FF:F4:B8:46` (installed 2026-07-05)
- `0A:EF:2E:5A:50:F0` (installed 2026-05-07)
- `06:F4:4C:2A:64:BD` (installed 2026-06-12)
- `06:C6:62:18:0A:40` (installed 2026-06-26)
- `0E:D1:1B:64:81:0A` (installed 2026-07-01)
- `0E:84:17:B0:8F:C9` (installed 2026-05-18)
- `02:F2:5E:3E:AE:98` (installed 2026-06-21)
- `0A:D3:9B:C5:95:EF` (installed 2026-06-17)
- `02:BC:BA:D3:0D:53` (installed 2026-06-05)
- **Finding:** Every single unobserved gateway has a future commissioning date in May, June, or July 2026. They were never installed during the August 2025 – March 2026 evaluation window.
- **Rule:** These 12 future gateways must be explicitly masked from ranking candidates during the scored window.

### 5.3 Decommissioned Gateways
Exactly 12 gateways in `gateway_master.csv` have a non-null `decommissioned_on` date:
- 10 gateways were decommissioned between September and December 2025.
- 2 gateways (`02:59:99:1B:A0:36` and `02:EB:C6:CD:43:98`) were decommissioned on `2026-02-04`.
- 1 gateway (`02:B7:42:64:6A:0E`) was decommissioned on `2026-02-25`.
- **Telemetry Verification:** Every decommissioned gateway reports telemetry up to 23:00:00 UTC on the calendar day immediately preceding its decommission date, and emits zero records thereafter.
- **Rule:** A gateway decommissioned prior to a scored Monday must not be dispatched for a site visit.

---

## 6. Telemetry Findings

### 6.1 Distributional Characteristics of Operational Metrics
Empirical profiling of core telemetry columns across the dataset reveals extreme zero-inflation and heavy right tails:

| Metric | Min | P25 | Median | Mean | P75 | P99 | Max | % Non-Zero |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`offline_duration_sec`** | 0 | 0 | 0 | 1,908.2 | 0 | 31,567 | 726,642 | 22.2% |
| **`disconnection_cnt`** | 0 | 0 | 0 | 0.80 | 0 | 15.0 | 55.0 | 22.2% |
| **`reboot_cnt`** | 0 | 0 | 0 | 0.06 | 0 | 1.0 | 32.0 | 1.6% |
| **`reboot_duration_sec`** | 0 | 0 | 0 | 109.9 | 0 | 376.0 | 439,061 | 1.6% |
| **`online_duration_mins`**| 48.2 | 59.6 | 60.17 | 60.14 | 60.78 | 62.28 | 64.25 | 100.0% |
| **`rx_nr_pkts`** | 9 | 25 | 30 | 305.6 | 36 | 61 | 133,945 | 100.0% |
| **`rx_crc_bad`** | 9 | 24 | 30 | 305.3 | 36 | 61 | 136,435 | 100.0% |
| **`avg_load1`** | 0.35 | 0.35 | 0.43 | 0.68 | 0.83 | 2.66 | 202.0 | 100.0% |
| **`avg_memfree`** | 30,147 | 55,150 | 63,020 | 64,132 | 72,112 | 94,580 | 114,706 | 100.0% |
| **`avg_uptime`** | 4.1 | 601,588 | 2.48M | 238.3M | 83.6M | 1.51B | 1.51B | 100.0% |

### 6.2 Cumulative Firmware Counters
A critical engineering discovery is that `offline_duration_sec` and `reboot_duration_sec` do **not** represent bounded 0-3,600 second hourly duration slices:
- In `offline_duration_sec`, values reach up to **726,642 seconds (~201.8 hours / 8.4 days)** in a single hourly row.
- In `reboot_duration_sec`, values reach **439,061 seconds (~122 hours)**.
- Inspection of longitudinal series for individual gateways confirms that firmware accumulates downtime across ongoing network dropouts until connection is re-established or the counter rolls over. Treating this column as a simple hourly rate without understanding its counter semantics would introduce severe distortion.

### 6.3 Radio Packet CRC Inversion
In 69,784 hourly rows (38.5% of rows), `rx_crc_bad` exceeds `rx_nr_pkts`.
- The Data Dictionary clarifies: `rx_nr_pkts` represents valid demodulated LoRa frames, whereas `rx_crc_bad` counts all received radio bursts that failed checksum validation.
- High `rx_crc_bad` indicates local RF noise or co-channel interference in industrial environments, not necessarily gateway hardware failure.

### 6.4 The 3-Sigma Baseline Structural Blind Spot
The provided baseline (`baseline_3sigma.py`) computes a 28-day mean and standard deviation for `offline_duration_sec`, `disconnection_cnt`, and `reboot_cnt`, flagging hours in the trailing 7 days where any metric exceeds $\mu + 3\sigma$.
- **Discovered Flaw:** Baseline filtering evaluates:
  ```python
  stats = window.groupby("gateway_id")[METRICS].agg(["mean", "std"])
  recent = window[window["ts"] >= end - dt.timedelta(days=RECENT_DAYS)].copy()
  grouped = recent.groupby("gateway_id").agg(flagged_hours=("flagged", "sum"))
  ```
- If a gateway suffered a catastrophic power failure or destroyed backhaul antenna and went **completely silent for 7 days**, it emits **zero rows** in `recent`.
- Consequently, `recent.groupby("gateway_id")` produces **zero rows** for this dead gateway. It receives 0 flagged hours and is completely omitted from the candidate list!
- In an operational utility network, a completely dead gateway is the single most urgent dispatch target (€600/week ongoing loss). The baseline completely ignores silent gateways.

---

## 7. Meter Read Findings

### 7.1 Read Success Rate Distribution
Across all 7,226 gateway-weeks in `meter_read_success.csv`:
- `meters_expected` ranges from 40 to 769 (median 278).
- `meters_read` ranges from 0 to 769.
- `meters_read` never exceeds `meters_expected` in any record.
- **Success Rate ($	ext{meters\_read} / 	ext{meters\_expected}$):**
  - Mean: 84.5%
  - Median: 90.9%
  - 10th percentile: 57.3%
  - 5th percentile: 38.6%
  - Severe failure ($< 50\%$ success): 567 gateway-weeks (7.8%).
  - Total blackouts (0% read): 2 gateway-weeks.

### 7.2 Correlation Between Telemetry Signals and Meter Reading
Weekly telemetry aggregates were joined with `meter_read_success.csv` across 3,628 aligned gateway-weeks:

| Weekly Aggregated Telemetry Metric | Pearson Correlation with Read Success Rate | Operational Rationale |
| :--- | :--- | :--- |
| **`hours_reported`** (Telemetry Completeness) | **+0.742** | Strongest positive predictor. Unreported hours directly reflect gateway downtime and dropped meter packets. |
| **`offline_sec_sum`** (Total Offline Seconds) | **-0.618** | Strong negative predictor. Backhaul dropouts prevent data relay to utility backend. |
| **`disc_cnt_sum`** (Disconnection Events) | **-0.580** | Frequent reconnection flapping degrades overall transmission throughput. |
| **`reboot_cnt_sum`** (Total Reboots) | **-0.300** | Reboot cycles interrupt relaying, but brief restarts are less harmful than prolonged disconnections. |
| **`rx_pkts_sum`** (Raw Received Packets) | **-0.001** | **Zero correlation.** Larger gateways have up to 900 meters and receive thousands of packets; smaller gateways have 40 meters. Scale reflects site size, not site health. |

---

## 8. Field Visit Findings

### 8.1 Outcome Breakdown and The 60.7% False Alarm Rate
Analysis of all 642 work orders in `field_visits.csv` reveals:
- **`Kein Fehler gefunden` (No fault found / False Alarm): 390 visits (60.7%)**
- **`Fehler behoben` (Fault resolved / True Positive): 223 visits (34.7%)**
- **`Kein Zugang` (Access denied / Inconclusive): 29 visits (4.5%)**

This provides empirical validation of the Challenge Brief’s opening statement: *"Today they choose those 15 from a spreadsheet and gut feel. Your job is to do better than that."* Over 60% of historic dispatches were wasted (€148,200 in direct wasted labor).

### 8.2 Outcome by Reported Dispatch Reason
Cross-tabulating technician outcomes against the recorded dispatch reason uncovers profound diagnostic disparities:

| Reported Dispatch Reason | Total Visits | Fehler behoben (Fixed) | Kein Fehler gefunden (No Fault) | Kein Zugang (No Access) | True Positive Rate (%) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`Keine Verbindung`** (No connection / Offline) | 100 | 65 | 32 | 3 | **65.0%** |
| **`Haeufige Neustarts`** (Frequent reboots) | 110 | 62 | 47 | 1 | **56.4%** |
| **`Kunde meldet Ausfall`** (Customer reports outage)| 101 | 54 | 46 | 1 | **53.5%** |
| **`Zaehler nicht gelesen`** (Meters not being read) | 86 | 42 | 42 | 2 | **48.8%** |
| **`Auffaellige Statistik`** (Statistical Anomaly) | 87 | **0** | 77 | 10 | **0.0%** |
| **`Routinepruefung`** (Routine inspection) | 79 | **0** | 73 | 6 | **0.0%** |
| **`Signal schwach`** (Weak cellular signal) | 79 | **0** | 73 | 6 | **0.0%** |

**Major Takeaway:**
When field visits were initiated due to statistical anomaly detection (`Auffaellige Statistik`), **technicians resolved zero faults** (88.5% no fault found, 11.5% no access). Similarly, weak cellular signal reports never resulted in a component fix (cellular coverage is an environmental property of the building/basement, not a gateway hardware defect). True positive dispatches were heavily concentrated in prolonged offline events (`Keine Verbindung`) and boot loops (`Haeufige Neustarts`).

### 8.3 Pre-Visit vs. Post-Visit Telemetry Validation
For 313 field visits where full 7-day pre-visit and 7-day post-visit telemetry existed, we measured telemetry shifts across outcomes:

| Outcome Group | Pre-Visit Offline (sec) | Post-Visit Offline (sec) | Pre-Visit Reboots | Post-Visit Reboots | Pre-Visit Reported Hours | Post-Visit Reported Hours |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`Fehler behoben`** (True Fault Fixed) | 1,913,525.5 | **1,012,626.7 (-47.1%)** | 47.2 | **30.9 (-34.5%)** | 100.9 | **117.2 (+16.2%)** |
| **`Kein Fehler gefunden`** (False Alarm) | 405,962.1 | 485,421.9 (+19.6%) | 7.7 | 8.5 (+10.4%) | 139.0 | 139.1 (0.0%) |
| **`Kein Zugang`** (Access Denied) | 142,196.6 | 79,829.4 | 0.1 | 0.1 | 147.9 | 145.6 |

**Physical Verification:**
- When a technician genuinely resolved a fault (`Fehler behoben`), offline seconds dropped by nearly half, reboots decreased by 35%, and reported telemetry hours rebounded.
- Gateways with true faults had **4.7x higher pre-visit offline time** and **6.1x higher pre-visit reboots** than gateways where technicians found nothing wrong.
- When `Kein Fehler gefunden` was returned, telemetry metrics were low prior to the visit and remained completely unchanged afterward.

### 8.4 Physical Failure Signatures (Parts Replaced)
Where physical parts were replaced (166 work orders), the failure distribution was:
- Power supply replacement (`Netzteil`): 39 visits (causes power instability / reboots)
- Antenna replacement (`Antenne`): 37 visits (causes weak RF / CRC corruption)
- Cable replacement (`Kabel`): 35 visits (causes intermittent dropouts)
- Complete gateway swap (`Gateway getauscht`): 30 visits (hardware brick / fatal board failure)
- SIM card swap (`SIM-Karte`): 25 visits (cellular registration failure)

---

## 9. Engineer Review Findings

### 9.1 Overview and Class Balance
In `engineer_review_2026-02.xlsx`, senior engineer M. Hoffmann audited 120 gateways on `2026-02-15`.
- Verdicts: Exactly **60 `Schlecht` (Bad)** and **60 `Normal` (Normal)** — a perfectly balanced audit sample.
- Qualitative remarks (`Bemerkung`): Populated for 53 of 60 `Schlecht` gateways and 21 of 60 `Normal` gateways.
  - Dominant `Schlecht` remarks: *"haeufige Ausfaelle, Standort pruefen"* (frequent dropouts, check location), *"Hardware vermutlich defekt"* (hardware probably defective), *"wiederholt neu gestartet"* (repeatedly rebooted).
  - Dominant `Normal` remarks: *"nach Tausch stabil"* (stable following component replacement).

### 9.2 Telemetry Alignment with Engineer Judgment
Evaluating the trailing 7 days of telemetry strictly prior to Hoffmann's audit date (`2026-02-08` to `2026-02-15`):
- **Mean 7-Day Offline Seconds:**
  - `Schlecht`: **1,176,507.3 seconds** (~326.8 hours of cumulative downtime)
  - `Normal`: **86,265.0 seconds** (~24.0 hours)
  - **Ratio: 13.6x higher offline duration for `Schlecht` gateways.**
- **Mean 7-Day Disconnections:**
  - `Schlecht`: **348.9 disconnections**
  - `Normal`: **38.8 disconnections**
  - **Ratio: 9.0x higher disconnection rate.**
- **Mean Reported Hours:**
  - `Schlecht`: 114.1 hours (missing ~54 hours in the week)
  - `Normal`: 146.1 hours (missing ~22 hours)

### 9.3 Temporal Leakage Warning
The engineer review took place on **2026-02-15**.
- In the scored challenge, Week 1 is `2026-02-02` and Week 2 is `2026-02-09`.
- **Finding:** Using `engineer_review_2026-02.xlsx` to inform rankings or train models for Week 1 or Week 2 constitutes severe temporal lookahead bias (data leakage).
- **Proper Role:** The review cannot be used as a feature before Feb 15. It may only serve as an external post-hoc sanity check for the final model on Week 3 (`2026-02-16`).

---

## 10. Cross-Dataset Findings

### 10.1 Entity Relationships and Schema Cardinality
```
[gateway_master] (1 row per gateway, 332 gateways)
       |
       +--(1 : N)-- [telemetry] (Hourly, 1.43M rows, 320 gateways)
       |
       +--(1 : N)-- [meter_read_success] (Weekly, 7.2k rows, 299 gateways, ends 2026-01-26)
       |
       +--(1 : N)-- [field_visits] (Work order events, 642 rows, 247 gateways)
       |
       +--(1 : 1 subset)-- [engineer_review_2026-02] (Single audit, 120 gateways on 2026-02-15)
```

### 10.2 Discrepancies in Meter Counts
`gateway_master.csv` records `n_meters_installed` (the registered meter count). `meter_read_success.csv` records `meters_expected` (meters scheduled for reading in a given week).
- Correlation between registered meters and weekly expected meters is high ($r = 0.94$), but they are not identical.
- In 71% of gateway-weeks, `meters_expected` deviates slightly from `n_meters_installed` due to churn, utility onboarding, or meter battery expiration. `meters_expected` is the authoritative operational denominator for read success rate.

---

## 11. Candidate Operational Signals

Below is the evidence table of operational signals evaluated during Phase 3. **No ranking weights or formulas are assigned.**

| Signal | What It Measures | Observed Distribution & Behavior | Empirical Evidence | Operational Interpretation | Limitations & Leakage Concerns |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Offline Duration** (`offline_duration_sec`) | Cumulative duration gateway radio/backhaul was detached | Highly skewed (78% zeros; P99 = 31k sec; max = 726k sec). | $r = -0.62$ with meter read success; 13.6x higher in engineer `Schlecht` audit. | Primary direct driver of failed meter packet relay. | Cumulative firmware counter behavior requires thresholding or diffing. |
| **Disconnection Flapping** (`disconnection_cnt`) | Frequency of backhaul dropouts per hour | Non-zero in 22% of hours; spikes up to 55/hr in degraded hardware. | $r = -0.58$ with meter success; 2.5x higher prior to true fault repairs. | Rapid connection flapping reflects failing power supply, SIM degradation, or RF antenna damage. | High disconnect count with very low offline duration may indicate benign network maintenance. |
| **Missing Telemetry Hours** (Implicit Silence) | Unreported hours where gateway emits no record | 23.2% overall missingness; worst active gateways miss >2,000 hours. | $r = +0.74$ between hours reported and read success; true faults report 38% fewer hours. | A dead/unpowered gateway cannot send alarms. Silence is the strongest operational failure signal. | Must distinguish decommissioned units and uninstalled units from actively failing units. |
| **Reboot Intensity** (`reboot_cnt`) | Hardware/software restart frequency | Concentrated in boot loops (max 32/hr); non-zero in only 1.6% of hours. | Pre-visit reboots dropped from 47.2 to 30.9 upon technician repair; 6x higher in true faults. | Boot looping indicates kernel panic, firmware corruption, or power supply ripple. | Isolated single reboots are normal maintenance; persistent rebooting is the true fault indicator. |
| **Backend Importance Scores** (`no_conn_importance`, `reboot_importance`) | Proprietary monitoring severity scores | High positive correlation with raw duration/counts; non-zero in identical periods. | Peaks sharply during major multi-day outages. | Provides vendor's heuristic weighting of dropouts and restarts. | Black-box calculation; undocumented units and scale. |
| **Meter Read Deficit** (`success_rate`) | Proportion of utility meters successfully read | Median 90.9%; 7.8% severe failures ($< 50\%$). | Directly measures the €600/week unread meter business penalty. | Ultimate ground-truth operational KPI for utility billing. | **STOPS on 2026-01-26.** Cannot be used as live trailing feature during February/March scored weeks. |
| **Radio CRC Failure Ratio** (`rx_crc_bad / rx_nr_pkts`) | Corrupted radio packets vs. valid frames | Exceeds 1.0 in 38.5% of hours due to raw noise burst counting. | Weak correlation with true component failure; `Auffaellige Statistik` yielded 0% fixes. | Reflects external RF environment and spectrum congestion. | Technician dispatch cannot resolve external radio interference or cell tower congestion. |
| **Cellular Signal Quality** (`rssi_bad`, `rscp_rsrp_bad`) | Signal strength degradation bands | Non-zero in 7% of hours; localized to basement/vault sites. | `Signal schwach` dispatches produced **0% fault resolutions**. | Indicates poor cellular carrier coverage at installation location. | Technicians cannot change building physics or cellular tower reach. Low utility for dispatch ranking. |

---

## 12. Data Limitations

1. **Meter-Read Horizon Cliff:** The complete cessation of meter-reading records on `2026-01-26` means that no direct meter-read feedback is available during the February–March 2026 scored window.
2. **Cumulative Counter Over-Accumulation:** Columns named with `_sec` (e.g. `offline_duration_sec`, `reboot_duration_sec`) are cumulative firmware registers that do not reset hourly and frequently exceed 3,600 seconds.
3. **Implicit Missingness in Telemetry:** Unpowered or disconnected gateways omit hourly records entirely rather than writing records with zero values.
4. **Duplicate Records in Odd Months:** Exact row duplication in partitions `month=2025-09`, `2025-11`, and `2026-01` (6,547 rows total) requires deduplication before computing window statistics.
5. **Character Encoding:** `gateway_master.csv` requires non-standard `latin1` decoding.
6. **Pre-Telemetry Field Visits:** More than half of historical field visits (Feb–Jul 2025) lack corresponding telemetry, restricting pre/post visit analysis to Aug 2025 – Feb 2026.
7. **Single-Observer Subjectivity:** The engineer review represents a single engineer's perspective (`M. Hoffmann`) on a single day.

---

## 13. Leakage Risks

1. **Engineer Review Lookahead Bias:** The audit occurred on `2026-02-15`. Using its labels or comments to rank gateways on `2026-02-02` (Week 1) or `2026-02-09` (Week 2) violates the strict temporal causality rule.
2. **Decommissioning Date Lookahead:** While decommissioning dates are recorded in `gateway_master.csv`, an operational ranking system predicting on `2026-02-02` must only use decommissioning events known as of that date.
3. **Future Installation Infiltration:** The 12 master gateways with commissioning dates in May–July 2026 must not be considered active candidates during February–March 2026.
4. **Pre-Scored Window Normalization:** Statistical baselines must strictly use trailing historical windows ($T < \text{Monday}$) rather than full-dataset normalization (which would incorporate future data from March 2026).

---

## 14. Key Findings

1. **Past Dispatches Were 60.7% False Alarms:** 390 of 642 past field visits concluded with `Kein Fehler gefunden`, costing €148,200 in wasted visits.
2. **Statistical Outlier Detection Caused 0% True Fixes:** Dispatches labeled `Auffaellige Statistik` had a 0.0% fault resolution rate. Naive 3-sigma anomaly detection mirrors this exact historical failure mode.
3. **Silence is the Deadliest Failure:** Telemetry completeness (`hours_reported`) is the single strongest correlate with meter-reading success ($r = +0.74$). Dead gateways stop sending telemetry.
4. **The Baseline Misses Dead Gateways Entirely:** `baseline_3sigma.py` computes statistics only on reported hours, completely blinding it to gateways that stopped transmitting during the recent window.
5. **True Faults Exhibit High Baseline Downtime:** Gateways where components were fixed had 4.7x higher offline duration and 6.1x higher reboot counts prior to the visit than false-alarm gateways.
6. **Meter Read Data Terminates Before Scored Window:** Because `meter_read_success.csv` ends on Jan 26, 2026, real-time dispatch decisions in Feb/Mar must rely primarily on telemetry-derived health signals.
7. **Firmware Counters are Cumulative:** Offline and reboot durations accumulate across events, reaching up to 726,000 seconds in a single row.
8. **Parquet Telemetry Contains 6,547 Row Clones:** Odd-month partitions contain exact duplicate rows that must be deduplicated.
9. **Engineer Audit Strongly Separates on Downtime:** Gateways classified as `Schlecht` exhibited 13.6x higher offline duration and 9.0x higher disconnections than `Normal` gateways in the 7 days prior.
10. **12 Master Gateways Do Not Yet Exist:** 12 gateways in the asset register have future installation dates in mid-2026.

---

## 15. Implications for Phase 4

The empirical evidence from Phase 3 establishes explicit design requirements for **Phase 4 (Ranking Strategy & Scoring Design)**:

1. **Explicit Silence Penalty:** The ranking system must explicitly measure and heavily penalize missing telemetry hours. A gateway that was active and suddenly went dark for 7 days must be prioritized, directly solving the fatal flaw of `baseline_3sigma.py`.
2. **Persistent Downtime Over Transient Blips:** Given that `Auffaellige Statistik` yielded 0% true fixes while `Keine Verbindung` yielded 65% true fixes, scoring must prioritize persistent, multi-hour cumulative downtime over isolated, single-hour statistical spikes.
3. **Cumulative Counter Handling:** Offline and reboot counters must be handled with appropriate thresholding, capping, or diffing rather than naive rate assumptions.
4. **Bridging the Meter-Read Data Cliff:** Because live meter-read data is missing during the scored window, the ranking pipeline must utilize historical meter-read deficit (up to Jan 26) as a static prior/risk factor, coupled with real-time telemetry degradation as the dynamic trigger.
5. **Decommissioned & Future Gateway Filtering:** The pipeline must enforce strict operational masking: any gateway not yet installed or already decommissioned prior to the target Monday must be filtered out before ranking the top 15.
6. **False-Positive Suppression & Cost Asymmetry:** Because a wasted visit costs €380, candidate ranking must avoid noisy, volatile signals like weak cellular RSSI and radio CRC noise, focusing strictly on high-confidence failure signatures (prolonged offline status, persistent boot loops, severe packet relay dropouts).
7. **Anti-Leakage Architecture:** All feature computation must strictly enforce temporal isolation, ensuring that features for any scored Monday $T$ consume data strictly from $t < T$.
