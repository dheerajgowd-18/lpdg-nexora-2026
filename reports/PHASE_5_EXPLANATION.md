# Phase 5 — Feature Engineering and Signal Selection

**LPDG Innovation Hub Selection Challenge 2026 (NEXORA 2026)**  
**Document Type:** High-Level Technical Explanation & Engineering Narrative  
**Audience:** Technical Reviewers, Evaluators, and Engineering Leadership  
**Status:** Complete, Validated & Fully Documented  
**Reference Technical Reports:**
- [`reports/PHASE_5_1_FEATURE_FEASIBILITY.md`](PHASE_5_1_FEATURE_FEASIBILITY.md)
- [`reports/PHASE_5_2_FEATURE_EXTRACTION.md`](PHASE_5_2_FEATURE_EXTRACTION.md)
- [`reports/PHASE_5_3_FEATURE_ANALYSIS.md`](PHASE_5_3_FEATURE_ANALYSIS.md)
- Codebase: `src/nexora/data_loader.py`, `src/nexora/feature_extractor.py`
- Executable Notebooks: `notebooks/02_feature_extraction_validation.ipynb`, `notebooks/03_feature_analysis.ipynb`

---

## 1. What Phase 5 Was Trying to Solve

The core operational challenge of NEXORA 2026 is simple to state: **every Monday morning, select up to 15 IoT gateways most worth physical inspection by field engineers**.

To accomplish this, we have access to hourly gateway telemetry (over 1.4 million rows spanning August 2025 through March 2026), gateway asset registry metadata, and historical weekly smart meter collection records.

However, **jumping directly from raw telemetry to a final ranking score would be dangerous and poor engineering**. In real-world IoT operations:
1. **Different fields have radically different meanings:** An incremental counter (e.g., reboots per hour) cannot be processed the same way as a cumulative firmware clock (e.g., offline seconds since boot).
2. **Missing telemetry is itself meaningful:** A gateway that sends no data might be completely offline, physically unplugged, or decommissioned. Treating missing packets as numeric zero would completely distort anomaly detection.
3. **Severe collinearity and redundancy:** Multiple raw fields often measure the exact same physical reality under different names or mathematical representations. Retaining all of them produces bloated, brittle scoring formulas.
4. **Information availability differs over time:** Certain datasets (such as meter reading history or human engineer audits) terminate or occur on specific dates. Using them blindly without temporal boundaries introduces fatal lookahead leakage.
5. **Leakage must be prevented by construction:** At decision Monday $T$, no information occurring at or after $T$ ($t \ge T$) can ever be allowed to influence features.

Phase 5 was designed to solve these foundational data reality issues before any ranking strategy was built. The goal was to transform messy, heterogeneous raw telemetry into a **compact, validated, leakage-safe, and defensible set of operational signals**.

---

## 2. Phase 5 in One Picture

Phase 5 progressed through three sequential micro-phases, moving from theoretical signal design to validated code and empirical statistical pruning:

```
Raw Telemetry + Gateway Master Register + Historical Meter Data
                           │
                           ▼
              Understand Feature Semantics
         (Incremental events vs. cumulative clocks)
                           │
                           ▼
          Define Candidate Features (Phase 4.2)
                (20 Candidate Features)
                           │
                           ▼
   Phase 5.1: Feasibility & Temporal Contract Audit
        - 15 READY (constructible without leakage)
        - 4 CONDITIONAL (unresolved parameters/drift)
        - 1 DEFERRED (unstable ratio)
                           │
                           ▼
    Phase 5.2: Deterministic Feature Extraction Code
         (`src/nexora/feature_extractor.py`)
        - Canonical gateway ID normalization
        - Active lifecycle universe gating
        - Retention of silent gateways
        - 20/20 invariant verification checks passed
                           │
                           ▼
   Phase 5.3: Empirical Distribution & Correlation Analysis
        - Quantile distributions & skewness profiles
        - Pearson (linear) & Spearman (rank) collinearity
        - Retrospective alignment with historical visits
                           │
                           ▼
             Defensible Signal Pruning
        - 3 Core Ranking Signals (F02, F09, F16)
        - 1 Conditional Silence Override (F05)
        - 3 Transformed Signals (F04, F06, F12)
        - 3 Deferred Backtest Options (F08, F10, F17)
        - 4 Dropped Collinear/Static Signals (F01, F03, F18, F20)
        - 1 Hard Eligibility Gate (F19)
                           │
                           ▼
       Defensible Feature Layer for Phase 6 Backtesting
```

