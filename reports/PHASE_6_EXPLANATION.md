# Phase 6 — Historical Backtesting and Strategy Selection

**LPDG Innovation Hub Selection Challenge 2026 (NEXORA 2026)**  
**Document Type:** High-Level Technical Explanation & Engineering Narrative  
**Audience:** Technical Reviewers, Evaluators, and Engineering Leadership  
**Status:** Complete, Validated & Fully Documented  
**Reference Technical Reports:**
- [`reports/PHASE_6_1_BACKTEST_TARGET.md`](PHASE_6_1_BACKTEST_TARGET.md)
- [`reports/PHASE_6_2_BACKTEST_ENGINE.md`](PHASE_6_2_BACKTEST_ENGINE.md)
- [`reports/PHASE_6_3_STRATEGY_DECISION.md`](PHASE_6_3_STRATEGY_DECISION.md)
- Data Artifacts: `reports/backtest/` (`strategy_comparison.csv`, `backtest_weekly_results.csv`, `backtest_summary.csv`, `backtest_topk.csv`, `backtest_rankings.csv`)
- Codebase: `src/nexora/backtesting/` (`strategies.py`, `backtester.py`, `leakage.py`), `src/nexora/target_constructor.py`
- Executable Notebook: `notebooks/05_historical_backtesting.ipynb`

---

## 1. What Phase 6 Was Trying to Answer

The central operational question that Phase 6 was designed to resolve is:

> **"Given strictly the information that would have been available on each historical Monday morning, which ranking strategy would have produced the most useful 15-gateway physical inspection list?"**

Phase 5 alone could not answer this question. Phase 5 established signal feasibility, engineered a deterministic feature extractor, and pruned redundant features to produce a catalog of candidate signals (such as missing hours, reboot counts, and disconnection volume). However, discovering that a feature correlates with technician activity in an exploratory correlation matrix does not prove that combining those features will produce a high-yield dispatch list in production.

Phase 6 moved from **signal extraction to operational evaluation**. It built a simulation engine to evaluate candidate ranking policies across 26 consecutive historical weeks, comparing simulated algorithmic decisions directly against subsequent operational outcomes.

Crucially, this evaluation represents **historical operational backtesting under observed field conditions, not a mathematical proof of future performance or causal failure prediction**.

---

## 2. Phase 5 → Phase 6

The transition from Phase 5 into Phase 6 represents the bridge between engineering reliable data signals and evaluating real-world operational decision policies:

```
                    PHASE 5: SIGNAL EXTRACTION & PRUNING
┌──────────────────────────────────────────────────────────────────────────┐
│  Raw Telemetry + Gateway Metadata + Historical Meter Reads              │
│       ↓                                                                  │
│  Feasibility Audit (Phase 5.1: 15 READY Features Identified)             │
│       ↓                                                                  │
│  Deterministic Feature Extraction Pipeline (`src/nexora/`)               │
│       ↓                                                                  │
│  Empirical Distribution & Multicollinearity Analysis (Phase 5.3)         │
│       ↓                                                                  │
│  Defensible Candidate Signals (Core, Transformed, Conditional, Deferred) │
└────────────────────────────────────┬─────────────────────────────────────┘
                                     │
                                     ▼
                    PHASE 6: OPERATIONAL DECISION BACKTESTING
┌──────────────────────────────────────────────────────────────────────────┐
│  Formal Target Construction (Phase 6.1: `requested_on` Attribution)      │
│       ↓                                                                  │
│  26 Historical Decision Mondays (2025-08-04 to 2026-01-26)               │
│       ↓                                                                  │
│  Temporal Anti-Leakage Guards (Strictly Pre-T Telemetry)                 │
│       ↓                                                                  │
│  Seven Candidate Ranking Strategies Evaluated Deterministically          │
│       ↓                                                                  │
│  Multi-Faceted Evaluation (Repairs, False Alarms, Top-K, Cost Proxies)   │
│       ↓                                                                  │
│  Evidence-Based Decision (Phase 6.3: Retain Baseline 3-Sigma)            │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 3. What Counts as a Historical Outcome?

To backtest a ranking algorithm fairly, we needed an unambiguous, leakage-safe definition of what happened after a decision was made. This was formalized in `reports/PHASE_6_1_BACKTEST_TARGET.md`.

### The Difference Between `requested_on` and `visited_on`
Every work order in `data/field_visits.csv` contains two distinct dates:
- **`requested_on`:** The date the field dispatch was requested/initiated by human operations.
- **`visited_on`:** The date the technician physically arrived at the site.

In the historical data, technicians physically arrived an average of **9.59 days** after the request was created (median 9.0 days, range 2 to 17 days).

### The Attribution Boundary: Why `requested_on \in [T, T+7	ext{d})`
If an algorithm makes a ranking decision on Monday morning $T$, it can only influence work orders requested *during that upcoming operational week* $[T, T+7	ext{d})$.
- A work order requested *before* $T$ (`requested_on < T`) was initiated under the legacy operational policy. Even if the physical visit took place on Tuesday ($t \in [T, T+7	ext{d})$), the decision at $T$ could not have caused that visit. Crediting $T$ with prior requests would contaminate the evaluation.
- Across the 26 historical weeks, exactly **266 pre-$T$ requests were safely excluded** from attribution to prevent this contamination.

### Delayed Realizations Must Be Preserved
Because of the 9.59-day dispatch lag:
- Only **53 dispatches (16.9%)** were physically visited within the same 7-day week (`visited_on < T+7	ext{d}`).
- Exactly **261 dispatches (83.1%)** were physically visited after $T+7	ext{d}$ (mean visit date $T + 12.7$ days).

A fundamental rule of our target construction was: **do not drop delayed visits, and do not label them negative**. The decision at $T$ initiated the dispatch; when the technician arrived 10 days later and replaced a broken antenna, that physical outcome belongs to the decision made at $T$.

### The Four Target Categories & Precedence
For each active gateway during week $[T, T+7	ext{d})$, the target $Y_i(T)$ was categorized into one of four mutually exclusive states:
1. **`REPAIR_REQUIRED`:** A technician visited and confirmed a repair (`Fehler behoben`).
2. **`FALSE_ALARM`:** A technician visited and found normal operation (`Kein Fehler gefunden`), with no repair.
3. **`INCONCLUSIVE`:** A technician attempted a visit but could not gain access (`Kein Zugang`).
4. **`UNOBSERVED`:** No dispatch was requested for this gateway during $[T, T+7	ext{d})$.

If multiple visits occurred for the same gateway in the same week, physical repairs took precedence:
$$	ext{REPAIR_REQUIRED} \succ 	ext{FALSE_ALARM} \succ 	ext{INCONCLUSIVE}$$

### Verified Target Totals
Across the 26 historical decision Mondays:
- Exactly **314 attributable dispatch requests** occurred.
- **116 confirmed repairs** (`Fehler behoben`).
- **184 false alarms** (`Kein Fehler gefunden`).
- **14 inconclusive visits** (`Kein Zugang`).

> [!IMPORTANT]
> **Data Science Invariant: `UNOBSERVED` does NOT mean healthy.**  
> Gateways that were not dispatched remain unobserved. Assuming unvisited gateways are healthy would introduce catastrophic survival bias. Furthermore, historical dispatches reflect past operational policies and customer calls, not randomized controlled experiments. Backtesting does not prove causal failure prediction.

---

## 4. How Leakage Was Prevented

Temporal leakage is the most common reason backtested models fail when deployed. If an algorithm uses information that occurred after Monday $T$ to rank gateways on Monday $T$, its historical performance is an illusion.

We enforced a strict **Right-Open Information Horizon**:
$$	ext{Pre-Decision Features: } t \in [T - 28	ext{d}, T) \quad 	ext{vs} \quad 	ext{Target Window: } t \in [T, T + 7	ext{d})$$
$$	ext{Strict Invariant: } 	ext{timestamp} < T \quad (	ext{NEVER } t \ge T)$$

### The Five Leakage Controls
1. **Telemetry Isolation:**  
   Telemetry was strictly filtered by `ts < T`. In our automated tests, injecting extreme artificial spikes ($999,999$) at $t=T$ and $t=T+2	ext{h}$ produced an absolute feature difference of exactly $0.000000$ across all 15 features.
2. **Structural Isolation of Field Visits:**  
   In our modular software architecture, `FeatureExtractor` never reads, references, or imports `data/field_visits.csv`. Field visits are ingested solely by `TargetConstructor` to build evaluation targets. Leakage of field-visit outcomes into features is structurally impossible by design.
3. **Engineer Review Temporal Guard:**  
   The `engineer_review_2026-02.xlsx` audit dataset is dated `2026-02-15`. Our data loader strictly quarantines this file, returning zero rows for all historical decision dates before February 15 ($T \le 	ext{2026-02-15}$).
4. **Meter Data Temporal Boundary:**  
   Historical meter collection records were strictly bounded by week date ($t < T$). On the earliest historical week (`2025-08-04`), meter features were identically $0.0$, preventing future read leakage.
5. **Deterministic Execution:**  
   All tie-breaking was made deterministic via `gateway_id` ascending. Re-running the simulation across multiple runs produced bitwise identical rankings (`check_exact=True`).

**Result:** All **4 out of 4 automated anti-leakage and determinism tests passed** cleanly prior to simulation.

---

## 5. What Was Actually Backtested?

The backtest simulated 26 consecutive operational Mondays spanning August 4, 2025 through January 26, 2026 (`2025-08-04` to `2026-01-26`).

For each historical Monday $T$:
1. **Identify Eligible Universe:** Filter `gateway_master.csv` for gateways installed on or before $T$ and not decommissioned (280 active gateways in the historical panel).
2. **Extract Pre-$T$ Telemetry:** Compute candidate signals strictly on telemetry where $t < T$.
3. **Apply Ranking Strategy:** Execute the candidate ranking logic to score and rank the active universe.
4. **Select Top 15:** Take the 15 highest-ranked gateways as the simulated dispatch list.
5. **Match Historical Outcomes:** Compare the 15 selections against the ground truth target for week $[T, T+7	ext{d})$.
6. **Record Weekly Metrics:** Measure confirmed repairs captured, false alarms incurred, missed repairs, and economic proxies.

Because every strategy was evaluated on the exact same universe, the same 26 Mondays, and the same historical target, the comparison was completely fair and unconfounded.

---

## 6. Strategies Compared

Exactly seven ranking strategies were evaluated. In accordance with the current implementation in `src/nexora/backtesting/strategies.py`, candidate strategies use **percentile-rank transformations** in $[0, 1]$ across the active universe, where higher percentile rank represents greater distress.

1. **`Baseline_3Sigma` (Benchmark):**
   - Uses the verified `baseline_3sigma.py` methodology.
   - For each gateway, computes 28-day baseline mean and standard deviation for `offline_duration_sec`, `disconnection_cnt`, and `reboot_cnt` strictly before $T$.
   - Evaluates the recent 7-day window $[T-7	ext{d}, T)$. Flags any hourly observation exceeding mean + $3\sigma$ for any metric.
   - Ranks gateways by total flagged-hour count descending.
   - Retains silent active gateways with 0 flagged hours; breaks ties deterministically by `gateway_id` ascending.
2. **`Candidate_A_Core` (Core Persistence Composite):**
   - Equal average of three core distress percentile ranks: F02 (missing hours), F09 (7d reboots), and F16 (acute/chronic divergence):
     $$	ext{Score}_A = (	ext{pct}(	ext{F02}) + 	ext{pct}(	ext{F09}) + 	ext{pct}(	ext{F16})) / 3.0$$
3. **`Candidate_B_Severity` (Persistence + Severity Composite):**
   - Equal average of five percentile ranks: F02, F09, F16, plus log-transformed peak offline duration $\log(1+	ext{F06})$ and log-transformed disconnections $\log(1+	ext{F12})$.
4. **`Candidate_C_SevereOffline` (Persistence + Severe Outage Hours):**
   - Equal average of four percentile ranks: F02, F09, F16, plus F08 (count of observed hours with offline duration $\ge 3,600	ext{s}$):
     $$	ext{Score}_C = (	ext{pct}(	ext{F02}) + 	ext{pct}(	ext{F09}) + 	ext{pct}(	ext{F16}) + 	ext{pct}(	ext{F08})) / 4.0$$
5. **`Candidate_D_LongTerm` (Persistence + Chronic Reboot History):**
   - Equal average of four percentile ranks: F02, F09, F16, plus chronic 28-day reboot sum (F10).
6. **`Candidate_E_Reliability` (Persistence + Meter Read Failure):**
   - Equal average of four percentile ranks: F02, F09, F16, plus historical meter collection failure rate $(1.0 - 	ext{F17})$.
7. **`Candidate_F_SilenceOverride` (Conditional Silence Priority Tier):**
   - Computes base score using Candidate B.
   - Evaluates F05 (completely silent in 7d). If $	ext{F05} == 1$, adds a $+10.0$ exploratory priority offset to place silent nodes in a top priority tier.

---

## 7. How Strategies Were Evaluated

Strategies were evaluated across operational, precision, and economic dimensions:

- **Repairs Captured:** Total confirmed historical repairs (`Fehler behoben`) present in the Top-15 list.
- **Repair Capture Rate:** Fraction of total available repairs identified: $	ext{Captured Repairs} / 116$.
- **False Alarms:** Total inspections resulting in no fault found (`Kein Fehler gefunden`).
- **False Alarm Rate:** Fraction of recommendations that were false alarms: $	ext{False Alarms} / 390$.
- **Repair Yield:** Fraction of recommendations resulting in confirmed repairs: $	ext{Captured Repairs} / 390$.
- **Missed Repairs:** Available repairs not captured: $116 - 	ext{Captured Repairs}$.
- **Standardized False-Alarm Cost Proxy:** Standardized cost of wasted truck rolls: $	ext{False Alarms} 	imes €380$.
- **Standardized Missed-Repair Cost Proxy:** Standardized one-week lower-bound proxy for delayed fault resolution: $	ext{Missed Repairs} 	imes €600$.
- **Combined Standardized Cost Proxy:** Sum of false alarm proxy and missed repair proxy.

> [!NOTE]
> These economic figures are standardized decision-analysis proxies established for strategy comparison, not actual historical financial costs incurred.

Both sides of the ledger matter: an operational strategy that captures one additional repair by incurring many additional false alarms wastes technician labor and escalates operational overhead.

---

## 8. Results — What Actually Happened?

Across all 26 historical weeks ($26 	imes 15 = 390$ recommendations per strategy, 116 available repairs), the backtest produced the following verified results (sourced from `reports/backtest/strategy_comparison.csv`):

| Strategy | Repairs Captured | Capture Rate | False Alarms | FA Rate | Repair Yield | Missed Repairs | Combined Cost Proxy (€) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`Baseline_3Sigma`** | **41** | **35.34%** | **14** | **3.59%** | **10.51%** | **75** | **€50,320** |
| `Candidate_C_SevereOffline` | 42 | 36.21% | 22 | 5.64% | 10.77% | 74 | €52,760 |
| `Candidate_A_Core` | 40 | 34.48% | 22 | 5.64% | 10.26% | 76 | €53,960 |
| `Candidate_B_Severity` | 37 | 31.90% | 21 | 5.38% | 9.49% | 79 | €55,380 |
| `Candidate_D_LongTerm` | 37 | 31.90% | 21 | 5.38% | 9.49% | 79 | €55,380 |
| `Candidate_E_Reliability` | 37 | 31.90% | 22 | 5.64% | 9.49% | 79 | €55,760 |
| `Candidate_F_SilenceOverride` | 37 | 31.90% | 21 | 5.38% | 9.49% | 79 | €55,380 |

### The Critical Comparison: Baseline vs. Candidate C
At first glance, Candidate C appears to win by capturing 42 repairs compared to 41 for the baseline. However, examining the full operational balance reveals:
- **Baseline:** 41 repairs, **14 false alarms**, €5,320 FA proxy + €45,000 missed repair proxy = **€50,320 combined proxy**.
- **Candidate C:** 42 repairs, **22 false alarms**, €8,360 FA proxy + €44,400 missed repair proxy = **€52,760 combined proxy**.

**The Operational Exchange:** Over the 6-month historical simulation, Candidate C gained exactly **1 additional repair**, but required **8 additional false alarms** (+57% increase in wasted truck rolls). Under the standardized economic proxy model, Candidate C produced a **€2,440 higher combined cost penalty**.

---

## 9. Why Candidate C Was NOT Selected

Candidate C was evaluated thoroughly as the strongest alternative to the baseline, but was rejected for production adoption based on four clear findings:

1. **Unfavorable Marginal Penalty Ratio (8:1):**  
   Incurring 8 additional false alarms to capture 1 additional repair is an inefficient operational trade-off. Under the standardized model, the 8 false visits cost $+€3,040$, while the single captured repair saves $-€600$, resulting in a net penalty of $+€2,440$.
2. **Weaker Early-Rank Concentration (Top-5 and Top-10):**  
   In operational dispatching, list ordering is critical:
   - In the **Top-5**, Baseline captured **19 repairs** (14.62% yield) vs. Candidate C's **14 repairs** (10.77% yield).
   - In the **Top-10**, Baseline captured **28 repairs** (10.77% yield) vs. Candidate C's **27 repairs** (10.38% yield).  
   Candidate C only caught up at the very tail of the Top-15 list ($K \ge 12$).
3. **Statistical Significance Testing:**
   - **Weekly Repairs Captured:** Paired two-tailed $t$-test yielded $t = 0.161, p = 0.8732$. *The paired test did not detect a statistically significant difference in weekly repair capture in this historical sample.*
   - **Weekly False Alarms:** Paired two-tailed $t$-test yielded $t = 2.133, p = 0.0430$. *The paired test detected a statistically significant difference in weekly false-alarm counts at the 0.05 level in this historical sample.*
4. **Engineering Assessment:**  
   In this historical evaluation, Candidate C's single extra repair was indistinguishable from sample variation, while its increase in false alarms represented a statistically detectable operational penalty. Replacing the baseline with Candidate C was not justified.

---

## 10. Why the Baseline Was Retained

**Decision:** `Baseline_3Sigma` was retained as the selected strategy for the final Part 1 pipeline.

We do not claim that Baseline 3-Sigma is "optimal" or "the best possible algorithm in the universe." We make an evidence-based engineering statement:
1. **Comparable Repair Capture:** It captured 41 out of 116 available repairs (35.34%), essentially matching the best candidate (42).
2. **Substantially Lower False Alarms:** It generated only 14 false alarms across 390 dispatches (3.59% false alarm rate), achieving a precision-like proportion of **74.55%** among realized outcomes.
3. **Lowest Combined Cost Proxy:** It achieved the lowest standardized combined cost proxy (€50,320) among all seven strategies.
4. **Superior Early Priority Concentration:** It placed high-confidence repairs higher in the visit list (19 in Top-5 vs. 14 for Candidate C).
5. **Simplicity and Operational Transparency:** It relies on an explainable physical anomaly threshold without arbitrary feature weights or complex heuristic ensembling.
6. **Insufficient Justification for Change:** In professional engineering, a legacy baseline should only be displaced when a candidate demonstrates substantial, statistically defensible operational improvement. Candidate C did not meet that bar.

---

## 11. What We Learned From Backtesting

- **Lesson 1 — More complexity did not improve the decision:** Introducing multi-feature percentile composites (Candidates B, D, E, F) degraded performance relative to the baseline, dropping repair capture to 37 while increasing false alarms to 21–22.
- **Lesson 2 — One additional captured repair is not automatically better:** Focusing solely on repair capture while ignoring false alarm inflation leads to costly operational decisions.
- **Lesson 3 — Ranking distribution matters:** Early-rank precision (Top-5) is often more valuable than tail accumulation (Top-15) when field resources are constrained.
- **Lesson 4 — Temporal controls are mandatory:** Without strict right-open boundaries and separate request/visit tracking, evaluation metrics would be contaminated by lookahead bias.
- **Lesson 5 — Simplicity has operational value:** An explainable anomaly baseline with low false alarms is less prone to overfitting than complex heuristic weighting schemes.

---

## 12. Important Limitations

The conclusions of Phase 6 are bounded by several clear operational limitations:
1. **Finite Historical Window (26 Weeks):** The backtest spans 26 Mondays and 116 historical repairs. While substantial, this finite operational sample cautions against over-interpreting single-repair differences.
2. **Observational Nature of Targets:** Historical dispatches were initiated by legacy dispatcher alerts and customer calls, not randomized field inspections.
3. **`UNOBSERVED` Does Not Equal Healthy:** Non-dispatched gateways cannot be verified as healthy.
4. **Standardized Economic Model:** The €380 false alarm cost and €600 missed repair cost are standardized proxies, not exact historical ledger entries.
5. **No Causal Failure Prediction:** The backtest confirms that 3-sigma telemetry spikes overlap strongly with subsequent technician interventions; it does not prove causal hardware failure.
6. **Lookahead Boundary of Engineer Review:** The audit dated 2026-02-15 was unavailable for historical weeks.
7. **The Silent-Gateway Limitation:**  
   In `baseline_3sigma.py`, a gateway that produces zero telemetry packets in the trailing 7 days has no recent rows, and by default would be omitted from the ranked list. In our Phase 6 backtesting wrapper, silent active gateways were retained with 0 flagged hours to ensure fair universe parity. In Phase 7, how the production pipeline handles completely silent gateways must be addressed deliberately.

---

## 13. What Phase 6 Produced

Phase 6 delivered the following concrete engineering deliverables:
- **A leakage-safe backtesting engine (`src/nexora/backtesting/`):** A modular simulation framework supporting reproducible policy evaluation.
- **A validated historical target constructor (`src/nexora/target_constructor.py`):** Correctly implementing `requested_on` attribution with delayed visit realization tracking.
- **Seven standardized, comparable ranking strategies:** Implementing baseline anomaly logic and candidate percentile composites.
- **Comprehensive machine-readable evaluation outputs (`reports/backtest/`):** Summary tables, weekly breakdowns, Top-$K$ curves, and ranking files.
- **A defensible strategy decision (`reports/PHASE_6_3_STRATEGY_DECISION.md`):** Formally retaining Baseline 3-Sigma for the final Part 1 pipeline.

---

## 14. Transition to Phase 7

Phase 6 answered:
> *"Which ranking strategy should we carry forward based on historical operational evidence?"*  
> **Answer:** Retain `Baseline_3Sigma`.

Phase 7 now answers:
> *"How do we turn that selected strategy into the final, reproducible Part 1 production pipeline?"*

```
                 PHASE 7 PRODUCTION ARCHITECTURE
