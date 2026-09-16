# NEXORA 2026 — Production Ranking Pipeline

**LPDG Innovation Hub Selection Challenge 2026**  
**Selected Specialization:** Area B — Software Development  
**Validated Submission Checksum (SHA-256):** `ec8489c8d9b4e64feb6ecc0635e6e32c77e1945818ffbb68ff8fe3bc7f415145`

---

## Submission Demonstration

A 6–8 minute technical demonstration covering the NEXORA solution, production pipeline, API, and representative result.

[Watch the NEXORA 2026 submission recording](https://drive.google.com/file/d/1WYtKEgd1VSFYbtq8BMMKFEchxsAFdxBI/view?usp=sharing)

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
5. **Option B Silent-Gateway Retention:** Commissioned gateways with zero telemetry in the trailing 7 days are retained in the candidate pool with `score = 0.0`, `flagged_hours = 0`, and `worst_metric = "no_telemetry"`.
6. **Deterministic Tie-Breaking:** Gateways are sorted by `score` **descending**, then `gateway_id` **ascending** (canonical lexicographical hex order). Top 15 are extracted.
7. **Observational Reason Generation:** Conforms strictly to $\le 300$ characters without unsupported physical claims (e.g. blown fuse, hardware failure).

### 3.1 Swappable Strategy Abstraction (Area B)

To fulfill the Area B software engineering requirement (*"Someone should be able to swap out how the ranking works without touching the API"*), ranking logic is decoupled via an explicit strategy abstraction (`src/nexora/strategy.py`):

```
    API / CLI Pipeline
           ↓
    PredictionService
           ↓
    PredictionStrategy (Protocol)
           ↓
    Baseline3SigmaStrategy (Selected Production Default)
           ↓
    Authoritative Scoring & Ranking Core (scoring.py, ranking.py, etc.)
```

- **Selected Production Strategy:** `Baseline_3Sigma` remains the frozen production strategy.
- **Decoupled Interface:** The API and pipeline interact strictly with `PredictionService` through the `PredictionStrategy` protocol. The active strategy can be hot-swapped at runtime or injected at app creation without altering a single line of API endpoint code.
- **Zero Algorithmic Change:** `Baseline3SigmaStrategy` delegates directly to the existing core modules (`scoring.py`, `ranking.py`, `eligibility.py`, `reasons.py`), ensuring zero code duplication and guaranteeing byte-for-byte reproducibility of `predictions.csv`.

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
│   ├── strategy.py                     # Swappable PredictionStrategy & PredictionService
│   ├── validation.py                   # Schema verification & validator wrapper
│   ├── pipeline.py                     # Single-week engine & CLI orchestrator
│   └── api.py                          # High-performance FastAPI REST service
├── frontend/                           # Evaluator demonstration UI (HTML/CSS/JS)
│   ├── index.html                      # Semantic UI layout & status indicator
│   ├── style.css                       # Minimal technical styling
│   └── app.js                          # Pure fetch client calling FastAPI backend
├── tests/                              # Automated regression test suite (186 tests)
│   ├── test_strategy_abstraction.py    # Swappable strategy protocol & API decoupling
│   ├── test_bug_regression.py          # Dedicated bug regression suite (Challenge requirement)
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
├── Makefile                            # One-command execution harness (make run, test, api)
├── Dockerfile                          # Isolated container build
├── docker-compose.yml                  # Container volume mount execution (docker compose up)
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

The challenge brief requires:
> *"It runs with one command on a computer that is not yours. docker compose up, make run, or whatever you prefer, reading the data from a folder called data."*

NEXORA supports all standard execution workflows out of the box:

### Option A: Via `make run` (Recommended)
```bash
make run
```

### Option B: Via `docker compose up` (Isolated container)
Mounts `./data` into the container as a read-only volume and writes `predictions.csv` directly:
```bash
docker compose up
```

### Option C: Direct Python Module Invocation
```bash
python -m nexora.pipeline --data data/ --out predictions.csv
```

### Execution Telemetry
- **Runtime:** ~6.2 seconds on a standard developer machine.
- **Telemetry Ingestion:** 1,426,840 records loaded and deduplicated in ~4.0s.
- **Scoring & Ranking:** 8 competition weeks scored in ~1.0s (~125 ms/week).
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

NEXORA wraps the production prediction engine in a high-performance, fully documented REST API strictly meeting the Challenge Brief specifications:
> *"A web API: ask it for this week's 15; ask it why a particular gateway is where it is; tell it to run again. Enough documentation that someone could call your API without asking you."*

Start the API service:
```bash
uvicorn nexora.api:app --host 0.0.0.0 --port 8000
# or via Makefile:
make api
```

### Endpoints
| Method | Path | Challenge Brief Requirement | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/health` | DevOps / Health Monitoring | Liveness check returning `{"status": "ok"}`. |
| `GET` | `/predictions` | *"ask it for this week's 15"* | Returns the 15 gateways to visit this week (defaults to latest competition week `2026-03-23`). |
| `GET` | `/predictions/{week_start}` | Specific Monday recommendations | Returns 15 ranked predictions for a competition Monday (e.g. `2026-02-02`). |
| `GET` | `/gateways/{gateway_id}/explanation` | *"ask it why a particular gateway is where it is"* | Returns rank, score, breach count, and observational reason for a gateway. |
| `GET` | `/gateways/{gateway_id}` | Fleet Asset Inspection | Master asset metadata and lifecycle eligibility status at date $T$. |
| `POST` | `/run` | *"tell it to run again"* | Dynamically reloads mounted data partitions and recomputes recommendations. |
| `GET` | `/docs` | Self-Documenting Interface | Interactive OpenAPI / Swagger UI documentation. |

### API Quick-Start Cheat Sheet (`curl`)

```bash
# 1. Check health
curl http://127.0.0.1:8000/health

# 2. Ask for this week's 15 gateways
curl http://127.0.0.1:8000/predictions

# 3. Ask for a specific Monday's 15 gateways
curl http://127.0.0.1:8000/predictions/2026-02-02

# 4. Ask why a particular gateway is where it is
curl "http://127.0.0.1:8000/gateways/0A2778A31BE3/explanation?week_start=2026-02-02"

# 5. Tell it to run again (reloading dynamic data partitions)
curl -X POST http://127.0.0.1:8000/run \
     -H "Content-Type: application/json" \
     -d '{"week_start": "2026-02-02"}'
```

### Web Demonstration Client (HTML/CSS/Vanilla JS)
A zero-dependency, browser-based demonstration client is served directly by the backend:
1. Start the API (`make api` or `uvicorn nexora.api:app --host 0.0.0.0 --port 8000`).
2. Open your browser directly to:
   ```
   http://127.0.0.1:8000
   ```
   FastAPI automatically mounts and serves the evaluator interface at `/`, enabling live health checks, interactive week selection, Top-15 table rendering, and raw API payload inspection.

---

## 10. Automated Test Suite

The repository features comprehensive regression protection with **186 automated tests across 16 test files**:

```bash
pytest -v
# or via Makefile:
make test
```

Expected output:
```
186 passed in ~55s
```

### Test Suite Structure
- `tests/test_bug_regression.py`: **Dedicated bug regression suite** fulfilling the brief requirement: *"Include one test you wrote because you found a bug."* Tests duplicate scored records rejection, FastAPI lifespan state initialization, reason length limits, synthetic mock gateway ID uniqueness, and API feature contracts.
- `tests/test_data_contracts.py`: **Data contract suite** verifying fail-fast validation for missing columns, malformed/null IDs, integer counts, negative counts, `meters_read <= meters_expected`, conflicting duplicates, lifecycle chronology, and temporal anti-leakage.
- `tests/test_api.py`: FastAPI endpoints, parameter validation, dataset isolation, and bitwise parity against `predict_week`.
- `tests/test_api_errors.py`: HTTP error status codes (`400`, `404`, `405`) and host path sanitization.
- `tests/test_api_live_hardening.py`: Unseen month live evaluation workflow, state reload isolation, and concurrency locks.
- `tests/test_strategy_abstraction.py`: Swappable ranking strategy interface (`PredictionStrategy`) and dynamic replacement.
- `tests/test_strategy_integrity.py`: Approved distress signal metrics set and unweighted breach accumulation.
- `tests/test_data_loader.py`: Telemetry parquet loading, Latin-1 parsing, identical duplicate collapsing, conflicting duplicate detection.
- `tests/test_eligibility.py`: Active lifecycle boundary evaluation (`installed_on <= T < decommissioned_on`).
- `tests/test_scoring.py`: 3-sigma anomaly thresholding, sample standard deviation ($ddof=1$), zero-variance handling.
- `tests/test_ranking.py`: Deterministic tie-breaking (score desc, gateway_id asc), Option B retention.
- `tests/test_reasons.py`: Observational reason format and `<= 300` character contract.
- `tests/test_pipeline_regression.py`: End-to-end multi-week pipeline validation and bitwise determinism.
- `tests/test_error_handling.py`: Boundary conditions, empty datasets, invalid types.
- `tests/test_normalization.py`: Canonical 12-char hex identifier normalization.
- `tests/test_research_backtesting.py`: Validation of field visits, engineer review ground truth contracts, and historical backtesting.

---

## 11. Expected Output & Verified Checksum

- **File:** `predictions.csv`
- **Total Rows:** Exactly 120 rows (8 weeks × 15 gateways).
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
