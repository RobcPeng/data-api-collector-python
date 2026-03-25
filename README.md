# Data API Collector

A service for sandboxing data ingestion pipelines, streaming data generation, and orchestrating connections across PostgreSQL, Redis, Kafka, Neo4j, and Elasticsearch. Built for local development with Databricks integration in mind.

## Architecture

```
                          +-----------+
                          |   Caddy   |  :10800 (HTTP) / :10443 (HTTPS)
                          | (reverse  |  API key auth on all routes
                          |  proxy)   |
                          +-----+-----+
                                |
              +-----------------+-----------------+
              |                                   |
        +-----+-----+                     +------+--------+
        | FastAPI    |                     | Spark         |
        | App :8000  |----(httpx proxy)--->| Generator     |
        |            |                     | :8003         |
        +--+--+--+---+                     +-------+-------+
           |  |  |                                 |
    +------+  |  +------+                   +------+------+
    |         |         |                   |             |
+---+---+ +---+---+ +---+---+         +----+----+   +----+----+
|Postgres| | Redis | | Neo4j |         |  Kafka  |   |  Spark  |
| :15432 | |:16379 | | :7474 |         |  :9092  |   | (local) |
+--------+ +-------+ | :7687 |         | (KRaft) |   +---------+
                      +-------+         +---------+

Other services: Elasticsearch :9200, OCR Service :8002
```

## Quick Start

```bash
# Clone the repository
git clone <repo-url>
cd data-api-collector-python

# Option A: Generate .env with strong random secrets
./scripts/setup-env.sh

# Option B: Manual setup
cp .env.example .env
# Edit .env — at minimum change SECRET_KEY, NEO4J_PASSWORD, POSTGRES_PASSWORD

# Start everything
docker compose up -d

# Run the test suite to verify
./tests/test_services.sh
```

## Services

| Service | Container | Ports (host) | Description |
|---|---|---|---|
| **Caddy** | data-api-caddy | 10800, 10443 | Reverse proxy with API key auth |
| **FastAPI App** | data-api-app | (internal 8000) | Main API application |
| **PostgreSQL** | data-api-postgres | 15432 | Relational database |
| **Redis** | data-api-redis | 16379 | Key-value cache |
| **Kafka** | data-api-kafka | 9092 | Message broker (KRaft, no Zookeeper) |
| **Neo4j** | data-api-neo4j | 7474, 7687 | Graph database |
| **Elasticsearch** | data-api-elasticsearch | 9200 | Search engine |
| **Spark Generator** | spark-generator | (internal 8003) | Streaming data generator (PySpark + dbldatagen) |
| **OCR Service** | ocr-service | (internal 8002) | Document/image analysis (GPU) |

## Authentication

All API endpoints require the `X-Api-Key` header. The key is your `SECRET_KEY` from `.env`.

```bash
# Example
curl -H "X-Api-Key: YOUR_SECRET_KEY" http://localhost:10800/api/v1/data-sources/orm

# Health check (no auth required)
curl http://localhost:10800/health
```

## API Endpoints

**Base URL:** `http://localhost:10800/api/v1`

### PostgreSQL

<details>
<summary>curl</summary>

```bash
curl -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/data-sources/orm
curl -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/data-sources/raw/sql
curl -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/data-sources/connection-info
```
</details>

```python
import requests

API = "http://localhost:10800/api/v1"
HEADERS = {"X-Api-Key": "YOUR_SECRET_KEY"}

# Test ORM connection
requests.get(f"{API}/data-sources/orm", headers=HEADERS).json()

# Test raw SQL
requests.get(f"{API}/data-sources/raw/sql", headers=HEADERS).json()

# Connection pool info
requests.get(f"{API}/data-sources/connection-info", headers=HEADERS).json()
```

### Neo4j

<details>
<summary>curl</summary>

```bash
curl -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/data-sources/neo4j/health
curl -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/data-sources/neo4j/version
curl -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/data-sources/neo4j/statistics
curl -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/data-sources/neo4j/connection-info
curl -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/data-sources/neo4j/query-test
```
</details>

```python
requests.get(f"{API}/data-sources/neo4j/health", headers=HEADERS).json()
requests.get(f"{API}/data-sources/neo4j/version", headers=HEADERS).json()
requests.get(f"{API}/data-sources/neo4j/statistics", headers=HEADERS).json()
requests.get(f"{API}/data-sources/neo4j/connection-info", headers=HEADERS).json()
requests.get(f"{API}/data-sources/neo4j/query-test", headers=HEADERS).json()
```

