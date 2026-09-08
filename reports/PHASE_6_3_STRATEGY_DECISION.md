# Phase 6.3 — Strategy Comparison & Decision Analysis

**LPDG Innovation Hub Selection Challenge 2026 (NEXORA 2026)**  
**Author:** Candidate Engineering Team  
**Status:** Complete & Validated  
**Parent Contract:** `reports/PHASE_6_1_BACKTEST_TARGET.md` (`requested_on` primary attribution)  
**Simulation Engine:** `reports/PHASE_6_2_BACKTEST_ENGINE.md`, `src/nexora/backtesting/`  
**Data Artifacts:** `reports/backtest/` (`strategy_comparison.csv`, `backtest_weekly_results.csv`, `backtest_summary.csv`, `backtest_topk.csv`, `backtest_rankings.csv`)  

---

## 1. Objective

The objective of Phase 6.3 is to conduct a rigorous, evidence-based comparative evaluation of the seven gateway ranking strategies simulated across the 26 historical decision weeks in Phase 6.2, and determine which ranking strategy should be carried forward as the selected strategy for the final Part 1 pipeline.

Prioritizing field dispatches requires balancing multiple competing operational objectives:
1. **Maximizing confirmed repair capture** (identifying assets that required physical intervention).
2. **Minimizing false alarms** (preventing wasted truck rolls to healthy or non-faulty equipment).
3. **Maximizing dispatch yield** (proportion of inspections that result in confirmed repairs).
4. **Minimizing missed repairs** (reducing the operational penalty of unaddressed equipment failures).
5. **Evaluating standardized operational cost proxies** (synthesizing false alarm costs and missed repair proxies).
6. **Ensuring weekly stability** (consistent performance across varying operating conditions without volatile swings).
7. **Examining Top-$K$ concentration** (ensuring high-confidence captures appear early in the dispatch list).
8. **Preserving simplicity and explainability** (ensuring field engineers and dispatchers understand why an asset is recommended).

Crucially, this evaluation answers whether candidate heuristics—specifically Candidate C's capture of one additional repair—genuinely improve operational decisions or merely introduce excess noise and costly false alarms.

---

## 2. Strategies Compared

All seven strategies were evaluated across an identical simulation environment: 26 consecutive historical Mondays ($T = \text{2025-08-04}$ through $\text{2026-01-26}$), selecting exactly $K=15$ gateways from an active universe of 280 assets (390 total recommendations per strategy), evaluated against 116 confirmed historical repair dispatches.

All candidate percentile ranks are calculated in $[0, 1]$ within the active gateway universe for decision Monday $T$, where higher percentile rank corresponds to greater distress/concern. Ties receive average percentile ranks.

1. **`Baseline_3Sigma` (Benchmark):**
   - Uses the verified `baseline_3sigma.py` implementation.
   - For each decision Monday $T$, uses telemetry strictly before $T$ ($t < T$).
   - Computes the preceding 28-day historical mean and standard deviation per gateway for:
     - `offline_duration_sec`
     - `disconnection_cnt`
     - `reboot_cnt`
   - Evaluates the recent 7-day window before $T$ ($[T-7\text{d}, T)$).
   - Flags recent hourly observations exceeding mean + 3 standard deviations for the respective baseline signals.
   - Ranks gateways by total flagged-hour count.
   - Aligns ranking to the active gateway universe used by the backtest (`feature_df`).
   - Retains active gateways with zero telemetry / zero flagged hours rather than silently dropping them.
   - Uses deterministic tie-breaking by `gateway_id` ascending.

2. **`Candidate_A_Core` (Core Persistence Composite):**
   - Combines the three core distress features:
     - Percentile rank of F02 (`missing_hours_7d`)
     - Percentile rank of F09 (`reboot_cnt_sum_7d`)
     - Percentile rank of F16 (`acute_chronic_divergence`)
   - Composite score: equal average of the three percentile ranks:
     $$\text{Score}_A = \frac{\text{pct\_rank}(\text{F02}) + \text{pct\_rank}(\text{F09}) + \text{pct\_rank}(\text{F16})}{3.0}$$
   - Sorted by `score` descending, `gateway_id` ascending.

