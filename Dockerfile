FROM python:3.10-slim

WORKDIR /app

# Prevent Python from buffering stdout/stderr and writing pyc files
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

# Copy project specification and source code
COPY pyproject.toml .
COPY src/ ./src/

# Install the package and dependencies
RUN pip install --no-cache-dir -e .

# Copy validation harness, tests, and configuration
COPY validate_submission.py baseline_3sigma.py pytest.ini ./
COPY tests/ ./tests/
COPY frontend/ ./frontend/

# Default command: execute pipeline reading mounted /app/data and writing predictions.csv
CMD ["python", "-m", "nexora.pipeline", "--data", "/app/data", "--out", "/app/predictions.csv"]
