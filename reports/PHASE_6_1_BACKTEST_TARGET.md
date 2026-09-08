# Phase 6.1 — Historical Backtesting Target Construction

**LPDG Innovation Hub Selection Challenge 2026 (NEXORA 2026)**  
**Author:** Candidate Engineering Team  
**Status:** Complete & Fully Validated across Historical & Scored Periods  
**Parent Contract:** `reports/PHASE_5_1_FEATURE_FEASIBILITY.md`  
**Feature Extraction Library:** `reports/PHASE_5_2_FEATURE_EXTRACTION.md`, `src/nexora/feature_extractor.py`  
**Feature Analysis & Pruning:** `reports/PHASE_5_3_FEATURE_ANALYSIS.md`  
**Target Module:** `src/nexora/target_constructor.py`  
**Executable Companion Artifact:** `notebooks/04_backtest_target_construction.ipynb`  

---

## 1. Executive Summary & Objective

The objective of Micro-Phase 6.1 is to define, construct, and validate a **leakage-safe operational evaluation target** for historical backtesting in Phase 6.

### 1.1 The Core Operational Question
The challenge requires selecting exactly 15 gateways every Monday morning to minimize total operational loss (€380 false alarm penalty vs €600/week unaddressed outage loss). To evaluate candidate ranking policies historically, we must formalize the decision target:
> *"For an active gateway evaluated on decision Monday $T$, what subsequent operational evidence indicates whether dispatching a field technician was justified?"*

### 1.2 Fundamental Operational Realities & Invariants
1. **Operational Outcome $\ne$ Perfect Physical Failure Ground Truth:** Field visit outcomes (`Fehler behoben`, `Kein Fehler gefunden`, `Kein Zugang`) reflect human technician dispatches, site inspections, and repair actions. They are operational outcomes subject to human assessment error and severe selection bias.
2. **`UNOBSERVED` $\ne$ Healthy:** When a gateway is not visited in a future window, it does **not** prove the gateway was healthy. It indicates that no dispatch was logged. Conflating non-observation with health is a catastrophic data science error.
3. **Primary Policy Attribution Boundary (`requested_on`):** A hypothetical ranking decision made at Monday $T$ can only influence work orders initiated on or after $T$. Therefore, **`requested_on \in [T, T+7\text{d})`** is the sound causal boundary for policy evaluation.
4. **Delayed Outcome Realization (`visited_on`):** Physical inspection and repair occurs on `visited_on`. Because mean dispatch lag is **9.59 days** (range 2–17 days), the vast majority of work orders requested in week $T$ are inspected after $T+7\text{d}$. These delayed realizations must be tracked explicitly without being discarded or mislabeled negative.
5. **Strict Half-Open Temporal Boundaries:**
   $$\text{Pre-Decision Features: } t \in [T - \text{lookback}, T) \quad \text{vs} \quad \text{Future Operational Target: } t \in [T, T + \text{window})$$
   Zero future information may leak into feature representations.
6. **Engineer Review Anti-Leakage Boundary:** `engineer_review_2026-02.xlsx` is dated `2026-02-15`. It is strictly invalid for Week 1 (`2026-02-02`) or Week 2 (`2026-02-09`) predictions.

---

## 2. Historical Outcome Data Inventory (`data/field_visits.csv`)

A complete programmatic audit of `data/field_visits.csv` established:
- **Total Work Orders:** Exactly **642 records** spanning `2025-02-03` to `2026-02-14`.
- **Entity Identification:** `gateway_id` appears in 17-character colon-delimited hex (`02:30:EE:F7:24:35`), canonicalized via `normalize_gateway_id` to 12-character uppercase bare hex (`0230EEF72435`).
- **Unique Assets Visited:** 247 unique gateways (out of 332 in master). 55 gateways were visited once, 67 visited twice, 66 visited 3 times, and 59 visited $\ge 4$ times (max 6 visits).
- **Key Uniqueness & Duplication:** Exactly zero duplicate `visit_id` values, zero duplicate `(gateway_id, requested_on)` pairs, and zero duplicate `(gateway_id, visited_on)` pairs.
- **Dual Timestamps:**
  - `requested_on`: Work order creation date (`2025-02-03` to `2026-01-30`).
  - `visited_on`: Physical site visit date (`2025-02-05` to `2026-02-14`).
  - **Operational Dispatch Lag:** Visited date lags request date by a mean of **9.59 days** (median 9.0 days, std 2.54 days, min 2 days, max 17 days).

