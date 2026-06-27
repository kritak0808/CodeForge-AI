# =========================
# Builder Stage
# =========================
FROM python:3.12-slim AS builder

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python packages
RUN pip install --upgrade pip
RUN pip install --user --no-cache-dir -r requirements.txt

# =========================
# Runtime Stage
# =========================
FROM python:3.12-slim

WORKDIR /app

# Copy installed packages
COPY --from=builder /root/.local /root/.local

# Copy application
COPY . .

# Make installed packages available
ENV PATH="/root/.local/bin:$PATH"

# Railway provides PORT automatically
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

# Start FastAPI
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]