3. **`Candidate_B_Severity` (Persistence + Severity Composite):**
   - Incorporates peak offline duration and reboot/disconnection volume:
     - Percentile rank of F02 (`missing_hours_7d`)
     - Percentile rank of F09 (`reboot_cnt_sum_7d`)
     - Percentile rank of F16 (`acute_chronic_divergence`)
     - Percentile rank of $\log(1 + \text{F06})$ (`offline_duration_max_7d`)
     - Percentile rank of $\log(1 + \text{F12})$ (`disconnection_cnt_sum_7d`)
   - Composite score: equal average of the five percentile ranks:
     $$\text{Score}_B = \frac{\text{pct\_rank}(\text{F02}) + \text{pct\_rank}(\text{F09}) + \text{pct\_rank}(\text{F16}) + \text{pct\_rank}(\log(1+\text{F06})) + \text{pct\_rank}(\log(1+\text{F12}))}{5.0}$$
   - Sorted by `score` descending, `gateway_id` ascending.

4. **`Candidate_C_SevereOffline` (Persistence + Severe Offline Counter):**
   - Extends the core distress features with thresholded offline counter excursions:
     - Percentile rank of F02 (`missing_hours_7d`)
     - Percentile rank of F09 (`reboot_cnt_sum_7d`)
     - Percentile rank of F16 (`acute_chronic_divergence`)
     - Percentile rank of F08 (`offline_hours_gt_3600_7d`)
   - Composite score: equal average of the four percentile ranks:
     $$\text{Score}_C = \frac{\text{pct\_rank}(\text{F02}) + \text{pct\_rank}(\text{F09}) + \text{pct\_rank}(\text{F16}) + \text{pct\_rank}(\text{F08})}{4.0}$$
   - Sorted by `score` descending, `gateway_id` ascending.

5. **`Candidate_D_LongTerm` (Persistence + Long-Term Reboot History):**
   - Evaluates whether chronic 28-day reboot counts add stability over 7-day counts:
     - Percentile rank of F02 (`missing_hours_7d`)
     - Percentile rank of F09 (`reboot_cnt_sum_7d`)
     - Percentile rank of F16 (`acute_chronic_divergence`)
     - Percentile rank of F10 (`reboot_cnt_sum_28d`)
   - Composite score: equal average of the four percentile ranks:
     $$\text{Score}_D = \frac{\text{pct\_rank}(\text{F02}) + \text{pct\_rank}(\text{F09}) + \text{pct\_rank}(\text{F16}) + \text{pct\_rank}(\text{F10})}{4.0}$$
   - Sorted by `score` descending, `gateway_id` ascending.

6. **`Candidate_E_Reliability` (Persistence + Historical Meter Reliability):**
   - Augments core distress features with historical meter read failure:
     - Percentile rank of F02 (`missing_hours_7d`)
     - Percentile rank of F09 (`reboot_cnt_sum_7d`)
     - Percentile rank of F16 (`acute_chronic_divergence`)
     - Percentile rank of $(1.0 - \text{F17})$ (meter read failure rate, where F17 is `hist_meter_success_pre_feb`)
   - Composite score: equal average of the four percentile ranks:
     $$\text{Score}_E = \frac{\text{pct\_rank}(\text{F02}) + \text{pct\_rank}(\text{F09}) + \text{pct\_rank}(\text{F16}) + \text{pct\_rank}(1.0 - \text{F17})}{4.0}$$
   - Sorted by `score` descending, `gateway_id` ascending.