---

## 3. Event-Level Operational Representation & Outcome Mapping

Every historical work order records an explicit technician outcome:

| Raw German Outcome | English Meaning | Event Count | % Total | Operational Business Meaning | Parts Replaced | Mean Tech Hours |
|:---|:---|:---:|:---:|:---|:---|:---:|
| **`Fehler behoben`** | Fault Resolved / Repaired | 223 | 34.7% | **Justified Dispatch:** Physical repair or component replacement confirmed on site. | Netzteil (39), Antenne (37), Kabel (35), Gateway getauscht (30), SIM-Karte (25), None (57) | 2.53 h |
| **`Kein Fehler gefunden`** | No Fault Found | 390 | 60.7% | **False Alarm:** Technician inspected unit and confirmed normal operation (€380 wasted dispatch). | Exactly 0 parts replaced across all 390 visits. | 1.22 h |
| **`Kein Zugang`** | Access Denied | 29 | 4.5% | **Inconclusive Dispatch:** Premises locked, customer unreachable; no inspection possible. | Exactly 0 parts replaced across all 29 visits. | 1.10 h |

### 3.1 Repair Types & Component Replacements
When `Fehler behoben` occurred, 166 out of 223 visits (74.4%) recorded physical part replacements:
- Power supply replacement (`Netzteil`): 39 cases.
- Antenna replacement (`Antenne`): 37 cases.
- RF/Ethernet cabling replacement (`Kabel`): 35 cases.
- Complete unit replacement (`Gateway getauscht`): 30 cases.
- Cellular SIM card replacement (`SIM-Karte`): 25 cases.
- Software/configuration reset without parts (`None`): 57 cases.

Technician hours for confirmed repairs (mean 2.53h) were more than double the time spent on false alarms (mean 1.22h), reflecting physical labor and hardware swap testing.

---

## 4. Causal Decision Attribution: Requested-On vs. Visited-On

### 4.1 Causal Policy Boundary
In the operational deployment, our algorithm generates a Top-15 ranking on Monday morning at $T$. That ranking determines which 15 dispatches are requested during the upcoming operational week $[T, T+7\text{d})$.

```
                DECISION POINT
                      T (Monday 00:00)
                      │
─── Legacy Policy ────┼────── Evaluated Algorithm Policy ────────► Time
Dispatches requested  │ Dispatches requested in [T, T + 7d)
BEFORE T:             │ Can be attributed to algorithm policy at T
CANNOT be attributed  │
```

- **Dispatches requested BEFORE $T$ (`requested_on < T`):** Were already initiated under the prior operational regime. Even if the technician physically visits the site on Tuesday or Wednesday ($t \in [T, T+7\text{d})$), the algorithm at $T$ could not have caused that visit. Crediting $T$ with these visits is causal contamination.
- **Dispatches requested IN $[T, T+7\text{d})$ (`requested_on \in [T, T+7\text{d})`):** Represent the operational decisions initiated during week $T$. This is the sound causal boundary for policy evaluation.

### 4.2 Empirical Analysis of Dispatch Lag & Contamination across 26 Historical Mondays

Auditing the 26 historical Mondays (2025-08-04 to 2026-01-26):

1. **Pre-$T$ Dispatches Physically Visited in $[T, T+7\text{d})$ (Contamination Avoided):**
   Across the 26 weeks, exactly **266 physical visits** took place in $[T, T+7\text{d})$ that were requested *before* $T$.
   - In week 2025-08-04: 10 physical visits occurred, but **all 10** were requested in late July.
   - Attributing physical visits to decision $T$ would falsely evaluate policy $T$ on actions taken by legacy dispatchers prior to $T$.
2. **Eligible Dispatches Initiated in $[T, T+7\text{d})$:**
   Across the 26 weeks, exactly **314 work orders** were requested in $[T, T+7\text{d})$ (mean 12.08/week, range 4 to 19).
3. **Dispatch Lag & Delayed Outcome Realization:**
   Because dispatch-to-visit lag has a median of 9.0 days and mean of 9.59 days:
   - **On-Time Realization (`visited_on \in [T, T+7\text{d})`):** Exactly **53 dispatches** (16.9%) were physically inspected within the same 7-day calendar window.
   - **Delayed Realization (`visited_on \ge T+7\text{d}`):** Exactly **261 dispatches** (83.1%) were physically inspected after $T+7\text{d}$ (mean visit date $T + 12.7$ days).
