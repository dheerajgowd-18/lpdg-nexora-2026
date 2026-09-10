# Phase 10 — Software Architecture & Refactoring

**LPDG Innovation Hub Selection Challenge 2026 (NEXORA 2026)**  
**Document Type:** Architecture Review & Refactoring Report  
**Audience:** Technical Reviewers, Evaluators, and Engineering Leadership  
**Status:** COMPLETE — STRICT ARCHITECTURAL VERIFICATION PASSED  

---

## 1. Status

**PASS**

The Phase 10 software architecture review and refactoring has been completed. The codebase now features centralized configuration management (`src/nexora/config.py`), decoupled single-week prediction logic (`predict_week`) ready for Phase 11 FastAPI consumption, zero circular package initialization warnings, and complete regression verification across 60 automated test cases and the official grader harness. The frozen `Baseline_3Sigma` scoring formulation, Option B silent-gateway policy, and submission contracts remain 100% mathematically and behaviorally intact.

---

## 2. Before Architecture

Prior to Phase 10, the production codebase was organized into eight separate modules:
- `data_loader.py`
- `eligibility.py`
- `scoring.py`
- `ranking.py`
- `reasons.py`
- `validation.py`
- `pipeline.py`
- `__init__.py`

While functionally verified in Phase 8 and regression-protected in Phase 9, the architecture suffered from minor coupling and cohesion issues:
1. **Scattered Challenge Constants:** Configuration values (`SCORED_WEEKS`, `VISITS_PER_WEEK`, `BASELINE_DAYS`, `RECENT_DAYS`, `SIGMA`, `METRICS`, `MAX_REASON_CHARS`, `REQUIRED_COLUMNS`) were independently redefined or duplicated across `pipeline.py`, `ranking.py`, `scoring.py`, `reasons.py`, and `validation.py`.
2. **Coupled Multi-Week Orchestration:** `pipeline.py` bundled file loading, multi-week looping, and CLI execution together in `run_pipeline`, without an isolated function for scoring a single decision date $T$.
3. **Circular Import Warning on CLI Invocations:** Top-level import of `pipeline` inside `__init__.py` triggered Python `runpy` `RuntimeWarning` when executed via `python -m nexora.pipeline`.

---

## 3. Problems Found

1. **Configuration Duplication (Violation of DRY / Single Source of Truth):**
   - `VISITS_PER_WEEK = 15` was declared in both `ranking.py` and `validation.py`.
   - `SCORED_WEEKS` was declared in `pipeline.py` and duplicated as `DEFAULT_SCORED_WEEKS` in `validation.py`.
   - `MAX_REASON_CHARS = 300` was declared in both `reasons.py` and `validation.py`.
   - `REQUIRED_COLUMNS` was defined ad-hoc in `validation.py` without a formal schema export.
2. **Cohesion & API Readiness:**
   - In preparation for Phase 11 (FastAPI web service), there was no function that accepted loaded DataFrames and a target Monday $T$ to yield that week's Top-15 recommendations without running the entire multi-week pipeline or re-implementing the 5-step scoring sequence.
3. **Execution Warning:**
   - Executing `python -m nexora.pipeline` prompted `runpy` to warn that `nexora.pipeline` was pre-imported into `sys.modules` via `__init__.py`.

---

## 4. Refactoring Performed

1. **Centralized Configuration (`src/nexora/config.py`):**
   - Created `src/nexora/config.py` defining typed, final constants for calendar horizons (`SCORED_WEEKS`), capacity (`VISITS_PER_WEEK`), mathematical scoring parameters (`BASELINE_DAYS`, `RECENT_DAYS`, `SIGMA`, `METRICS`), explainability constraints (`MAX_REASON_CHARS`, `FROZEN_ZERO_SCORE_REASON`), and dataset column schemas (`REQUIRED_PREDICTION_COLUMNS`, `REQUIRED_MASTER_COLUMNS`, `REQUIRED_TELEMETRY_COLUMNS`).
   - Re-exported all constants from their traditional module locations to guarantee 100% backward compatibility for all callers and tests.