---

## 3. Phase 5.1 — Feature Feasibility

### What is "Feature Feasibility"?
Before writing production extraction code or fitting models, we performed a feasibility audit on the 20 candidate features specified in Phase 4.2. "Feasibility" answers a fundamental systems question:
> *Can this feature be calculated accurately, reproducibly, and strictly without lookahead leakage from local source files for every scored Monday?*

Crucially, Phase 5.1 made an important distinction between **prediction-time availability** (is the data physically present before Monday $T$?) and **operational usefulness** (does this signal actually help prioritize broken hardware?). A feature might be mathematically computable, but if its underlying data source stops updating or suffers from counter resets, it cannot be safely used.

Every candidate feature was assigned to one of three operational categories:
- **READY (15 features):** Fully supported by raw data, clear semantics, zero lookahead leakage, constructible for all evaluation weeks.
- **CONDITIONAL (4 features):** Constructible in principle, but dependent on unresolved counter reset mechanics or uncalibrated heuristic thresholds.
- **DEFERRED (1 feature):** Structurally unstable or noisy; deferred indefinitely.

### The 15 READY Features
These 15 features formed the authoritative feature contract for implementation:

| Feature ID | Feature Name | Operational Meaning |
| :--- | :--- | :--- |
| **F01** | `reported_hours_7d` | Count of unique hours with observed telemetry in the trailing 7 days $[T-7	ext{d}, T)$. |
| **F02** | `missing_hours_7d` | Hourly packet deficit relative to continuous weekly operation ($168 - 	ext{F01}$). |
| **F03** | `reporting_ratio_7d` | Normalized availability ratio ($	ext{F01} / 168.0$), bounded in $[0.0, 1.0]$. |
| **F04** | `consecutive_missing_at_cutoff` | Elapsed hours from decision Monday $T$ back to the latest observed telemetry packet. |
| **F05** | `is_completely_silent_7d` | Binary indicator ($\mathbb{I}(	ext{F01} == 0)$) flagging gateways with zero telemetry in the trailing 7 days. |
| **F06** | `offline_duration_max_7d` | Peak reported value of the `offline_duration_sec` counter in the trailing 7 days. |
| **F08** | `offline_hours_gt_3600_7d` | Count of observed hourly packets where the offline counter exceeded 3,600 seconds. |
| **F09** | `reboot_cnt_sum_7d` | Total sum of incremental reboot events across the trailing 7-day window. |
| **F10** | `reboot_cnt_sum_28d` | Total sum of incremental reboot events across the trailing 28-day baseline window. |
| **F12** | `disconnection_cnt_sum_7d` | Total sum of incremental backhaul disconnection events in the trailing 7 days. |
| **F16** | `acute_chronic_divergence` | Sudden availability collapse: prior 21-day average availability minus recent 7-day availability. |
| **F17** | `hist_meter_success_pre_feb` | Static historical meter read collection success rate prior to February ($\le 	ext{2026-01-26}$). |
| **F18** | `hist_meter_outage_freq` | Static historical fraction of zero-read weeks prior to February ($\le 	ext{2026-01-26}$). |
| **F19** | `is_lifecycle_active` | Binary asset eligibility gate: gateway was installed before $T$ and not decommissioned. |
| **F20** | `installed_age_days` | Operational lifespan exposure measured in elapsed days from installation date to $T$. |

