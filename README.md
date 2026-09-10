# NEXORA 2026 — Production Ranking Pipeline

**LPDG Innovation Hub Selection Challenge 2026**  
**Selected Specialization:** Area B — Software Development  
**Validated Submission Checksum (SHA-256):** `ec8489c8d9b4e64feb6ecc0635e6e32c77e1945818ffbb68ff8fe3bc7f415145`

---

## 1. What NEXORA Does

LPDG operates a smart metering radio network of approximately 320 active LoRaWAN gateways across Germany, each relaying hourly telemetry for 40 to 900 downstream utility meters. When a gateway degrades or fails silently, connected meters cannot be billed automatically, requiring costly manual reads and causing customer disputes.

Physical field maintenance capacity is strictly capped at **15 site visits per week**. Historically, sites were selected via manual spreadsheets and intuition, resulting in a **60.7% false alarm rate**.

NEXORA automates this operational decision: every Monday morning, it evaluates telemetry up to midnight and deterministically ranks the **15 gateways most urgently requiring inspection**, providing factual, non-causal explanation strings for dispatch crews.

---

## 2. Challenge Requirements & Specifications

The challenge brief establishes strict technical and economic criteria:
- **8 Scored Competition Mondays:** `2026-02-02`, `2026-02-09`, `2026-02-16`, `2026-02-23`, `2026-03-02`, `2026-03-09`, `2026-03-16`, `2026-03-23`.
- **Submission Output:** Exactly $8 \times 15 = 120$ rows in `predictions.csv`.
- **Schema Contract:** `week_start, rank, gateway_id, score, reason`.
- **Validation:** Must pass the official grader harness `python validate_submission.py predictions.csv` with exit code `0`.
- **Economic Cost Proxies:** Standardized decision-analysis penalties of **€380** for a false dispatch (`Kein Fehler gefunden`) and **€600/week** for an unaddressed defect (`Fehler behoben`).
- **Temporal Anti-Leakage Boundary:** Strict right-open temporal filtering ($ts < T$). Data recorded on or after decision Monday $T$ never participates in scoring.

---

## 3. Production Strategy: Baseline_3Sigma

Following 26 weeks of historical backtesting (`DECISIONS.md`), **`Baseline_3Sigma`** was selected as the frozen production strategy:
1. **Trailing 28-Day Baseline Window $[T-28\text{d}, T)$:** Computes sample mean ($\mu$) and standard deviation ($\sigma$, pandas $ddof=1$) per gateway across three approved telemetry signals:
   - `offline_duration_sec`
   - `disconnection_cnt`
   - `reboot_cnt`
2. **Zero-Variance & Insufficient Baseline Protection:** If historical baseline variance is zero ($\sigma = 0$) or observation count $N=1$, $\sigma$ is replaced with `NaN`, ensuring constant baselines produce zero false breaches ($x > \text{NaN} \to \text{False}$).
3. **Trailing 7-Day Recent Evaluation Window $[T-7\text{d}, T)$:** Flags any hour where an individual metric strictly exceeds $\mu + 3\sigma$.
4. **Unweighted Breach Accumulation:** Score equals the total sum of individual metric breaches across the 7-day window (each observation hour contributes 0, 1, 2, or 3 breaches).
5. **Option B Silent-Gateway Retention:** Commissioned gateways with zero telemetry in the trailing 7 days are retained in the candidate pool with $score = 0.0$, $flagged\_hours = 0$, and $worst\_metric = \text{"no\_telemetry"}$.
6. **Deterministic Tie-Breaking:** Gateways are sorted by `score` **descending**, then `gateway_id` **ascending** (canonical lexicographical hex order). Top 15 are extracted.
7. **Observational Reason Generation:** Conforms strictly to $\le 300$ characters without unsupported physical claims (e.g. blown fuse, hardware failure).

---

## 4. Repository Structure

