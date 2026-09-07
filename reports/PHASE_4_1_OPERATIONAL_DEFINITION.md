# Phase 4.1 — Defining "Needs a Visit"

**Project:** LPDG Innovation Hub Selection Challenge 2026 (NEXORA 2026)  
**Author:** Candidate Engineering Team  
**Phase Status:** Micro-Phase 4.1 — Operational Definition  
**Date:** September 2026  
**Reference Documents:**  
- [PHASE_3_DEEP_DATA_INVESTIGATION.md](PHASE_3_DEEP_DATA_INVESTIGATION.md)  
- [PHASE_3_VERIFICATION.md](PHASE_3_VERIFICATION.md)  
- [PHASE_3_EXPLAINED.md](PHASE_3_EXPLAINED.md)

---

## 1. Objective

The objective of Micro-Phase 4.1 is to establish a rigorous, defensible, and domain-grounded operational concept of:

$$\text{"Gateway Needs a Technician Visit"}$$

Before designing a numerical ranking formula, selecting feature weights, or training machine learning models, an engineer must first formalize what real-world condition the system is attempting to identify.

In the NEXORA challenge, the central question for any prediction Monday $T$ is:
> *"Given only information available strictly before prediction Monday $T$, what empirical evidence should make operations believe that a gateway deserves one of the 15 available physical technician visits?"*

This document translates the verified empirical discoveries of Phase 3 into an operational decision framework. It bridges raw sensor measurements and business action while respecting challenge constraints, economic penalties, temporal boundaries, and capacity limits.

---

## 2. Operational Problem

### 2.1 What Does "Needs a Visit" Mean?
In an industrial IoT utility network, a gateway does **not** need a technician visit simply because a sensor metric looks statistically unusual or deviates from a Gaussian distribution. A gateway needs a physical site visit if and only if:
1. **The asset is suffering an active, severe operational impairment** that prevents it from relaying utility meter readings;
2. **The impairment cannot be resolved remotely** via automated retries, cellular network reconnection, or remote software commands; and
3. **Physical intervention on-site** (e.g. replacing a blown power supply, repairing a damaged antenna, swapping a corroded cable, replacing an unseated SIM card, or swapping the entire physical gateway unit) is required to restore packet relay.

If a technician arrives on-site and the gateway is working normally, or if the problem was an external cellular carrier outage that resolved itself without physical repair, the dispatch was an operational failure.

### 2.2 Why "Statistical Anomaly" $
e$ "Needs a Technician Visit"
A statistical anomaly is purely a mathematical property of a probability distribution: it measures whether an observation lies in the tail of a historical distribution (e.g. $X > \mu + 3\sigma$).

Phase 3 established decisive empirical proof that statistical anomalies do not equate to physical hardware faults:
- **Historical work orders dispatched for `Auffaellige Statistik` (statistical anomalies) resulted in a 0.0% fault resolution rate across 87 dispatches** (88.5% no fault found, 11.5% access denied). Every single technician dispatched on statistical suspicion found zero physical faults on-site.
- **`Signal schwach` (weak cellular RSSI/RSRP) resulted in a 0.0% fault resolution rate across 79 dispatches.** Poor cellular coverage in a building basement is an environmental property of the site, not a gateway hardware defect. A technician visiting the site cannot move a cellular base station.
- **Conversely, work orders dispatched for `Keine Verbindung` (complete loss of connection) and `Haeufige Neustarts` (reboot loops) achieved 65.0% and 56.4% physical repair rates**, leading to component replacements (power supplies, antennas, cables, gateway swaps).

A statistical spike can be caused by benign network maintenance, momentary cell-tower handovers, or transient radio noise. Dispatching a technician on statistical blips is the primary reason why 60.75% of past historical visits were wasted false alarms.

### 2.3 Prioritization Problem vs. Binary Classification
In traditional machine learning, failure detection is often framed as an unconstrained binary classification task: predict whether gateway $i$ is broken ($\hat{y}_i \in \{0, 1\}$).

In this operational setting, binary classification is fundamentally mismatched with reality:
1. **Hard Capacity Constraint:** The field team has a fixed upper bound of **exactly 15 site visits per week**. The team cannot dispatch 0 visits, nor can they dispatch 30.
2. **Resource Allocation:** If 35 gateways exhibit degradation, the business cannot attend all 35. The algorithm must rank them by failure confidence, severity, and economic urgency, selecting the top 15.
3. **Zero-Defect Scenarios:** If only 6 gateways are genuinely degraded in a given week, the operations team must still dispatch 15 visits (the 15 visits are a budget cap that the challenge requires filling in `predictions.csv`). The algorithm must prioritize the 6 truly degraded units at ranks 1–6 and fill ranks 7–15 with the next most suspicious or historically vulnerable units.

Therefore, the problem is strictly a **constrained operational ranking and resource-allocation problem**, not an unconstrained binary classifier.