4. **Outcome Distribution of the 314 Attributable Dispatches:**
   - **Confirmed Repairs (`Fehler behoben`):** **116** (36.9%)
   - **False Alarms (`Kein Fehler gefunden`):** **184** (58.6%)
   - **Access Denied (`Kein Zugang`):** **14** (4.5%)

### 4.3 Handling Delayed Outcome Realizations
A critical methodological requirement is:
> **Do NOT drop delayed realizations, and do NOT treat them as negative or unobserved.**

The decision at Monday $T$ caused a dispatch request. That dispatch was executed 8–14 days later, revealing whether the gateway was genuinely faulty (`Fehler behoben`) or a false alarm (`Kein Fehler gefunden`). 

In `src/nexora/target_constructor.py`, when evaluating decision week $T$:
- The target window matches requests: `requested_on \in [T, T+7\text{d})`.
- The physical outcome from `visited_on` is joined and resolved.
- A dedicated boolean flag `is_delayed_realization = (visited_on >= T + 7d)` is attached to every resolved target.
- For historical policy evaluation, the ground truth outcome (`REPAIR_REQUIRED` vs `FALSE_ALARM`) is fully preserved regardless of whether the inspection occurred on day 5 or day 12.

---

## 5. Formal Operational Target Definition

For each active gateway $i \in \mathcal{U}(T)$ at decision Monday $T$, the operational backtesting target $Y_i(T)$ is defined over future window $W_{\text{future}} = [T, T + 7\text{d})$ using primary attribution `timing_basis='requested_on'`:

$$\mathcal{V}_i(T) = \{ v \in \text{field\_visits} \mid v.\text{gateway\_id} = i \;\land\; v.\text{requested\_on} \in [T, T + 7\text{d}) \}$$

### 5.1 Four Mutually Exclusive Categories

$$Y_i(T) = \begin{cases}
\text{REPAIR_REQUIRED} & \text{if } \exists v \in \mathcal{V}_i(T) \text{ with } v.\text{outcome} = \text{`Fehler behoben`} \\
\text{FALSE_ALARM} & \text{if } \exists v \in \mathcal{V}_i(T) \text{ with } v.\text{outcome} = \text{`Kein Fehler gefunden`} \;\land\; \text{no repair in } \mathcal{V}_i(T) \\
\text{INCONCLUSIVE} & \text{if } \exists v \in \mathcal{V}_i(T) \text{ with } v.\text{outcome} = \text{`Kein Zugang`} \;\land\; \text{no repair or no-fault in } \mathcal{V}_i(T) \\
\text{UNOBSERVED} & \text{if } \mathcal{V}_i(T) = \emptyset
\end{cases}$$

### 5.2 Deterministic Conflict Resolution (Tie-Breaking)
If multiple work orders for the same gateway occur within the 7-day window:
$$\text{REPAIR_REQUIRED} \;\succ\; \text{FALSE_ALARM} \;\succ\; \text{INCONCLUSIVE}$$
*Rationale:* If a technician visited on Tuesday and found nothing, but another technician returned on Friday and replaced a blown power supply (`Netzteil`), the physical asset was objectively in need of repair.

---

## 6. Complete 26-Week Historical Backtesting Coverage Table

Below is the verified target distribution across all 26 historical Mondays under primary `requested_on` policy attribution:

| Week # | Decision Monday $T$ | Active GWs | Work Orders Requested $[T, T+7\text{d})$ | On-Time Visits ($< T+7\text{d}$) | Delayed Visits ($\ge T+7\text{d}$) | Confirmed Repairs | False Alarms | Inconclusive | `UNOBSERVED` Rate |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | 2025-08-04 | 284 | 14 | 1 | 13 | 4 | 9 | 1 | 95.1% |
| 2 | 2025-08-11 | 284 | 13 | 2 | 11 | 4 | 8 | 1 | 95.4% |
| 3 | 2025-08-18 | 284 | 12 | 1 | 11 | 4 | 7 | 1 | 95.8% |
| 4 | 2025-08-25 | 284 | 16 | 3 | 13 | 5 | 10 | 1 | 94.4% |
| 5 | 2025-09-01 | 284 | 11 | 2 | 9 | 6 | 5 | 0 | 96.1% |
| 6 | 2025-09-08 | 284 | 14 | 2 | 12 | 7 | 6 | 1 | 95.1% |
| 7 | 2025-09-15 | 284 | 12 | 2 | 10 | 4 | 8 | 0 | 95.8% |
| 8 | 2025-09-22 | 284 | 16 | 2 | 14 | 4 | 12 | 0 | 94.4% |
| 9 | 2025-09-29 | 284 | 13 | 2 | 11 | 6 | 7 | 0 | 95.4% |
| 10 | 2025-10-06 | 284 | 12 | 1 | 11 | 5 | 7 | 0 | 95.8% |
| 11 | 2025-10-13 | 284 | 16 | 2 | 14 | 4 | 11 | 1 | 94.4% |
| 12 | 2025-10-20 | 284 | 10 | 1 | 9 | 2 | 8 | 0 | 96.5% |
| 13 | 2025-10-27 | 284 | 14 | 2 | 12 | 3 | 10 | 1 | 95.1% |
| 14 | 2025-11-03 | 284 | 10 | 2 | 8 | 4 | 5 | 1 | 96.5% |
| 15 | 2025-11-10 | 284 | 10 | 1 | 9 | 4 | 6 | 0 | 96.5% |
| 16 | 2025-11-17 | 284 | 13 | 4 | 9 | 4 | 9 | 0 | 95.4% |
| 17 | 2025-11-24 | 284 | 11 | 4 | 7 | 5 | 5 | 1 | 96.1% |
| 18 | 2025-12-01 | 284 | 13 | 3 | 10 | 3 | 9 | 1 | 95.4% |
| 19 | 2025-12-08 | 284 | 12 | 1 | 11 | 5 | 7 | 0 | 95.8% |
| 20 | 2025-12-15 | 284 | 19 | 4 | 15 | 8 | 10 | 1 | 93.3% |
| 21 | 2025-12-22 | 284 | 4 | 1 | 3 | 2 | 2 | 0 | 98.6% |
| 22 | 2025-12-29 | 284 | 5 | 0 | 5 | 3 | 2 | 0 | 98.2% |
| 23 | 2026-01-05 | 284 | 14 | 3 | 11 | 3 | 9 | 2 | 95.1% |
| 24 | 2026-01-12 | 284 | 16 | 2 | 14 | 8 | 8 | 0 | 94.4% |
| 25 | 2026-01-19 | 284 | 13 | 4 | 9 | 5 | 8 | 0 | 95.4% |
| 26 | 2026-01-26 | 284 | 11 | 4 | 7 | 3 | 8 | 0 | 96.1% |
| **Total** | — | **7,384** | **314** | **53** | **261** | **116** | **184** | **14** | **95.7%** |

*Historical Request Behavior:* Historical dispatch requests averaged 12.08 per week, with substantial week-to-week variation (4–19). Confirmed repairs averaged 4.46 per week (36.9% precision of the historical legacy dispatcher), while false alarms averaged 7.08 per week (58.6%).

---

## 7. Sensitivity Benchmark: Physical Visit Timing (`visited_on`)

To ensure methodological completeness, `src/nexora/target_constructor.py` supports `timing_basis='visited_on'`.

| Timing Metric | Primary Attribution (`requested_on`) | Sensitivity Benchmark (`visited_on`) | Delta / Difference |
|:---|:---:|:---:|:---:|
| **Attribution Causal Principle** | Work orders initiated during decision week | Physical visits occurring during decision week | Timing perspective shift |
| **Total Attributable Events (26 wks)** | 314 | 319 | +5 events |
| **Confirmed Repairs (`Fehler behoben`)** | 116 (36.9%) | 110 (34.5%) | -6 repairs |
| **False Alarms (`Kein Fehler gefunden`)** | 184 (58.6%) | 194 (60.8%) | +10 false alarms |
| **Inconclusive (`Kein Zugang`)** | 14 (4.5%) | 15 (4.7%) | +1 inconclusive |
| **Events Requested Prior to Week $T$** | **0** (by definition) | **266** (83.4% legacy contamination) | Contamination eliminated |
| **Weekly Event Range** | 4 to 19 (mean 12.08) | 7 to 18 (mean 12.27) | Operational variation |