```
lpdg-nexora-2026/
├── data/                               # Authoritative challenge datasets
│   ├── gateway_master.csv              # Master asset registry (332 gateways)
│   └── telemetry/month=*/part-0.parquet # Hourly telemetry (1.43M records)
├── src/nexora/                         # Production software package (Area B)
│   ├── __init__.py                     # Clean package exports
│   ├── config.py                       # Centralized configuration constants
│   ├── data_loader.py                  # Ingestion, hex normalization, deduplication
│   ├── eligibility.py                  # Lifecycle asset date filtering
│   ├── scoring.py                      # Baseline_3Sigma 3-metric breach accumulator
│   ├── ranking.py                      # Option B retention, Top-15 deterministic sorting
│   ├── reasons.py                      # Compliant observational reason generation
│   ├── validation.py                   # Schema verification & validator wrapper
│   ├── pipeline.py                     # Single-week engine & CLI orchestrator
│   └── api.py                          # High-performance FastAPI REST service
├── tests/                              # Automated regression test suite (123 tests)
│   ├── test_api.py                     # FastAPI core endpoints, lifecycle cache
│   ├── test_api_errors.py              # HTTP error status codes, path leak prevention
│   ├── test_data_loader.py             # File parsing, normalization, dedup
│   ├── test_eligibility.py             # Active lifecycle date evaluation
│   ├── test_error_handling.py          # Boundary conditions, empty datasets, invalid types
│   ├── test_normalization.py           # Hex identifier canonicalization
│   ├── test_pipeline_regression.py     # End-to-end pipeline determinism & parity
│   ├── test_ranking.py                 # Option B retention, duplicate rejection
│   ├── test_reasons.py                 # Reason template compliance (<=300 chars)
│   ├── test_scoring.py                 # 3-Sigma thresholding, std(ddof=1), breaches
│   └── test_strategy_integrity.py      # Metric set integrity, unweighted breaches
├── reports/                            # Detailed phase engineering records
├── baseline_3sigma.py                  # Challenge reference baseline script
├── validate_submission.py              # Official challenge submission validator
├── pyproject.toml                      # Standard package configuration & dependencies
├── pytest.ini                          # Test configuration (pythonpath = src)
├── predictions.csv                     # Validated 120-row submission artifact
├── DECISIONS.md                        # The five core engineering decisions
├── AI-USAGE.md                         # AI disclosure & specific errors caught
└── README.md                           # Evaluator guide & documentation
```

---

## 5. Data Requirements & Dataset Isolation

### Required Production Datasets
- `data/gateway_master.csv`: Latin-1 master asset register containing commissioning and decommissioning timestamps.
- `data/telemetry/month=*/part-0.parquet`: 8 monthly partitions covering August 2025 through March 2026.

### Strictly Forbidden from Production
The production prediction pipeline enforces strict dataset isolation and **never loads, imports, or references**:
- `data/field_visits.csv` (used only in historical research backtesting)
- `data/meter_read_success.csv`
- `data/engineer_review_2026-02.xlsx`

Automated test `test_pipeline_dataset_isolation` verifies that execution succeeds even when all three auxiliary files are physically deleted.

---

## 6. Installation & Environment Setup

Ensure Python 3.10+ is installed, then install the package in editable mode:

```bash
pip install -e ".[dev]"
```

Alternatively, install dependencies directly and set `PYTHONPATH=src`:
```bash
pip install pandas pyarrow numpy pytest fastapi uvicorn httpx
# Linux/macOS:
export PYTHONPATH=src
# Windows PowerShell:
$env:PYTHONPATH = "src"
```

---

## 7. One-Command Production Execution

Execute the authoritative production pipeline from the project root:

```bash
python -m nexora.pipeline --data data/ --out predictions.csv
```

### Execution Telemetry
- **Runtime:** ~6.5 seconds on a standard developer machine.
- **Telemetry Ingestion:** 1,426,840 records loaded and deduplicated in ~4.1s.
- **Scoring & Ranking:** 8 competition weeks scored in ~1.1s (~141 ms/week).
- **Output:** Writes exactly 120 rows to `predictions.csv`.
- **Automated Validation:** Automatically executes `validate_submission.py` upon completion.

---

## 8. Official Submission Validation

Verify the generated predictions independently using the challenge validator:

```bash
python validate_submission.py predictions.csv
```

Expected output:
```
predictions.csv: OK
  15 ranked gateways for each of 8 weeks, 2026-02-02 to 2026-03-23
```
- **Exit Code:** `0`

---

