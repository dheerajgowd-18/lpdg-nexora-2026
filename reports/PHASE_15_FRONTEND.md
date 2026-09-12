# Phase 15 — Frontend Demonstration Client

**LPDG Innovation Hub Selection Challenge 2026 (NEXORA 2026)**  
**Document Type:** Frontend Client Architecture & Verification Report  
**Audience:** Technical Reviewers, Evaluators, and Engineering Leadership  
**Status:** COMPLETE — ALL VERIFICATIONS PASSED  

---

## 1. Status & Overview

**PASS**

Phase 15 (Frontend Demonstration Client) has been implemented and verified. A minimal, dependency-free, and evaluator-friendly client application has been built using **pure HTML, CSS, and Vanilla JavaScript** (`frontend/index.html`, `frontend/style.css`, `frontend/app.js`).

The frontend acts exclusively as a lightweight presentation layer that consumes the production FastAPI service. It contains zero duplicated scoring, ranking, eligibility, tie-breaking, or prediction logic. The backend remains the single authoritative source of truth.

---

## 2. Purpose of the Frontend

The frontend provides an interactive, evaluator-ready interface for demonstrating the live capabilities of the NEXORA Part 2 REST API:
1. **Real-Time API Health Monitoring:** Automatically probes `/health` upon page load and every 20 seconds, displaying live `API ONLINE` / `API OFFLINE` / `CHECKING` indicators.
2. **Weekly Anomaly Generation:** Allows evaluators to select any of the 8 authoritative competition decision Mondays (`2026-02-02` through `2026-03-23`) and trigger live execution.
3. **Structured Recommendations Presentation:** Renders the Top 15 ranked gateways with Rank (1–15), canonical 12-character hexadecimal Gateway ID, Baseline_3Sigma score, and unmanipulated observational reason strings.
4. **Transparent Verification:** Provides a collapsible "View API Response" inspection panel displaying the raw JSON payload returned by FastAPI, proving that data originates directly from the backend rather than static client-side fixtures.
5. **Defensive Error Handling:** Surfaces structured HTTP error details (400, 404, 422, 500) and connection timeouts/failures cleanly without crashing or exposing stack traces.

---

## 3. Technology Constraint Adherence

In strict compliance with instructions, the frontend uses **zero external dependencies**:
- **No Node.js frontend tooling:** No npm, yarn, pnpm, or bun packages.
- **No Build Step:** No Vite, Webpack, Rollup, Parcel, or Babel.
- **No JS Frameworks:** No React, Vue, Angular, Svelte, or Solid.
- **No CSS Frameworks:** No Tailwind, Bootstrap, Bulma, or Material UI.
- **Pure Web Standards:** Standard W3C HTML5 semantics, CSS3 Flexbox/Grid, and modern ES2020+ Vanilla JavaScript with native `fetch()`.

---

## 4. Architecture & Component Interaction

```
   ┌────────────────────────────────────────────────────────────┐
   │                     Web Browser Window                     │
   │                                                            │
   │  ┌──────────────────────────────────────────────────────┐  │
   │  │             frontend/index.html (DOM)                │  │
   │  │  - Header & Status Badge (Online/Offline/Checking)   │  │
   │  │  - Control Panel (8-Monday Select Dropdown)          │  │
   │  │  - Results State Container (Empty/Loading/Error/Table│  │
   │  │  - Raw API JSON Inspector (<details>/<pre><code>)    │  │
   │  │  - Engineering Attribution Footer                    │  │
   │  └──────────────────────────┬───────────────────────────┘  │
   │                             │ DOM Events / Rendering       │
   │  ┌──────────────────────────▼───────────────────────────┐  │
   │  │              frontend/app.js (Client)                │  │
   │  │  - checkApiHealth(): Probes /health                  │  │
   │  │  - fetchPredictions(week): Calls /predictions/{week} │  │
   │  │  - renderRecommendationsTable(): Populates DOM table │  │
   │  │  - setRawResponse(): Injects unmanipulated JSON      │  │
   │  └──────────────────────────┬───────────────────────────┘  │
   └─────────────────────────────┼──────────────────────────────┘
                                 │
                   HTTP REST API │ Native fetch()
                   (Port 8000)   │ (CORS Enabled)
                                 ▼
   ┌────────────────────────────────────────────────────────────┐
   │            NEXORA FastAPI Service (src/nexora/api.py)      │
   │                                                            │
   │  - GET  /health ──► Status 200 {"status": "ok"}            │
   │  - GET  /predictions/{week_start}                          │
   │          │                                                 │
   │          ▼                                                 │
   │    predict_week() (src/nexora/pipeline.py)                 │
   │      - get_eligible_gateways() (Lifecycle active fleet)   │
   │      - score_week() (Baseline_3Sigma 3-metric accumulator) │
   │      - rank_and_select() (Option B silent fleet retention) │
   │      - add_reasons() (Observational non-causal reason)     │
   └────────────────────────────────────────────────────────────┘
```

