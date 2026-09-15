/**
 * NEXORA 2026 — Predictive Maintenance Client Application
 * Vanilla JavaScript (Zero external libraries or frameworks)
 *
 * Calls the production FastAPI service to display deterministic
 * Baseline_3Sigma recommendations for the 8 scored competition weeks.
 */

// =============================================================================
// API Configuration
// =============================================================================

const API_BASE_URL =
  typeof window !== "undefined" && window.location && window.location.port === "8000"
    ? window.location.origin
    : "http://localhost:8000";

/** Request timeout in milliseconds */
const REQUEST_TIMEOUT_MS = 10000;

// =============================================================================
// DOM Elements Cache
// =============================================================================

const DOM = {
  // Status
  statusBadge: document.getElementById("apiStatusBadge"),
  statusText: document.getElementById("apiStatusText"),

  // Controls
  weekSelect: document.getElementById("weekSelect"),
  generateBtn: document.getElementById("generateBtn"),
  runAgainBtn: document.getElementById("runAgainBtn"),

  // Banners & Inspection
  reloadBanner: document.getElementById("reloadBanner"),
  reloadBannerDesc: document.getElementById("reloadBannerDesc"),
  explanationCard: document.getElementById("explanationCard"),
  explainGatewayId: document.getElementById("explainGatewayId"),
  explainRank: document.getElementById("explainRank"),
  explainScore: document.getElementById("explainScore"),
  explainSelected: document.getElementById("explainSelected"),
  explainReason: document.getElementById("explainReason"),
  closeExplainBtn: document.getElementById("closeExplainBtn"),

  // Results & States
  resultsMeta: document.getElementById("resultsMeta"),
  emptyState: document.getElementById("emptyState"),
  loadingState: document.getElementById("loadingState"),
  errorState: document.getElementById("errorState"),
  errorBadge: document.getElementById("errorBadge"),
  errorStatus: document.getElementById("errorStatus"),
  errorMessage: document.getElementById("errorMessage"),
  errorDetail: document.getElementById("errorDetail"),

  // Table
  tableContainer: document.getElementById("tableContainer"),
  recommendationsBody: document.getElementById("recommendationsBody"),

  // Raw Response
  rawDetails: document.getElementById("rawDetails"),
  rawResponseCode: document.getElementById("rawResponseCode"),
};

// =============================================================================
// State Management Helpers
// =============================================================================

/**
 * Updates the API health status indicator in the header.
 * @param {"online" | "offline" | "checking"} state
 */
function setApiStatus(state) {
  if (!DOM.statusBadge || !DOM.statusText) return;

  DOM.statusBadge.classList.remove("online", "offline", "checking");
  DOM.statusBadge.classList.add(state);

  switch (state) {
    case "online":
      DOM.statusText.textContent = "API ONLINE";
      break;
    case "offline":
      DOM.statusText.textContent = "API OFFLINE";
      break;
    case "checking":
    default:
      DOM.statusText.textContent = "CHECKING";
      break;
  }
}

/**
 * Updates button labels and interactive state.
 * @param {"idle" | "loading" | "retry"} state
 */
function setButtonState(state) {
  if (!DOM.generateBtn) return;

  DOM.generateBtn.classList.remove("btn-retry");

  switch (state) {
    case "loading":
      DOM.generateBtn.disabled = true;
      DOM.generateBtn.textContent = "Loading...";
      if (DOM.runAgainBtn) DOM.runAgainBtn.disabled = true;
      break;
    case "retry":
      DOM.generateBtn.disabled = false;
      DOM.generateBtn.textContent = "Retry";
      DOM.generateBtn.classList.add("btn-retry");
      if (DOM.runAgainBtn) DOM.runAgainBtn.disabled = false;
      break;
    case "idle":
    default:
      DOM.generateBtn.disabled = false;
      DOM.generateBtn.textContent = "Generate Recommendations";
      if (DOM.runAgainBtn) DOM.runAgainBtn.disabled = false;
      break;
  }
}

/**
 * Switches between the four exclusive UI states.
 * @param {"empty" | "loading" | "error" | "table"} activeState
 */
function switchUiState(activeState) {
  DOM.emptyState.classList.add("is-hidden");
  DOM.loadingState.classList.add("is-hidden");
  DOM.errorState.classList.add("is-hidden");
  DOM.tableContainer.classList.add("is-hidden");

  switch (activeState) {
    case "loading":
      DOM.loadingState.classList.remove("is-hidden");
      break;
    case "error":
      DOM.errorState.classList.remove("is-hidden");
      break;
    case "table":
      DOM.tableContainer.classList.remove("is-hidden");
      break;
    case "empty":
    default:
      DOM.emptyState.classList.remove("is-hidden");
      break;
  }
}