### Redis

<details>
<summary>curl</summary>

```bash
curl -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/redis/test

curl -X POST -H "X-Api-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"key_store": "my_key", "value": {"foo": "bar"}}' \
  http://localhost:10800/api/v1/redis/set

curl -H "X-Api-Key: $KEY" "http://localhost:10800/api/v1/redis/get?key_store=my_key"
```
</details>

```python
# Connection test
requests.get(f"{API}/redis/test", headers=HEADERS).json()

# Set a value (string or JSON)
requests.post(f"{API}/redis/set", headers=HEADERS,
    json={"key_store": "my_key", "value": {"foo": "bar"}}
).json()

# Get a value
requests.get(f"{API}/redis/get", headers=HEADERS,
    params={"key_store": "my_key"}
).json()
```

### Kafka

<details>
<summary>curl</summary>

```bash
curl -X POST -H "X-Api-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"topic_name": "my-topic", "topic_message": "hello", "source": "test"}' \
  http://localhost:10800/api/v1/kafka/producer/send-message

curl -H "X-Api-Key: $KEY" \
  "http://localhost:10800/api/v1/kafka/consume/consume-message?topic_name=my-topic&message_limit=5"

curl -H "X-Api-Key: $KEY" "http://localhost:10800/api/v1/kafka/events?limit=10"
```
</details>

```python
# Produce a message
requests.post(f"{API}/kafka/producer/send-message", headers=HEADERS,
    json={"topic_name": "my-topic", "topic_message": "hello", "source": "test"}
).json()

# Consume messages
requests.get(f"{API}/kafka/consume/consume-message", headers=HEADERS,
    params={"topic_name": "my-topic", "message_limit": 5}
).json()

# View event log
requests.get(f"{API}/kafka/events", headers=HEADERS,
    params={"limit": 10}
).json()
```

### Kafka Streaming Generators

Generate synthetic streaming data to Kafka topics using PySpark and dbldatagen. Three use cases are available:

| Use Case | Default Topic | Data |
|---|---|---|
| `fraud_detection` | `streaming-fraud-transactions` | Credit card transactions with merchant categories, amounts, geo coords |
| `telemetry` | `streaming-device-telemetry` | IoT sensor readings with battery, signal strength, anomaly flags |
| `web_traffic` | `streaming-web-traffic` | Clickstream events with pages, referrers, actions, HTTP status |

<details>
<summary>curl</summary>

```bash
# Start a generator (auto-stops after timeout_minutes)
curl -X POST -H "X-Api-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"use_case": "fraud_detection", "rows_per_batch": 100, "batch_interval_seconds": 1.0, "timeout_minutes": 10}' \
  http://localhost:10800/api/v1/kafka/generators/start

# List all generators
curl -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/kafka/generators

# Check status
curl -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/kafka/generators/{id}

# Stop a generator
curl -X POST -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/kafka/generators/{id}/stop

# Clean up finished generators
curl -X DELETE -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/kafka/generators/cleanup
```
</details>

```python
# Start a generator
resp = requests.post(f"{API}/kafka/generators/start", headers=HEADERS, json={
    "use_case": "fraud_detection",     # or "telemetry" or "web_traffic"
    "rows_per_batch": 100,
    "batch_interval_seconds": 1.0,
    "timeout_minutes": 10,
    # "topic_name": "custom-topic",    # optional, overrides default
})
generator = resp.json()
generator_id = generator["generator_id"]
print(generator)

# List all generators
requests.get(f"{API}/kafka/generators", headers=HEADERS).json()

# Check status of a specific generator
requests.get(f"{API}/kafka/generators/{generator_id}", headers=HEADERS).json()

# Stop a generator
requests.post(f"{API}/kafka/generators/{generator_id}/stop", headers=HEADERS).json()

# Clean up finished/stopped generators
requests.delete(f"{API}/kafka/generators/cleanup", headers=HEADERS).json()

# Start all three use cases at once
for use_case in ["fraud_detection", "telemetry", "web_traffic"]:
    resp = requests.post(f"{API}/kafka/generators/start", headers=HEADERS, json={
        "use_case": use_case,
        "rows_per_batch": 100,
        "batch_interval_seconds": 1.0,
        "timeout_minutes": 10,
    })
    print(f"{use_case}: {resp.json()['generator_id']}")
```

### SLED Data Generators (State, Local & Higher Ed)

