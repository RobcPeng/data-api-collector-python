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

## Why This Stack / Value Drivers

- **Multi-source data integration sandbox.** One `docker compose up` gives you Kafka streaming, graph (Neo4j), relational (Postgres), key-value (Redis), and search (Elasticsearch) — all pre-wired and talking to each other. No separate installs, no manual plumbing.
- **Databricks-native design.** Every data source is consumable from Databricks out of the box:
  - Structured Streaming for Kafka (SASL/SSL, schemas provided)
  - JDBC and Lakehouse Federation for Postgres
  - Spark Connector and Bolt protocol for Neo4j
  - Delta table writes throughout the example notebooks
- **Realistic SLED data at scale.** Six government and education use cases (student enrollment, grant/budget, citizen services, K-12 early warning, procurement, case management) with rich schemas — weighted distributions, realistic IDs, cross-entity relationships. This is not toy data.
- **POC acceleration.** Custom generators let SEs and customers define data schemas via JSON and instantly get streaming + graph + relational data without writing code. POST a column spec, get a running Kafka producer or a populated Neo4j graph in seconds.
- **Self-contained and portable.** Runs on a laptop, a cloud VM, or a CI pipeline. Docker Compose up, one `.env` file, no external dependencies beyond Docker itself.
- **End-to-end demo flow.** Populate data via the API, stream it to Databricks, query graphs, read tables over JDBC, write results to Delta — all covered in the provided notebooks with working code.

## How It Works — Deep Dives

New to the stack? These guides explain the internals — how data is generated, why design decisions were made, and how each system fits together. Start with whichever system you're working with:

| Guide | What you'll learn |
|-------|-------------------|
| [Kafka Data Generation](docs/kafka-data-generation.md) | How PySpark + dbldatagen generates streaming data, the generator lifecycle, weighted distributions, all 9 use case schemas, custom generators, and consuming from Databricks Structured Streaming |
| [Neo4j Graph Generation](docs/neo4j-graph-generation.md) | How graph data is populated with batch Cypher, node/relationship models for all 6 SLED use cases, custom graph generators, graph vs. relational trade-offs, and querying from Databricks via the Spark connector |
| [PostgreSQL Data Generation](docs/postgres-data-generation.md) | How relational data is bulk-inserted, table schemas for all 6 SLED use cases, the Kafka event audit log, custom table generators, and reading from Databricks via JDBC and Lakehouse Federation |

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

### Custom Data Generators (Experimental)

Define ad-hoc data generators via JSON and POST them to the API — no server code changes needed. Designed for POCs from Databricks or any HTTP client.

#### Custom Kafka Generators

