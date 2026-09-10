# Phase 13 — End-to-End Testing & Clean-Snapshot Verification

**LPDG Innovation Hub Selection Challenge 2026 (NEXORA 2026)**  
**Document Type:** Comprehensive End-to-End Verification & Reproducibility Audit Report  
**Audience:** Technical Evaluators, Reviewers, and Engineering Leadership  
**Status:** COMPLETE — STRICT VERIFICATION GATE PASSED  

---

## 1. Objective

The objective of Phase 13 is to prove the end-to-end operational reproducibility, mathematical determinism, and contract compliance of the NEXORA 2026 production pipeline from an independent evaluator's perspective:
1. Verify clean-environment reproducibility of the **current uncommitted working-tree implementation** in an isolated filesystem and virtual environment.
2. Verify committed git `HEAD` reproducibility.
3. Confirm one-command production pipeline execution, runtime performance, and automated validation.
4. Validate strict official grader acceptance criteria via `validate_submission.py`.
5. Guarantee exact bitwise output reproducibility against the validated reference (`predictions.csv`) across all 120 rows and 5 columns.
6. Verify SHA-256 checksum invariance (`ec8489c8d9b4e64feb6ecc0635e6e32c77e1945818ffbb68ff8fe3bc7f415145`).
7. Audit REST API end-to-end integration and error boundary handling in the isolated snapshot.
8. Perform an exhaustive production dependency audit to guarantee zero reliance on forbidden historical datasets (`field_visits.csv`, `meter_read_success.csv`, `engineer_review_2026-02.xlsx`).
9. Maintain strict repository hygiene with zero staged changes and zero unauthorized commits.

---

## 2. Test Environment

- **Operating System:** Windows 11 Enterprise (x86_64)
- **Shell:** PowerShell 5.1 / Windows Terminal
- **Python Version:** Python 3.10.11 (Host) / Python 3.10.11 (Isolated Virtual Environment)
- **Key Dependencies Installed:**
  - `pandas`: 2.2.2
  - `numpy`: 1.26.4
  - `pyarrow`: 25.0.1
  - `pytest`: 8.4.2
  - `fastapi`: 0.115.0
  - `starlette`: 0.37.2
  - `uvicorn`: 0.29.0
  - `pydantic`: 2.13.4
- **Working Directory:** `d:\lpdg-nexora-2026`
- **Authoritative Data Location:** `d:\lpdg-nexora-2026\data`

---

## 3. Clean-Snapshot Reproducibility Procedure

Because Phases 10–13 represent deliberate, uncommitted engineering enhancements governed by the strict "DO NOT COMMIT" rule, verification was conducted across two distinct reproducibility tiers:

### Tier A: Current Working-Tree Snapshot Verification
To prove the **current hardened Phase 12/13 implementation** operates autonomously without reliance on local working tree state or developer-specific `.pth` paths:
1. **Isolated Snapshot Assembly:**
   A clean temporary directory (`nexora_curr_snapshot_...`) was created in `AppData/Local/Temp/`. The following files were copied:
   - `src/nexora/` (all current code including `config.py` and `api.py`; excluding `__pycache__` and `*.pyc`)
   - `tests/` (all 123 tests including `test_api.py`, `test_api_errors.py`, `test_error_handling.py`; excluding `__pycache__`)
   - `pyproject.toml` (standard package and dependency specification)
   - `pytest.ini`
   - `validate_submission.py`
   - `baseline_3sigma.py`
   - `.gitignore`
   - `README.md`
   *(Excluded: `.git`, `__pycache__`, `.pytest_cache`, reports, and existing `predictions.csv`).*

2. **Isolated Virtual Environment & Dependency Installation:**
   A dedicated Python virtual environment was created inside the snapshot (`<snapshot>/venv`). Dependencies and the current package were installed in editable mode:
   ```bash
   pip install -e ".[dev]"
   ```
   Verified that `import nexora` resolved strictly to the snapshot directory:
   `C:\Users\dheer\AppData\Local\Temp\nexora_curr_snapshot_a2nzr_k3\src\nexora\__init__.py`