### 2.4 Economic Asymmetry and Loss Structure
The Challenge Brief defines an asymmetric cost structure:
- **Wasted Site Visit Penalty:** **€380** (Type I error / False Alarm / False Dispatch). A technician drives to the site, inspects the gateway, finds nothing wrong, and drives back. The €380 labor and travel cost is permanently lost.
- **Unaddressed Fault Penalty:** **€600 per week** (Type II error / False Negative / Missed Outage). A broken gateway fails to relay readings for 40 to 900 meters. The utility cannot bill its customers, leading to customer churn, regulatory penalties, and manual meter-reading trucks. This €600 loss recurs *every single week* until the gateway is fixed.

```
Economic Tradeoff:
+-----------------------------------------------------------------------------+
| Action Taken               | Gateway Was Fine      | Gateway Was Broken     |
+-----------------------------------------------------------------------------+
| Dispatch Technician        | €380 Wasted           | Fault Fixed (€600/wk   |
| (Top 15 Ranking)           | (False Positive)      | Loss Terminated!)      |
+-----------------------------------------------------------------------------+
| Do Not Dispatch            | €0 (Correct)          | €600 Lost THIS Week    |
| (Rank > 15)                |                       | + €600 NEXT Week...    |
+-----------------------------------------------------------------------------+
```

Because missed broken gateways compound at €600 every week while false dispatches cost €380 once:
- The system must have **high recall on severe, persistent failures**: missing an active failure is 1.58× more expensive than a false dispatch in week 1, and 3.16× more expensive by week 2.
- However, because the list is capped at 15 visits, **every slot wasted on a false alarm directly crowds out a potentially broken gateway**. A false positive in the top 15 induces a false negative for rank 16!

---

## 3. Signal → Condition → Decision Framework

To prevent ad-hoc heuristics and maintain clean architectural separation, the operational concept is structured into three distinct layers:

```
+-----------------------------------------------------------------------------+
| LAYER 1: OBSERVABLE SIGNALS (Raw & Cleaned Measurement Data)                |
| - Missing telemetry hours (implicit silence)                                |
| - Cumulative offline duration (offline_duration_sec)                         |
| - Disconnection count (disconnection_cnt)                                   |
| - Reboot events & causes (reboot_cnt, r_cnt_power_cycle)                    |
| - Historical meter read performance (pre-Jan 26 success_rate)               |
| - Asset lifecycle records (installed_on, decommissioned_on)                 |
+-----------------------------------------------------------------------------+
                                      ↓
+-----------------------------------------------------------------------------+
| LAYER 2: OPERATIONAL CONDITIONS (Inferred Physical Health State)            |
| - Condition A: Complete Communication Blackout (Total hardware/power death) |
| - Condition B: Severe Backhaul Detachment (Persistent offline state)        |
| - Condition C: Boot Loop Instability (Failing power supply/kernel panic)    |
| - Condition D: Flapping Connectivity (Antenna/cable/SIM degradation)        |
| - Condition E: Ineligible Asset (Not commissioned, already decommissioned)  |
+-----------------------------------------------------------------------------+
                                      ↓
+-----------------------------------------------------------------------------+
| LAYER 3: VISIT PRIORITY & RESOURCE ALLOCATION (Ranking & Selection)         |
| 1. Filter out ineligible assets (lifecycle mask)                            |
| 2. Evaluate physical condition severity & temporal persistence              |
| 3. Order eligible gateways by evidence strength and estimated urgency       |
| 4. Select top 15 gateways for the Monday work-order schedule                |
+-----------------------------------------------------------------------------+
```

### Layer 1: Observable Signals
These are factual, point-in-time sensor readings, missingness indicators, and asset metadata available strictly before prediction Monday $T$. No business interpretation is made at this layer.

### Layer 2: Operational Conditions
Observable signals are combined to infer physical asset states. A single elevated metric does not constitute a condition; an operational condition represents a synthesized, physically grounded failure hypothesis (e.g. *Gateway is experiencing repeated power supply brownouts causing boot loops*).

### Layer 3: Visit Priority
Operational conditions are evaluated against the weekly constraint (15 visits). The system weighs the severity, persistence, and confidence of each condition against the €380 vs €600 loss matrix to establish relative ranking.

---

## 4. Candidate Visit-Worthy Conditions

We define and evaluate 8 candidate conditions based on Phase 3 evidence. Not all conditions are equally valid for dispatch ranking.

---

