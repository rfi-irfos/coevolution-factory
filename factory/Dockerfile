FROM python:3.12-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# FT_ENGINE_KEY is injected at runtime via `fly secrets set` (never baked here).
# If unset/'local' the service runs in DEMO mode — public surface stays up but
# panel sessions return a clear "engine key not configured" note instead of
# faking gated-engine output. FT_AGENT_REGISTRY points at the registry baked
# into the image (copied from the host at build time) so panels expand offline.
ENV FT_PORT=8091 \
    FT_ENGINE_URL=https://lauras-agents-api-v2.fly.dev \
    FT_ENGINE_KEY=local \
    FT_AGENT_REGISTRY=/app/agents_registry

# Copy the real agent registry into the image so panels expand from genuine
# slugs even if the live registry mount is absent.
COPY agents_registry ./agents_registry

EXPOSE 8091
CMD ["python", "runtime.py"]