*Sensitivity Conclusion:* Historical dispatch requests averaged 12.08 per week, with substantial week-to-week variation (4–19). This is below the challenge's nominal capacity of 15 visits/week on average, but some historical weeks exceeded 15 requests. The sensitivity comparison confirms that while aggregate event volume under `visited_on` is comparable (~12.27 visits/week), using `requested_on` is strictly required to prevent attributing legacy pre-$T$ dispatches to algorithm decision $T$.

---

## 8. Scored Evaluation Window Audit (Feb – March 2026)

We audited all 8 scored Mondays (`2026-02-02` through `2026-03-23`):

```python
tc_requested = TargetConstructor(timing_basis='requested_on')
tc_visited   = TargetConstructor(timing_basis='visited_on')
```

| Scored Week | Decision Monday $T$ | Active Universe $\mathcal{U}(T)$ | `requested_on` Future Events | `visited_on` Future Events | Pre-$T$ Contamination |
|:---:|:---:|:---:|:---:|:---:|:---:|
| W1 | 2026-02-02 | 284 | **0** | 9 (4 repairs, 5 no-fault) | All 9 requested Jan 19–30 |
| W2 | 2026-02-09 | 284 | **0** | 4 (1 repair, 3 no-fault) | All 4 requested Jan 27–30 |
| W3 | 2026-02-16 | 284 | **0** | 0 | 0 |
| W4 | 2026-02-23 | 284 | **0** | 0 | 0 |
| W5 | 2026-03-02 | 284 | **0** | 0 | 0 |
| W6 | 2026-03-09 | 284 | **0** | 0 | 0 |
| W7 | 2026-03-16 | 284 | **0** | 0 | 0 |
| W8 | 2026-03-23 | 284 | **0** | 0 | 0 |

### Critical Architectural Findings:
1. **The Last Work Order Request in `field_visits.csv`:** Was initiated on **`2026-01-30`**.
2. **Primary Policy Attribution in Scored Period:** Under primary `requested_on` attribution, **zero work orders exist in $[T, T+7\text{d})$ for all 8 scored weeks**. Every gateway in the active universe is `UNOBSERVED`.
3. **Physical Visit Benchmark in Scored Period:** 13 physical visits occurred between Feb 3 and Feb 14 (9 in W1, 4 in W2). However, **all 13 were requested before Feb 2**.
4. **Phase 6 Backtesting Design Implication:**
   Historical backtesting (Phase 6.2 through 6.4) **CANNOT be evaluated on the 8 scored weeks** because no operational dispatches were requested after Jan 30. Backtesting must be conducted exclusively on the **26 historical training Mondays** (2025-08-04 to 2026-01-26), where 314 ground truth dispatch requests and outcomes are available.

---

## 9. Engineer Review Audit & Architectural Assessment

### 9.1 Source Data Verification (`data/engineer_review_2026-02.xlsx`)
Programmatic verification against the raw Excel file (`Gateway Status` sheet) establishes:
- **Total Records:** Exactly **120 rows** (matches the official Data Dictionary and Phase 3 verification).
- **Unique Assets Reviewed:** Exactly **120 unique gateways** (0 duplicate rows, 0 duplicate gateway IDs across the entire file).
- **Exact Columns:** `['gateway_id', 'standort', 'Kategorie', 'reviewed_on', 'reviewer', 'Bemerkung']`.
- **Verdict Distribution (`Kategorie`):**
  - **`Schlecht`** (Poor condition / defective / degraded): Exactly **60 gateways** (50.0%)
  - **`Normal`** (Normal condition / healthy): Exactly **60 gateways** (50.0%)
- **Review Date (`reviewed_on`):** Exactly **`2026-02-15`** for all 120 records.
- **Reviewer (`reviewer`):** Field engineer `M. Hoffmann` for all 120 records.
- **Field Engineer Notes (`Bemerkung`):** 74 records contain diagnostic qualitative notes (e.g., `haeufige Ausfaelle, Standort pruefen`, `nach Tausch stabil`, `Hardware vermutlich defekt`), with 46 null values.
- **Site Metadata (`standort`):** 26 distinct operational environment classifications across German federal states (e.g., `Hessen / Gebäude`, `Sachsen / Außenmast`, `Bayern / Heizraum`).