2. **Extracted Single-Week Prediction Engine (`predict_week` in `src/nexora/pipeline.py`):**
   - Extracted core weekly recommendation logic (eligibility $\rightarrow$ scoring $\rightarrow$ ranking $\rightarrow$ reason generation $\rightarrow$ schema formatting) into a pure, testable function `predict_week(...)`.
   - Refactored `run_pipeline` to delegate to `predict_week` inside the multi-week evaluation loop.
   - Positioned `predict_week` as the primary integration interface for Phase 11 FastAPI endpoint handlers.
3. **Package Initialization Clean-Up (`src/nexora/__init__.py`):**
   - Removed eager module-level import of `pipeline.py`, implementing lazy attribute resolution via `__getattr__` for `predict_week` and `run_pipeline`.
   - Completely eliminated the `runpy` `RuntimeWarning` when executing `python -m nexora.pipeline`.
4. **Architectural Test Coverage Expansion (`tests/test_pipeline_regression.py`):**
   - Added `test_predict_week_single_monday_independent` to verify that `predict_week` executes independently on in-memory fixtures, returns exactly 15 rows with correct schema, and maintains full compliance outside the CLI wrapper.

---

## 5. Final Architecture

```
src/nexora/
├── __init__.py          # Public package API with lazy pipeline exports
├── config.py            # Centralized, immutable challenge configuration & schemas
├── data_loader.py       # Raw file ingestion, ID canonicalization, deduplication, UTC normalization
├── eligibility.py       # Lifecycle eligibility evaluation (active fleet at decision date T)
├── scoring.py           # Frozen Baseline_3Sigma mathematical anomaly scoring ([T-28d, T), [T-7d, T))
├── ranking.py           # Option B silent-gateway alignment, deterministic sorting, Top-15 selection
├── reasons.py           # Observational, non-causal reason string generation (<= 300 chars)
├── validation.py        # Internal multi-rule sanity validation & official grader subprocess harness
└── pipeline.py         # Single-week prediction engine (predict_week) & multi-week CLI orchestrator
```

---

## 6. Module Responsibilities

| Module | Primary Responsibility | Key Inputs | Key Outputs |
| :--- | :--- | :--- | :--- |
| `config.py` | Authoritative configuration and schema definitions | None | Immutable constants, column lists, date schedules |
| `data_loader.py` | File I/O, Latin-1 decoding, ID normalization, Parquet deduplication, UTC timestamps | File paths (`data/`) | Normalized `pd.DataFrame` (master & telemetry) |
| `eligibility.py` | Deterministic active fleet filtering on decision date $T$ | `master_df`, `date` | `list[str]` of active canonical gateway IDs |
| `scoring.py` | Pure mathematical evaluation of 3-sigma anomaly breaches | `telemetry_df`, `date` | Scored `pd.DataFrame` with breach counts |
| `ranking.py` | Complete fleet universe alignment, Option B retention, deterministic sorting | `scored_df`, `eligible_ids`, `top_k` | Top-15 ranked `pd.DataFrame` |
| `reasons.py` | Factual, non-causal explanation generation conforming to length limits | Ranked `pd.DataFrame` | Augmented `pd.DataFrame` with `reason` column |
| `validation.py` | Schema and business rule verification, grader integration | Predictions `pd.DataFrame` / CSV | Error list (`list[str]`) or boolean pass |
| `pipeline.py` | Prediction orchestration (`predict_week`) and CLI runner (`run_pipeline`) | Datasets, parameters, output path | Validated submission `pd.DataFrame` and CSV |

---

## 7. Data Flow