### Condition A: Complete Communication Silence (Total Hardware / Power Outage)
- **What is the condition?** A gateway that was previously active and reporting suddenly emits **zero telemetry records** over an extended trailing window (e.g. 48 to 168 consecutive hours).
- **Data supporting it:** Missing hourly records in `telemetry/` Parquet partitions; +0.786 correlation between reported hours and meter reading success.
- **Why it justifies a visit:** A complete cessation of transmissions indicates catastrophic failure: AC mains power disconnection, blown power adapter, physical vandalism, or dead motherboard. No telemetry means zero meters relayed.
- **Possible false positive:** A gateway that was officially decommissioned by the utility, but the decommissioning paperwork has not yet been processed in `gateway_master.csv`.
- **Possible false negative:** Assuming silence is normal maintenance if the threshold window is set too wide.
- **Safe before prediction Monday?** **YES (SAFE).** Computed strictly from trailing telemetry timestamps prior to Monday 00:00:00 UTC.
- **Dynamic or historical?** **Dynamic.**

---

### Condition B: Persistent Backhaul Detachment (Severe Offline Downtime)
- **What is the condition?** The gateway remains attached to power and emits periodic telemetry, but records persistent, multi-day backhaul disconnections (e.g. cumulative offline duration spanning tens or hundreds of thousands of seconds across the week).
- **Data supporting it:** `offline_duration_sec` counter accumulation; -0.603 correlation with meter success; 13.6× higher offline duration in engineer `Schlecht` audit; 38.8× higher median offline time in true historical fixes.
- **Why it justifies a visit:** Cellular modem failure, severed coaxial antenna feed, or deactivated SIM card preventing data backhaul to the utility server.
- **Possible false positive:** Regional cellular carrier base-station maintenance that took down local towers for 12 hours and resolved automatically without gateway hardware faults.
- **Possible false negative:** Misinterpreting cumulative counter values as single-hour rates and filtering them out as anomalies.
- **Safe before prediction Monday?** **YES (SAFE).**
- **Dynamic or historical?** **Dynamic.**

---

### Condition C: Boot Loop Instability (Recurring Power Supply / Kernel Panics)
- **What is the condition?** The gateway reboots repeatedly across multiple hours (e.g. 10 to 30+ reboots per hour, recurring across multiple days).
- **Data supporting it:** `reboot_cnt`, `reboot_duration_sec`, `r_cnt_power_cycle`; true fault repairs exhibited 6.17× higher mean reboots (47.2 vs 7.65) and dropped 34.5% post-repair; parts replaced were dominated by power supplies (`Netzteil`, 39).
- **Why it justifies a visit:** Degrading electrolytic capacitors in power supplies cause voltage ripple under transmission load, triggering brownout resets. Firmware watchdog panics cause infinite reboot loops. This requires physical power supply or gateway board replacement.
- **Possible false positive:** An automated over-the-air firmware update pushed by network operations that rebooted the gateway 1–2 times during a scheduled maintenance window.
- **Possible false negative:** Setting reboot thresholds too high, missing slow power-supply degradation.
- **Safe before prediction Monday?** **YES (SAFE).**
- **Dynamic or historical?** **Dynamic.**

---

### Condition D: Disconnection Flapping (Marginal Cellular / Backhaul Instability)
- **What is the condition?** Rapid, repeated cycling between online and offline states (e.g. 20 to 50+ disconnections per hour) without catastrophic cumulative duration.
- **Data supporting it:** `disconnection_cnt`; -0.557 correlation with meter read success; 9.0× higher disconnections in engineer `Schlecht` audit; pre-visit disconnections were 2.5× higher in true faults.
- **Why it justifies a visit:** Loose antenna connector, water ingress in coaxial cabling, or intermittent SIM card tray contact causing constant link renegotiation.
- **Possible false positive:** Poor cellular signal propagation during atmospheric inversions or cell tower load balancing that causes link handovers without hardware defects.
- **Possible false negative:** Ignoring flapping when cumulative offline seconds appear low.
- **Safe before prediction Monday?** **YES (SAFE).**
- **Dynamic or historical?** **Dynamic.**

---

### Condition E: Compounded Degradation (Co-Occurring Offline + Flapping + Reboots)
- **What is the condition?** Simultaneous presence of multiple operational failure symptoms: elevated cumulative offline time, frequent disconnection flapping, and elevated reboot counts.
- **Data supporting it:** Gateways where technicians performed physical fixes (`Fehler behoben`) had simultaneous elevations across all three dimensions; engineer audit comments specifically cite compounding issues (*"haeufige Ausfaelle, wiederholt neu gestartet"*).
- **Why it justifies a visit:** Multiple distinct subsystems failing simultaneously represents a high-confidence hardware breakdown. The probability of co-occurring cellular carrier maintenance, power blips, and radio noise happening simultaneously by pure chance is extremely low.
- **Possible false positive:** Extremely low. Compounding symptoms filter out single-metric environmental noise.
- **Possible false negative:** A gateway that suffers a single clean mode of failure (e.g. pure silent power loss with 0 reboots) would be missed if compounding is strictly required as an AND-gate.
- **Safe before prediction Monday?** **YES (SAFE).**
- **Dynamic or historical?** **Dynamic.**

---

