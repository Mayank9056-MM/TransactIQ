FROM python:3.13-slim

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Install Python deps (layer-cached until pyproject.toml changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source
COPY . .

# Upload dir (overridden by volume in compose)
RUN mkdir -p /app/uploads

ENV PATH="/app/.venv/bin:$PATH"