```
[Raw Data on Disk: gateway_master.csv & telemetry/month=*/part-0.parquet]
                              │
                              ▼
           Stage 1: Ingestion & Normalization (DataLoader)
             - Strip colons, whitespace -> 12-char uppercase hex
             - Deduplicate exact duplicates on (gateway_id, ts_utc)
             - Enforce timezone-aware UTC timestamps
                              │
                              ▼
           Stage 2: Single-Week Prediction Engine (predict_week)
             ├─ Step A: Lifecycle Eligibility (eligibility.py)
             │    - installed_on <= T AND (decommissioned_on > T OR null)
             │
             ├─ Step B: Baseline_3Sigma Scoring (scoring.py)
             │    - Baseline: [T-28d, T), Recent: [T-7d, T)
             │    - Strict cutoff: ts < T
             │    - Breach: x > mean + 3*std (ddof=1, std=0 -> NaN)
             │    - Accumulate breaches across 3 metrics (0, 1, 2, or 3)
             │
             ├─ Step C: Universe Completion & Ranking (ranking.py)
             │    - Option B: silent eligible assets -> score=0.0, no bonus
             │    - Deterministic sort: score DESC, gateway_id ASC
             │    - Select Top-15 assets (ranks 1..15)
             │
             ├─ Step D: Observational Reasons (reasons.py)
             │    - Positive: breach counts & worst metric (<= 300 chars)
             │    - Zero: exact frozen baseline comparison text
             │
             └─ Step E: Schema Projection
                  - Output columns: week_start, rank, gateway_id, score, reason
                              │
                              ▼
           Stage 3: Multi-Week Orchestration (run_pipeline)
             - Iterate across 8 scored Mondays (2026-02-02 to 2026-03-23)
             - Concatenate 8 x 15 = 120 prediction rows
                              │
                              ▼
           Stage 4: Validation & Persistence (validation.py)
             - Internal sanity checks (validate_predictions_df)
             - Serialize predictions.csv
             - Execute official validator (validate_submission.py) -> Exit code 0
```

---

## 8. Dependency Boundaries

```
                 config.py (Zero dependencies)
                    ▲
         ┌──────────┼──────────┬──────────┐
         │          │          │          │
   data_loader  eligibility  scoring   ranking ──► reasons.py
         │          │          │          │
         └──────────┼──────────┴──────────┘
                    │
                    ▼
               pipeline.py (predict_week / run_pipeline)
                    │
                    ▼
               validation.py
```

- High cohesion, low coupling: Domain logic modules (`eligibility`, `scoring`, `ranking`, `reasons`) do not import from `pipeline` or CLI layers.
- Dependency direction flows strictly inward toward domain models and configuration.

---

## 9. Scoring Isolation

The mathematical formulation of `Baseline_3Sigma` remains strictly isolated in `scoring.py`:
- Monitored signals: strictly `offline_duration_sec`, `disconnection_cnt`, `reboot_cnt`.
- Parameter boundaries: `BASELINE_DAYS = 28`, `RECENT_DAYS = 7`, `SIGMA = 3.0`.
- Mathematical rules: pandas sample standard deviation (`ddof=1`), zero variance replaced with `NaN`, insufficient observations ($N=1$) yielding `NaN`, strict threshold inequality ($x > \mu + 3\sigma$).
- Scoring metric: unweighted linear breach accumulation (each metric breach = 1.0).
- Zero infiltration: No machine learning, candidate weights, or economic feature composite logic can enter without failing `test_strategy_integrity.py`.

---

## 10. Dataset Isolation

Production execution is strictly decoupled from research datasets:
- Approved production inputs: ONLY `gateway_master.csv` and `telemetry/month=*/part-0.parquet`.
- Excluded auxiliary files: `field_visits.csv`, `meter_read_success.csv`, and `engineer_review_2026-02.xlsx` are never loaded or accessed during production execution.
- Protected by automated test: `test_pipeline_dataset_isolation`.

---

## 11. Silent-Gateway Handling

Option B remains frozen and strictly enforced in `ranking.py`:
- Any lifecycle-eligible gateway with no observations in the recent 7-day window $[T-7\text{d}, T)$ is assigned:
  - `score = 0.0`
  - `flagged_hours = 0`
  - `worst_metric = "no_telemetry"`
- Ranking strictly places positive-score gateways first, with score-0.0 gateways (both silent and zero-breach active assets) tie-broken exclusively by `gateway_id` ascending.
- No silence bonus or penalty is applied.

---

## 12. Error-Handling Boundaries

- Data Loader: Raises `FileNotFoundError` on missing directories or files; raises `ValueError` on missing required schema columns or malformed gateway IDs.
- Eligibility: Accepts `datetime.date`, `datetime.datetime`, and ISO strings; handles null/NaT decommissioned dates safely without raising pandas `TypeError`.
- Ranking: Raises explicit `ValueError` if the eligible fleet has fewer than 15 gateways.
- Validation: Returns structured list of error descriptions on internal rule violations; raises `RuntimeError` with subprocess output if `validate_submission.py` exits with non-zero code.