POST a column spec that maps to [dbldatagen's](https://github.com/databrickslabs/dbldatagen) `withColumn()` API. The service builds a `DataGenerator`, streams batches to Kafka, and injects `event_timestamp` automatically.

**Column spec options:** `expr` (Spark SQL), `values`/`weights` (categorical), `min_value`/`max_value` (ranges), `template`, `unique_values`, `percent_nulls`, `begin`/`end` (dates), `base_column`.

<details>
<summary>curl</summary>

```bash
# Validate a spec (dry run — returns resolved schema + sample row)
curl -X POST -H "X-Api-Key: $KEY" -H "Content-Type: application/json" \
  -d '{
    "name": "iot_sensors",
    "topic_name": "custom-iot-data",
    "columns": [
      {"name": "device_id", "type": "string", "expr": "concat('"'"'DEV-'"'"', lpad(cast(int(rand()*500+1) as string), 4, '"'"'0'"'"'))"},
      {"name": "temp_celsius", "type": "decimal(5,2)", "min_value": -20.0, "max_value": 120.0, "random": true},
      {"name": "status", "type": "string", "values": ["online", "offline", "error"], "weights": [8, 1, 1]}
    ]
  }' http://localhost:10800/api/v1/kafka/generators/custom/validate

# Start the generator
curl -X POST -H "X-Api-Key: $KEY" -H "Content-Type: application/json" \
  -d '{
    "name": "iot_sensors",
    "topic_name": "custom-iot-data",
    "rows_per_batch": 50,
    "batch_interval_seconds": 2.0,
    "timeout_minutes": 15,
    "columns": [
      {"name": "device_id", "type": "string", "expr": "concat('"'"'DEV-'"'"', lpad(cast(int(rand()*500+1) as string), 4, '"'"'0'"'"'))"},
      {"name": "temp_celsius", "type": "decimal(5,2)", "min_value": -20.0, "max_value": 120.0, "random": true},
      {"name": "status", "type": "string", "values": ["online", "offline", "error"], "weights": [8, 1, 1]},
      {"name": "battery_pct", "type": "integer", "min_value": 0, "max_value": 100, "random": true}
    ]
  }' http://localhost:10800/api/v1/kafka/generators/custom/start

# List / stop / get spec
curl -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/kafka/generators/custom
curl -X POST -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/kafka/generators/custom/{id}/stop
curl -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/kafka/generators/custom/{id}/spec
```
</details>

```python
# Define and start a custom Kafka generator from Databricks
resp = requests.post(f"{API}/kafka/generators/custom/start", headers=HEADERS, json={
    "name": "iot_sensors",
    "topic_name": "custom-iot-data",
    "rows_per_batch": 50,
    "batch_interval_seconds": 2.0,
    "timeout_minutes": 15,
    "columns": [
        {"name": "device_id", "type": "string", "expr": "concat('DEV-', lpad(cast(int(rand()*500+1) as string), 4, '0'))"},
        {"name": "temp_celsius", "type": "decimal(5,2)", "min_value": -20.0, "max_value": 120.0, "random": True},
        {"name": "status", "type": "string", "values": ["online", "offline", "error"], "weights": [8, 1, 1]},
        {"name": "battery_pct", "type": "integer", "min_value": 0, "max_value": 100, "random": True},
    ],
})
print(resp.json())

# Validate without starting (returns schema + sample row)
requests.post(f"{API}/kafka/generators/custom/validate", headers=HEADERS, json={...}).json()

# List running custom generators
requests.get(f"{API}/kafka/generators/custom", headers=HEADERS).json()

# Get the spec back (for cloning/debugging)
requests.get(f"{API}/kafka/generators/custom/{generator_id}/spec", headers=HEADERS).json()

# Stop
requests.post(f"{API}/kafka/generators/custom/{generator_id}/stop", headers=HEADERS).json()
```

#### Custom Neo4j Graph Generators

Define node types (label, count, properties) and relationships (type, probability, fan-out) via JSON.

**Property generator types:** `uuid`, `sequence`, `choice`, `range_int`, `range_float`, `bool`, `date`, `timestamp`, `name`, `email`, `phone`, `address`, `constant`, `null_or`.

<details>
<summary>curl</summary>

```bash
curl -X POST -H "X-Api-Key: $KEY" -H "Content-Type: application/json" \
  -d '{
    "name": "org_chart",
    "clear_before": true,
    "nodes": [
      {"label": "Employee", "count": 500, "properties": [
        {"name": "emp_id", "generator_rule": {"generator": "sequence", "prefix": "EMP-", "width": 5}},
        {"name": "name", "generator_rule": {"generator": "name"}},
        {"name": "dept", "generator_rule": {"generator": "choice", "values": ["Engineering", "Sales", "HR"]}}
      ]},
      {"label": "Office", "count": 5, "properties": [
        {"name": "city", "generator_rule": {"generator": "choice", "values": ["NYC", "SF", "Chicago"]}}
      ]}
    ],
    "relationships": [
      {"type": "WORKS_IN", "from_label": "Employee", "to_label": "Office", "probability": 0.25, "max_per_source": 1}
    ]
  }' http://localhost:10800/api/v1/data-sources/neo4j/custom/start
```
</details>

```python
resp = requests.post(f"{API}/data-sources/neo4j/custom/start", headers=HEADERS, json={
    "name": "org_chart",
    "clear_before": True,
    "nodes": [
        {"label": "Employee", "count": 500, "properties": [
            {"name": "emp_id", "generator_rule": {"generator": "sequence", "prefix": "EMP-", "width": 5}},
            {"name": "name", "generator_rule": {"generator": "name"}},
            {"name": "department", "generator_rule": {"generator": "choice", "values": ["Engineering", "Sales", "HR", "Finance"]}},
            {"name": "salary", "generator_rule": {"generator": "range_int", "min": 50000, "max": 200000}},
        ]},
        {"label": "Office", "count": 10, "properties": [
            {"name": "city", "generator_rule": {"generator": "choice", "values": ["NYC", "SF", "Chicago", "Austin"]}},
        ]},
    ],
    "relationships": [
        {"type": "WORKS_IN", "from_label": "Employee", "to_label": "Office", "probability": 0.15, "max_per_source": 1},
        {"type": "REPORTS_TO", "from_label": "Employee", "to_label": "Employee", "probability": 0.003, "max_per_source": 1},
    ],
})
print(resp.json())

# List jobs / check status
requests.get(f"{API}/data-sources/neo4j/custom", headers=HEADERS).json()
requests.get(f"{API}/data-sources/neo4j/custom/{job_id}", headers=HEADERS).json()

# Clear nodes created by a specific job
requests.delete(f"{API}/data-sources/neo4j/custom/{job_id}/clear", headers=HEADERS).json()
```

#### Custom PostgreSQL Table Generators

Define table schemas and column generation rules. Tables are auto-prefixed with `custom_` to avoid collisions.

<details>
<summary>curl</summary>

```bash
curl -X POST -H "X-Api-Key: $KEY" -H "Content-Type: application/json" \
  -d '{
    "name": "survey",
    "table_name": "survey_responses",
    "num_records": 10000,
    "columns": [
      {"name": "id", "sql_type": "VARCHAR(40)", "primary_key": true, "generator_rule": {"generator": "uuid"}},
      {"name": "respondent", "sql_type": "VARCHAR(100)", "generator_rule": {"generator": "name"}},
      {"name": "score", "sql_type": "INT", "generator_rule": {"generator": "range_int", "min": 1, "max": 10}},
      {"name": "feedback", "sql_type": "VARCHAR(20)", "generator_rule": {"generator": "choice", "values": ["positive", "neutral", "negative"]}}
    ]
  }' http://localhost:10800/api/v1/data-sources/custom/start

# Get schema and sample rows
curl -H "X-Api-Key: $KEY" http://localhost:10800/api/v1/data-sources/custom/{id}/schema
curl -H "X-Api-Key: $KEY" "http://localhost:10800/api/v1/data-sources/custom/{id}/sample?limit=5"
```
</details>

```python
resp = requests.post(f"{API}/data-sources/custom/start", headers=HEADERS, json={
    "name": "survey",
    "table_name": "survey_responses",
    "num_records": 10000,
    "drop_existing": True,
    "columns": [
        {"name": "response_id", "sql_type": "VARCHAR(40)", "primary_key": True, "generator_rule": {"generator": "uuid"}},
        {"name": "respondent", "sql_type": "VARCHAR(100)", "generator_rule": {"generator": "name"}},
        {"name": "score", "sql_type": "INT", "generator_rule": {"generator": "range_int", "min": 1, "max": 10}},
        {"name": "category", "sql_type": "VARCHAR(20)", "generator_rule": {"generator": "choice", "values": ["positive", "neutral", "negative"], "weights": [5, 3, 2]}},
        {"name": "submitted_at", "sql_type": "DATE", "generator_rule": {"generator": "date", "start": "2024-01-01", "end": "2025-12-31"}},
    ],
})
print(resp.json())

# Check schema / sample rows
requests.get(f"{API}/data-sources/custom/{job_id}/schema", headers=HEADERS).json()
requests.get(f"{API}/data-sources/custom/{job_id}/sample?limit=5", headers=HEADERS).json()

# Drop the table
requests.delete(f"{API}/data-sources/custom/{job_id}/drop", headers=HEADERS).json()
```

#### Custom Generator Reference

| Endpoint | Method | Description |
|---|---|---|
| `/kafka/generators/custom/health` | GET | Health check |
| `/kafka/generators/custom/validate` | POST | Dry-run validation (returns schema + sample) |
| `/kafka/generators/custom/start` | POST | Start a custom Kafka generator |
| `/kafka/generators/custom` | GET | List all custom Kafka generators |
| `/kafka/generators/custom/{id}` | GET | Get status |
| `/kafka/generators/custom/{id}/spec` | GET | Get the column spec back |
| `/kafka/generators/custom/{id}/stop` | POST | Stop a running generator |
| `/kafka/generators/custom/cleanup` | DELETE | Remove finished generators |
| `/data-sources/neo4j/custom/health` | GET | Health check |
| `/data-sources/neo4j/custom/start` | POST | Generate custom graph |
| `/data-sources/neo4j/custom` | GET | List jobs |
| `/data-sources/neo4j/custom/{id}` | GET | Get job status |
| `/data-sources/neo4j/custom/{id}/clear` | DELETE | Clear nodes by job |
| `/data-sources/neo4j/custom/cleanup` | DELETE | Remove finished jobs |
| `/data-sources/custom/health` | GET | Health check |
| `/data-sources/custom/start` | POST | Generate custom table |
| `/data-sources/custom` | GET | List jobs |
| `/data-sources/custom/{id}` | GET | Get job status |
| `/data-sources/custom/{id}/schema` | GET | Get table schema |
| `/data-sources/custom/{id}/sample` | GET | Get sample rows |
| `/data-sources/custom/{id}/clear` | DELETE | Truncate table |
| `/data-sources/custom/{id}/drop` | DELETE | Drop table |
| `/data-sources/custom/cleanup` | DELETE | Remove finished jobs |

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

## Local Hosting & External Access

### Quick Start (local only)

```bash
# Start all services
docker compose up -d

# Verify everything is healthy
./tests/test_services.sh
```

All services are accessible on `localhost` at the ports listed in the Services table above. No additional configuration is needed for local-only use.

### Exposing to external consumers (Databricks, cloud)

When Databricks or other external clients need to reach this stack, you have three main options.

#### Option A: zrok (simplest for dev/demos)

[zrok](https://zrok.io/) is a free, open-source (Apache 2.0) tunnel built on [OpenZiti](https://openziti.io/). It supports **both HTTP and TCP** tunnels, so it can expose all services — API, Kafka, Postgres, and Neo4j — without separate tools.

```bash
# Install (Linux)
curl -sSf https://get.openziti.io/install.bash | sudo bash -s zrok

# macOS
brew install zrok

# One-time setup: create a free account at https://api.zrok.io and enable your environment
zrok invite    # sends email with token
zrok enable <token>
```

**Expose the API gateway (HTTP — public, no client setup needed):**

```bash
zrok share public http://localhost:10800
# Outputs a public URL like https://abc123.share.zrok.io
```

**Expose TCP services (private — requires `zrok access` on the client):**

```bash
# Run each in a separate terminal on the host machine
zrok share private --backend-mode tcpTunnel 127.0.0.1:9094    # Kafka
zrok share private --backend-mode tcpTunnel 127.0.0.1:15433   # PostgreSQL
zrok share private --backend-mode tcpTunnel 127.0.0.1:7687    # Neo4j Bolt
# Each outputs a share token like "abc123xyz"
```

**Access TCP services (run on your client machine / Databricks driver):**

```bash
# Install zrok on the client machine too, then:
zrok access private --bind 127.0.0.1:9094 <kafka-share-token>
zrok access private --bind 127.0.0.1:15433 <postgres-share-token>
zrok access private --bind 127.0.0.1:7687 <neo4j-share-token>
# Now connect to localhost:9094, localhost:15433, localhost:7687 as if local
```

**Persistent shares (survive restarts):**

```bash
# Reserve a share token (reusable)
zrok reserve private --backend-mode tcpTunnel 127.0.0.1:9094
# Returns a permanent token — use it with `zrok share reserved <token>`
```

> **When to use:** Quick demos, POCs, sharing with a colleague. No firewall rules or cloud infrastructure needed. The public HTTP share gives instant browser-accessible URLs; private TCP shares give full database/broker access to anyone with the share token.

#### Option B: Cloud VM / VPS

Deploy the stack on an EC2 instance, GCP VM, or Azure VM for persistent, always-on access.

- Open the required ports in your security group / firewall rules (see port reference below)
- Point a DNS name at the VM's public IP
- Caddy will automatically provision Let's Encrypt certificates for HTTPS if you configure a domain in the Caddyfile
- For Kafka and Postgres SSL, the stack already includes nginx TLS termination and native SSL — just ensure the cert paths are set in `.env`

### Port reference

| Port | Service | Protocol | External access needed? | Notes |
|------|---------|----------|------------------------|-------|
| 10800 | Caddy (HTTP) | HTTP | Yes | API gateway, API key auth on all routes |
| 10443 | Caddy (HTTPS) | HTTPS | Yes | Auto-HTTPS when domain is configured |
| 9092 | Kafka (internal) | TCP | No | Plaintext, Docker-internal only |
| 9094 | Kafka (external) | TCP/SASL | Yes | SASL/PLAIN auth, use for external clients |
| 9093 | Kafka (SSL) | TCP/SASL_SSL | Yes | nginx TLS termination + SASL auth |
| 15432 | PostgreSQL (local) | TCP | No | Bound to 127.0.0.1, no SSL |
| 15433 | PostgreSQL (SSL) | TCP/SSL | Yes | Native SSL with Let's Encrypt certs |
| 7474 | Neo4j (HTTP) | HTTP | No | Browser UI, typically local only |
| 7687 | Neo4j (Bolt) | TCP | Yes | Bolt protocol for drivers and Spark connector |
| 7688 | Neo4j (Bolt+TLS) | TCP/TLS | Yes | nginx TLS termination for Bolt |
| 16379 | Redis | TCP | Rarely | Only if Databricks connects directly |
| 9200 | Elasticsearch | HTTP | Rarely | Only if Databricks connects directly |

### SSL/TLS notes

- **Caddy** handles auto-HTTPS natively. When a domain name is configured in the Caddyfile (instead of `:10800`), Caddy provisions and renews Let's Encrypt certificates automatically. No manual cert management needed.
- **PostgreSQL** exposes native SSL on port `15433`. The entrypoint copies Let's Encrypt certs into the container with correct ownership. Cert paths are configured via `SSL_CERT_PATH` and `SSL_KEY_PATH` in `.env`.
- **Kafka** uses nginx on port `9093` for TLS termination in front of the SASL/PLAIN listener on `9094`. Databricks connects to `9093` with `SASL_SSL` security protocol.
- **Neo4j** uses nginx on port `7688` for TLS termination in front of the Bolt listener on `7687`. Use `bolt+s://<host>:7688` for encrypted connections.

### Cloud Deployment (Terraform)

For persistent, always-on deployment, use the included Terraform scripts to provision an EC2 instance with the full stack pre-configured.

```bash
cd deploy/aws
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — set key_name, allowed_cidr_blocks

terraform init
terraform plan
terraform apply
```

Terraform provisions an Ubuntu EC2 instance, installs Docker, clones the repo, generates secrets, and starts the stack automatically. Outputs include the public IP, API URL, and SSH command.

See [`deploy/README.md`](deploy/README.md) for full documentation including:
- **AWS Terraform** — automated EC2 deployment with security groups and bootstrap
- **Any Cloud VM** — manual setup on GCP, Azure, DigitalOcean, etc.
- **Docker Desktop** — local development with zrok tunnel exposure
- **Security recommendations** and port reference

---

## Databricks Integration

Import the example notebooks into your Databricks workspace. All notebooks share configuration from a single file — update `HOST` and your secret scope once in `_config`.

| Notebook | Description |
|---|---|
| [`examples/quickstart.ipynb`](examples/quickstart.ipynb) | Quick start — health checks + one test per service |
| [`examples/_config.ipynb`](examples/_config.ipynb) | Shared configuration — HOST, secrets, Kafka options, helper functions |
| [`examples/kafka_streaming.ipynb`](examples/kafka_streaming.ipynb) | 9 Kafka streaming use cases (core + SLED) with schemas and readStream |
| [`examples/neo4j_graph.ipynb`](examples/neo4j_graph.ipynb) | Populate SLED graph data + Cypher queries per use case |
| [`examples/postgres_jdbc.ipynb`](examples/postgres_jdbc.ipynb) | Populate SLED relational tables + JDBC reads with Spark aggregations |
| [`examples/custom_kafka.ipynb`](examples/custom_kafka.ipynb) | Custom Kafka generators — IoT, clickstream, healthcare vitals examples |
| [`examples/custom_neo4j_postgres.ipynb`](examples/custom_neo4j_postgres.ipynb) | Custom Neo4j graphs + Postgres tables — org chart, supply chain, survey, fleet examples |

Each capability notebook runs `%run ./_config` to load shared settings. The quick start runs `%run ./examples/_config`.

This stack is designed to serve as a local data source that Databricks can connect to for streaming ingestion, batch reads, and graph queries. Below are connection instructions for each service.

### Prerequisites

**Network access:** Your Databricks workspace must reach your local services. Options:

- **Same VPC/VNet:** Allow inbound traffic on the relevant ports via security groups
- **Tunnel (local dev):** Use [zrok](https://zrok.io/) to expose HTTP + TCP services (free, open source)
- **Cloud deploy:** Use the included [Terraform scripts](deploy/README.md) for AWS
- **VPN:** Connect your local network to the Databricks VPC

For zrok (HTTP + TCP):
```bash
zrok share public http://localhost:10800                              # API (public URL)
zrok share private --backend-mode tcpTunnel 127.0.0.1:9094           # Kafka
zrok share private --backend-mode tcpTunnel 127.0.0.1:15433          # Postgres
zrok share private --backend-mode tcpTunnel 127.0.0.1:7687           # Neo4j
```

See [Local Hosting & External Access](#local-hosting--external-access) for full setup instructions.

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
├── examples/
│   ├── quickstart.ipynb           # Quick start — health checks + connectivity test
│   ├── _config.ipynb              # Shared config — HOST, secrets, helpers
│   ├── kafka_streaming.ipynb      # 9 Kafka streaming use cases (core + SLED)
│   ├── neo4j_graph.ipynb          # SLED graph populate + Cypher queries
│   ├── postgres_jdbc.ipynb        # SLED table populate + JDBC reads
│   ├── custom_kafka.ipynb         # Custom Kafka generators (experimental)
│   └── custom_neo4j_postgres.ipynb # Custom Neo4j + Postgres generators (experimental)
├── deploy/
│   ├── README.md                  # Full deployment guide (AWS, cloud VM, local)
│   └── aws/                       # Terraform scripts for AWS EC2
│       ├── main.tf                # EC2 instance + security group
│       ├── variables.tf           # Configurable variables
│       ├── outputs.tf             # Instance IP, URLs, SSH command
│       ├── user_data.sh           # Bootstrap script (Docker, clone, start)
│       └── terraform.tfvars.example
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
│           ├── kafka_custom_generators.py  # Experimental: custom Kafka generators
│           ├── custom_generators.py        # Experimental: custom Neo4j + Postgres generators
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