7. **`Candidate_F_SilenceOverride` (Conditional Silence Priority Tier):**
   - Computes base score using Candidate B:
     $$\text{BaseScore} = \frac{\text{pct\_rank}(\text{F02}) + \text{pct\_rank}(\text{F09}) + \text{pct\_rank}(\text{F16}) + \text{pct\_rank}(\log(1+\text{F06})) + \text{pct\_rank}(\log(1+\text{F12}))}{5.0}$$
   - Evaluates F05 (`is_completely_silent_7d`, binary indicator $\mathbb{I}(\text{F01} == 0)$).
   - Gateways completely silent in 7d ($\text{F05} == 1$) receive a $+10.0$ priority offset, placing them strictly into a top priority tier.
   - Composite score:
     $$\text{Score}_F = (\mathbb{I}(\text{F05} == 1) \times 10.0) + \text{BaseScore}$$
   - Sorted by `score` descending, `gateway_id` ascending.

---

## 3. Overall Performance

The overall evaluation results across all 26 historical weeks are summarized below (sourced directly from `reports/backtest/strategy_comparison.csv`):

| Strategy | Repairs Captured | Total Available | Repair Capture Rate | False Alarms | False Alarm Rate | Repair Yield | Missed Repairs | FA Cost Proxy (€380) | Missed Repair Proxy (€600) | Combined Cost Proxy (€) | Top-5 Capture | Top-10 Capture | Top-15 Capture |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **`Baseline_3Sigma`** | **41** | **116** | **35.34%** | **14** | **3.59%** | **10.51%** | **75** | **€5,320** | **€45,000** | **€50,320** | **19** | **28** | **41** |
| `Candidate_C_SevereOffline` | 42 | 116 | 36.21% | 22 | 5.64% | 10.77% | 74 | €8,360 | €44,400 | €52,760 | 14 | 27 | 42 |
| `Candidate_A_Core` | 40 | 116 | 34.48% | 22 | 5.64% | 10.26% | 76 | €8,360 | €45,600 | €53,960 | 12 | 26 | 40 |
| `Candidate_B_Severity` | 37 | 116 | 31.90% | 21 | 5.38% | 9.49% | 79 | €7,980 | €47,400 | €55,380 | 13 | 28 | 37 |
| `Candidate_D_LongTerm` | 37 | 116 | 31.90% | 21 | 5.38% | 9.49% | 79 | €7,980 | €47,400 | €55,380 | 10 | 24 | 37 |
| `Candidate_E_Reliability` | 37 | 116 | 31.90% | 22 | 5.64% | 9.49% | 79 | €8,360 | €47,400 | €55,760 | 16 | 25 | 37 |
| `Candidate_F_SilenceOverride` | 37 | 116 | 31.90% | 21 | 5.38% | 9.49% | 79 | €7,980 | €47,400 | €55,380 | 13 | 28 | 37 |

### Key Observations:
- **Baseline Precision in Historical Sample:** `Baseline_3Sigma` produced only **14 false alarms** across 390 inspections (3.59% false alarm rate), achieving a **precision-like proportion of 74.55%** among resolved dispatches (defined as: "precision-like proportion = confirmed repairs / (confirmed repairs + false alarms)"). Every candidate strategy produced between 21 and 22 false alarms (5.38% to 5.64% false alarm rate).
- **Repair Capture Clustered Near Baseline:** `Baseline_3Sigma` captured 41 repairs. `Candidate_C_SevereOffline` captured 42 repairs (+1). `Candidate_A_Core` captured 40 repairs (-1). Candidates B, D, E, and F captured 37 repairs (-4).
- **Candidate C Trade-off:** `Candidate_C` captured 1 additional confirmed repair over the 26-week historical horizon, but generated **8 additional false alarms** (+57.1% relative increase in wasted dispatches).

---

## 4. Baseline Delta Analysis

To evaluate whether candidate strategies represent operational improvements over the verified challenge baseline, we compute the exact deltas relative to `Baseline_3Sigma`:

$$\Delta = \text{Metric}_{\text{Candidate}} - \text{Metric}_{\text{Baseline}}$$