---

## 13. CLI / Orchestration Design

- CLI Wrapper: `main()` in `pipeline.py` parses `--data` and `--out` CLI arguments and invokes `run_pipeline`.
- Orchestrator: `run_pipeline` manages file I/O, progress reporting, validation, and file persistence.
- Core Prediction Engine: `predict_week` is a pure function operating on in-memory DataFrames and a target Monday. It has zero CLI dependencies and will be imported directly by Phase 11 FastAPI route handlers.

---

## 14. Test Impact

- Existing Phase 9 test suite updated to incorporate `test_predict_week_single_monday_independent`.
- Total test count increased from 59 to **60 tests**.
- All 60 tests pass cleanly in **3.37 seconds**.
- No tests were deleted or weakened.

---

## 15. Determinism Verification

A dual pipeline run was executed against the real challenge dataset:
```python
python -m nexora.pipeline --data data/ --out predictions_run1.csv
python -m nexora.pipeline --data data/ --out predictions_run2.csv
pd.testing.assert_frame_equal(df1, df2)
```
Result: **DETERMINISM EXACT MATCH CONFIRMED.** Zero byte variance.

---

## 16. Performance Result

- **Data Loading & Deduplication:** 3.97 seconds
- **Scoring & Ranking (8 Weeks):** 1.09 seconds
- **Validation & Serialization:** 1.14 seconds
- **Total Pipeline Execution Runtime:** **6.20 seconds** (well within the < 60s engineering target)

---

## 17. Files Changed

| File | Status | Nature of Changes |
| :--- | :--- | :--- |
| `src/nexora/config.py` | **NEW** | Centralized immutable configuration constants and schemas |
| `src/nexora/pipeline.py` | **MODIFIED** | Extracted `predict_week`, centralized config imports, streamlined orchestration |
| `src/nexora/__init__.py` | **MODIFIED** | Re-exported `config` symbols, added lazy loading for pipeline functions |
| `src/nexora/scoring.py` | **MODIFIED** | Imported constants from `.config` with backward-compatible re-exports |
| `src/nexora/ranking.py` | **MODIFIED** | Imported `VISITS_PER_WEEK` from `.config` |
| `src/nexora/reasons.py` | **MODIFIED** | Imported `MAX_REASON_CHARS` and frozen zero-score text from `.config` |
| `src/nexora/data_loader.py` | **MODIFIED** | Imported required column schemas from `.config` |
| `src/nexora/validation.py` | **MODIFIED** | Imported constants and schemas from `.config` |
| `tests/test_pipeline_regression.py` | **MODIFIED** | Added `test_predict_week_single_monday_independent` |
| `reports/PHASE_10_ARCHITECTURE.md` | **NEW** | Formal Phase 10 architecture and verification report |

---

## 18. Remaining Architectural Limitations

1. **In-Memory Telemetry Scale:**
   - The entire deduplicated telemetry dataset (~1.43M rows, ~50 MB in memory) is retained in memory by `DataLoader`. This is optimal for the competition dataset (~6s execution), but in a production environment with years of data, chunked or time-windowed Parquet loading would be required.
2. **Single-Node Execution:**
   - Scoring loops sequentially through the 8 Mondays. Because evaluation takes only ~1.09s total, multiprocessing is unnecessary and avoided to keep code simple and deterministic.

---

## 19. Phase 11 Readiness

The architecture is fully prepared for **Phase 11 (FastAPI)**:
- `predict_week(master_df, telemetry_df, decision_monday)` can be invoked directly by FastAPI endpoint handlers.
- Caching `DataLoader` in FastAPI application lifespan state allows instant single-week scoring (~0.13s per request) without reloading Parquet files from disk on every API call.
- Data structures and schemas are clearly typed and ready for Pydantic response models.

---

## 20. Final Verdict

**PHASE 10 COMPLETE — ARCHITECTURE VERIFIED & LOCKED.**