Generate large volumes of realistic mock data across Kafka, Neo4j, and PostgreSQL for 6 SLED use cases. Data is generated programmatically (not hardcoded) with configurable scale, weighted distributions, and realistic value sets.

| Use Case | Kafka Topic | Neo4j Nodes | Postgres Tables |
|---|---|---|---|
| `student_enrollment` | `streaming-student-enrollment` | Student, Course, Department, DegreeProgram | sled_students, sled_courses, sled_enrollment_events |
| `grant_budget` | `streaming-grant-budget` | FundingSource, Agency, Program, Vendor, LineItem | sled_budget_transactions, sled_agencies, sled_vendors |
| `citizen_services` | `streaming-citizen-services` | Citizen, ServiceRequest, ServiceDepartment, Asset, District | sled_service_requests, sled_citizens, sled_assets |
| `k12_early_warning` | `streaming-k12-early-warning` | K12Student, School, Teacher, RiskIndicator, Intervention | sled_k12_events, sled_k12_students, sled_schools |
| `procurement` | `streaming-procurement` | ProcAgency, ProcVendor, Contract, Lobbyist | sled_procurement_events, sled_contracts |
| `case_management` | `streaming-case-management` | Client, Case, Caseworker, HHSAgency, HHSProgram | sled_case_events, sled_clients, sled_cases |

#### Kafka — Stream SLED events

Uses the same generator start/stop pattern as fraud/telemetry/web_traffic.

<details>
<summary>curl</summary>

```bash
# Start a SLED streaming generator
curl -X POST -H "X-Api-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"use_case": "student_enrollment", "rows_per_batch": 100, "batch_interval_seconds": 1.0, "timeout_minutes": 10}' \
  http://localhost:10800/api/v1/kafka/generators/start

# Start all 6 SLED generators
for uc in student_enrollment grant_budget citizen_services k12_early_warning procurement case_management; do
  curl -X POST -H "X-Api-Key: $KEY" -H "Content-Type: application/json" \
    -d "{\"use_case\": \"$uc\", \"rows_per_batch\": 100, \"batch_interval_seconds\": 1.0, \"timeout_minutes\": 10}" \
    http://localhost:10800/api/v1/kafka/generators/start
done
```
</details>

```python
# Start all SLED Kafka generators
sled_use_cases = [
    "student_enrollment", "grant_budget", "citizen_services",
    "k12_early_warning", "procurement", "case_management",
]

for use_case in sled_use_cases:
    resp = requests.post(f"{API}/kafka/generators/start", headers=HEADERS, json={
        "use_case": use_case,
        "rows_per_batch": 100,
        "batch_interval_seconds": 1.0,
        "timeout_minutes": 10,
    })
    print(f"{use_case}: {resp.json()['generator_id']}")
```

#### Neo4j — Populate & clear graph data

Generates nodes with rich properties and relationship networks (e.g., Student→Course→Department, Client→Case→Caseworker→Agency). The `num_records` parameter controls base entity count; related entities and relationships scale proportionally.

<details>
<summary>curl</summary>

```bash
# Populate Neo4j with student enrollment graph (5000 students + courses, departments, programs, relationships)
curl -X POST -H "X-Api-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"num_records": 5000}' \
  http://localhost:10800/api/v1/data-sources/neo4j/sled/student_enrollment/populate

# Check status
curl -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/data-sources/neo4j/sled/student_enrollment/status

# Clear a use case's graph data
curl -X DELETE -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/data-sources/neo4j/sled/student_enrollment/clear

# List populate jobs
curl -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/data-sources/neo4j/sled/jobs
```
</details>

```python
# Populate all 6 use cases in Neo4j
for use_case in sled_use_cases:
    resp = requests.post(
        f"{API}/data-sources/neo4j/sled/{use_case}/populate",
        headers=HEADERS,
        json={"num_records": 5000},
    )
    print(f"{use_case}: {resp.json()}")

# Check counts
for use_case in sled_use_cases:
    status = requests.get(f"{API}/data-sources/neo4j/sled/{use_case}/status", headers=HEADERS).json()
    print(f"{use_case}: {status['counts']}")

# Clear a specific use case
requests.delete(f"{API}/data-sources/neo4j/sled/procurement/clear", headers=HEADERS).json()
```

#### PostgreSQL — Populate & clear relational data

Creates tables automatically (`CREATE TABLE IF NOT EXISTS`) and bulk inserts data in batches. Tables are prefixed with `sled_` to avoid collisions with existing tables.

<details>
<summary>curl</summary>