## 9. FastAPI REST Service (Part 2 — Software Development)

NEXORA wraps the production prediction engine in a high-performance REST API:

```bash
uvicorn nexora.api:app --host 0.0.0.0 --port 8000
```

### Endpoints
| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Healthcheck returning `{"status": "ok"}`. |
| `GET` | `/predictions/{week_start}` | Returns 15 ranked predictions for a competition Monday (e.g. `2026-02-02`) in <200ms. |
| `GET` | `/gateways/{gateway_id}` | Master asset metadata and active lifecycle evaluation for date $T$. |
| `POST` | `/run` | Programmatic weekly prediction execution via JSON payload (`{"week_start": "2026-02-02"}`). |
| `GET` | `/docs` | Interactive OpenAPI / Swagger documentation. |

The API and CLI pipeline share the exact same underlying `predict_week` engine, ensuring 100% bitwise parity.

---

## 10. Automated Test Suite

Run all 123 automated regression tests:

```bash
pytest -q
```

Expected output:
```
123 passed in ~10s
```

The suite guarantees zero regression on scoring formulations, active fleet eligibility, Option B silent-gateway retention, deterministic sorting, API responses, and edge-case boundary errors.

---

## 11. Expected Output & Verified Checksum

- **File:** `predictions.csv`
- **Total Rows:** Exactly 120 rows ($8 \text{ weeks} \times 15 \text{ gateways}$).
- **Columns:** `week_start, rank, gateway_id, score, reason`.
- **Validated SHA-256 Checksum:**  
  `ec8489c8d9b4e64feb6ecc0635e6e32c77e1945818ffbb68ff8fe3bc7f415145`

---

## 12. What It Cannot Do & Operational Limitations

As required by the challenge brief, we document the honest boundaries of the system:
1. **Statistical Anomaly vs. Physical Root Cause:**  
   3-sigma metric breaches describe empirical distress, not physical failure modes. A high breach count indicates the gateway is behaving abnormally relative to its own history, but cannot distinguish an antenna disconnect from a degraded power supply or local frequency interference.
2. **Firmware Counter Rollover & Irregularity:**  
   Firmware counters (`disconnection_cnt`, `reboot_cnt`) can experience monotonic rollover or sudden firmware resets. While our trailing 28-day sample standard deviation buffers against modest noise, an abrupt counter reset produces a temporary single-hour spike.
3. **Ambiguity of Silent Gateways:**  
   Under Option B, gateways producing zero telemetry receive score 0.0. In physical reality, a silent gateway might have suffered a total catastrophic power failure or might merely be an intermittently transmitting installation.
4. **Hard Physical Capacity Constraint:**  
   The system ranks exactly 15 gateways per week. If 25 gateways experience severe distress in a single week, the 10 lowest-scoring anomalies are deferred to subsequent weeks due to crew bandwidth constraints.

### What Another Two Weeks Would Fix
1. **Neighborhood Spatial Correlation:** Cross-correlate silent gateways with adjacent network relays within a 5 km radius. If neighboring gateways are healthy, the silence is an isolated gateway hardware defect; if neighbors are also dark, it indicates a wider utility power outage or cellular carrier outage.
2. **Dynamic Top-K & Economic Sensitivity Slider:** Expose an operational API parameter allowing dispatch managers to adjust dispatch volume based on technician availability and fuel costs.
3. **Real-Time Streaming Adapter:** Ingest live MQTT or Kafka telemetry streams directly, replacing batch parquet directory scans with a real-time anomaly sliding window.

---

## 13. Clean Reproduction Protocol

To independently reproduce the submission on another machine:
```bash
# 1. Clone repository
git clone <repo-url> && cd lpdg-nexora-2026

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Place dataset in data/
# (Ensure data/gateway_master.csv and data/telemetry/ exist)

# 4. Run pipeline
python -m nexora.pipeline --data data/ --out predictions.csv

# 5. Validate
python validate_submission.py predictions.csv

# 6. Verify checksum (PowerShell)
(Get-FileHash predictions.csv -Algorithm SHA256).Hash
# Expected: EC8489C8D9B4E64FEB6ECC0635E6E32C77E1945818FFBB68FF8FE3BC7F415145
```