### Condition F: Chronic Historical Meter-Read Deficit
- **What is the condition?** A gateway that consistently failed to read its expected meter quota prior to February 2026 (e.g. weekly `success_rate` chronically $< 50\%$).
- **Data supporting it:** `meter_read_success.csv` (7,226 rows); 567 gateway-weeks had $< 50\%$ read success.
- **Why it justifies a visit:** Indicates chronically broken receiver hardware, damaged LoRa antenna, or deaf front-end amplifiers that continuously fail to relay billing packets.
- **Possible false positive:** Many meters behind this gateway were decommissioned or battery-depleted, but the utility's `meters_expected` database was not updated (administrative discrepancy, not gateway fault).
- **Possible false negative:** A previously healthy gateway that suddenly failed in February 2026 will have a pristine historical meter-read record.
- **Safe before prediction Monday?** **YES (SAFE, BUT STATIC).**
- **Dynamic or historical?** **Historical prior only.** Cannot reflect new outages occurring during the February–March scored window.

---

### Condition G: Asset Lifecycle Ineligibility (Uninstalled or Decommissioned)
- **What is the condition?** The asset either has a future commissioning date ($T_{	ext{Monday}} < 	ext{installed\_on}$) or was already taken out of service ($	ext{decommissioned\_on} < T_{	ext{Monday}}$).
- **Data supporting it:** `gateway_master.csv` (12 gateways installed May–Jul 2026; 12 decommissioned Sep 2025–Feb 2026).
- **Why it justifies a visit:** **IT DOES NOT.** Dispatching to an ineligible asset guarantees a **100% false positive (€380 wasted)**.
- **Possible false positive:** N/A (this is a negative filter).
- **Safe before prediction Monday?** **YES (SAFE).**
- **Dynamic or historical?** **Static / Lifecycle mask.**

---

### Condition H: Generic Statistical Outlier Detection (3-Sigma Exceedance)
- **What is the condition?** Any metric in the trailing 7 days exceeding its trailing 28-day gateway baseline by more than 3 standard deviations ($\mu + 3\sigma$).
- **Data supporting it:** `baseline_3sigma.py`.
- **Why it justifies a visit:** In theory, flags significant shifts from normal behavior.
- **Why it fails in practice (Evidence):** Historical work orders dispatched for statistical anomalies (`Auffaellige Statistik`) had a **0.0% physical repair rate**. A noisy or quiet gateway can breach $3\sigma$ on minor, harmless metric blips. Furthermore, complete silence emits 0 rows and is completely invisible to this condition.
- **Safe before prediction Monday?** **YES (SAFE).**
- **Operational Assessment:** **WEAK / REJECTED AS PRIMARY DISPATCH TRIGGER.**

---

## 5. Persistence

A cornerstone insight from Phase 3 is that **transient metric spikes are noise; persistent multi-day degradation is hardware failure**.

### Why Single-Hour Anomalies Are Misleading
In a wireless cellular telemetry network, isolated single-hour disruptions occur routinely without physical equipment damage:
- Cellular base-station overnight software updates (1–2 hours of disconnection).
- Temporary carrier tower congestion during local events.
- Power grid switching transients.
- Routine over-the-air firmware maintenance.

If an algorithm flags a gateway because offline seconds spiked during a single 2:00 AM maintenance window, the technician will arrive three days later to find the gateway operating perfectly (€380 wasted).

### The Spectrum of Persistence
We define four conceptual tiers of temporal persistence:

```
[Level 1: 1-Hour Anomaly]  --> Cellular handover / transient blip (Do NOT dispatch!)
            ↓
[Level 2: Multi-Hour Event] --> 4 to 12 consecutive hours of downtime (Elevated suspicion)
            ↓
[Level 3: Multi-Day Failure] --> 48 to 168 hours of sustained outage / silence (High-confidence fault!)
            ↓
[Level 4: Recurring Degrade] --> Outages recurring across multiple consecutive weeks (Chronic hardware decay)
```

1. **1-Hour Anomaly (Transient Noise):** A single isolated hour exceeding normal bounds. High probability of self-recovery. Not visit-worthy.
2. **Multi-Hour Persistence (Emerging Failure):** Downtime or disconnections spanning 4 to 12 consecutive hours within a day. Suggests localized power failure or severe link instability.
3. **Multi-Day Persistence (Confirmed Failure):** Continuous downtime or total communication silence spanning 48 to 168 hours. Negligible probability of self-recovery. High visit urgency.
4. **Chronic Recurrence (Physical Decay):** Gateways that repeatedly flap, boot-loop, or drop packets week after week. Reflects aging physical components (e.g. failing power supplies or corroded outdoor antennas).

