# CLAUDE.md

## Project Overview

Data API Collector — a containerized service stack for sandboxing data ingestion pipelines, streaming data generation, and orchestrating connections across multiple data services. Designed for local development with Databricks integration.

## Quick Reference

```bash
# Start the stack
docker compose up -d

# Run tests (60 tests across all services)
./tests/test_services.sh
./tests/test_services.sh [health|postgres|neo4j|redis|kafka|generators|ollama]

# Rebuild after code changes
docker compose up -d --build app

# Rebuild spark generator after changes
docker compose up -d --build spark-generator

# Generate fresh .env with strong secrets
./start.sh
```

## Architecture

- **Caddy** (`:10800`) — reverse proxy, API key auth on all routes except `/health`
- **FastAPI App** (internal `:8000`) — main API, proxies generator requests to spark-generator
- **Spark Generator** (internal `:8003`) — standalone PySpark + dbldatagen service for Kafka streaming data
- **Kafka** (`:9092` internal, `:9094` external SASL) — KRaft mode, no Zookeeper
- **PostgreSQL** (`:15432` local, `:15433` SSL external) — native SSL with Let's Encrypt certs
- **Neo4j** (`:7474`, `:7687`) — exposed externally via nginx on `:7688` with TLS
- **Redis** (`:16379`), **Elasticsearch** (`:9200`), **OCR Service** (internal `:8002`)

## Code Layout

```
app/
  main.py                         # FastAPI app init, docs disabled when DEBUG=false
  core/
    config.py                     # Pydantic BaseSettings, extra="ignore" for forward compat
    database.py                   # SQLAlchemy engine + session
    neo_database.py               # Neo4j singleton driver
  api/endpoints/
    __init__.py                   # Router aggregation under /api/v1
    data_sources.py               # PostgreSQL health/connection endpoints
    neo4j.py                      # Neo4j health/version/stats/query endpoints
    kafka.py                      # Kafka produce/consume/events
    kafka_generators.py           # Thin httpx proxy to spark-generator service
    redis.py                      # Redis set/get
    ollama_test.py                # Ollama connectivity debug
    service_ocr.py                # OCR service proxy
  models/events.py                # Pydantic + SQLAlchemy models (KafkaMessage, RedisReq, KafkaEventLog)
services/
  spark_generator/                # Standalone service: PySpark + dbldatagen → Kafka
    spark_generator/main.py       # FastAPI with generator start/stop/status/cleanup
  ocr_service/                    # Standalone OCR service (GPU)
```

## Key Patterns

- **Service proxy pattern**: Internal services (spark-generator, ocr-service) run their own FastAPI apps. The main app proxies to them via httpx. See `kafka_generators.py` and `service_ocr.py`.
- **Error handling**: All endpoint error responses use generic messages (`"internal error"`), never `str(e)`. Real errors go to container logs.
- **Input validation**: Kafka topic names are regex-constrained (`^[a-zA-Z0-9._\-]+$`), message size capped at 1MB, Redis keys limited to 512 chars. See `models/events.py`.
- **Config**: Pydantic BaseSettings with `extra="ignore"` so new `.env` vars don't break the app. Defaults provided for optional fields.
- **Auth**: Single API key via `X-Api-Key` header, checked by Caddy (not FastAPI). Key comes from `SECRET_KEY` in `.env`.

## Kafka Setup

- **Internal listener** (`:9092`, `INTERNAL`) — plaintext, no auth, used by Docker services
- **External listener** (`:9094`, `EXTERNAL`) — SASL/PLAIN auth, exposed via nginx SSL on `:9093`
- **SASL config**: `kafka_server_jaas.conf` (gitignored) mounted read-only into Kafka container
- **Databricks note**: Use `kafkashaded.org.apache.kafka.common.security.plain.PlainLoginModule` (not `org.apache.kafka`) in JAAS config due to Databricks class shading

## PostgreSQL SSL

- Native SSL enabled via entrypoint that copies Let's Encrypt certs with correct ownership
- Port `15432` — local access (localhost-bound, no SSL)
- Port `15433` — external access with SSL (cert paths from `SSL_CERT_PATH`/`SSL_KEY_PATH` env vars)

## Database Migrations

Uses Alembic. Migrations run automatically on container start via `docker-entrypoint.sh`.

```bash
# Inside the app container or locally with the venv
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1
```

## Security Notes

- `.env` is gitignored — contains all real credentials
- `kafka_server_jaas.conf` is gitignored — contains Kafka SASL credentials
- `.env.example` has only placeholder values, safe for git
- All database ports bound to `127.0.0.1` except Postgres `:15433` (SSL, needs external access)
- Caddy blocks all unauthenticated requests (except `/health`)
- Docs/redoc/openapi disabled when `DEBUG=false`
- No real hostnames or credentials in any tracked file — parameterized via env vars

## Testing

```bash
./tests/test_services.sh          # All 60 tests
./tests/test_services.sh generators  # Just the Spark generator tests (takes ~60s for Spark cold start)
```

The test script sources `.env` automatically. It tests health, auth, Postgres, Neo4j, Redis, Kafka produce/consume, all 3 generator use cases (fraud, telemetry, web traffic), and Ollama connectivity.

## Common Tasks

**Add a new endpoint**: Create file in `app/api/endpoints/`, add router to `__init__.py`.

**Add a new generator use case**: Add schema builder in `services/spark_generator/spark_generator/main.py`, register in `_USE_CASE_BUILDERS` and `_DEFAULT_TOPICS` dicts.

**Rotate credentials**: Run `./start.sh` or edit `.env` manually. For Postgres/Neo4j password changes, wipe their volumes: `docker compose down && docker volume rm data-api-collector-python_postgres_data data-api-collector-python_neo4j_data && docker compose up -d`.

**Rebuild after dependency changes**: Update `pyproject.toml`, run `uv lock`, then `docker compose up -d --build app` (or `spark-generator` for that service).