/**
 * Formats and renders raw JSON into the collapsible inspection panel.
 * @param {any} data
 */
function setRawResponse(data) {
  if (!DOM.rawResponseCode) return;
  try {
    DOM.rawResponseCode.textContent = JSON.stringify(data, null, 2);
  } catch {
    DOM.rawResponseCode.textContent = String(data);
  }
}

// =============================================================================
// API Service Calls
// =============================================================================

/**
 * Performs a fetch request with an enforced timeout.
 * @param {string} url
 * @param {RequestInit} [options]
 * @returns {Promise<Response>}
 */
async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    return response;
  } finally {
    clearTimeout(timeoutId);
  }
}

/**
 * Probes the backend /health endpoint.
 * Returns true if online, false otherwise.
 */
async function checkApiHealth() {
  try {
    const res = await fetchWithTimeout(`${API_BASE_URL}/health`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (res.ok) {
      const body = await res.json().catch(() => ({}));
      if (body.status === "ok") {
        setApiStatus("online");
        return true;
      }
    }
    setApiStatus("offline");
    return false;
  } catch (err) {
    setApiStatus("offline");
    return false;
  }
}

/**
 * Fetches the Top-15 recommendations from FastAPI for a specific Monday.
 * @param {string} weekStart ISO date string (YYYY-MM-DD)
 * @returns {Promise<{ ok: boolean, status: number, data: any, errorText?: string }>}
 */
async function fetchPredictions(weekStart) {
  const endpoint = `${API_BASE_URL}/predictions/${encodeURIComponent(weekStart)}`;

  try {
    const res = await fetchWithTimeout(endpoint, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    const json = await res.json().catch(() => null);

    if (res.ok && json) {
      return { ok: true, status: res.status, data: json };
    }

    // Backend returned an error response (400, 404, 422, 500)
    let detail = "An unexpected error occurred while generating recommendations.";
    if (json && json.detail) {
      if (typeof json.detail === "string") {
        detail = json.detail;
      } else if (Array.isArray(json.detail)) {
        detail = json.detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
      }
    }

    return {
      ok: false,
      status: res.status,
      data: json || { status: res.status, statusText: res.statusText },
      errorText: detail,
    };
  } catch (err) {
    // Network failure, DNS error, or timeout
    const isTimeout = err.name === "AbortError";
    const errorText = isTimeout
      ? `Request timed out after ${REQUEST_TIMEOUT_MS / 1000} seconds.`
      : `Unable to reach NEXORA API at ${API_BASE_URL}. Ensure the service is running.`;

    return {
      ok: false,
      status: 0,
      data: {
        error: isTimeout ? "TimeoutError" : "NetworkError",
        message: errorText,
        targetUrl: endpoint,
      },
      errorText,
    };
  }
}

/**
 * Executes POST /run on the production FastAPI backend.
 * Reloads mounted data partitions from disk and recomputes recommendations.
 * @param {string} weekStart ISO Monday date (YYYY-MM-DD)
 * @returns {Promise<{ ok: boolean, status: number, data: any, errorText?: string }>}
 */
async function postRunPrediction(weekStart) {
  const endpoint = `${API_BASE_URL}/run`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const res = await fetch(endpoint, {
      method: "POST",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ week_start: weekStart }),
    });

    clearTimeout(timeoutId);
    const json = await res.json().catch(() => null);

    if (res.ok && json) {
      return { ok: true, status: res.status, data: json };
    }

    let detail = "An unexpected error occurred while executing POST /run.";
    if (json && json.detail) {
      if (typeof json.detail === "string") {
        detail = json.detail;
      } else if (Array.isArray(json.detail)) {
        detail = json.detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
      }
    }

    return {
      ok: false,
      status: res.status,
      data: json || { status: res.status, statusText: res.statusText },
      errorText: detail,
    };
  } catch (err) {
    clearTimeout(timeoutId);
    const isTimeout = err.name === "AbortError";
    const errorText = isTimeout
      ? `POST /run timed out after ${REQUEST_TIMEOUT_MS / 1000} seconds.`
      : `Unable to reach NEXORA API at ${API_BASE_URL}. Ensure the service is running.`;

    return {
      ok: false,
      status: 0,
      data: {
        error: isTimeout ? "TimeoutError" : "NetworkError",
        message: errorText,
        targetUrl: endpoint,
      },
      errorText,
    };
  }
}

// =============================================================================
// Rendering Engine
// =============================================================================