3. **Isolated Pipeline Execution:**
   Executed from within the isolated snapshot pointing to authoritative data:
   ```bash
   <snapshot>/venv/Scripts/python -m nexora.pipeline --data D:\lpdg-nexora-2026\data --out predictions.csv
   ```
   - **Exit Code:** `0`
   - **Runtime:** `9.51 seconds` (Data loading: 5.48s, Scoring & ranking: 1.33s)
   - **Output Generated:** Exactly 120 rows across 8 competition weeks.
   - **Official Validator:** Passed with exit code `0`.
   - **Isolated SHA-256 Checksum:** `ec8489c8d9b4e64feb6ecc0635e6e32c77e1945818ffbb68ff8fe3bc7f415145`.

### Tier B: Committed Git HEAD Verification
A secondary clean copy was extracted directly from `git archive HEAD` into an isolated directory (`nexora_clean_checkout_...`).
- Pipeline command exited `0` in `7.54s`.
- Validator exited `0`.
- Produced identical SHA-256: `ec8489c8d9b4e64feb6ecc0635e6e32c77e1945818ffbb68ff8fe3bc7f415145`.

Both tiers confirmed complete reproducibility.

---

## 4. One-Command Production Execution

The authoritative entrypoint was executed from the repository root:
```bash
python -m nexora.pipeline --data data/ --out predictions.csv
```

### Execution Log
```
[NEXORA Pipeline] Initializing production pipeline...
  Data directory: D:\lpdg-nexora-2026\data
  Target output:  D:\lpdg-nexora-2026\predictions.csv
  Scored weeks:   8 Mondays (2026-02-02 to 2026-03-23)
[NEXORA Pipeline] Loading gateway_master.csv...
  Loaded 332 master asset records.
[NEXORA Pipeline] Loading and deduplicating telemetry partitions...
  Telemetry loaded: 1,426,840 rows processed across all partitions (4.09s).
  Week 1/8 [2026-02-02]: Top-15 selected (0.13s)
  Week 2/8 [2026-02-09]: Top-15 selected (0.13s)
  Week 3/8 [2026-02-16]: Top-15 selected (0.15s)
  Week 4/8 [2026-02-23]: Top-15 selected (0.13s)
  Week 5/8 [2026-03-02]: Top-15 selected (0.16s)
  Week 6/8 [2026-03-09]: Top-15 selected (0.14s)
  Week 7/8 [2026-03-16]: Top-15 selected (0.15s)
  Week 8/8 [2026-03-23]: Top-15 selected (0.14s)
[NEXORA Pipeline] Running internal production validation...
  Internal validation PASSED with zero errors.
[NEXORA Pipeline] Serialized 120 rows to D:\lpdg-nexora-2026\predictions.csv
[NEXORA Pipeline] Executing official validate_submission.py...
  Official submission validation PASSED successfully (exit code 0).
[NEXORA Pipeline] Execution completed successfully in 6.50s!
  Data loading: 4.09s | Scoring & ranking: 1.13s
```

---

## 5. Production Runtime

- **Host Repository Pipeline Runtime:** **6.50 seconds**
  - Data Ingestion & Deduplication: 4.09s (1.43M raw rows $\to$ 1,426,840 deduplicated rows)
  - Scoring & Ranking (8 weeks): 1.13s (~141 ms per week)
  - Validation & Serialization: 0.12s
  - Official Validator Subprocess: 1.16s
- **Isolated Snapshot Pipeline Runtime:** **9.51 seconds**
- **Test Suite Runtime (Isolated Snapshot):** **10.97 seconds**

---

## 6. Full Pytest Result in Isolated Snapshot

Executed inside the isolated current-implementation snapshot using its own virtual environment:
```bash
<snapshot>/venv/Scripts/pytest -q
```
```
........................................................................ [ 58%]
...................................................                      [100%]
123 passed, 2 warnings in 10.97s
```
- **Total Tests:** 123 passed (0 failed, 0 skipped, 0 xfailed)
- **No tests were deleted, weakened, or skipped.**