| Strategy | $\Delta$ Repairs Captured | $\Delta$ False Alarms | $\Delta$ Capture Rate | $\Delta$ FA Cost Proxy (€) | $\Delta$ Missed Repair Proxy (€) | $\Delta$ Combined Cost Proxy (€) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`Baseline_3Sigma`** | **0** | **0** | **0.00%** | **€0** | **€0** | **€0** |
| `Candidate_C_SevereOffline` | +1 | +8 | +0.86% | +€3,040 | -€600 | **+€2,440** (worse) |
| `Candidate_A_Core` | -1 | +8 | -0.86% | +€3,040 | +€600 | **+€3,640** (worse) |
| `Candidate_B_Severity` | -4 | +7 | -3.45% | +€2,660 | +€2,400 | **+€5,060** (worse) |
| `Candidate_D_LongTerm` | -4 | +7 | -3.45% | +€2,660 | +€2,400 | **+€5,060** (worse) |
| `Candidate_E_Reliability` | -4 | +8 | -3.45% | +€3,040 | +€2,400 | **+€5,440** (worse) |
| `Candidate_F_SilenceOverride` | -4 | +7 | -3.45% | +€2,660 | +€2,400 | **+€5,060** (worse) |

### Detailed Discrepancy Breakdown: `Baseline_3Sigma` vs `Candidate_C_SevereOffline`
Examining the individual gateway recommendations reveals significant divergence between the two approaches:
- **Shared Selections:** Out of 390 total recommendations, exactly **125 gateway dispatches were identical** between Baseline and Candidate C.
- **Divergent Selections:** Exactly **265 recommendations differed** (67.9% divergence).
- **Outcomes of Divergent Selections:**
  - **Baseline-only recommendations (265 assets):** yielded **19 confirmed repairs**, **6 false alarms**, and 240 unobserved.
  - **Candidate C-only recommendations (265 assets):** yielded **20 confirmed repairs**, **14 false alarms**, and 231 unobserved.
- **Net Operational Exchange:** Over the 26-week simulation, swapping 265 Baseline recommendations for Candidate C recommendations exchanged 6 false alarms for 14 false alarms (+8 false alarms) in return for exchanging 19 repairs for 20 repairs (+1 repair).

---

## 5. Weekly Stability

To evaluate consistency across varying operational conditions, we analyzed weekly capture statistics across the 26 historical decision Mondays:

| Strategy | Weekly Mean ($\mu$) | Weekly Std ($\sigma$) | Min | Max | Weeks $\ge 1$ Repair | Weeks $= 0$ Repairs |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`Baseline_3Sigma`** | **1.577** | **1.172** | **0** | **4** | **21 (80.8%)** | **5 (19.2%)** |
| `Candidate_C_SevereOffline` | 1.615 | 1.203 | 0 | 4 | 21 (80.8%) | 5 (19.2%) |
| `Candidate_A_Core` | 1.538 | 1.067 | 0 | 4 | 22 (84.6%) | 4 (15.4%) |
| `Candidate_B_Severity` | 1.423 | 1.027 | 0 | 3 | 20 (76.9%) | 6 (23.1%) |
| `Candidate_D_LongTerm` | 1.423 | 0.987 | 0 | 4 | 22 (84.6%) | 4 (15.4%) |
| `Candidate_E_Reliability` | 1.423 | 1.065 | 0 | 4 | 21 (80.8%) | 5 (19.2%) |
| `Candidate_F_SilenceOverride` | 1.423 | 1.027 | 0 | 3 | 20 (76.9%) | 6 (23.1%) |

### Week-by-Week Comparative Trajectory:
- Comparing `Baseline_3Sigma` and `Candidate_C_SevereOffline` week-by-week:
  - **Identical repair capture:** 13 weeks (50.0% of evaluated weeks).
  - **Candidate C captured more repairs:** 8 weeks.
  - **Baseline captured more repairs:** 5 weeks.