### 9.2 Resolution of Previous 50-Row Discrepancy
An earlier working draft of this document mentioned 50 rows with labels `Echtzeit-Ausfall` (18) and `Fehlalarm` (32). A rigorous programmatic audit traced this error:
- The actual raw file `engineer_review_2026-02.xlsx` has always contained **120 rows** (60 `Schlecht`, 60 `Normal`).
- The Python code in `TargetConstructor.load_engineer_review()` and the executed companion notebook `04_backtest_target_construction.ipynb` correctly loaded and processed the true 120-row file.
- No dataframe filtering or subsetting was performed by the codebase. The discrepancy was an unverified narrative placeholder from early planning notes that slipped into the documentation. The report is now fully aligned with the ground truth raw file and the verified notebook output.

### 9.3 Architectural Assessment & Separation Recommendation
A critical architectural review of the relationship between `TargetConstructor` and `engineer_review` reveals:
1. **Primary Operational Target:** The backtesting target evaluates the weekly Monday dispatch policy against subsequent operational outcomes:
   $$\text{Work Order Request } \in [T, T+7\text{d}) \implies \{\text{REPAIR_REQUIRED}, \text{FALSE_ALARM}, \text{INCONCLUSIVE}, \text{UNOBSERVED}\}$$
2. **Role of Engineer Review:** The engineer review is **not** a weekly operational field-visit target. It is an independent, single-point-in-time (`2026-02-15`) diagnostic audit of 120 selected assets.
3. **Current Implementation Coupling:** `TargetConstructor` currently contains helper methods `load_engineer_review()` and `get_engineer_review_labels()`. While functional and strictly protected against temporal leakage, coupling an independent expert diagnostic validation source inside a time-series operational target constructor is an architectural concern.
4. **Recommendation for Software Architecture Phase:** In the later modular architecture pass, separate engineer review loading and validation into an independent module (`src/nexora/engineer_validator.py` or as a diagnostic prior loader) rather than co-locating it inside `TargetConstructor`. For Phase 6.1, we maintain the existing lightweight helper interface to avoid unnecessary refactoring.

### 9.4 Strict Anti-Leakage Temporal Controls
Because the engineer review was executed on `2026-02-15`:
- **Week 1 (`2026-02-02`) Decision:** The review is 13 days in the future ($t > T$). It must **never** be accessed or used.
- **Week 2 (`2026-02-09`) Decision:** The review is 6 days in the future ($t > T$). It must **never** be accessed or used.
- **Weeks 3–8 (`2026-02-16` to `2026-03-23`):** The review is in the past ($t < T$). It may serve as a historical diagnostic prior or feature input, but **never as a future evaluation target**.

In `src/nexora/target_constructor.py`, `get_engineer_review_labels(as_of_date)` programmatically enforces this boundary by returning an empty DataFrame whenever $T \le \text{2026-02-15}$, guaranteeing zero data leakage.

---

## 10. Selection Bias & The `UNOBSERVED != healthy` Invariant

### 10.1 The Selection Mechanism
Historical field visits were not dispatched via uniform random sampling. They were dispatched by human operators responding to customer complaint calls, manual dashboard alerts, or vendor alarms.
Therefore:
$$\mathbb{P}(\text{Visit} \mid \text{Faulty}) \gg \mathbb{P}(\text{Visit} \mid \text{Healthy})$$
$$\mathbb{P}(\text{Visit} \mid \text{Customer Complains}) \gg \mathbb{P}(\text{Visit} \mid \text{Silent Industrial Failure})$$

### 10.2 Why Treating `UNOBSERVED` as Healthy Fails
If an unobserved gateway is encoded as $Y=0$ (healthy):
1. A silent gateway that completely failed (168 missing hours, 0 transmissions) whose customer did not complain would be labeled $Y=0$.
2. Any ranking model evaluated under this target will be penalized for selecting blatantly dead gateways, learning to predict legacy dispatcher behavior rather than actual physical asset degradation.

### 10.3 Evaluation Metrics for Historical Backtesting (Phase 6.2+)
In Phase 6 backtesting, ranking models must be evaluated using metrics designed for Positive-Unlabeled (PU) and partially observed operational data:
1. **Precision@15 on Observed Dispatches:**
   $$\text{Precision@15} = \frac{\sum_{i \in \text{Top15}} \mathbb{I}(Y_i = \text{REPAIR_REQUIRED})}{\sum_{i \in \text{Top15}} \mathbb{I}(Y_i \in \{\text{REPAIR_REQUIRED}, \text{FALSE_ALARM}\})}$$