### Test Breakdown by Module
| Module | Tests | Description | Result |
| :--- | :---: | :--- | :---: |
| `tests/test_api.py` | 16 | FastAPI endpoints, lifecycle cache, Swagger UI, real data integration | **PASS** |
| `tests/test_api_errors.py` | 25 | HTTP status codes (400, 404, 405, 422), path leak prevention | **PASS** |
| `tests/test_data_loader.py` | 14 | Master & telemetry loading, ID normalization, dedup | **PASS** |
| `tests/test_eligibility.py` | 10 | Asset installation & decommission date lifecycle logic | **PASS** |
| `tests/test_error_handling.py` | 21 | Boundary inputs, missing files/columns, NaN metric handling | **PASS** |
| `tests/test_normalization.py` | 3 | Hex identifier canonicalization contract | **PASS** |
| `tests/test_pipeline_regression.py` | 6 | End-to-end pipeline determinism, isolation, contract | **PASS** |
| `tests/test_ranking.py` | 7 | Option B retention, Top-15 slicing, duplicate rejection | **PASS** |
| `tests/test_reasons.py` | 4 | Observational reason templates, <=300 character constraint | **PASS** |
| `tests/test_scoring.py` | 13 | Baseline_3Sigma thresholding, sample std(ddof=1), breaches | **PASS** |
| `tests/test_strategy_integrity.py` | 4 | Metric set integrity, unweighted breach accumulation | **PASS** |
| **Total** | **123** | **Complete System Regression & Hardening Coverage** | **PASS** |

---

## 7. Official Validator Result

Executed:
```bash
python validate_submission.py predictions.csv
```
- **Exit Code:** `0`
- **Output:**
  ```
  predictions.csv: OK
    15 ranked gateways for each of 8 weeks, 2026-02-02 to 2026-03-23
  ```

---

## 8. Exact Output Comparison

The predictions generated in the isolated current snapshot were compared against the validated Phase 12 reference artifact:

```python
pd.testing.assert_frame_equal(iso_df, ref_df)
```

| Column | Comparison Check | Mismatch Count | Status |
| :--- | :---: | :---: | :---: |
| `week_start` | Exact string match | 0 / 120 | **PASS** |
| `rank` | Exact integer match | 0 / 120 | **PASS** |
| `gateway_id` | Exact canonical hex match | 0 / 120 | **PASS** |
| `score` | Exact float match | 0 / 120 | **PASS** |
| `reason` | Exact string match | 0 / 120 | **PASS** |

**Result:** Zero DataFrame differences across all 120 rows and 5 columns (100% bitwise identical).

---

## 9. SHA-256 Comparison

- **Validated Reference SHA-256:**  
  `ec8489c8d9b4e64feb6ecc0635e6e32c77e1945818ffbb68ff8fe3bc7f415145`
- **Committed Git HEAD SHA-256:**  
  `ec8489c8d9b4e64feb6ecc0635e6e32c77e1945818ffbb68ff8fe3bc7f415145`
- **Isolated Current Snapshot SHA-256:**  
  `ec8489c8d9b4e64feb6ecc0635e6e32c77e1945818ffbb68ff8fe3bc7f415145`
- **Match Status:** **EXACT MATCH** (Zero drift).

---

## 10. API End-to-End Results in Isolated Snapshot

The REST API service (`src/nexora/api.py`) was executed in the isolated snapshot environment using its own dependencies:

1. **`GET /health`:** HTTP 200 OK (`{"status": "ok"}`).
2. **`GET /predictions/{week_start}`:**
   - Evaluated across all 8 competition Mondays (`2026-02-02` through `2026-03-23`).
   - Every weekly response matches `predictions.csv` bitwise across all columns.
3. **`GET /gateways/{gateway_id}`:**
   - Known gateway (`0A2778A31BE3`): HTTP 200 with factual metadata.
   - Lifecycle evaluation (`?week_start=2026-02-02`): HTTP 200 with `is_eligible=True`.
   - Malformed gateway ID (`XYZ_BAD`): HTTP 400 Bad Request.
   - Unknown gateway ID (`FFFFFFFFFFFF`): HTTP 404 Not Found.
4. **`POST /run`:**
   - Valid JSON payload (`{"week_start": "2026-02-02"}`): HTTP 200 with 15 ranked predictions matching pipeline output.
   - Missing body or empty JSON: HTTP 422 Unprocessable Entity.
   - Malformed date string: HTTP 400 Bad Request.
   - Out-of-competition date: HTTP 404 Not Found.