---

## 5. Actual API Endpoints & Contracts Used

The client communicates exclusively with the existing, verified FastAPI routes in `src/nexora/api.py`:

### 1. Health Probe
- **Method:** `GET`
- **Route:** `/health`
- **Response Schema:**
  ```json
  {
    "status": "ok"
  }
  ```
- **Usage:** Validates service connectivity on page load and every 20-second polling interval.

### 2. Weekly Recommendations
- **Method:** `GET`
- **Route:** `/predictions/{week_start}`
- **Parameters:** `week_start` (Path parameter, string, ISO format `YYYY-MM-DD`).
- **Response Schema (`PredictionResponse`):**
  ```json
  {
    "week_start": "2026-02-02",
    "count": 15,
    "predictions": [
      {
        "week_start": "2026-02-02",
        "rank": 1,
        "gateway_id": "0A2778A31BE3",
        "score": 43.0,
        "reason": "43 individual 3-sigma metric breach(es) against this gateway's own 28-day baseline in the last 7 days; first breach on disconnection_cnt"
      }
    ]
  }
  ```
- **Error Responses:**
  - `400 Bad Request`: When `week_start` is malformed.
  - `404 Not Found`: When `week_start` is not one of the 8 scored competition Mondays.

---

## 6. Request / Response Lifecycle

1. **User Selection:** Evaluator selects a decision Monday from the dropdown (e.g., `2026-02-02 (Week 1)`).
2. **Execution Trigger:** User clicks "Generate Recommendations".
3. **UI Transition:** Button changes to "Loading..." (disabled); UI transitions to the loading spinner state ("Generating recommendations...").
4. **Asynchronous Dispatch:** Native `fetch()` calls `GET http://localhost:8000/predictions/2026-02-02` with an enforced 10-second timeout.
5. **Data Ingestion:**
   - On `200 OK`: JSON payload is parsed. Exactly 15 predictions are rendered into the table. The raw JSON is populated in the `<details>` inspector. Button returns to "Generate Recommendations" (enabled).
   - On `HTTP Error` (e.g. 404): Error status and backend `detail` string are extracted and displayed in the alert card. Raw error JSON is shown in the inspector. Button transitions to "Retry" (enabled).
   - On `Network Failure` (server stopped): Connection error is captured; API status indicator switches to `API OFFLINE`. Clean instructions to start Uvicorn are presented. Button transitions to "Retry".

---

## 7. Files Created & Modified

### Created Files
| File Path | Size | Description |
| :--- | :--- | :--- |
| `frontend/index.html` | 5.2 KB | Semantic HTML5 structure with header, status badge, control panel, 4 UI states, raw JSON inspector, and engineering footer. |
| `frontend/style.css` | 8.8 KB | Minimal premium technical interface stylesheet. Clean typography, slate color palette, subtle borders, responsive flex/grid layouts. |
| `frontend/app.js` | 9.4 KB | Vanilla JavaScript client module. Manages health polling, fetch requests, DOM rendering, error states, and JSON inspection. |
| `reports/PHASE_15_FRONTEND.md` | ~12 KB | Comprehensive Phase 15 architecture, verification, and audit documentation. |

### Modified Files
| File Path | Description | Rationale |
| :--- | :--- | :--- |
| `src/nexora/api.py` | Added `CORSMiddleware` and mounted `frontend/` static interface at root `/` in `create_app()`. | Allows local browser clients to communicate without CORS rejection, and enables immediate browser access directly at `http://127.0.0.1:8000` without requiring a separate web server. Zero scoring/ranking logic altered. |
| `frontend/app.js` | Configured dynamic `API_BASE_URL` origin detection for port 8000. | Seamlessly targets `window.location.origin` when loaded from FastAPI port 8000, while falling back to `http://localhost:8000` when served via a separate port. |
| `README.md` | Added `frontend/` to repository directory tree and added Web Demonstration Client instructions in Section 9. | Provides clear instructions for evaluators to open the frontend demonstration directly or via a static server. |

