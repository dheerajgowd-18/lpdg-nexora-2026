# =============================================================================
# NEXORA 2026 — Makefile
# LPDG Innovation Hub Selection Challenge 2026
# =============================================================================

.PHONY: run test api validate clean help

help:
	@echo "NEXORA 2026 — Available Targets:"
	@echo "  make run        - Execute production ranking pipeline -> predictions.csv"
	@echo "  make test       - Run full automated regression test suite"
	@echo "  make validate   - Verify predictions.csv with official grader script"
	@echo "  make api        - Launch FastAPI REST service on http://127.0.0.1:8000"
	@echo "  make clean      - Remove build and test cache artifacts"

run:
	python -m nexora.pipeline --data data --out predictions.csv

test:
	pytest -v

validate:
	python validate_submission.py predictions.csv

api:
	uvicorn nexora.api:app --host 0.0.0.0 --port 8000

clean:
	python -c "import shutil, pathlib; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('__pycache__')]"
	python -c "import shutil, pathlib; [shutil.rmtree(p) for p in pathlib.Path('.').rglob('.pytest_cache')]"