### What Must Be Determined in Phase 5/6 Backtesting:
We do not hardcode arbitrary persistence cutoffs today. In Phase 5 and Phase 6, empirical backtesting against historical field visit outcomes and baseline benchmark costs will determine:
- Exactly how many hours of consecutive silence (e.g. 24h vs 48h vs 72h) maximize true positive fault detection.
- Whether rolling 7-day cumulative hours or consecutive streak counts provide higher ranking precision.

---

## 6. Complete Silence as a Special Case

The handling of completely silent gateways represents the most critical conceptual gap in the existing baseline.

### The Mechanistic Breakdown of Baseline Anomaly Detection
Traditional anomaly detection algorithms (including `baseline_3sigma.py`) operate under an implicit assumption:
$$	ext{An anomaly is an extreme value contained within an observed record.}$$

This creates a fatal architectural failure mode when applied to IoT devices:
```
Gateway Operating Normally        --> Emits 168 records/week --> Evaluated by 3-Sigma
Gateway Experiencing Flapping     --> Emits 168 records/week --> Evaluated by 3-Sigma
Gateway Dies Completely (No Power)--> Emits 0 records/week   --> COMPLETELY INVISIBLE!
```

### The Baseline Vulnerability Exposed:
In `baseline_3sigma.py`, the recent evaluation window is filtered as:
```python
recent = window[window["ts"] >= end - dt.timedelta(days=RECENT_DAYS)].copy()
grouped = recent.groupby("gateway_id").agg(flagged_hours=("flagged", "sum"))
```
- If gateway $G$ was commissioned and running in December and January, it exists in the asset master and in historical telemetry.
- On February 1, someone unplugs the gateway or its power supply burns out.
- During the week of February 2 to February 8, gateway $G$ transmits **zero packets**.
- When `rank_week` executes on Monday, February 9:
  - `window` contains historical rows for $G$ (so $G$ has a baseline $\mu$ and $\sigma$).
  - But `recent` contains **zero rows** for gateway $G$!
  - `recent.groupby("gateway_id")` does not contain gateway $G$.
  - Gateway $G$ receives **zero flagged hours**.
  - Gateway $G$ completely vanishes from the candidate ranking!

### The Operational Paradox:
A gateway with 5 hours of moderate disconnections gets flagged 5 times and ranks in the top 15. A gateway that is **100% dead, completely silent, and relaying zero meter readings for 900 customer meters receives a score of 0 and is completely ignored**.

### Operational Definition Principle:
**Silence is not the absence of data; silence is the presence of a critical failure signal.**  
The operational definition of *"needs a visit"* must explicitly treat missing telemetry hours as a first-class, high-severity operational failure condition.

---

## 7. Temporal Validity

Every candidate signal must be strictly classified by its availability prior to prediction Monday $T$. Any feature that consumes future information creates catastrophic lookahead bias (data leakage).

```
Timeline Relative to Prediction Monday T (00:00:00 UTC):
Past (t < T)                                  | Prediction Cutoff T | Future (t >= T)
[============== AVAILABLE DATA ==============]| <--- GATE CLOSED ---> | [=== STRICTLY FORBIDDEN ===]
- Trailing 7-day / 28-day telemetry          |                      | - Future telemetry
- Asset installation dates (<= T)             |                      | - Future decommissioning
- Historical meter reads (pre-Jan 26)         |                      | - Future work orders / reviews
- Past work orders (attended < T)             |                      |
```

### Temporal Safety Classification:

| Candidate Signal / Data Asset | Temporal Status | Operational Constraint & Leakage Rules |
| :--- | :--- | :--- |
| **Trailing Telemetry Windows** ($T - 7	ext{d}$ to $T$) | **SAFE** | Strictly compute aggregates on $t < T_{	ext{Monday}} 	ext{ 00:00:00 UTC}$. Never include hours from Monday itself. |
| **Trailing Telemetry Baseline** ($T - 28	ext{d}$ to $T$) | **SAFE** | Rolling historical statistics computed strictly prior to cutoff $T$. |
| **Historical Field Visits** (`visited_on` $< T$) | **SAFE** | Historical work order outcomes may inform static priors or repeat-visit suppression, provided visit date is strictly in the past. |
| **Asset Commissioning Date** (`installed_on`) | **SAFE** | Valid if $	ext{installed\_on} \le T$. Gateways installed in the future relative to $T$ must be masked out. |
| **Asset Decommissioning Date** (`decommissioned_on`) | **CONDITIONALLY SAFE** | **Leakage Trap:** Only valid if $	ext{decommissioned\_on} < T$. If a gateway was decommissioned on February 25, that fact cannot be known on February 2! |
| **Meter-Read Success Rate** (`meter_read_success.csv`) | **CONDITIONALLY SAFE** | Valid as a historical prior. **Staleness Trap:** Cannot be treated as live data after Jan 26, 2026. Lag grows from 1 week (Week 1) to 8 weeks (Week 8). |
| **Engineer Review Labels** (`engineer_review_2026-02.xlsx`) | **UNSAFE FOR WEEKS 1 & 2** | Conducted on **2026-02-15**. Strictly forbidden for predictions on Week 1 (`2026-02-02`) and Week 2 (`2026-02-09`). Conditionally safe only as evaluation benchmark after Feb 15. |
| **Global Dataset Normalization** (Full-dataset $\mu, \sigma$) | **UNSAFE** | Normalizing features using statistics computed across all 8 months (including March 2026) leaks future distributions into February predictions. |