### Summary of CONDITIONAL and DEFERRED Features
- **F07 (`offline_duration_delta_7d` - CONDITIONAL):** Summing differences in the `offline_duration_sec` counter required knowing exact counter reset rules during multi-hour communication dropouts.
- **F11 (`reboot_intensity_ratio` - CONDITIONAL):** Ratio of recent 7d reboots to chronic 28d reboots suffered from small-denominator instability ($0/0$ division).
- **F14 & F15 (Syndrome indicators - CONDITIONAL):** Dual-threshold binary flags requiring arbitrary threshold tuning ($	heta_r, 	heta_o, 	heta_d$).
- **F13 (`disconn_to_offline_ratio` - DEFERRED):** Numerical instability when offline duration was low, producing extreme volatility with minimal diagnostic utility.

---

## 4. Phase 5.2 — Deterministic Feature Extraction

Phase 5.2 translated the approved 15 READY feature specifications into modular, pure-Python/Pandas extraction code in `src/nexora/` (`DataLoader` and `FeatureExtractor`).

### Engineering Architecture & Principles
1. **Canonical Gateway ID Normalization:**  
   The asset register (`gateway_master.csv`) used colon-delimited MAC-style strings (e.g., `06:39:EA:56:02:C1`), whereas telemetry and meter logs used 12-character bare hex strings (e.g., `0639EA5602C1`). We implemented `normalize_gateway_id()` to enforce uppercase 12-character bare hex across all internal tables.
2. **Duplicate Handling Before Aggregation:**  
   In raw telemetry, 6,547 duplicate records existed where identical `(gateway_id, ts_utc)` pairs appeared with conflicting counter values across overlapping monthly Parquet partitions. Deduplication was applied before feature extraction to prevent artificial inflation of event sums.
3. **Temporal Windows ($[T-28	ext{d}, T)$ and $[T-7	ext{d}, T)$):**  
   Strict right-open intervals were enforced: telemetry timestamps must satisfy $t < T$ (never $t \le T$). This ensured that no packet recorded on Monday morning could leak into the pre-decision feature matrix.
4. **Active Gateway Universe Gating:**  
   Gateways were dynamically filtered using `gateway_master.csv` lifecycle dates: $	exttt{installed\_on} \le T$ and $(	exttt{decommissioned\_on} > T \lor 	ext{null})$. The active universe grew steadily from 290 gateways on 2026-02-02 to 308 gateways on 2026-03-23.
5. **Retention of Silent Gateways:**  
   In conventional feature extraction, a gateway with zero telemetry rows during the window would simply drop out of a `groupby`. In our pipeline, every active gateway in the master register was preserved via a complete index reindex. Silent gateways received explicit default values ($	ext{F01} = 0$, $	ext{F02} = 168$, $	ext{F04} = 672.0	ext{h}$, $	ext{F05} = 1$).
6. **Deterministic Execution:**  
   No random seeds, no floating-point ordering ambiguity, and deterministic tie-breaking ensured that running extraction twice produced bitwise identical dataframes (`assert_frame_equal`).

### Verified Implementation Results
- **20 out of 20 invariant verification checks passed** across all 8 scored Mondays.
- **2,393 total gateway-week rows** were generated (100% complete coverage across active nodes).
- **Total runtime:** Approximately **7.03 seconds** across all 8 evaluation weeks combined.

---

## 5. Why Counter Semantics Mattered

A critical engineering insight in Phase 5 was uncovering how different telemetry fields behave over time:

1. **Incremental Hourly Counters (`reboot_cnt`, `disconnection_cnt`):**  
   These fields record the number of discrete events that occurred *within that specific hour*. When a gateway is offline, no events can be recorded. Therefore, summing these values over a 7-day window ($\sum 	exttt{reboot\_cnt}$) is mathematically sound and directly reflects event volume.