```bash
# Populate Postgres with K-12 early warning data (5000 students + schools, events)
curl -X POST -H "X-Api-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"num_records": 5000}' \
  http://localhost:10800/api/v1/data-sources/sled/k12_early_warning/populate

# Check row counts
curl -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/data-sources/sled/k12_early_warning/status

# Truncate tables for a use case
curl -X DELETE -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/data-sources/sled/k12_early_warning/clear
```
</details>

```python
# Populate all 6 use cases in Postgres
for use_case in sled_use_cases:
    resp = requests.post(
        f"{API}/data-sources/sled/{use_case}/populate",
        headers=HEADERS,
        json={"num_records": 10000},
    )
    print(f"{use_case}: {resp.json()}")

# Check row counts
for use_case in sled_use_cases:
    status = requests.get(f"{API}/data-sources/sled/{use_case}/status", headers=HEADERS).json()
    print(f"{use_case}: {status['counts']}")
```

#### SLED Kafka Schemas (for Databricks Structured Streaming)

<details>
<summary>Student Enrollment schema</summary>

```python
student_enrollment_schema = StructType([
    StructField("event_id", StringType()),
    StructField("student_id", StringType()),
    StructField("course_id", StringType()),
    StructField("action", StringType()),
    StructField("semester", StringType()),
    StructField("department", StringType()),
    StructField("grade", StringType()),
    StructField("credits", IntegerType()),
    StructField("campus", StringType()),
    StructField("gpa_impact", DecimalType(4, 2)),
    StructField("event_timestamp", StringType()),
])
```
</details>

<details>
<summary>Grant & Budget schema</summary>

```python
grant_budget_schema = StructType([
    StructField("transaction_id", StringType()),
    StructField("fund_source_id", StringType()),
    StructField("agency_id", StringType()),
    StructField("program_id", StringType()),
    StructField("vendor_id", StringType()),
    StructField("transaction_type", StringType()),
    StructField("amount", DecimalType(14, 2)),
    StructField("fund_category", StringType()),
    StructField("fiscal_year", IntegerType()),
    StructField("quarter", StringType()),
    StructField("cost_center", StringType()),
    StructField("account_code", StringType()),
    StructField("description", StringType()),
    StructField("event_timestamp", StringType()),
])
```
</details>

<details>
<summary>Citizen Services (311) schema</summary>

```python
citizen_services_schema = StructType([
    StructField("request_id", StringType()),
    StructField("citizen_id", StringType()),
    StructField("request_type", StringType()),
    StructField("department", StringType()),
    StructField("status", StringType()),
    StructField("priority", StringType()),
    StructField("district", IntegerType()),
    StructField("asset_id", StringType()),
    StructField("latitude", DecimalType(8, 5)),
    StructField("longitude", DecimalType(9, 5)),
    StructField("response_time_hours", IntegerType()),
    StructField("satisfaction_rating", IntegerType()),
    StructField("event_timestamp", StringType()),
])
```
</details>

<details>
<summary>K-12 Early Warning schema</summary>

```python
k12_early_warning_schema = StructType([
    StructField("event_id", StringType()),
    StructField("student_id", StringType()),
    StructField("school_id", StringType()),
    StructField("event_type", StringType()),
    StructField("grade_level", IntegerType()),
    StructField("teacher_id", StringType()),
    StructField("risk_score", DecimalType(5, 2)),
    StructField("attendance_rate", DecimalType(5, 2)),
    StructField("gpa", DecimalType(3, 2)),
    StructField("behavior_incidents_ytd", IntegerType()),
    StructField("intervention_type", StringType()),
    StructField("school_type", StringType()),
    StructField("free_reduced_lunch", BooleanType()),
    StructField("english_learner", BooleanType()),
    StructField("special_education", BooleanType()),
    StructField("event_timestamp", StringType()),
])
```
</details>

<details>
<summary>Procurement schema</summary>

```python
procurement_schema = StructType([
    StructField("event_id", StringType()),
    StructField("agency_id", StringType()),
    StructField("vendor_id", StringType()),
    StructField("event_type", StringType()),
    StructField("contract_id", StringType()),
    StructField("amount", DecimalType(14, 2)),
    StructField("procurement_method", StringType()),
    StructField("commodity_code", StringType()),
    StructField("category", StringType()),
    StructField("minority_owned", BooleanType()),
    StructField("small_business", BooleanType()),
    StructField("local_vendor", BooleanType()),
    StructField("contract_duration_months", IntegerType()),
    StructField("payment_terms", StringType()),
    StructField("event_timestamp", StringType()),
])
```
</details>