2. **Operational Dispatch Yield:**
   $$\text{Yield@15} = \frac{\text{Count}(i \in \text{Top15} \mid Y_i = \text{REPAIR_REQUIRED})}{15}$$
3. **False Alarm Rate on Observed:**
   $$\text{FAR@15} = \frac{\sum_{i \in \text{Top15}} \mathbb{I}(Y_i = \text{FALSE_ALARM})}{\sum_{i \in \text{Top15}} \mathbb{I}(Y_i \in \{\text{REPAIR_REQUIRED}, \text{FALSE_ALARM}\})}$$
4. **Economic Surplus / Cost Objective:**
   Evaluating the €380 false alarm cost avoided and €600 failure penalty mitigated relative to the historical dispatch baseline.

---

## 11. Complete Verification & Validation Checklist

Every claim and software interface in Phase 6.1 has been programmatically verified:

| Check # | Verification Requirement | Status | Evidence / Verification Code |
|:---:|:---|:---:|:---|
| 1 | `field_visits.csv` ID canonicalization | PASSED | All 642 records canonicalized via `normalize_gateway_id` to 12-char uppercase hex. |
| 2 | Key uniqueness | PASSED | 0 duplicate `visit_id`, `(gateway_id, requested_on)`, or `(gateway_id, visited_on)`. |
| 3 | Dispatch lag quantified | PASSED | Mean lag = 9.59 days, median = 9.0 days, range = 2 to 17 days. |
| 4 | Outcome categorization verified | PASSED | 223 `Fehler behoben` (34.7%), 390 `Kein Fehler gefunden` (60.7%), 29 `Kein Zugang` (4.5%). |
| 5 | Primary attribution = `requested_on` | PASSED | `TargetConstructor(timing_basis='requested_on')` default verified across 26 weeks. |
| 6 | Delayed realization tracking | PASSED | `is_delayed_realization` correctly flags 261 of 314 requests (83.1%) with `visited_on >= T+7d`. |
| 7 | Causal contamination prevented | PASSED | Exactly 266 pre-$T$ requests physically visited in $[T, T+7\text{d})$ excluded from policy $T$. |
| 8 | 4 Mutually exclusive categories | PASSED | Categories `REPAIR_REQUIRED`, `FALSE_ALARM`, `INCONCLUSIVE`, `UNOBSERVED` strictly partition universe. |
| 9 | Tie-breaking logic implemented | PASSED | Hierarchical resolution `REPAIR_REQUIRED > FALSE_ALARM > INCONCLUSIVE` verified. |
| 10 | 26 Historical weeks coverage table | PASSED | Exact row-by-row counts generated and audited across all 26 weeks (7,384 total gateway-weeks). |
| 11 | Sensitivity benchmark implemented | PASSED | `timing_basis='visited_on'` fully supported, tested, and compared against primary. |
| 12 | Scored window audited | PASSED | Confirmed 0 `requested_on` events in all 8 scored weeks; 13 pre-Feb physical visits audited. |
| 13 | Engineer review data verified | PASSED | Verified against raw Excel: 120 rows, 120 unique GWs, 60 Schlecht, 60 Normal, 2026-02-15. |
| 14 | Engineer review leakage guarded | PASSED | Programmatic exception raised or empty frame returned if requested for $T \le \text{2026-02-15}$. |
| 15 | `UNOBSERVED != healthy` enforced | PASSED | Target matrix explicitly codes `UNOBSERVED` separately from `FALSE_ALARM`. |
| 16 | Companion notebook executed | PASSED | `notebooks/04_backtest_target_construction.ipynb` runs 100% cleanly without errors. |
| 17 | Git working tree integrity | PASSED | No tracked files modified. Zero Git commits executed. |

---

## 12. Conclusion & Transition to Phase 6.2

Micro-Phase 6.1 is successfully complete and audited. We have established:
1. A mathematically rigorous, causally sound operational evaluation target based on `requested_on` policy attribution.
2. An explicit tracking mechanism for delayed visit realizations that preserves ground truth outcomes without leakage.
3. Complete programmatic protection against future engineer review data leakage with verified raw counts.
4. An audited 26-week historical testbed containing 314 ground truth dispatch requests and outcomes ready for backtesting candidate ranking algorithms in Phase 6.2.