2. **Cumulative Firmware Clocks (`offline_duration_sec`, `reboot_duration_sec`):**  
   These fields do not measure hourly increments; they represent internal running clocks. In the raw data, `offline_duration_sec` reached values exceeding 700,000 seconds (over 8 days continuous). Differencing these counters across time was unsafe because when communication dropped, the counter would reset or jump unpredictably upon reconnection.
3. **Engineering Judgement Over Blind Modeling:**  
   Rather than pretending counter semantics were perfectly understood or forcing uncalibrated differences ($\Delta C$), we explicitly bounded the signal: we extracted peak observed duration ($	ext{F06}$) and count of severe excursions ($	ext{F08}$), while deferring differencing ($	ext{F07}$) until controlled backtesting.

---

## 6. Phase 5.3 — Distribution and Correlation Analysis

Phase 5.3 analyzed the empirical distributions and pairwise correlations across all $N=2,393$ extracted gateway-weeks to identify redundancy, extreme skewness, and uninformative features before designing ranking strategies.

### Key Distributional Findings:
- **Skewed & Heavy-Tailed Features:**  
   `reboot_cnt_sum_7d` ($	ext{F09}$) was zero-inflated (79.9% of gateway-weeks had zero reboots), but exhibited an extreme right tail (skewness $+17.20$, maximum 78 reboots). `offline_duration_max_7d` ($	ext{F06}$) ranged from 0 to 726,642 seconds (skewness $+5.02$).
- **Near-Constant Features:**  
   `hist_meter_outage_freq` ($	ext{F18}$) was 0.0 across 99.3% of the fleet (only 2 active gateways ever recorded a zero-read week). It provided zero diagnostic separation.
- **Sparse Silence Signal:**  
   `is_completely_silent_7d` ($	ext{F05}$) occurred in only 3 instances (0.1% of gateway-weeks), and all three occurred on newly commissioned gateways on day 0 of installation.

### Key Correlation & Redundancy Findings:
- **Exact Mathematical Duplicates ($	ext{F01} \leftrightarrow 	ext{F02} \leftrightarrow 	ext{F03}$):**  
   $	ext{F02} \equiv 168 - 	ext{F01}$ ($r = -1.00$) and $	ext{F03} \equiv 	ext{F01} / 168.0$ ($r = +1.00$). Retaining all three in a scoring model adds redundant parameters. $	ext{F02}$ was retained because missingness scales naturally as an operational deficit penalty.
- **Consecutive Outage vs. Silence ($	ext{F04} \leftrightarrow 	ext{F05}$):**  
   Strong linear correlation ($r = 0.98$) because completely silent nodes produce the maximum cutoff lag ($672	ext{h}$).
- **Peak Offline vs. Threshold Excursions ($	ext{F06} \leftrightarrow 	ext{F08}$):**  
   Strong rank correlation ($
ho = 0.91$). Both measure severe offline duration.
- **Acute vs. Chronic Reboots ($	ext{F09} \leftrightarrow 	ext{F10}$):**  
   High correlation ($r = 0.93$, $
ho = 0.82$). Gateways that reboot frequently this week almost always rebooted frequently over the past month.
- **Installation Age ($	ext{F20}$):**  
   Showed near-zero correlation with operational distress ($r = -0.02$ with missing hours, $r = -0.01$ with reboots). Gateway failures were not simple functions of chronological age.

---

## 7. What Survived the Pruning Process

Based on statistical distributions, collinearity, and retrospective operational alignment, Phase 5.3 assigned every feature a definitive pruning decision:

| Feature ID | Feature Name | Phase 5.3 Pruning Decision | Operational Rationale |
| :--- | :--- | :---: | :--- |
| **F01** | `reported_hours_7d` | **DROP_FOR_RANKING** | Exact redundant linear inverse of F02 ($r = -1.00$). |
| **F02** | `missing_hours_7d` | **KEEP** | Primary direct measure of weekly availability deficit. |
| **F03** | `reporting_ratio_7d` | **DROP_FOR_RANKING** | Exact redundant scalar multiple of F01 ($r = +1.00$). |
| **F04** | `consecutive_missing_at_cutoff` | **KEEP_WITH_TRANSFORMATION** | Primary ongoing blackout signal; requires capping ($\le 72	ext{h}$) to control 672h tail. |
| **F05** | `is_completely_silent_7d` | **KEEP — CONDITIONAL OVERRIDE** | Critical for silent dead nodes, but must be conditioned on asset age. |
| **F06** | `offline_duration_max_7d` | **KEEP_WITH_TRANSFORMATION** | Peak outage duration; requires $\log(1 + 	ext{F06})$ to stabilize extreme counter spikes. |
| **F08** | `offline_hours_gt_3600_7d` | **DEFER_TO_BACKTEST** | Highly collinear with F06 ($
ho = 0.91$); defer to backtest to compare counter vs. threshold. |
| **F09** | `reboot_cnt_sum_7d` | **KEEP** | Direct acute reboot storm indicator; strong empirical association with historical repairs. |
| **F10** | `reboot_cnt_sum_28d` | **DEFER_TO_BACKTEST** | Highly collinear with F09 ($r = 0.93$); defer to backtest as potential chronic baseline. |
| **F12** | `disconnection_cnt_sum_7d` | **KEEP_WITH_TRANSFORMATION** | Backhaul connection drop volume; requires $\log(1 + 	ext{F12})$ scaling to dampen network noise. |
| **F16** | `acute_chronic_divergence` | **KEEP** | Orthogonal availability collapse signal ($
ho = 0.15$ with reboots); captures sudden drops. |
| **F17** | `hist_meter_success_pre_feb` | **DEFER_TO_BACKTEST** | Valuable static pre-Feb prior, but requires careful imputation for post-Jan 26 nodes. |
| **F18** | `hist_meter_outage_freq` | **DROP_FOR_RANKING** | Near-constant feature (99.3% zeros); zero diagnostic separation across active fleet. |
| **F19** | `is_lifecycle_active` | **KEEP — ELIGIBILITY GATE** | Mandatory eligibility filter; zero ranking variance by definition. |
| **F20** | `installed_age_days` | **DROP_FOR_RANKING** | Near-zero correlation with failure; dropped from ranking and tie-breaking. |

### Architectural Categorization Summary:
- **Core Ranking Signals (3):** F02, F09, F16
- **Transformed Ranking Signals (3):** F04 (capped), F06 ($\log1	ext{p}$), F12 ($\log1	ext{p}$)
- **Conditional Override Signal (1):** F05 (silence priority tier)
- **Deferred Backtest Options (3):** F08, F10, F17
- **Dropped for Ranking (4):** F01 (collinear), F03 (collinear), F18 (near-constant), F20 (uncorrelated)
- **Hard Eligibility Gate (1):** F19 (lifecycle filter)

---

## 8. The Most Important Engineering Decisions

1. **We did not use every available telemetry field simply because it existed:**  
   Raw telemetry contained dozens of columns (voltages, temperatures, RSSI, error codes). Including raw unvalidated signals without knowing their missingness mechanics would have introduced noise.
2. **Mathematical redundancies were eliminated early:**  
   Recognizing that F01, F02, and F03 were linear transformations of each other prevented building bloated scoring formulas with duplicate availability penalties.
3. **Lifecycle eligibility was treated as a gate, not a distress score:**  
   Whether an asset is active is a binary operational constraint, not a gradient of distress. Decoupling eligibility filtering (F19) from ranking scoring preserved clean separation of concerns.
4. **Missingness was treated as operational signal, not missing data to impute:**  
   When a gateway produces no packets, conventional pipelines impute zeros or column means. In NEXORA, missing packets represent communication silence—a primary indicator of operational degradation.
5. **Historical meter data was treated with extreme temporal caution:**  
   Because meter read collection records terminated on January 26, 2026, meter history could only serve as a static pre-February prior. We refused to treat it as live weekly telemetry during the scored challenge period.