---

## 8. Gateway Eligibility / Lifecycle

Not all 332 gateways in `gateway_master.csv` are eligible to receive a technician visit on a given Monday. Dispatching a technician to an ineligible asset guarantees a **€380 wasted visit penalty**.

### The Three Classes of Ineligible Gateways:
1. **Uninstalled / Future Assets:** Exactly 12 gateways in `gateway_master.csv` have commissioning dates in May, June, or July 2026. They did not physically exist on rooftops during the February–March 2026 scored window.
2. **Decommissioned Assets:** Gateways taken out of service by the utility prior to prediction Monday $T$. Once decommissioned, a gateway is intended to be dead; dispatching a technician to fix it is a pure operational error.
3. **Zero Operational Exposure:** Gateways that were never commissioned or deployed into active service.

### Conceptual Eligibility Rule:
On any scored Monday $T$, a gateway $g$ is defined as **Eligible for Dispatch Ranking** if and only if:

$$	ext{Eligible}(g, T) \iff \Big(	ext{installed\_on}(g) \le T\Big) \;\land\; \Big(	ext{decommissioned\_on}(g) 	ext{ is NULL} \;\lor\; 	ext{decommissioned\_on}(g) > T\Big)$$

Gateways failing this rule are masked out of the candidate pool before ranking begins.

---

## 9. False Positive vs. False Negative Tradeoffs

Every candidate operational condition carries specific failure modes that must be weighed against the €380 false alarm penalty and the €600/week unaddressed outage loss:

| Operational Condition | Potential False Positive (Wasted €380 Visit) | Potential False Negative (Unaddressed €600/wk Outage) | Net Operational Risk Profile |
| :--- | :--- | :--- | :--- |
| **Complete Telemetry Silence** | Asset was unannounced decommissioned; local utility site power shut off for planned building renovation. | Threshold window too long; dead gateway left unaddressed for weeks while waiting to confirm silence. | **High Benefit / Low Risk:** True positive correlation is +0.786. Must verify gateway was previously active. |
| **Persistent Cumulative Offline** | Carrier cell-tower outage affecting entire district; resolves automatically without physical gateway fix. | Cumulative counter rollover misinterpreted as zero downtime; real outage ignored. | **High Benefit:** True faults show 38.8× higher median offline seconds. Requires multi-hour persistence check. |
| **Reboot Boot-Looping** | Network operations pushes scheduled over-the-air firmware update causing 1–2 planned reboots. | Dismissing intermittent reboots as harmless, missing progressive power supply capacitor decay. | **Medium Benefit:** Reboots must be persistent across days or accompanied by high hourly frequency ($>10/	ext{hr}$). |
| **Disconnection Flapping** | Benign cellular carrier dynamic IP renegotiation or tower handovers occurring with zero packet loss. | Flapping ignored because cumulative offline duration appears low, missing damaged coaxial feed line. | **Moderate Benefit:** Weak on its own; highly reliable when combined with offline duration. |
| **Weak Cellular Signal (RSSI/RSRQ)** | Dispatching technician to a basement vault where cellular coverage has always been weak; technician cannot fix tower. | Ignoring a physical antenna that snapped off the roof, assuming signal was always bad. | **HIGH RISK / NEGATIVE BENEFIT:** 0% historical fix rate. Must NOT be used as primary dispatch driver! |
| **Radio CRC Errors (`rx_crc_bad`)** | Industrial RF noise or co-channel interference from nearby electronics; gateway hardware is 100% fine. | Severe antenna water damage corrupting legitimate packets dismissed as atmospheric noise. | **HIGH RISK / LOW BENEFIT:** Corrupted bursts exceed valid packets in 38.5% of hours network-wide. Highly noisy. |
| **Historical Meter Deficit** | Customer meters decommissioned or batteries expired, but expected database quota was never updated. | Healthy historical record masks a sudden physical gateway failure that occurred in February. | **Moderate Benefit:** Reliable asset prior, but blind to dynamic real-time failures. |

---

## 10. Baseline Gap Analysis

### What `baseline_3sigma.py` Does Well:
1. **Normalized Asset Baseline:** By comparing each gateway to its own trailing 28-day history ($\mu, \sigma$), it accounts for gateway-specific baselines (a naturally noisy site is not penalized for its normal background noise).
2. **Multi-Metric Coverage:** Incorporates offline duration, disconnection count, and reboot frequency simultaneously.
3. **Simplicity and Transparency:** Clear, explainable rationale string for every flagged breach.

