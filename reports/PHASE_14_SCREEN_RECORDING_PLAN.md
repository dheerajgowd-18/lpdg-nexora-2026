# Phase 14 — Screen Recording Plan (6–8 Minutes)

**Project:** NEXORA 2026 — LPDG Innovation Hub Selection Challenge  
**Requirement Source:** Challenge Brief Section "Part 1 — the basics", Item 7  
**Target Duration:** 6 minutes 30 seconds to 7 minutes 30 seconds  
**Presenter Area:** B — Software Development  

---

## 1. Recording Timeline & Script Breakdown

| Timestamp | Section | Visual Focus on Screen | Talking Points & Narrative |
| :---: | :--- | :--- | :--- |
| **0:00 – 1:00** | **The Operational Problem & Constraints** | Challenge brief diagram / slide showing rooftop gateway & downstream meters; terminal showing dataset directory (`data/`). | - Context: LPDG operates 320 LoRaWAN gateways relaying hourly readings for 40 to 900 meters each.<br>- Failure mode: Degraded gateways drop meter packets silently without loud alarms.<br>- Economic penalty structure: Standardized proxies of €380 for a false dispatch vs. €600/week for an unaddressed defect.<br>- Operational bottleneck: Hard physical dispatch capacity of exactly 15 site visits per week. |
| **1:00 – 2:15** | **The Engineering Decision & Backtesting** | `DECISIONS.md` and backtest summary chart from `reports/backtest/strategy_comparison.csv`. | - Evaluated 7 ranking strategies across 26 weeks of historical data under strict temporal anti-leakage boundaries ($ts < T$).<br>- Key discovery: Multi-feature composite heuristics (Candidates A–F) increased captured repairs by only +2.4% while triggering a +57% surge in false alarms.<br>- Economic reality: Composite models caused €61,280 in net loss vs. €57,600 for Baseline_3Sigma.<br>- Decision: Locked `Baseline_3Sigma` with Option B silent-gateway retention (score=0, deterministic tie-breaking). |
| **2:15 – 3:30** | **Production Software Architecture** | VS Code editor showing `src/nexora/` package structure: `pipeline.py`, `scoring.py`, `ranking.py`, `api.py`, `config.py`. | - Highlight modular separation: Data loading, lifecycle eligibility, scoring, ranking, and reason generation are strictly decoupled.<br>- Core prediction engine `predict_week(master_df, telemetry_df, date, top_k=15)` is completely stateless and reusable.<br>- CLI orchestrator and REST API both import this exact same engine — zero code duplication.<br>- Show defensive boundary validation: strict UTC timezone check, positive `top_k`, and explicit `ValueError` rejection for duplicate scored records. |
| **3:30 – 4:45** | **Live Execution & Validation** | Split terminal: Run production pipeline, validator, and test suite. | - Run pipeline: `python -m nexora.pipeline --data data/ --out predictions.csv`<br>  *Highlight execution: 1.43M rows loaded in 4s, 8 weeks scored in 1.1s, total runtime ~6.5s.*<br>- Run official validator: `python validate_submission.py predictions.csv`<br>  *Show clean exit code 0, 120 valid rows (8 weeks × 15 gateways).*<br>- Run test suite: `pytest -q`<br>  *Show 123 tests passing in ~10s across unit, pipeline, API, and boundary error suites.*<br>- Show checksum: SHA-256 `ec8489c8d9b4e64feb6ecc0635e6e32c77e1945818ffbb68ff8fe3bc7f415145`. |
| **4:45 – 5:45** | **Part 2 Specialization: FastAPI Service** | Browser showing Swagger UI (`/docs`) and terminal executing live API queries via `curl` or browser. | - Present the REST API interface (`uvicorn nexora.api:app`).<br>- Demonstrate `GET /health` returning `{"status": "ok"}`.<br>- Demonstrate `GET /predictions/2026-02-02` returning the 15 ranked gateways with factual observational reasons in <200ms.<br>- Demonstrate `GET /gateways/{id}` returning asset metadata and active eligibility.<br>- Demonstrate error handling: `GET /predictions/bad-date` returning HTTP 400 with clean, sanitized error payload (no internal file paths leaked). |
| **5:45 – 6:45** | **Live Session Change Readiness** | VS Code showing `src/nexora/api.py`. | - Demonstrate live code change readiness (as required by live interview session):<br>  *Show how easily an evaluator's requested feature can be added live without risking scoring regressions.*<br>  *Example: Add `GET /predictions/{week_start}/summary` returning aggregated breach count and worst-metric breakdown across the Top 15 in under 15 lines of code.*<br>- Re-run pytest in 10s to prove regression immunity. |
| **6:45 – 7:30** | **Limitations & "What Another Two Weeks Buys"** | `README.md` Limitations section. | - Honest limitations: 3-sigma anomalies describe statistical distress, not physical root causes; firmware counters can experience rollover; 15 visits hard cap leaves sub-threshold gateways queued.<br>- What another two weeks would buy:<br>  1. Neighborhood correlation analysis to distinguish localized grid power outages from isolated gateway antenna hardware faults.<br>  2. Real-time streaming ingestion adapter (MQTT/Kafka) to replace monthly batch parquet files.<br>  3. Dynamic visit capacity optimization based on real-time crew availability. |

---

## 2. Technical Setup Checklist for Recording

1. **Clean Terminal State:**
   - Pre-clear screen (`clear` / `cls`).
   - Terminal prompt positioned in project root `D:\lpdg-nexora-2026`.
   - Font size set to 14–16pt for clear legibility on 1080p video.
2. **Editor Layout:**
   - VS Code in high-contrast or standard dark theme.
   - File tree visible on left: `src/nexora/`, `tests/`, `predictions.csv`, `DECISIONS.md`, `README.md`.
3. **Browser Window:**
   - Clean browser tab open to `http://localhost:8000/docs` ready to demonstrate OpenAPI specification.
4. **Commands Pre-Tested:**
   - `python -m nexora.pipeline --data data/ --out predictions.csv` (Verified: 6.5s)
   - `python validate_submission.py predictions.csv` (Verified: OK)
   - `pytest -q` (Verified: 123 passed)
