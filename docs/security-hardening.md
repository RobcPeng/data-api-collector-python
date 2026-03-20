# Security Hardening Guide

## Current State & Risks

### What's already good
- `.env` is in `.gitignore` — secrets stay out of git
- Caddy acts as a reverse proxy with API key auth on all `/api/*` routes
- Internal services (app:8000, spark-generator:8003, ocr-service:8002) are not exposed to the host — only reachable through Caddy or the Docker network
- `.env.example` uses placeholder values, not real secrets

### Issues to address

| Issue | Severity | Description |
|---|---|---|
| Default catch-all route | High | `handle /* { reverse_proxy app:8000 }` bypasses API key auth for any path not under `/api/*` |
| Single shared API key | Medium | One key for all consumers; no rotation, no per-user access |
| No rate limiting | Medium | No protection against brute force or abuse |
| Plaintext Kafka | Medium | No auth/TLS between Kafka and producers/consumers |
| Neo4j/ES directly proxied | Medium | Full admin access through Caddy with same API key |
| `.env.example` has weak defaults | Low | Users may deploy with `your-secret-key-change-this-in-production` |

---

## Recommendations

### 1. Fix the Caddy catch-all route

The current `handle /*` at the bottom of the Caddyfile allows unauthenticated access to the FastAPI app on any path that doesn't match earlier rules. This means `/docs`, `/openapi.json`, and any non-`/api/` route are fully open.

**Fix:** Require auth on all routes except health, or block unmatched paths:

```caddyfile
:80 {
    # Health check - no auth
    handle /health {
        respond "OK" 200
    }

    # Everything else requires API key
    @unauthorized {
        not header X-Api-Key "{$SECRET_KEY}"
    }
    handle @unauthorized {
        respond "Unauthorized" 401
    }

    handle /api/* {
        reverse_proxy app:8000
    }

    handle /elasticsearch/* {
        uri strip_prefix /elasticsearch
        reverse_proxy data-api-elasticsearch:9200
    }

    handle /neo4j/* {
        uri strip_prefix /neo4j
        reverse_proxy data-api-neo4j:7474
    }

    # Block everything else
    handle {
        respond "Not Found" 404
    }
}
```

### 2. Keep secrets out of GitHub while maintaining deployability

**Approach: `.env.example` + documentation + optional Docker secrets**

The current `.gitignore` already excludes `.env`. To make deployment smooth:

1. **`.env.example`** — checked into git with placeholder values and comments explaining each variable. This is the "template" developers copy to `.env`.

2. **Generate strong secrets automatically** — add a setup script:

```bash
#!/usr/bin/env bash
# scripts/setup-env.sh
if [[ -f .env ]]; then
    echo ".env already exists. Remove it first to regenerate."
    exit 1
fi

SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
NEO4J_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
POSTGRES_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")

cp .env.example .env
sed -i "s|your-secret-key-change-this-in-production|$SECRET_KEY|" .env
sed -i "s|your-neo4j-password|$NEO4J_PASSWORD|" .env
sed -i "s|dataapi123|$POSTGRES_PASSWORD|" .env
# Update DATABASE_URL with new password
sed -i "s|dataapi123|$POSTGRES_PASSWORD|" .env

echo "Generated .env with strong secrets."
echo "SECRET_KEY=$SECRET_KEY"
```

3. **For CI/CD or cloud deploys**, use environment variables or a secrets manager (Vault, AWS Secrets Manager, etc.) instead of `.env` files. Docker Compose supports `environment:` directly.

4. **Pre-commit hook** (optional) — prevent accidental `.env` commits:

```bash
# .githooks/pre-commit
#!/bin/bash
if git diff --cached --name-only | grep -q "^\.env$"; then
    echo "ERROR: Attempting to commit .env file with secrets."
    echo "This file is in .gitignore for a reason."
    exit 1
fi
```

### 3. Add rate limiting in Caddy

```caddyfile
:80 {
    # Global rate limit: 100 requests per minute per IP
    rate_limit {remote.ip} 100r/m

    # ... rest of config
}
```

Note: Caddy's built-in rate limiting requires the `caddy-ratelimit` plugin. Alternatively, use a simple approach with `respond` for specific paths.

### 4. Secure Kafka (if exposing externally)

For local development, plaintext Kafka is fine. If exposing to Databricks or external consumers:

```yaml
# docker-compose.yml - add SASL_SSL listener
kafka:
  environment:
    KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,SASL_SSL://0.0.0.0:9093
    KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092,SASL_SSL://your-external-host:9093
    KAFKA_SASL_MECHANISM_INTER_BROKER_PROTOCOL: PLAIN
    KAFKA_SASL_ENABLED_MECHANISMS: PLAIN
    # Add SSL certs and JAAS config
```

### 5. Restrict Elasticsearch and Neo4j proxy access

Consider separating admin access from API access:

- **Option A:** Remove the ES/Neo4j proxies entirely — access them directly on their ports only from localhost
- **Option B:** Use a separate admin API key for these routes
- **Option C:** Restrict to read-only operations via Caddy request matchers

### 6. Docker network isolation

Currently all services share `app-network`. For defense in depth:

```yaml
networks:
  frontend:  # Caddy + app
  backend:   # app + databases
  kafka-net: # app + kafka + spark-generator
```

This prevents Caddy from directly reaching databases, and prevents the spark-generator from reaching Postgres.

---

## File Sensitivity Reference

| File | Sensitive? | In .gitignore? | Notes |
|---|---|---|---|
| `.env` | Yes | Yes | Contains all passwords and keys |
| `.env.example` | No | No (tracked) | Template with placeholders only |
| `api-keys.json` | Yes | Yes | Caddy API key file (if used) |
| `Caddyfile` | No | No (tracked) | References `{$SECRET_KEY}` env var, not the value |
| `docker-compose.yml` | No | No (tracked) | References `${VAR}` placeholders, not values |

---

## Quick Checklist

- [ ] Copy `.env.example` to `.env` and set strong, unique values
- [ ] Never commit `.env` — it's in `.gitignore`
- [ ] Run `scripts/setup-env.sh` to auto-generate strong secrets
- [ ] Review Caddy catch-all route before exposing to network
- [ ] Use Databricks secrets for storing connection credentials
- [ ] Enable SASL/SSL on Kafka before exposing externally
- [ ] Consider network segmentation for production deployments