6. **Physical failure causes were not invented from telemetry:**  
   We avoided making speculative claims that high disconnection counts "proved antenna failure" or that missing packets "proved power loss." The signals were treated as empirical behavioral indicators associated with technician intervention.

---

## 9. What Phase 5 Taught Us

- **Telemetry semantics must precede modeling:** Understanding whether a field is an event counter or a firmware clock is essential to computing valid aggregations.
- **Missing telemetry is valuable operational information:** Complete silence or packet deficits carry stronger associations with historical field interventions than subtle baseline drifts.
- **More features do not mean a better ranking:** Many candidate signals measure overlapping behavior. Pruning collinear features creates robust, explainable ranking models.
- **Temporal boundaries matter as much as statistical correlation:** A highly predictive signal is useless—and dangerous—if it relies on data unavailable at prediction time.
- **Signals should be tested in backtesting rather than promoted prematurely:** Rather than arbitrarily declaring whether threshold counts (F08) or log durations (F06) were superior, ambiguous choices were formally deferred to historical backtesting.

---

## 10. What Phase 5 Produced

Phase 5 delivered two concrete, durable assets to the project:
1. **A verified, deterministic feature extraction engine (`src/nexora/`):** Capable of extracting validated, leak-free feature matrices across any decision Monday in seconds.
2. **A pruned, defensible catalog of candidate signals:** Structured into clear operational families (core distress, transformed volume, conditional overrides, and deferred options).

**Phase 5 did NOT select the final ranking strategy.** That critical decision was deliberately reserved for Phase 6.

---

## 11. Known Limitations

As documented across the Phase 5 technical reports:
1. **Limited Temporal Coverage of Meter Data:**  
   `meter_read_success.csv` ends on 2026-01-26. Gateways commissioned after January 26 have no historical meter data, requiring explicit fallback imputation.
2. **Cumulative Counter Ambiguity During Telemetry Dropouts:**  
   When gateways experience long communication blackouts, firmware counter resets cannot be observed in real time.
3. **Observational Association vs. Causality:**  
   Historical associations between feature elevations and technician dispatches reflect past dispatch practices, not randomized controlled experiments.
4. **Fleet Coverage Gap in Meter History:**  
   Exactly 33 gateways in the master register never appeared in the historical meter log, limiting the universal applicability of meter-based signals.

---

## 12. Transition to Phase 6

The boundary between Phase 5 and Phase 6 represents the transition from signal extraction to operational decision-making:

- **Phase 5 answered:** *"What signals can we construct reliably, reproducibly, and defensibly from raw telemetry without temporal leakage?"*
- **Phase 6 answered:** *"Which combination of these signals actually performs best when evaluated against historical field visit outcomes under operational economic constraints?"*

By completing Phase 5 thoroughly, Phase 6 had access to a clean, deterministic feature extraction library that enabled a leakage-safe 26-week historical backtest across seven candidate ranking strategies.

---

## Related Technical Reports

For detailed statistical proofs, schema tables, and exact code implementations, refer to the underlying Phase 5 reports:
- [`reports/PHASE_5_1_FEATURE_FEASIBILITY.md`](PHASE_5_1_FEATURE_FEASIBILITY.md) — The 20-feature feasibility matrix, temporal contract audit, and classification into READY/CONDITIONAL/DEFERRED.
- [`reports/PHASE_5_2_FEATURE_EXTRACTION.md`](PHASE_5_2_FEATURE_EXTRACTION.md) — Implementation architecture, deduplication logic, active universe gating, and the 20-check invariant test suite.
- [`reports/PHASE_5_3_FEATURE_ANALYSIS.md`](PHASE_5_3_FEATURE_ANALYSIS.md) — Empirical distribution profiles, Pearson/Spearman correlation matrices, retrospective field visit analysis, and formal pruning decisions.