### The Critical Gaps in `baseline_3sigma.py`:
1. **The 100% Silent Gateway Blind Spot:** As proven in Section 6, the baseline computes statistics only on rows present in the recent 7-day window. If a gateway dies completely and emits 0 rows, it receives 0 flagged hours and is completely omitted from the candidate list.
2. **Vulnerability to Outlier Spikes:** A gateway with a single, highly unusual 2-hour blip can accumulate enough metric breach flags to jump into the top 15, crowding out a gateway experiencing continuous 48-hour degradation.
3. **Ignores Asset Lifecycle:** Does not filter out uninstalled gateways or decommissioned assets.
4. **Ignores Meter Read Prior:** Does not incorporate whether the gateway actually relays meter readings successfully.
5. **Treats Cumulative Counters as Rates:** Computes standard deviations on raw counter values that can accumulate to >700,000 seconds, severely skewing Gaussian assumptions ($\mu, \sigma$).

---

## 11. Preliminary Operational Definition

We synthesize the preceding engineering analysis into a qualitative operational definition:

> ### Operational Definition: "Gateway Needs a Visit"
>
> A gateway is defined as **potentially visit-worthy** for a given deployment week if and only if, based strictly on information available prior to the Monday cutoff:
>
> 1. **Eligibility:** The gateway is an active, physically commissioned asset (installed on or before Monday, and not decommissioned).
> 2. **Physical Incapacitation:** The gateway exhibits high-confidence evidence of severe operational failure, characterized by:
>    - **Complete Communication Blackout:** An active gateway that previously reported normally has become entirely silent, emitting zero telemetry across an extended trailing window; **OR**
>    - **Persistent Operational Downtime:** The gateway suffers multi-day cumulative backhaul detachment or severe disconnection flapping that prevents packet relay; **OR**
>    - **Hardware Reboot Instability:** The gateway is trapped in a persistent reboot cycle (boot loop) indicative of power supply or firmware failure; **OR**
>    - **Compounded Subsystem Decay:** Co-occurring elevation of downtime, disconnections, and reboots that rules out single-metric environmental noise.
> 3. **Non-Transient Persistence:** The observed degradation reflects sustained or chronically recurring failure rather than an isolated, self-recovering single-hour anomaly.
> 4. **Economic Priority:** The estimated probability and severity of unaddressed meter-reading failure (€600/week ongoing loss) exceeds the operational risk of a false dispatch (€380 wasted visit), ranking the asset within the top 15 most urgent candidates for the available weekly field capacity.

*Note: This is an operational policy framework, not a numerical formula. Numerical weights, thresholds, and ranking equations will be empirically validated in Phase 5 and Phase 6.*

---

## 12. What We Know vs. What We Still Need to Test

### What We KNOW (Conclusively Established by Phase 3 & 4.1):
1. **Silence is Fatal:** Telemetry completeness (`hours_reported`) has the strongest positive correlation with meter reading success ($r = +0.786$). Completely silent gateways are critical failures.
2. **Baseline Blind Spot:** `baseline_3sigma.py` completely misses 100% silent gateways because it only groups rows that exist in the recent window.
3. **Statistical Anomalies Cause False Alarms:** Dispatches triggered by statistical anomalies (`Auffaellige Statistik`) historically had a 0.0% repair rate, driving a 60.75% overall false alarm rate.
4. **Persistent Downtime Reflects Real Faults:** True hardware fixes exhibit 38.8× higher median offline duration than false alarms, and downtime drops by 47% upon physical repair.
5. **Meter-Read Horizon Stops Jan 26, 2026:** Meter reads cannot serve as a live updating feature during the scored February–March window.
6. **Engineer Review Must Be Quarantined:** The February 15 review cannot be used for Weeks 1 and 2 predictions without lookahead bias.
7. **Lifecycle Filtering is Non-Negotiable:** 12 master gateways were installed in mid-2026 and must be masked out to avoid guaranteed €380 false dispatches.
8. **Counters Are Cumulative:** Firmware counters reach >700,000 seconds and require thresholding or differencing.

### What We STILL NEED TO TEST (To Be Solved in Phase 5 & 6):
1. **Silence Threshold Optimization:** Exactly how many consecutive hours of silence (e.g. 24h, 48h, 72h, or 168h) provide the optimal balance between catching dead gateways and avoiding temporary site power shutoffs?
2. **Persistence Windowing:** Does a rolling 7-day cumulative sum, a trailing streak count, or an exponential decay weighting provide the best discrimination?
3. **Relative Metric Weighting:** How should silence, cumulative offline duration, reboot frequency, and disconnection flapping be mathematically weighted in the final scoring formula?
4. **Historical Meter Deficit Incorporation:** Exactly how much weight should the static pre-January 26 meter success prior carry relative to live dynamic telemetry dropouts?
5. **Repeat Visit Dampening:** If a gateway was visited last week and `Kein Fehler gefunden` was recorded, how many weeks should it be penalized or suppressed to avoid repeating historical false alarm cycles?
6. **Economic Cost Optimization:** What scoring threshold minimizes the global challenge cost function ($380 	imes 	ext{False Visits} + 600 	imes 	ext{Unaddressed Weeks}$)?