/**
 * Populates the recommendations table with exact API response records.
 * Uses safe DOM text nodes to prevent XSS and preserve exact reason strings.
 * @param {Array<{ rank: number, gateway_id: string, score: number, reason: string }>} predictions
 */
function renderRecommendationsTable(predictions) {
  if (!DOM.recommendationsBody) return;

  // Clear existing rows
  DOM.recommendationsBody.innerHTML = "";

  predictions.forEach((row) => {
    const tr = document.createElement("tr");

    // 1. Rank
    const tdRank = document.createElement("td");
    tdRank.className = "td-rank";
    tdRank.textContent = String(row.rank);
    tr.appendChild(tdRank);

    // 2. Gateway ID
    const tdGateway = document.createElement("td");
    tdGateway.className = "td-gateway";
    tdGateway.textContent = String(row.gateway_id);
    tr.appendChild(tdGateway);

    // 3. Score
    const tdScore = document.createElement("td");
    tdScore.className = "td-score";
    tdScore.textContent = Number(row.score).toFixed(1);
    tr.appendChild(tdScore);

    // 4. Reason (Preserved exactly as returned by API)
    const tdReason = document.createElement("td");
    tdReason.className = "td-reason";
    tdReason.textContent = String(row.reason);
    tr.appendChild(tdReason);

    // 5. Inspect / Explain Action
    const tdAction = document.createElement("td");
    tdAction.className = "td-action";
    const inspectBtn = document.createElement("button");
    inspectBtn.type = "button";
    inspectBtn.className = "btn-inspect";
    inspectBtn.textContent = "Explain";
    inspectBtn.title = `Explain why gateway ${row.gateway_id} was selected`;
    inspectBtn.addEventListener("click", () => handleInspectClick(row.gateway_id));
    tdAction.appendChild(inspectBtn);
    tr.appendChild(tdAction);

    DOM.recommendationsBody.appendChild(tr);
  });
}

/**
 * Queries GET /gateways/{id}/explanation and populates the inspection card.
 * @param {string} gatewayId
 */
