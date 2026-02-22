FROM python:3.11-slim

# System dependencies for geospatial libs
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libgeos-dev \
    libproj-dev \
    libgdal-dev \
    libeccodes-dev \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged user for runtime
RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --create-home appuser

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY --chown=appuser:appuser . .

USER appuser

EXPOSE 8000
