# Testing & Databricks Integration Guide

## Table of Contents

- [Running the Test Suite](#running-the-test-suite)
- [Service Authentication](#service-authentication)
- [Kafka Generator Endpoints](#kafka-generator-endpoints)
- [Connecting Databricks to Kafka](#connecting-databricks-to-kafka)
- [Connecting Databricks to PostgreSQL](#connecting-databricks-to-postgresql)
- [Connecting Databricks to Neo4j](#connecting-databricks-to-neo4j)
- [Connecting Databricks to Elasticsearch](#connecting-databricks-to-elasticsearch)

---

## Running the Test Suite

### Prerequisites

- Docker Compose stack is running: `docker compose up -d`
- `.env` file exists with `SECRET_KEY` set

### Run all tests

```bash
./tests/test_services.sh
```

### Run specific test groups

```bash
./tests/test_services.sh health       # Caddy health + auth check
./tests/test_services.sh postgres     # PostgreSQL ORM, raw SQL, pool info
./tests/test_services.sh neo4j        # Neo4j health, version, stats, queries
./tests/test_services.sh redis        # Redis set/get with strings and JSON
./tests/test_services.sh kafka        # Basic Kafka produce/consume
./tests/test_services.sh generators   # Spark-based streaming generators (all 3 use cases)
./tests/test_services.sh ollama       # Ollama connectivity (optional)
```

### What the test suite covers

| Test Group | What It Tests |
|---|---|
| `health` | Caddy reverse proxy, API key authentication (401 without key, 200 with key) |
| `postgres` | SQLAlchemy ORM connection, raw SQL execution, connection pool stats |
| `neo4j` | Health check, version info, node/relationship stats, connection info, query execution |
| `redis` | Connection test, string set/get, JSON object set/get |
| `kafka` | Produce message to topic, consume from topic, event log retrieval |
| `generators` | Start all 3 generator types (fraud, telemetry, web traffic), verify Spark produces data, stop generator, custom topic names, cleanup |
| `ollama` | Environment config, connectivity (gracefully skips if Ollama is not running) |

---

## Service Authentication

All API endpoints behind `/api/*` require the `X-Api-Key` header matching the `SECRET_KEY` from your `.env` file.

```bash
# Example authenticated request
curl -H "X-Api-Key: YOUR_SECRET_KEY" http://localhost:10800/api/v1/data-sources/orm
```

---

## Kafka Generator Endpoints

The generator service uses `dbldatagen` (Databricks Labs Data Generator) with PySpark to produce synthetic streaming data to Kafka topics. It runs in its own container (`spark-generator`).

### Start a generator

```bash
curl -X POST -H "X-Api-Key: $SECRET_KEY" -H "Content-Type: application/json" \
  -d '{
    "use_case": "fraud_detection",
    "rows_per_batch": 100,
    "batch_interval_seconds": 1.0,
    "timeout_minutes": 10
  }' \
  http://localhost:10800/api/v1/kafka/generators/start
```

**Use cases and default topics:**

| Use Case | Default Topic | Schema |
|---|---|---|
| `fraud_detection` | `streaming-fraud-transactions` | transaction_id, user_id, merchant_id, amount, currency, merchant_category, payment_method, ip_address, device_id, lat/lng, card_type, event_timestamp |
| `telemetry` | `streaming-device-telemetry` | event_id, device_id, device_type, reading_value, unit, battery_level, signal_strength_dbm, firmware_version, facility_id, lat/lng, anomaly_flag, event_timestamp |
| `web_traffic` | `streaming-web-traffic` | event_id, session_id, user_id, page_url, referrer, user_agent, ip_address, country, device_type, action, duration_ms, http_status, event_timestamp |

### Check status / Stop / Cleanup

```bash
# List all generators
curl -H "X-Api-Key: $SECRET_KEY" http://localhost:10800/api/v1/kafka/generators

# Check specific generator
curl -H "X-Api-Key: $SECRET_KEY" http://localhost:10800/api/v1/kafka/generators/{generator_id}

# Stop a running generator
curl -X POST -H "X-Api-Key: $SECRET_KEY" http://localhost:10800/api/v1/kafka/generators/{generator_id}/stop

# Remove completed/stopped generators
curl -X DELETE -H "X-Api-Key: $SECRET_KEY" http://localhost:10800/api/v1/kafka/generators/cleanup
```

---

## Connecting Databricks to Kafka

This is the primary use case for the generators — stream synthetic data into Databricks for real-time feature engineering, fraud detection pipelines, etc.

### 1. Network access

Your Databricks workspace must be able to reach your Kafka broker. Options:

- **Databricks on cloud + Kafka on-prem/local**: Use a VPN, SSH tunnel, or expose Kafka via a public IP with TLS + SASL auth.
- **Same VPC/VNet**: Ensure security group/NSG rules allow inbound on port 9092.
- **Local development (ngrok/tailscale)**: Use [ngrok](https://ngrok.com/) or [Tailscale](https://tailscale.com/) to create a tunnel from your local machine to Databricks.

For a tunnel using ngrok:

```bash
# Expose local Kafka to the internet
ngrok tcp 9092
# Note the forwarding address, e.g., 0.tcp.ngrok.io:12345
```

Then update `KAFKA_ADVERTISED_LISTENERS` in `docker-compose.yml` to include the external address:

```yaml
KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092,EXTERNAL://0.tcp.ngrok.io:12345
KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT,EXTERNAL:PLAINTEXT
```

### 2. Read Kafka stream in Databricks (PySpark)

```python
# Databricks notebook
kafka_bootstrap = "your-kafka-host:9092"  # or ngrok address

df = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", kafka_bootstrap)
    .option("subscribe", "streaming-fraud-transactions")
    .option("startingOffsets", "earliest")
    .load()
)

# Parse the JSON values
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
    df.select(from_json(col("value").cast("string"), fraud_schema).alias("data"))
    .select("data.*")
)

display(parsed)
```

### 3. Write to Delta table

```python
(
    parsed.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", "/tmp/checkpoints/fraud_transactions")
    .toTable("catalog.schema.fraud_transactions")
)
```

### 4. Authentication (if you add SASL)

If you configure Kafka with SASL/SSL (recommended for production), add these options:

```python
df = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", kafka_bootstrap)
    .option("subscribe", "streaming-fraud-transactions")
    .option("kafka.security.protocol", "SASL_SSL")
    .option("kafka.sasl.mechanism", "PLAIN")
    .option("kafka.sasl.jaas.config",
            'org.apache.kafka.common.security.plain.PlainLoginModule required '
            'username="your-api-key" password="your-api-secret";')
    .load()
)
```

You can also store credentials in Databricks secrets:

```python
username = dbutils.secrets.get(scope="kafka", key="username")
password = dbutils.secrets.get(scope="kafka", key="password")
```

---

## Connecting Databricks to PostgreSQL

### 1. JDBC connection

```python
jdbc_url = "jdbc:postgresql://your-postgres-host:15432/data_collector"

df = (
    spark.read
    .format("jdbc")
    .option("url", jdbc_url)
    .option("dbtable", "kafka_event_logs")
    .option("user", "dataapi")
    .option("password", dbutils.secrets.get(scope="postgres", key="password"))
    .option("driver", "org.postgresql.Driver")
    .load()
)

display(df)
```

### 2. Using Databricks secrets for credentials

```bash
# Set up secret scope (CLI)
databricks secrets create-scope postgres

# Store credentials
databricks secrets put-secret postgres host --string-value "your-host"
databricks secrets put-secret postgres password --string-value "your-password"
```

```python
# Retrieve in notebook
host = dbutils.secrets.get(scope="postgres", key="host")
password = dbutils.secrets.get(scope="postgres", key="password")
```

### 3. Lakehouse Federation (Unity Catalog)

For a governed approach, create a foreign connection in Unity Catalog:

```sql
-- In Databricks SQL
CREATE CONNECTION postgres_conn
TYPE POSTGRESQL
OPTIONS (
  host 'your-postgres-host',
  port '15432',
  user 'dataapi',
  password secret('postgres', 'password')
);

CREATE FOREIGN CATALOG postgres_catalog
USING CONNECTION postgres_conn
OPTIONS (database 'data_collector');

-- Query directly
SELECT * FROM postgres_catalog.public.kafka_event_logs LIMIT 10;
```

---

## Connecting Databricks to Neo4j

### 1. Neo4j Spark Connector

Install the Neo4j Spark connector on your cluster. In your cluster configuration, add:

```
spark.jars.packages org.neo4j:neo4j-connector-apache-spark_2.12:5.3.1_for_spark_3
```

### 2. Read nodes

```python
df = (
    spark.read
    .format("org.neo4j.spark.DataSource")
    .option("url", "bolt://your-neo4j-host:7687")
    .option("authentication.type", "basic")
    .option("authentication.basic.username", "neo4j")
    .option("authentication.basic.password",
            dbutils.secrets.get(scope="neo4j", key="password"))
    .option("labels", "Person")
    .load()
)

display(df)
```

### 3. Run Cypher queries

```python
df = (
    spark.read
    .format("org.neo4j.spark.DataSource")
    .option("url", "bolt://your-neo4j-host:7687")
    .option("authentication.type", "basic")
    .option("authentication.basic.username", "neo4j")
    .option("authentication.basic.password",
            dbutils.secrets.get(scope="neo4j", key="password"))
    .option("query", "MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 100")
    .load()
)
```

### 4. Write data back to Neo4j

```python
(
    df.write
    .format("org.neo4j.spark.DataSource")
    .option("url", "bolt://your-neo4j-host:7687")
    .option("authentication.type", "basic")
    .option("authentication.basic.username", "neo4j")
    .option("authentication.basic.password",
            dbutils.secrets.get(scope="neo4j", key="password"))
    .option("labels", ":Transaction")
    .option("node.keys", "transaction_id")
    .mode("Overwrite")
    .save()
)
```

---

## Connecting Databricks to Elasticsearch

### 1. Elasticsearch Spark Connector

Add to cluster config:

```
spark.jars.packages org.elasticsearch:elasticsearch-spark-30_2.12:8.17.0
```

### 2. Read an index

```python
df = (
    spark.read
    .format("es")
    .option("es.nodes", "your-es-host")
    .option("es.port", "9200")
    .option("es.net.ssl", "false")
    .load("your-index-name")
)

display(df)
```

### 3. Write to an index

```python
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

## Setting Up Databricks Secrets

All external credentials should be stored in Databricks secrets, never hardcoded.

```bash
# Install Databricks CLI
pip install databricks-cli

# Configure authentication
databricks configure --token
# Enter your workspace URL and personal access token

# Create scopes for each service
databricks secrets create-scope kafka
databricks secrets create-scope postgres
databricks secrets create-scope neo4j
databricks secrets create-scope elasticsearch

# Store credentials
databricks secrets put-secret kafka bootstrap-servers --string-value "your-host:9092"
databricks secrets put-secret postgres password --string-value "your-password"
databricks secrets put-secret neo4j password --string-value "your-password"
```

Use in notebooks:

```python
bootstrap = dbutils.secrets.get(scope="kafka", key="bootstrap-servers")
pg_pass = dbutils.secrets.get(scope="postgres", key="password")
neo4j_pass = dbutils.secrets.get(scope="neo4j", key="password")
```

---

## Local Ports Reference

| Service | Internal Port | External Port | Protocol |
|---|---|---|---|
| Caddy (HTTP) | 80 | 10800 | HTTP |
| Caddy (HTTPS) | 443 | 10443 | HTTPS |
| PostgreSQL | 5432 | 15432 | TCP |
| Redis | 6379 | 16379 | TCP |
| Kafka | 9092 | 9092 | TCP |
| Neo4j Browser | 7474 | 7474 | HTTP |
| Neo4j Bolt | 7687 | 7687 | TCP |
| Elasticsearch | 9200 | 9200 | HTTP |
| App (internal) | 8000 | - | HTTP |
| Spark Generator (internal) | 8003 | - | HTTP |
| OCR Service (internal) | 8002 | - | HTTP |