- The mean weekly difference $(\text{Repairs}_C - \text{Repairs}_{\text{Base}})$ is $+0.038 \pm 1.216$ repairs per week.
- Both strategies identified at least one repair in **21 out of 26 weeks** (80.8% hit consistency) and recorded zero repairs in exactly 5 weeks.

---

## 6. Top-$K$ Analysis

In operational dispatch environments, the ordering of recommendations within the top-15 list is critical. If physical teams can only execute 5 or 10 visits in a given week due to resource constraints, early capture concentration is paramount.

We evaluated cumulative repairs captured and false alarms across every value of $K \in [1, 15]$:

### 6.1 Cumulative Repairs Captured Across $K$
| $K$ | `Baseline_3Sigma` | `Candidate_A` | `Candidate_B` | `Candidate_C` | `Candidate_D` | `Candidate_E` | `Candidate_F` |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | **6** | 0 | 1 | 3 | 1 | 2 | 1 |
| **2** | **13** | 5 | 3 | 5 | 4 | 4 | 3 |
| **3** | **16** | 10 | 7 | 12 | 8 | 10 | 6 |
| **4** | **17** | 10 | 8 | 12 | 9 | 13 | 8 |
| **5** | **19** | 12 | 13 | 14 | 10 | 16 | 13 |
| **6** | **21** | 15 | 15 | 18 | 12 | 16 | 14 |
| **7** | **24** | 16 | 19 | 20 | 16 | 19 | 18 |
| **8** | **25** | 19 | 21 | 22 | 20 | 23 | 21 |
| **9** | **26** | 22 | 23 | 24 | 23 | 23 | 23 |
| **10** | **28** | 26 | 28 | 27 | 24 | 25 | 28 |
| **11** | **31** | 33 | 32 | 31 | 28 | 27 | 32 |
| **12** | 33 | **35** | 33 | 34 | 30 | 28 | 33 |
| **13** | 36 | 36 | 34 | **37** | 34 | 31 | 33 |
| **14** | 39 | 37 | 35 | **40** | 34 | 34 | 34 |
| **15** | 41 | 40 | 37 | **42** | 37 | 37 | 37 |

### 6.2 Cumulative False Alarms Across $K$
| $K$ | `Baseline_3Sigma` | `Candidate_A` | `Candidate_B` | `Candidate_C` | `Candidate_D` | `Candidate_E` | `Candidate_F` |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **1** | 1 | 0 | 1 | 1 | 1 | 0 | 1 |
| **2** | 1 | 2 | 3 | 1 | 1 | 2 | 3 |
| **3** | 2 | 2 | 3 | 1 | 1 | 3 | 3 |
| **4** | 3 | 3 | 4 | 1 | 2 | 4 | 4 |
| **5** | 4 | 4 | 5 | 1 | 4 | 6 | 5 |
| **6** | 5 | 6 | 7 | 2 | 9 | 9 | 6 |
| **7** | 5 | 8 | 9 | 4 | 11 | 9 | 7 |
| **8** | 7 | 10 | 13 | 7 | 13 | 9 | 12 |
| **9** | 9 | 10 | 14 | 11 | 16 | 9 | 14 |
| **10** | 11 | 12 | 14 | 14 | 17 | 11 | 14 |
| **11** | 12 | 17 | 16 | 18 | 19 | 14 | 15 |
| **12** | 13 | 19 | 18 | 19 | 19 | 15 | 17 |
| **13** | 13 | 21 | 19 | 20 | 20 | 20 | 18 |
| **14** | 14 | 22 | 21 | 21 | 20 | 21 | 21 |
| **15** | **14** | 22 | 21 | 22 | 21 | 22 | 21 |

