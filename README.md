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

## Databricks Integration

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
├── scripts/
│   └── setup-env.sh              # Generate .env with strong secrets
├── tests/
│   └── test_services.sh          # Comprehensive test suite (60 tests)
├── docs/
│   ├── testing-and-databricks-integration.md
│   └── security-hardening.md
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py             # Pydantic settings from .env
│   │   ├── database.py           # PostgreSQL (SQLAlchemy)
│   │   └── neo_database.py       # Neo4j client
│   ├── models/
│   │   └── events.py             # SQLAlchemy + Pydantic models
│   ├── schemas/
│   │   └── events.py
│   └── api/
│       └── endpoints/
│           ├── __init__.py        # Router aggregation
│           ├── data_sources.py    # PostgreSQL endpoints
│           ├── neo4j.py           # Neo4j endpoints
│           ├── kafka.py           # Kafka produce/consume
│           ├── kafka_generators.py # Proxy to spark-generator
│           ├── redis.py           # Redis set/get
│           ├── ollama_test.py     # Ollama connectivity
│           ├── llms.py            # LLM endpoints (WIP)
│           └── service_ocr.py     # OCR service proxy
├── services/
│   ├── spark_generator/           # PySpark + dbldatagen service
│   │   ├── Dockerfile
│   │   ├── pyproject.toml
│   │   └── spark_generator/
│   │       └── main.py
│   └── ocr_service/               # Document analysis service
│       ├── Dockerfile
│       ├── pyproject.toml
│       └── ocr_service/
│           └── main.py
└── migrations/                    # Alembic database migrations
```