async function handleInspectClick(gatewayId) {
  const selectedWeek = DOM.weekSelect && DOM.weekSelect.value ? DOM.weekSelect.value : "2026-02-02";
  const endpoint = `${API_BASE_URL}/gateways/${encodeURIComponent(gatewayId)}/explanation?week_start=${encodeURIComponent(selectedWeek)}`;

  try {
    const res = await fetch(endpoint);
    const data = await res.json();
    if (res.ok && data) {
      if (DOM.explainGatewayId) DOM.explainGatewayId.textContent = data.gateway_id;
      if (DOM.explainRank) DOM.explainRank.textContent = data.rank !== null ? `#${data.rank}` : "Unranked";
      if (DOM.explainScore) DOM.explainScore.textContent = data.score !== null ? Number(data.score).toFixed(1) : "0.0";
      if (DOM.explainSelected) DOM.explainSelected.textContent = data.selected ? "YES (Top 15)" : "NO";
      if (DOM.explainReason) DOM.explainReason.textContent = data.reason || "No explanation provided.";
      if (DOM.explanationCard) DOM.explanationCard.classList.remove("is-hidden");
      DOM.explanationCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  } catch (err) {
    console.error("Failed to fetch gateway explanation:", err);
  }
}

/**
 * Handles the "Generate Recommendations" button click workflow (GET /predictions/{week}).
 */
async function handleGenerateClick() {
  const selectedWeek = DOM.weekSelect ? DOM.weekSelect.value : "";

  if (!selectedWeek) {
    switchUiState("empty");
    if (DOM.weekSelect) {
      DOM.weekSelect.focus();
    }
    return;
  }

  if (DOM.reloadBanner) DOM.reloadBanner.classList.add("is-hidden");
  if (DOM.explanationCard) DOM.explanationCard.classList.add("is-hidden");

  // Set UI to loading state
  setButtonState("loading");
  switchUiState("loading");
  if (DOM.resultsMeta) DOM.resultsMeta.textContent = "";

  // Call API
  const result = await fetchPredictions(selectedWeek);

  // Update raw response panel regardless of outcome
  setRawResponse(result.data);

  if (result.ok && result.data && Array.isArray(result.data.predictions)) {
    // Successfully received predictions
    setApiStatus("online");
    renderRecommendationsTable(result.data.predictions);

    if (DOM.resultsMeta) {
      DOM.resultsMeta.textContent = `Week: ${result.data.week_start} • ${result.data.count} Gateways Ranked`;
    }

    switchUiState("table");
    setButtonState("idle");
  } else {
    // Failure handling (HTTP error or network failure)
    if (result.status === 0) {
      setApiStatus("offline");
      if (DOM.errorBadge) DOM.errorBadge.textContent = "Network Error";
      if (DOM.errorStatus) DOM.errorStatus.textContent = "Connection Refused";
      if (DOM.errorMessage) DOM.errorMessage.textContent = result.errorText;
      if (DOM.errorDetail) {
        DOM.errorDetail.textContent =
          "Verify the backend server is running: uvicorn nexora.api:app --host 0.0.0.0 --port 8000";
      }
    } else {
      if (DOM.errorBadge) DOM.errorBadge.textContent = `HTTP ${result.status}`;
      if (DOM.errorStatus) DOM.errorStatus.textContent = `Status ${result.status}`;
      if (DOM.errorMessage) DOM.errorMessage.textContent = result.errorText;
      if (DOM.errorDetail) {
        DOM.errorDetail.textContent =
          "The API rejected the request. Supported evaluation dates are the 8 scored competition Mondays.";
      }
    }

    switchUiState("error");
    setButtonState("retry");
  }
}

/**
 * Handles the "Run Again (POST /run)" button click workflow.
 * Triggers backend partition reloading from disk and fresh recommendation calculation.
 */
async function handleRunAgainClick() {
  const selectedWeek = DOM.weekSelect && DOM.weekSelect.value ? DOM.weekSelect.value : "2026-02-02";

  if (DOM.reloadBanner) DOM.reloadBanner.classList.add("is-hidden");
  if (DOM.explanationCard) DOM.explanationCard.classList.add("is-hidden");

  setButtonState("loading");
  switchUiState("loading");
  if (DOM.resultsMeta) DOM.resultsMeta.textContent = "";

  const result = await postRunPrediction(selectedWeek);
  setRawResponse(result.data);

  if (result.ok && result.data && Array.isArray(result.data.predictions)) {
    setApiStatus("online");
    renderRecommendationsTable(result.data.predictions);

    if (DOM.resultsMeta) {
      DOM.resultsMeta.textContent = `Week: ${result.data.week_start} • ${result.data.count} Gateways Ranked (Live POST /run Reload)`;
    }

    if (DOM.reloadBanner) {
      if (DOM.reloadBannerDesc) {
        DOM.reloadBannerDesc.textContent = `Data partitions reloaded from mounted volume; fresh recommendations computed for ${result.data.week_start}.`;
      }
      DOM.reloadBanner.classList.remove("is-hidden");
    }

    switchUiState("table");
    setButtonState("idle");
  } else {
    if (result.status === 0) {
      setApiStatus("offline");
      if (DOM.errorBadge) DOM.errorBadge.textContent = "Network Error";
      if (DOM.errorStatus) DOM.errorStatus.textContent = "Connection Refused";
      if (DOM.errorMessage) DOM.errorMessage.textContent = result.errorText;
      if (DOM.errorDetail) {
        DOM.errorDetail.textContent =
          "Verify the backend server is running: uvicorn nexora.api:app --host 0.0.0.0 --port 8000";
      }
    } else {
      if (DOM.errorBadge) DOM.errorBadge.textContent = `HTTP ${result.status}`;
      if (DOM.errorStatus) DOM.errorStatus.textContent = `Status ${result.status}`;
      if (DOM.errorMessage) DOM.errorMessage.textContent = result.errorText;
      if (DOM.errorDetail) {
        DOM.errorDetail.textContent =
          "POST /run failed. Check server logs or request payload.";
      }
    }

    switchUiState("error");
    setButtonState("retry");
  }
}

// =============================================================================
// Application Initialization
// =============================================================================

document.addEventListener("DOMContentLoaded", () => {
  // 1. Initial health check
  setApiStatus("checking");
  checkApiHealth();

  // 2. Periodic background health poll every 20 seconds
  setInterval(checkApiHealth, 20000);

  // 3. Event Listeners
  if (DOM.generateBtn) {
    DOM.generateBtn.addEventListener("click", handleGenerateClick);
  }

  if (DOM.runAgainBtn) {
    DOM.runAgainBtn.addEventListener("click", handleRunAgainClick);
  }

  if (DOM.closeExplainBtn) {
    DOM.closeExplainBtn.addEventListener("click", () => {
      if (DOM.explanationCard) DOM.explanationCard.classList.add("is-hidden");
    });
  }

  if (DOM.weekSelect) {
    DOM.weekSelect.addEventListener("change", () => {
      // If user changes week while in retry state, reset button to standard idle
      if (DOM.generateBtn && DOM.generateBtn.classList.contains("btn-retry")) {
        setButtonState("idle");
      }
    });
  }
});