<details>
<summary>Case Management (HHS) schema</summary>

```python
case_management_schema = StructType([
    StructField("event_id", StringType()),
    StructField("client_id", StringType()),
    StructField("case_id", StringType()),
    StructField("caseworker_id", StringType()),
    StructField("event_type", StringType()),
    StructField("program", StringType()),
    StructField("agency_id", StringType()),
    StructField("benefit_amount", DecimalType(10, 2)),
    StructField("household_size", IntegerType()),
    StructField("income_bracket", StringType()),
    StructField("county", StringType()),
    StructField("determination", StringType()),
    StructField("referral_source", StringType()),
    StructField("priority", StringType()),
    StructField("event_timestamp", StringType()),
])
```
</details>

### Elasticsearch (via Caddy proxy)

<details>
<summary>curl</summary>

```bash
curl -H "X-Api-Key: $KEY" http://localhost:10800/elasticsearch/_cluster/health
```
</details>

```python
requests.get("http://localhost:10800/elasticsearch/_cluster/health", headers=HEADERS).json()
```

## Testing

```bash
# Run all tests (health, postgres, neo4j, redis, kafka, generators, ollama)
./tests/test_services.sh

# Run specific test groups
./tests/test_services.sh health
./tests/test_services.sh postgres
./tests/test_services.sh neo4j
./tests/test_services.sh redis
./tests/test_services.sh kafka
./tests/test_services.sh generators
./tests/test_services.sh ollama
```

## Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "your migration message"

# Apply migrations (also runs automatically on container start)
alembic upgrade head

# Rollback
alembic downgrade -1
```

---

## Resetting the Environment

### Clear SLED data only (keeps services running)

```bash
KEY="YOUR_SECRET_KEY"
API="http://localhost:10800/api/v1"

# Clear all 6 SLED use cases from Neo4j
for uc in student_enrollment grant_budget citizen_services k12_early_warning procurement case_management; do
  curl -s -X DELETE -H "X-Api-Key: $KEY" "$API/data-sources/neo4j/sled/$uc/clear"
done

# Clear all 6 SLED use cases from Postgres
for uc in student_enrollment grant_budget citizen_services k12_early_warning procurement case_management; do
  curl -s -X DELETE -H "X-Api-Key: $KEY" "$API/data-sources/sled/$uc/clear"
done
```

```python
sled_use_cases = [
    "student_enrollment", "grant_budget", "citizen_services",
    "k12_early_warning", "procurement", "case_management",
]

# Clear Neo4j
for uc in sled_use_cases:
    print(requests.delete(f"{API}/data-sources/neo4j/sled/{uc}/clear", headers=HEADERS).json())

# Clear Postgres
for uc in sled_use_cases:
    print(requests.delete(f"{API}/data-sources/sled/{uc}/clear", headers=HEADERS).json())
```

### Stop all Kafka generators

```bash
# Stop all running generators, then clean up
curl -s -H "X-Api-Key: $KEY" "$API/kafka/generators" | \
  python3 -c "import sys,json;[print(g['generator_id']) for g in json.load(sys.stdin) if g['status']=='running']" | \
  xargs -I{} curl -s -X POST -H "X-Api-Key: $KEY" "$API/kafka/generators/{}/stop"

curl -s -X DELETE -H "X-Api-Key: $KEY" "$API/kafka/generators/cleanup"
```

```python
# Stop all running generators
for g in requests.get(f"{API}/kafka/generators", headers=HEADERS).json():
    if g["status"] == "running":
        requests.post(f"{API}/kafka/generators/{g['generator_id']}/stop", headers=HEADERS)

# Clean up finished generators
requests.delete(f"{API}/kafka/generators/cleanup", headers=HEADERS).json()
```

### Full reset (wipe all data volumes)

This destroys **all** data across Postgres, Neo4j, Redis, Kafka, and Elasticsearch. Credentials in `.env` are preserved.

```bash
docker compose down

# Remove all data volumes
docker volume rm \
  data-api-collector-python_postgres_data \
  data-api-collector-python_neo4j_data \
  data-api-collector-python_redis_data \
  data-api-collector-python_kafka_data \
  data-api-collector-python_elastic_data

# Bring everything back up (Postgres migrations run automatically on start)
docker compose up -d
```

### Rotate credentials + full reset

```bash
# Generate new .env with fresh secrets, then wipe and restart
./scripts/setup-env.sh
docker compose down
docker volume rm \
  data-api-collector-python_postgres_data \
  data-api-collector-python_neo4j_data