### 6.3 Critical Insights on Ranking Distribution:
1. **Strong Early-Rank Concentration for Baseline:**
   - At $K=1$, `Baseline_3Sigma` captured **6 confirmed repairs** (23.08% yield), whereas Candidate C captured 3 and Candidate A captured 0.
   - At $K=2$, Baseline reached **13 confirmed repairs** (25.00% yield) with only 1 false alarm, compared to 5 for Candidate C and 5 for Candidate A.
   - At $K=5$, Baseline captured **19 repairs** (14.62% yield), substantially outpacing Candidate C (14 repairs) and Candidate A (12 repairs).
   - At $K=10$, Baseline captured **28 repairs** (10.77% yield), leading Candidate C (27 repairs).
2. **Late Convergence of Candidate C:**
   - Candidate C only matches or overtakes Baseline at the very tail of the distribution ($K \ge 12$).
   - This indicates that Candidate C does not possess superior top-of-list discrimination in this backtest; rather, its combination of missing hours (F02) and offline excursions (F08) pulls in assets that occasionally correlate with repairs toward the bottom of the top-15, while accumulating elevated false alarms across the list.

---

## 7. Operational Cost Proxy Analysis

To evaluate the competing trade-offs between repair discovery and false alarms, we apply the standardized economic cost model established in Phase 6.1 and 6.2:
- **Cost of a False Alarm ($C_{\text{FA}}$):** €380 per wasted truck roll (technician travel, diagnostics, administrative overhead).
- **Standardized Missed-Repair Proxy ($C_{\text{Missed}}$):** €600 per missed repair (standardized one-week lower-bound proxy for delayed resolution, unbilled meter reads, and field escalation).

$$\text{Combined Cost Proxy} = (\text{False Alarms} \times €380) + (\text{Missed Repairs} \times €600)$$

> [!NOTE]
> The missed-repair cost calculation is not the actual historical cost incurred. It is a standardized one-week lower-bound proxy used only for strategy comparison.

| Strategy | False Alarms | FA Cost Proxy (€) | Missed Repairs | Missed Repair Proxy (€) | Combined Cost Proxy (€) | Delta vs Baseline (€) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **`Baseline_3Sigma`** | **14** | **€5,320** | **75** | **€45,000** | **€50,320** | **€0** |
| `Candidate_C_SevereOffline` | 22 | €8,360 | 74 | €44,400 | €52,760 | +€2,440 |
| `Candidate_A_Core` | 22 | €8,360 | 76 | €45,600 | €53,960 | +€3,640 |
| `Candidate_B_Severity` | 21 | €7,980 | 79 | €47,400 | €55,380 | +€5,060 |
| `Candidate_D_LongTerm` | 21 | €7,980 | 79 | €47,400 | €55,380 | +€5,060 |
| `Candidate_F_SilenceOverride` | 21 | €7,980 | 79 | €47,400 | €55,380 | +€5,060 |
| `Candidate_E_Reliability` | 22 | €8,360 | 79 | €47,400 | €55,760 | +€5,440 |

### Economic Assessment Across All Cutoffs ($K=1 \dots 15$):
Evaluating the combined cost proxy across every rank cutoff $K$ confirms that `Baseline_3Sigma` achieves the lowest combined cost proxy at **every single value of $K$**:
- At $K=5$: Baseline €59,720 vs Candidate C €61,580 (Baseline €1,860 lower).
- At $K=10$: Baseline €56,980 vs Candidate C €58,720 (Baseline €1,740 lower).
- At $K=15$: Baseline €50,320 vs Candidate C €52,760 (Baseline €2,440 lower).

---

## 8. Trade-offs: Does Candidate C's Additional Repair Justify Its False Alarms?

To assess whether Candidate C represents an improvement over Baseline 3-Sigma, we evaluate three critical dimensions:

### 8.1 Statistical Evidence
- **Paired Two-Tailed t-test on Weekly Repair Captures:**
  - $t = 0.161$, $p = 0.8732$
  - The paired test did not detect a statistically significant difference in weekly repair capture in this historical sample.
- **Paired Wilcoxon Signed-Rank Test on Weekly Repair Captures:**
  - $W = 54.0$, $p = 0.6366$
  - The non-parametric test also did not detect a statistically significant difference in weekly repair distributions.