┌────────────────────────────────────────────────────────────────┐
│  Selected Strategy: Baseline 3-Sigma Anomaly Ranking           │
│       ↓                                                        │
│  Modular Ingestion (`hourly_telemetry.parquet`, `master.csv`)  │
│       ↓                                                        │
│  Active Gateway Lifecycle Filter (Pre-Monday T)                │
│       ↓                                                        │
│  3-Sigma Flagged-Hour Aggregation (Preceding 28d vs. 7d)       │
│       ↓                                                        │
│  Deterministic Sorting (Flagged Hours Desc, Gateway ID Asc)    │
│       ↓                                                        │
│  Top-15 Gateway Selection for Scored Mondays (Feb–Mar 2026)    │
│       ↓                                                        │
│  Generate Official Submission File (`predictions.csv`)         │
│       ↓                                                        │
│  Validate Format via `validate_submission.py`                  │
└────────────────────────────────────────────────────────────────┘
```

In Phase 7, the pipeline will operationalize this selected strategy to generate the final `predictions.csv` for the 8 scored challenge Mondays, resolving any silent-gateway handling deliberately within the production architecture.

---

## 15. Related Technical Reports

For detailed statistical proofs, schema tables, and exact code implementations, refer to the underlying Phase 6 reports:
- [`reports/PHASE_6_1_BACKTEST_TARGET.md`](PHASE_6_1_BACKTEST_TARGET.md) — Target definition, `requested_on` attribution boundary, delayed realization tracking, and historical outcome distributions.
- [`reports/PHASE_6_2_BACKTEST_ENGINE.md`](PHASE_6_2_BACKTEST_ENGINE.md) — Simulation engine implementation, anti-leakage test suite, and aggregate 26-week backtest results.
- [`reports/PHASE_6_3_STRATEGY_DECISION.md`](PHASE_6_3_STRATEGY_DECISION.md) — Comparative delta analysis, Top-$K$ curves, paired statistical testing, and formal strategy retention justification.
- [`reports/backtest/strategy_comparison.csv`](backtest/strategy_comparison.csv) — Machine-readable summary of all seven evaluated strategies across 18 operational metrics.
