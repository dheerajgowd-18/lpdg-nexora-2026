# AI Usage Disclosure

**Project:** NEXORA 2026 — LPDG Innovation Hub Selection Challenge  
**Requirement Source:** Challenge Brief Section "Part 1 — the basics", Item 5  

---

## 1. What AI Tools Were Used For

During the engineering of NEXORA 2026, AI coding assistants (Google Antigravity / Gemini) were utilized to accelerate development in specific, controlled tasks:
1. **Test Suite Generation:** Authoring boilerplate test fixtures and parameterized test matrices (e.g. testing combinations of malformed gateway IDs, edge-case date formats, and schema deviations in `tests/test_api_errors.py` and `tests/test_error_handling.py`).
2. **FastAPI Boilerplate & Pydantic Schemas:** Generating standard REST API boilerplate, Pydantic response models, and OpenAPI docstrings in `src/nexora/api.py`.
3. **Drafting Documentation & Phase Reports:** Structuring markdown templates and summarizing test execution telemetry into formal engineering records.
4. **Shell & Process Automation:** Formulating cross-platform PowerShell and Python subprocess scripts for clean-snapshot reproducibility testing.

---

## 2. What AI Tools Were NOT Used For

All core architectural decisions, strategy selections, and verification gates were governed strictly by human engineering analysis:
- **Operational Decision Making:** The decision to lock `Baseline_3Sigma` over multi-feature ML candidates was driven by human evaluation of the €380 false alarm vs €600 missed repair penalty trade-offs in 26 weeks of historical backtesting.
- **Contract Integrity:** The definition of the Option B silent-gateway policy, 28-day baseline window, sample variance ($ddof=1$), and strict temporal right-open cutoff ($ts < T$) was established by the engineering team.
- **Verification Authority:** Every test execution, official validator run, SHA-256 checksum, and DataFrame bitwise comparison was verified independently against the authoritative dataset.

---

## 3. Concrete Errors Made by AI Tools That Were Caught and Corrected

During development, AI assistants produced specific technical and contractual errors that required human intervention:

### Error 1: Silent Masking of Duplicate Scored Records (Phase 12)
- **What the AI Did:** When asked to harden `ranking.py` against duplicate records, the AI assistant implemented a silent deduplication fallback:
  ```python
  # AI-generated implementation:
  valid_scores = (
      scored_df[scored_df["gateway_id"].isin(eligible_set)]
      .drop_duplicates(subset=["gateway_id"], keep="first")
      .copy()
  )
  ```
- **Why It Was Wrong:** Silently selecting the first or highest score violates production safety standards. If upstream telemetry scoring produces duplicate scored records for the same gateway ID, it indicates an upstream pipeline corruption. Silently picking one masks the defect.
- **The Correction:** The engineering team rejected the silent deduplication and enforced an explicit fail-fast exception:
  ```python
  # Corrected production rule:
  if scored_df["gateway_id"].duplicated().any():
      dups = scored_df.loc[scored_df["gateway_id"].duplicated(), "gateway_id"].unique()
      raise ValueError(f"Duplicate scored records detected for gateway(s): {list(dups)}")
  ```
  A regression test (`test_duplicate_scored_records_raises_valueerror`) was added to permanently protect this invariant.

### Error 2: Inventing an Undocumented Reason String for Silent Gateways (Phase 12)
- **What the AI Did:** In drafting the Phase 12 documentation, the AI assistant documented that silent gateways receive an observational reason of:
  `"No telemetry received in recent 7d window."`
- **Why It Was Wrong:** The production reason contract frozen in Phase 8 and locked across Phases 9–11 specifies that all gateways with $score = 0.0$ (including silent gateways retained under Option B) must use the exact frozen template:
  `"0 individual 3-sigma metric breaches against this gateway's own 28-day baseline in the last 7 days"`.
  Changing this reason would introduce contract drift and cause submission discrepancies.
- **The Correction:** The engineering team identified the documentation divergence, verified that the underlying production code in `reasons.py` remained untouched, and corrected the report to adhere strictly to the frozen reason contract.

### Error 3: Testing Clean Checkout Against Committed HEAD Instead of Current Working Tree (Phase 13)
- **What the AI Did:** In Phase 13, the AI assistant automated a clean-checkout reproducibility test using:
  `git archive HEAD`
- **Why It Was Wrong:** Because Phases 10–13 enhancements (FastAPI, centralized config, error hardening) remained uncommitted in accordance with the strict "DO NOT COMMIT" protocol, archiving `HEAD` tested the Phase 9 baseline rather than the current working tree.
- **The Correction:** The engineering team flagged the reproducibility gap. We constructed a true clean-snapshot test harness that exported the complete current working tree (including uncommitted code, tests, and packaging) into an isolated directory, built a fresh virtual environment from scratch, ran the pipeline, and verified bitwise equality (`assert_frame_equal`) and SHA-256 identity (`ec8489c8d9b4e64feb6ecc0635e6e32c77e1945818ffbb68ff8fe3bc7f415145`).
