FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# The order-signing SDK is only installed for the live image (docker compose --profile live).
ARG LIVE=0
RUN if [ "$LIVE" = "1" ]; then pip install --no-cache-dir py-clob-client-v2; fi
COPY polybt ./polybt
COPY config.yaml config.local.yaml ./

# data/ (DuckDB + HTTP cache) and output/ are volumes so sessions survive restarts and upgrades.
VOLUME ["/app/data", "/app/output"]
ENTRYPOINT ["python", "-m", "polybt"]
CMD ["--help"]