docker compose up -d
```

---

## Databricks Integration

Import the example notebooks into your Databricks workspace. Each notebook is self-contained — update `HOST` and your secret scope in the setup cell of whichever notebook you use.

| Notebook | Description |
|---|---|
| [`example.ipynb`](example.ipynb) | Quick start — health checks + one test per service |
| [`examples/kafka_streaming.ipynb`](examples/kafka_streaming.ipynb) | 9 Kafka streaming use cases (core + SLED) with schemas and readStream |
| [`examples/neo4j_graph.ipynb`](examples/neo4j_graph.ipynb) | Populate SLED graph data + Cypher queries per use case |
| [`examples/postgres_jdbc.ipynb`](examples/postgres_jdbc.ipynb) | Populate SLED relational tables + JDBC reads with Spark aggregations |
| [`examples/_config.ipynb`](examples/_config.ipynb) | Reference copy of shared config (HOST, secrets, helpers) |

This stack is designed to serve as a local data source that Databricks can connect to for streaming ingestion, batch reads, and graph queries. Below are connection instructions for each service.

### Prerequisites

**Network access:** Your Databricks workspace must reach your local services. Options:

- **Same VPC/VNet:** Allow inbound traffic on the relevant ports via security groups
- **Tunnel (local dev):** Use [ngrok](https://ngrok.com/) or [Tailscale](https://tailscale.com/) to expose local ports
- **VPN:** Connect your local network to the Databricks VPC

For ngrok:
```bash
# Expose Kafka
ngrok tcp 9092

# Expose PostgreSQL
ngrok tcp 15432
```

**Databricks secrets:** Store all credentials in Databricks secrets, never hardcode them.

```bash
# Install CLI and configure
pip install databricks-cli
databricks configure --token

# Create secret scopes
databricks secrets create-scope kafka
databricks secrets create-scope postgres
databricks secrets create-scope neo4j

# Store credentials
databricks secrets put-secret kafka bootstrap-servers --string-value "your-host:9092"
databricks secrets put-secret postgres password --string-value "your-password"
databricks secrets put-secret postgres host --string-value "your-host"
databricks secrets put-secret neo4j password --string-value "your-password"
databricks secrets put-secret neo4j host --string-value "your-host"
```

---

### Kafka Streaming (Structured Streaming)

#### 1. Start a generator on the server

```bash
# Start producing fraud detection data (runs for 10 minutes by default)
curl -X POST -H "X-Api-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"use_case": "fraud_detection", "rows_per_batch": 100, "batch_interval_seconds": 1.0, "timeout_minutes": 10}' \
  http://localhost:10800/api/v1/kafka/generators/start

# Start telemetry data
curl -X POST -H "X-Api-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"use_case": "telemetry", "rows_per_batch": 100, "batch_interval_seconds": 1.0, "timeout_minutes": 10}' \
  http://localhost:10800/api/v1/kafka/generators/start

# Start web traffic data
curl -X POST -H "X-Api-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"use_case": "web_traffic", "rows_per_batch": 100, "batch_interval_seconds": 1.0, "timeout_minutes": 10}' \
  http://localhost:10800/api/v1/kafka/generators/start

# Check what's running
curl -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/kafka/generators

# Stop a specific generator
curl -X POST -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/kafka/generators/{id}/stop

# Stop all — clean up finished generators, then stop any still running
curl -X DELETE -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/kafka/generators/cleanup
```

#### 2. Connect from Databricks

The external Kafka listener uses SASL/PLAIN authentication over SSL (nginx terminates TLS, Kafka validates credentials).

> **Note:** Databricks shades Kafka classes — use `kafkashaded.org.apache.kafka` instead of `org.apache.kafka` in the JAAS config.

```python
# Store these in Databricks secrets for production use
KAFKA_HOST = "your-hostname.com:9093"
KAFKA_USER = dbutils.secrets.get(scope="kafka", key="username")
KAFKA_PASSWORD = dbutils.secrets.get(scope="kafka", key="password")

raw = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", KAFKA_HOST)
    .option("kafka.security.protocol", "SASL_SSL")
    .option("kafka.sasl.mechanism", "PLAIN")
    .option("kafka.sasl.jaas.config",
            'kafkashaded.org.apache.kafka.common.security.plain.PlainLoginModule required '
            f'username="{KAFKA_USER}" '
            f'password="{KAFKA_PASSWORD}";')
    .option("subscribe", "streaming-fraud-transactions")
    .option("startingOffsets", "earliest")
    .load()
)
```

#### 3. Parse the JSON payload

```python
from pyspark.sql.functions import from_json, col
from pyspark.sql.types import *