5. **Information Security:** Zero internal filesystem paths, drive letters, or stack traces leak in error payloads.

---

## 11. Production Data Dependency Audit

An exhaustive import and filesystem audit in the isolated environment confirmed that production prediction generation depends exclusively on:
- `gateway_master.csv`
- `telemetry/month=*/part-0.parquet`

### Verification Findings
- `field_visits.csv`: **NOT LOADED** (Present only in legacy historical backtesting; zero production imports).
- `meter_read_success.csv`: **NOT LOADED** (Zero references in `src/nexora/`).
- `engineer_review_2026-02.xlsx`: **NOT LOADED** (Present only in historical research scripts; zero production imports).
- **Dynamic Sandbox Verification:** A sandboxed data directory was constructed containing strictly `gateway_master.csv` and `telemetry/`. The isolated pipeline executed against this sandbox with zero auxiliary files:
  - Exit code: `0`
  - Output DataFrame: 100% bitwise identical to reference `predictions.csv`.

---

## 12. Repository Hygiene Audit

Inspected via `git status --short`:
```
 M src/nexora/__init__.py
 M src/nexora/data_loader.py
 M src/nexora/pipeline.py
 M src/nexora/ranking.py
 M src/nexora/reasons.py
 M src/nexora/scoring.py
 M src/nexora/validation.py
 M tests/test_pipeline_regression.py
 M tests/test_ranking.py
?? README.md
?? predictions.csv
?? pyproject.toml
?? reports/PHASE_10_ARCHITECTURE.md
?? reports/PHASE_11_FASTAPI.md
?? reports/PHASE_12_ERROR_HANDLING.md
?? reports/PHASE_13_END_TO_END_TESTING.md
?? src/nexora/api.py
?? src/nexora/config.py
?? tests/test_api.py
?? tests/test_api_errors.py
?? tests/test_error_handling.py
```

### Classification of Items
- **Required Deliverables (Uncommitted Phases 10–13):**
  - Architecture & Packaging: `src/nexora/config.py`, `pyproject.toml`, `reports/PHASE_10_ARCHITECTURE.md`
  - FastAPI Service: `src/nexora/api.py`, `tests/test_api.py`, `reports/PHASE_11_FASTAPI.md`
  - Error Handling: `tests/test_api_errors.py`, `tests/test_error_handling.py`, `reports/PHASE_12_ERROR_HANDLING.md`
  - Evaluator Docs: `README.md`, `reports/PHASE_13_END_TO_END_TESTING.md`
  - Submission Artifact: `predictions.csv` (unignored by `.gitignore`)
- **Accidental Datasets:** None.
- **Temporary Test Artifacts:** None (all snapshot directories cleaned).
- **Secrets / API Keys:** None.
- **Stage Pollution:** Clean. Zero files staged (`git add .` strictly avoided).

---

## 13. Failures Encountered & Resolutions

- **Subprocess Path Resolution in Isolated Snapshot:**
  - *Observation:* A bare `import nexora` in a fresh venv failed because the package was not yet registered in site-packages.
  - *Resolution:* Added standard `pyproject.toml` configuration enabling `pip install -e ".[dev]"`. The package installed cleanly in the isolated snapshot, verifying proper modular distribution.
  - *Result:* All 123 tests, pipeline, API, and audits passed with zero subsequent issues.

---

## 14. Final PASS / FAIL Decision

**PASS**

The current implementation independently reproduced the validated predictions with zero differences across all 120 rows and 5 columns, passed all 123 tests in an isolated virtual environment, satisfied the official submission validator, and passed all production dependency and security audits.

---

## 15. Explicit Invariance Statement

**Current implementation independently reproduced the validated predictions with zero differences.**  
Exact DataFrame comparison across all 120 rows and 5 columns (`week_start`, `rank`, `gateway_id`, `score`, `reason`) and SHA-256 checksum verification (`ec8489c8d9b4e64feb6ecc0635e6e32c77e1945818ffbb68ff8fe3bc7f415145`) conclusively prove that prediction outputs remain 100% bitwise identical to the validated production baseline.