---

## 8. How to Run the Frontend

### Option A: Direct Access via FastAPI (Recommended)
1. In the project root, start the API service:
   ```bash
   uvicorn nexora.api:app --host 0.0.0.0 --port 8000
   ```
2. Open your browser directly to:
   ```
   http://127.0.0.1:8000
   ```
   FastAPI automatically serves `frontend/index.html` at `/`, and the client connects directly to the co-hosted prediction engine.

### Option B: Separate Static Web Server
1. Start the API service:
   ```bash
   uvicorn nexora.api:app --host 0.0.0.0 --port 8000
   ```
2. In a second terminal, serve the static frontend:
   ```bash
   python -m http.server 3000 --directory frontend
   ```
3. Open `http://localhost:3000` in your web browser. CORS middleware enables cross-origin communication with port 8000.

---

## 9. Verification Performed

The implementation was subjected to comprehensive automated and manual verification:

### 1. Automated Health & CORS Header Probe
- Probed `http://127.0.0.1:8000/health` with simulated browser `Origin: http://localhost:3000`.
- **Status:** `200 OK`
- **Body:** `{"status": "ok"}`
- **Header:** `Access-Control-Allow-Origin: *` (PASS).

### 2. Automated Prediction Endpoint Execution
- Requested `http://127.0.0.1:8000/predictions/2026-02-02`.
- **Status:** `200 OK`
- **Row Count:** Exactly 15 recommendations.
- **Rank 1 Gateway:** `0A2778A31BE3`, Score: `43.0`.
- **Reason:** Exact string match with production baseline.

### 3. Automated Error Handling & Rejection Test
- Requested `http://127.0.0.1:8000/predictions/2026-01-05` (un-scored Monday).
- **Status:** `404 Not Found`
- **Error Detail:** `Unsupported week_start: 2026-01-05. Must be one of the 8 scored competition Mondays...` (Cleanly captured by frontend without runtime crashes).

### 4. DOM Identifier & Structural Alignment
- Executed automated AST / HTML parser check verifying that all 16 `document.getElementById` targets in `frontend/app.js` exist in `frontend/index.html`.
- Verified that all 8 `<option>` values in the dropdown match `config.SCORED_WEEKS` exactly.
- Verified syntax integrity with `node -c frontend/app.js` (Zero errors).

### 5. Official Submission Integrity
- Executed `python validate_submission.py predictions.csv`:
  ```
  predictions.csv: OK
    15 ranked gateways for each of 8 weeks, 2026-02-02 to 2026-03-23
  ```
- Checked SHA-256 hash:
  `ec8489c8d9b4e64feb6ecc0635e6e32c77e1945818ffbb68ff8fe3bc7f415145` (100% Bitwise Match).

### 6. Full Automated Regression Test Suite
- Executed `pytest -q`:
  ```
  123 passed in 13.96s
  ```
- All 123 tests across 11 test modules passed with zero regressions.

---

## 10. Confirmation of Unchanged Prediction Logic

The following core invariant properties remain **strictly preserved and unchanged**:
1. **Mathematical Scoring Formulation:** Unweighted accumulation of discrete hourly breaches where metric strictly exceeds $\mu + 3\sigma$ ($ddof=1$) over trailing 28 days $[T-28\text{d}, T)$ evaluated over trailing 7 days $[T-7\text{d}, T)$.
2. **Approved Metric Set:** Exclusively `offline_duration_sec`, `disconnection_cnt`, and `reboot_cnt`.
3. **Option B Silent Gateway Policy:** Commissioned gateways with zero recent telemetry retain score `0.0`, `flagged_hours = 0`, and `worst_metric = "no_telemetry"`.
4. **Deterministic Ranking & Tie-Breaking:** `score` descending, then `gateway_id` canonical hex ascending.
5. **Zero Client-Side Computation:** The browser JavaScript calculates zero scores, computes zero means or standard deviations, and modifies zero prediction records.
6. **Submission Checksum Parity:** `predictions.csv` has not been altered or regenerated.

---

## 11. Final Verdict

**PHASE 15 FRONTEND DEMONSTRATION CLIENT COMPLETE, VERIFIED, AND APPROVED.**