fraud_schema = StructType([
    StructField("transaction_id", StringType()),
    StructField("user_id", IntegerType()),
    StructField("merchant_id", IntegerType()),
    StructField("amount", DecimalType(10, 2)),
    StructField("currency", StringType()),
    StructField("merchant_category", StringType()),
    StructField("payment_method", StringType()),
    StructField("ip_address", StringType()),
    StructField("device_id", StringType()),
    StructField("latitude", DecimalType(8, 5)),
    StructField("longitude", DecimalType(9, 5)),
    StructField("card_type", StringType()),
    StructField("event_timestamp", StringType()),
])

parsed = (
    raw.select(from_json(col("value").cast("string"), fraud_schema).alias("data"))
    .select("data.*")
)
```

#### 4. Display or write to Delta

```python
# Preview the stream (requires a checkpoint location on Databricks)
display(parsed, checkpointLocation="/Volumes/your_catalog/your_schema/checkpoints/fraud_preview")

# Write to a Delta table
(
    parsed.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", "/Volumes/your_catalog/your_schema/checkpoints/fraud_transactions")
    .toTable("your_catalog.your_schema.fraud_transactions")
)
```

To reset a stream from scratch, clear the checkpoint:

```python
dbutils.fs.rm("/Volumes/your_catalog/your_schema/checkpoints/fraud_preview", recurse=True)
```

#### Telemetry schema

```python
telemetry_schema = StructType([
    StructField("event_id", StringType()),
    StructField("device_id", StringType()),
    StructField("device_type", StringType()),
    StructField("reading_value", DecimalType(10, 4)),
    StructField("unit", StringType()),
    StructField("battery_level", DecimalType(5, 2)),
    StructField("signal_strength_dbm", IntegerType()),
    StructField("firmware_version", StringType()),
    StructField("facility_id", IntegerType()),
    StructField("latitude", DecimalType(8, 5)),
    StructField("longitude", DecimalType(9, 5)),
    StructField("anomaly_flag", BooleanType()),
    StructField("event_timestamp", StringType()),
])
```

#### Web traffic schema

```python
web_schema = StructType([
    StructField("event_id", StringType()),
    StructField("session_id", StringType()),
    StructField("user_id", IntegerType()),
    StructField("page_url", StringType()),
    StructField("referrer", StringType()),
    StructField("user_agent", StringType()),
    StructField("ip_address", StringType()),
    StructField("country", StringType()),
    StructField("device_type", StringType()),
    StructField("action", StringType()),
    StructField("duration_ms", IntegerType()),
    StructField("http_status", IntegerType()),
    StructField("event_timestamp", StringType()),
])
```

---

### PostgreSQL (JDBC)

```python
pg_host = dbutils.secrets.get(scope="postgres", key="host")
pg_pass = dbutils.secrets.get(scope="postgres", key="password")

df = (
    spark.read
    .format("jdbc")
    .option("url", f"jdbc:postgresql://{pg_host}:15432/data_collector")
    .option("dbtable", "kafka_event_logs")
    .option("user", "dataapi")
    .option("password", pg_pass)
    .option("driver", "org.postgresql.Driver")
    .load()
)

display(df)
```

**Lakehouse Federation (Unity Catalog)** for governed access without JDBC code:

```sql
-- Create a foreign connection
CREATE CONNECTION postgres_conn
TYPE POSTGRESQL
OPTIONS (
  host '<your-host>',
  port '15432',
  user 'dataapi',
  password secret('postgres', 'password')
);

-- Create a foreign catalog
CREATE FOREIGN CATALOG postgres_data
USING CONNECTION postgres_conn
OPTIONS (database 'data_collector');

-- Query directly via Unity Catalog
SELECT * FROM postgres_data.public.kafka_event_logs LIMIT 10;
```

---

### Neo4j (Spark Connector)

Add the Neo4j Spark connector to your cluster configuration:

```
spark.jars.packages org.neo4j:neo4j-connector-apache-spark_2.12:5.3.1_for_spark_3
```

**Read nodes:**

```python
neo4j_host = dbutils.secrets.get(scope="neo4j", key="host")
neo4j_pass = dbutils.secrets.get(scope="neo4j", key="password")

