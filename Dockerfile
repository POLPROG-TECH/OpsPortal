# ── Build stage ──────────────────────────────────────────────
FROM python:3.13-slim AS builder

WORKDIR /build

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir build \
    && python -m build --wheel --outdir /build/dist

# ── Runtime stage ────────────────────────────────────────────
FROM python:3.13-slim

LABEL maintainer="POLPROG <polprog.tech@gmail.com>"
LABEL org.opencontainers.image.source="https://github.com/polprog-tech/OpsPortal"
LABEL org.opencontainers.image.description="Unified developer operations portal"

# Non-root user for security
RUN groupadd --gid 1000 portal \
    && useradd --uid 1000 --gid portal --create-home portal

WORKDIR /app

# Install the built wheel
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl \
    && rm -rf /tmp/*.whl

# Create data directories
RUN mkdir -p /app/work /app/artifacts \
    && chown -R portal:portal /app

# Copy default manifest if user doesn't mount one
COPY --chown=portal:portal opsportal.yaml /app/opsportal.yaml

USER portal

ENV OPSPORTAL_HOST="0.0.0.0" \
    OPSPORTAL_PORT="8080" \
    OPSPORTAL_WORK_DIR="/app/work" \
    OPSPORTAL_ARTIFACT_DIR="/app/artifacts" \
    OPSPORTAL_MANIFEST_PATH="/app/opsportal.yaml"

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import httpx; r = httpx.get('http://localhost:8080/api/health'); r.raise_for_status()"

ENTRYPOINT ["opsportal"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8080"]