- **Paired Two-Tailed t-test on Weekly False Alarms:**
  - $t = 2.133$, $p = 0.0430$
  - The paired test detected a statistically significant difference in weekly false-alarm counts at the 0.05 level in this historical sample.
- **Statistical Summary:** In this 26-week sample, Candidate C's single additional repair capture is not statistically distinguishable from the baseline, whereas its 8 additional false alarms represent a statistically detectable increase in dispatch noise.

### 8.2 Operational & Economic Trade-offs
1. **Marginal Exchange Ratio:**
   - In this backtest, gaining 1 additional confirmed repair was accompanied by **8 additional false alarms** (a marginal false alarm ratio of 8:1).
2. **Economic Balance:**
   - The standardized proxy cost of 8 additional false alarms is $+€3,040$ ($8 \times €380$).
   - The standardized proxy benefit of capturing 1 additional repair is $-€600$ ($1 \times €600$).
   - Under these standardized assumptions, Candidate C results in a higher combined cost proxy by $+€2,440$.
   - For Candidate C to achieve cost parity under this proxy model, the standardized valuation of an unaddressed repair would need to exceed **€3,040 per week**, which is more than five times the €600 reference proxy.

### 8.3 Operational Explainability
- `Baseline_3Sigma` is straightforward to explain to field teams: an asset is dispatched because its recent 7-day hourly observations exceeded mean + 3 standard deviations from its preceding 28-day baseline on offline duration, disconnection count, or reboot count.
- Candidate C combines percentile ranks of missing hours (F02), reboot sums (F09), divergence (F16), and thresholded offline counters (F08). As observed in Phase 5.3 and 6.2, offline duration counters and missing hours were associated with non-fault outcomes in the historical evaluation, while their inclusion coincided with higher false-alarm counts.

---

## 9. Recommended Strategy

### Recommendation: **Option A — Baseline Retained as the Selected Strategy for the Final Part 1 Pipeline**

Based on the evidence from the 26-week historical backtest, **`Baseline_3Sigma` is retained as the selected strategy for the final Part 1 pipeline**.

### Rationale for Selection:
1. **Lowest False Alarm Rate:**
   `Baseline_3Sigma` achieved a 3.59% false alarm rate (14 false alarms across 390 dispatches), compared to 5.64% (22 false alarms) for Candidate C and Candidate A. Its precision-like proportion among realized outcomes is **74.55%** (vs 65.62% for Candidate C).
2. **Stronger Early-Rank Concentration (Top-5 and Top-10):**
   `Baseline_3Sigma` captured **19 repairs in Top-5** (vs. 14 for Candidate C) and **28 repairs in Top-10** (vs. 27 for Candidate C). When field resources are constrained, Baseline provided higher repair density early in the visit queue.
3. **Lowest Combined Cost Proxy:**
   `Baseline_3Sigma` achieved the lowest combined operational cost proxy (€50,320), outperforming Candidate C (€52,760) by €2,440 and all other candidate strategies.
4. **Statistical Testing Outcome:**
   The observed repair difference between Candidate C and Baseline was not statistically significant ($p = 0.87$), while the increase in false alarms was statistically significant ($p = 0.043$). The evidence in this sample does not justify adopting the candidate.
5. **Simplicity and Transparency:**
   `Baseline_3Sigma` uses the established, verified anomaly methodology without empirical weight tuning, making it robust against overfitting to historical dispatch patterns.

---

## 10. Why Alternatives Were Not Selected

1. **`Candidate_C_SevereOffline`:**
   - *Observations:* Captured 42 repairs (+1 over Baseline).
   - *Why Not Selected:* Generated 8 additional false alarms (+57% increase). Required €3,040 in extra false alarm proxy costs to capture €600 in repair proxy. Underperformed Baseline at $K=5$ (14 vs 19) and $K=10$ (27 vs 28). The repair difference was not statistically significant ($p = 0.87$).