df = (
    spark.read
    .format("org.neo4j.spark.DataSource")
    .option("url", f"bolt://{neo4j_host}:7687")
    .option("authentication.type", "basic")
    .option("authentication.basic.username", "neo4j")
    .option("authentication.basic.password", neo4j_pass)
    .option("labels", "Person")
    .load()
)

display(df)
```

**Run Cypher queries:**

```python
df = (
    spark.read
    .format("org.neo4j.spark.DataSource")
    .option("url", f"bolt://{neo4j_host}:7687")
    .option("authentication.type", "basic")
    .option("authentication.basic.username", "neo4j")
    .option("authentication.basic.password", neo4j_pass)
    .option("query", "MATCH (n)-[r]->(m) RETURN n, type(r) as rel, m LIMIT 100")
    .load()
)
```

**Write data to Neo4j:**

```python
(
    df.write
    .format("org.neo4j.spark.DataSource")
    .option("url", f"bolt://{neo4j_host}:7687")
    .option("authentication.type", "basic")
    .option("authentication.basic.username", "neo4j")
    .option("authentication.basic.password", neo4j_pass)
    .option("labels", ":Transaction")
    .option("node.keys", "transaction_id")
    .mode("Overwrite")
    .save()
)
```

---

### Elasticsearch (Spark Connector)

Add the Elasticsearch Spark connector to your cluster:

```
spark.jars.packages org.elasticsearch:elasticsearch-spark-30_2.12:8.17.0
```

```python
# Read
df = (
    spark.read
    .format("es")
    .option("es.nodes", "your-es-host")
    .option("es.port", "9200")
    .option("es.net.ssl", "false")
    .load("your-index-name")
)

# Write
(
    df.write
    .format("es")
    .option("es.nodes", "your-es-host")
    .option("es.port", "9200")
    .option("es.resource", "fraud-transactions")
    .mode("append")
    .save()
)
```

---

### Redis (from Databricks)

Redis doesn't have a native Spark connector, but you can use it from Python:

```python
# Install on cluster: pip install redis
import redis
import json

r = redis.Redis(
    host=dbutils.secrets.get(scope="redis", key="host"),
    port=16379,
    decode_responses=True
)

# Read
value = r.get("my_key")
data = json.loads(value) if value else None

# Write
r.set("databricks:result", json.dumps({"processed": True, "count": 42}))
```

---

## Project Structure

```
data-api-collector-python/
├── docker-compose.yml
├── Dockerfile
├── Caddyfile
├── pyproject.toml
├── startup.sh
├── .env.example
├── .gitignore
├── example.ipynb                  # Quick start notebook (Databricks)
├── examples/
│   ├── _config.ipynb              # Shared config — HOST, secrets, helpers
│   ├── kafka_streaming.ipynb      # 9 Kafka streaming use cases (core + SLED)
│   ├── neo4j_graph.ipynb          # SLED graph populate + Cypher queries
│   └── postgres_jdbc.ipynb        # SLED table populate + JDBC reads
├── scripts/
│   └── setup-env.sh               # Generate .env with strong secrets
├── tests/
│   └── test_services.sh           # Comprehensive test suite (60 tests)
├── docs/
│   ├── testing-and-databricks-integration.md
│   └── security-hardening.md
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py              # Pydantic settings from .env
│   │   ├── database.py            # PostgreSQL (SQLAlchemy)
│   │   └── neo_database.py        # Neo4j client
│   ├── models/
│   │   └── events.py              # SQLAlchemy + Pydantic models
│   ├── schemas/
│   │   └── events.py
│   └── api/
│       └── endpoints/
│           ├── __init__.py         # Router aggregation
│           ├── data_sources.py     # PostgreSQL endpoints
│           ├── neo4j.py            # Neo4j endpoints
│           ├── kafka.py            # Kafka produce/consume
│           ├── kafka_generators.py # Proxy to spark-generator
│           ├── redis.py            # Redis set/get
│           ├── sled.py             # SLED populate/clear (Neo4j + Postgres)
│           ├── ollama_test.py      # Ollama connectivity
│           ├── llms.py             # LLM endpoints (WIP)
│           └── service_ocr.py      # OCR service proxy
├── services/
│   ├── spark_generator/            # PySpark + dbldatagen (core + SLED)
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── spark_generator/
│   │       └── main.py
│   └── ocr_service/                # Document analysis service
│       ├── Dockerfile
│       ├── pyproject.toml
│       └── ocr_service/
│           └── main.py
└── migrations/                     # Alembic database migrations
```