---

## 13. Conceptual Decision Pipeline

The operational concept translates into an 8-stage conceptual decision pipeline for each scored Monday $T$:

```
[All 332 Master Gateways]
           ↓
[Stage 1: Lifecycle & Commissioning Filter]
  - Filter: installed_on <= T AND (decommissioned_on IS NULL OR decommissioned_on > T)
  - Result: Eligible candidate pool (~308–320 gateways)
           ↓
[Stage 2: Telemetry Data Ingestion & Deduplication]
  - Load trailing 28-day telemetry strictly for t < T
  - Deduplicate exact row clones on (gateway_id, ts_utc)
           ↓
[Stage 3: Silence & Completeness Detection]
  - Measure reported hours in trailing 7 days: hours_reported in [0, 168]
  - Identify completely silent active gateways (hours_reported == 0)
           ↓
[Stage 4: Operational Signal Extraction & Transformation]
  - Transform cumulative counters (threshold exceedance / diffing)
  - Extract disconnection flapping, reboot intensity, and boot loops
           ↓
[Stage 5: Persistence & Compounding Evaluation]
  - Separate multi-day sustained failure from 1-hour transient blips
  - Measure co-occurrence of downtime, flapping, and reboots
           ↓
[Stage 6: Historical Asset Prior Integration]
  - Ingest static pre-Jan 26 meter-read deficit as baseline risk factor
           ↓
[Stage 7: Multi-Criteria Ranking]
  - Rank eligible gateways by synthesized failure confidence and urgency
           ↓
[Stage 8: Top 15 Selection & Audit Reason Generation]
  - Select ranks 1 to 15
  - Format 300-character operational explanation for field operations manager
```

---

## 14. How This Leads to Phase 4.2 / Phase 5

Micro-Phase 4.1 establishes the conceptual rules of the game. The subsequent phases build directly upon this foundation:

```
[Phase 4.1: Operational Definition] (COMPLETE)
  - Established what "needs a visit" means physically and economically
  - Identified 4 valid failure conditions and rejected generic statistical outliers
  - Formalized lifecycle masking and the complete silence requirement
          ↓
[Phase 4.2: Mathematical Formulation & Scoring Strategy]
  - Translate qualitative conditions into formal mathematical feature representations
  - Define normalization, counter differencing, and silence scoring equations
  - Establish candidate scoring architectures (heuristic multi-criteria vs rule-based)
          ↓
[Phase 5: Feature Engineering & Baseline Enhancement]
  - Implement clean, reproducible code pipeline in Python / Pandas
  - Build feature store computing trailing-7d and trailing-28d metrics strictly for t < T
          ↓
[Phase 6: Backtesting, Cost Evaluation & Model Tuning]
  - Evaluate pipeline across the 8 scored weeks against baseline_3sigma.py
  - Calculate exact financial performance (€380 false visits vs €600 unaddressed outages)
```

---

## 15. Interview Explanation

*Use this 1-to-2 minute spoken response in an interview to explain why you developed an operational definition before building a scoring algorithm:*

> "After completing our deep data investigation in Phase 3, we deliberately paused before writing any ranking code or training models. We recognized that the central question of the challenge—*what does 'needs a visit' actually mean?*—was an operational question, not a mathematical one.
>
> In Phase 4.1, we translated our empirical discoveries into a formal operational decision framework. We established that a statistical anomaly is not a hardware failure: historically, work orders dispatched on statistical outlier blips had an exact 0.0% repair rate, driving a 60.7% overall false alarm rate that cost the company €148,000. True component repairs occurred only when there was sustained physical incapacitation: severe multi-day blackouts and boot loops, where median downtime was 38 times higher.
>
> Furthermore, we formalized the complete silence problem. Because the provided 3-sigma baseline only aggregates over rows that exist in the recent window, a completely dead gateway that emits zero telemetry receives zero flagged hours and is completely ignored by operations. Our framework establishes that silence is not missing data—it is a first-class operational failure signal.
>
> Finally, we structured the problem as a constrained prioritization task under an asymmetric cost matrix—balancing a €380 false visit penalty against a compounding €600 weekly outage loss under a strict 15-visit cap. Establishing this operational concept first ensured that when we design our scoring formulas in Phase 5, every single feature directly reflects a verified physical failure mode rather than arbitrary mathematical noise."

---

> Phase 4.1 status: OPERATIONAL DEFINITION ESTABLISHED — READY FOR PHASE 4.2