2. **`Candidate_A_Core`:**
   - *Observations:* Consistent weekly performance ($\sigma = 1.067$, 22 hit weeks).
   - *Why Not Selected:* Captured 40 repairs (-1 vs Baseline) while incurring 22 false alarms (+8 vs Baseline). Underperformed Baseline at $K=5$ (12 vs 19) and had a higher combined cost proxy (+€3,640).
3. **`Candidate_B_Severity`, `Candidate_D_LongTerm`, `Candidate_F_SilenceOverride`:**
   - *Why Not Selected:* Each captured only 37 repairs (-4 vs Baseline, 31.90% capture rate) while generating 21 false alarms (+7 vs Baseline). Each resulted in a combined cost proxy of €55,380 (+€5,060 worse than Baseline).
4. **`Candidate_E_Reliability`:**
   - *Why Not Selected:* Captured only 37 repairs (-4 vs Baseline) while generating 22 false alarms (+8 vs Baseline), resulting in the highest combined cost proxy among all strategies (€55,760, +€5,440 worse than Baseline). The historical meter failure feature (F17) did not improve prioritization in this backtest.

---

## 11. Limitations & Observational Constraints

The findings of this backtest and decision analysis are subject to several important operational and methodological limitations:

1. **Sample Scope (26 Weeks):**
   The historical evaluation covers 26 Mondays (August 2025 – January 2026). The 116 confirmed repairs represent a finite operational sample where minor numerical variations should not be over-interpreted.
2. **Observational Nature of Historical Dispatches:**
   Historical field visits were generated by past operational practices, not randomized trials. Gateways not selected for dispatch remain unobserved; unobserved gateways cannot be assumed to be healthy or non-faulty.
3. **Standardized Cost Proxies vs. Actual Business Costs:**
   The €380 false-alarm cost and €600 missed-repair cost are standardized evaluation proxies established for strategy comparison. They do not represent actual historical financial costs or contractual service-level agreements.
4. **No Claim of Causal Failure Prediction:**
   Ranking strategies prioritize gateways for field inspection based on observed associations between telemetry deviations and subsequent repair actions. We do not claim that telemetry deviations causally prove physical hardware failures.
5. **Temporal Boundary of Engineer Review:**
   The `engineer_review_2026-02.xlsx` dataset is dated 2026-02-15. Under strict temporal leakage guards, it cannot be used to evaluate or inform decisions during the earlier historical weeks.
6. **Generalization to the Scored Period:**
   The challenge evaluation period covers February and March 2026. While `Baseline_3Sigma` performed most reliably in this historical backtest, operational conditions or failure patterns during the scored window may differ.

---

## 12. What Phase 7 Will Do

Having evaluated the backtest results and selected `Baseline_3Sigma` as the strategy for the final Part 1 pipeline, the project proceeds to Phase 7:

1. **Phase 7.1 — End-to-End Production Pipeline Architecture:**
   Construct a clean, modular, deterministic pipeline in `src/nexora/` that orchestrates:
   - Data ingestion (`hourly_telemetry.parquet`, `weekly_meter_data.csv`, `gateway_master.csv`).
   - Active universe lifecycle filtering.
   - 3-Sigma anomaly extraction using the verified baseline methodology, followed by deterministic flagged-hour aggregation and ranking.
   - Deterministic tie-breaking and Top-15 gateway selection.
2. **Phase 7.2 — Weekly Submission Generation:**
   Generate the official submission file `predictions.csv` for the 8 scored challenge Mondays:
   `2026-02-02`, `2026-02-09`, `2026-02-16`, `2026-02-23`, `2026-03-02`, `2026-03-09`, `2026-03-16`, `2026-03-23`.
3. **Phase 7.3 — Official Submission Validation:**
   Validate `predictions.csv` against `validate_submission.py` ensuring exact adherence to schema, active gateway universe, non-empty selections, rank uniqueness ($1 \dots 15$), and zero formatting anomalies.
