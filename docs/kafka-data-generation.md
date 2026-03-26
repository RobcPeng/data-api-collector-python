# Kafka Data Generation: How It Works

This guide explains the streaming data generation pipeline — from how synthetic data is created with PySpark and dbldatagen, to how it lands on Kafka topics, and how you consume it from Databricks.

## Table of Contents

- [The Big Picture](#the-big-picture)
- [Architecture](#architecture)
- [How dbldatagen Builds Synthetic Data](#how-dbldatagen-builds-synthetic-data)
- [The Generator Lifecycle](#the-generator-lifecycle)
- [Use Cases and Their Schemas](#use-cases-and-their-schemas)
  - [Fraud Detection](#fraud-detection)
  - [Device Telemetry](#device-telemetry)
  - [Web Traffic / Clickstream](#web-traffic--clickstream)
  - [SLED Use Cases](#sled-use-cases)
- [Custom Generators](#custom-generators)
- [Consuming from Databricks](#consuming-from-databricks)
- [How Kafka Is Configured](#how-kafka-is-configured)

---

## The Big Picture

The system generates realistic streaming data by combining three technologies:

1. **PySpark** — a distributed data processing engine (running locally in the container)
2. **dbldatagen** (Databricks Labs Data Generator) — a library that uses Spark to generate synthetic data with realistic distributions
3. **confluent-kafka** — a Python Kafka producer that publishes each generated row to a topic

When you start a generator, you're kicking off a background loop that repeatedly:
1. Uses dbldatagen to generate a batch of rows as a Spark DataFrame
2. Converts each row to JSON
3. Injects a real-time `event_timestamp`
4. Publishes each JSON record to the Kafka topic

This loop runs until the timeout expires or you explicitly stop it.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  Spark Generator Container (spark-generator:8003)               │
│                                                                 │
│  ┌──────────────┐    ┌───────────────┐    ┌──────────────────┐  │
│  │  FastAPI      │    │  PySpark +    │    │  confluent-kafka │  │
│  │  /generators/ │───>│  dbldatagen   │───>│  Producer        │──┼──> Kafka :9092
│  │  start        │    │  (build DF)   │    │  (produce JSON)  │  │
│  └──────────────┘    └───────────────┘    └──────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
         ▲
         │ httpx proxy
         │
┌────────┴──────────┐
│  Main FastAPI App  │  <── User calls /api/v1/kafka/generators/start
│  (app:8000)        │
└───────────────────┘
```

The main FastAPI app doesn't run Spark itself — it proxies generator requests to a dedicated **spark-generator** container via httpx. This isolation keeps the main app lightweight and prevents Spark's JVM from interfering with other services.

### Why a separate container?

Spark starts a JVM under the hood, which takes 10-30 seconds to initialize and consumes significant memory. By isolating it:
- The main API stays responsive (no JVM startup lag)
- Spark can be independently scaled or restarted
- Memory limits are clearly separated (`512m` for Spark driver vs. the main app)

## How dbldatagen Builds Synthetic Data

[dbldatagen](https://github.com/databrickslabs/dbldatagen) is a Databricks Labs library for generating test data at scale. It runs on top of PySpark and uses Spark's distributed engine to generate rows.

### The core pattern

Every generator starts by defining a `DataGenerator` specification — a blueprint for what each row looks like:

```python
import dbldatagen as dg

spec = (
    dg.DataGenerator(spark, name="fraud_transactions", rows=100, partitions=2)
    .withColumn("transaction_id", "string", expr="uuid()")
    .withColumn("amount", "decimal(10,2)", minValue=0.50, maxValue=15000.00, random=True)
    .withColumn("currency", "string",
                values=["USD", "EUR", "GBP"],
                random=True,
                weights=[5, 2, 1])  # USD appears 5x more often than GBP
)

df = spec.build()  # Returns a Spark DataFrame with 100 rows
```

### Key generation techniques

| Technique | Example | What it does |
|-----------|---------|-------------|
| `expr` | `expr="uuid()"` | Runs a Spark SQL expression to compute the value |
| `values` + `weights` | `values=["USD","EUR"], weights=[5,1]` | Picks from a list with weighted probability |
| `minValue` / `maxValue` | `minValue=0.5, maxValue=15000` | Generates random values in a numeric range |
| `random=True` | On any column | Randomizes selection instead of sequential cycling |
| Boolean via expr | `expr="rand() < 0.05"` | Creates boolean flags with a specific probability (5% true here) |
| Computed IDs | `expr="concat('DEV-', lpad(...))"` | Builds realistic-looking identifiers |

### Why weighted distributions matter

Real data isn't uniformly distributed. In fraud detection data:
- Most payments are credit cards (Visa > Mastercard > Amex > Discover)
- Most transactions are in USD
- Most payments use chip or contactless, not swipe

The `weights` parameter controls this distribution. `weights=[5, 2, 1]` means the first value appears 5/8 of the time, the second 2/8, and the third 1/8.

## The Generator Lifecycle

```
     POST /generators/start
              │
              ▼
     ┌────────────────┐
     │  Create state   │  generator_id = random UUID prefix
     │  dict + asyncio │  status = "running"
     │  task            │
     └───────┬────────┘
             │
             ▼
    ┌────────────────────────────────────────────┐
    │           _generator_loop (async)           │
    │                                             │
    │  while status == "running":                 │
    │    1. Check timeout → break if expired      │
    │    2. _generate_batch():                    │
    │       - Build DataGenerator spec            │
    │       - spec.build() → Spark DataFrame      │
    │       - df.toJSON().collect() → list[str]   │
    │    3. For each JSON row:                    │
    │       - Inject event_timestamp (UTC ISO)    │
    │       - producer.produce(topic, json)       │
    │    4. producer.flush()                      │
    │    5. asyncio.sleep(interval)               │
    │                                             │
    └──────────────┬──────────────────────────────┘
                   │
         Timeout expires or POST /stop
                   │
                   ▼
            status = "completed" or "stopped"
```

### Key design decisions

**Thread pool offloading**: Spark operations are CPU-heavy and synchronous. The loop uses `asyncio.run_in_executor()` to offload the Spark batch generation to a thread pool, keeping the FastAPI event loop responsive for status checks and stop requests.

**Batching**: Instead of generating one row at a time, the system generates `rows_per_batch` rows (default 100) in a single Spark operation, then publishes them individually. This is much faster because:
- Spark has fixed overhead per job (task scheduling, serialization)
- Kafka producers batch internally and flush once per cycle
- dbldatagen generates millions of rows per second when given a batch

**State tracking**: Each generator's state (rows produced, elapsed time, errors) is stored in a Python dict. No database — this is intentionally ephemeral. If the container restarts, generators are gone. This is a dev/sandbox tool, not a production system.

## Use Cases and Their Schemas

### Fraud Detection

**Topic**: `streaming-fraud-transactions`

Simulates credit card transaction data for fraud detection ML models. Every record represents a single transaction.

| Column | Type | Generation | Why it matters |
|--------|------|-----------|---------------|
| `transaction_id` | string | `uuid()` | Unique identifier per transaction |
| `user_id` | integer | 1–5,000 | Simulates a pool of cardholders |
| `merchant_id` | integer | 1–500 | Simulates a pool of merchants |
| `amount` | decimal(10,2) | $0.50–$15,000 random | Transaction amount — anomaly detection targets outliers |
| `currency` | string | USD (50%), EUR (20%), GBP/CAD/AUD (10% each) | Weighted toward USD |
| `merchant_category` | string | 10 categories, uniform | grocery, electronics, gas_station, etc. |
| `payment_method` | string | chip (25%), contactless (25%), online (25%), swipe (8%), mobile (17%) | Reflects real card-present vs. card-not-present mix |
| `ip_address` | string | Random valid IPv4 | For geolocation-based fraud rules |
| `device_id` | string | Format: `dev-XXXX-XXXX` | Device fingerprint for velocity checks |
| `latitude/longitude` | decimal | Worldwide random | Geo coordinates — impossible travel detection |
| `card_type` | string | Visa (40%), MC (30%), Amex (20%), Discover (10%) | Market share distribution |

**Databricks schema for Structured Streaming:**

```python
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
```

### Device Telemetry

**Topic**: `streaming-device-telemetry`

Simulates IoT sensor data from industrial or facility monitoring systems. Each record is a single sensor reading.

| Column | Type | Generation | Why it matters |
|--------|------|-----------|---------------|
| `event_id` | string | `uuid()` | Unique event identifier |
| `device_id` | string | Format: `iot-XXXX-XXXX` | Identifies the physical sensor |
| `device_type` | string | 8 types (temperature, pressure, humidity, etc.) | Different sensors report different units |
| `reading_value` | decimal(10,4) | -50.0 to 500.0 | The actual measurement |
| `unit` | string | celsius, psi, percent, ppm, etc. | Matches device type |
| `battery_level` | decimal(5,2) | 0–100% | Low battery → maintenance alert |
| `signal_strength_dbm` | integer | -120 to -30 | RF signal quality — dead zones detection |
| `firmware_version` | string | 5 versions | Tracks firmware rollouts |
| `facility_id` | integer | 1–50 | Physical facility location |
| `latitude/longitude` | decimal | Continental US bounds | Realistic US coordinates |
| `anomaly_flag` | boolean | 5% true | Pre-labeled anomalies for supervised ML |

### Web Traffic / Clickstream

**Topic**: `streaming-web-traffic`

Simulates website clickstream data — the kind of data web analytics platforms capture. Each record is a single user interaction.

| Column | Type | Generation | Why it matters |
|--------|------|-----------|---------------|
| `event_id` | string | `uuid()` | Unique event identifier |
| `session_id` | string | Format: `sess-XXXX-XXXX-XXXX` | Groups events by user session |
| `user_id` | integer | 1–10,000 | Identifies logged-in users |
| `page_url` | string | 10 pages, weighted (/home gets 5x more traffic) | Realistic page popularity distribution |
| `referrer` | string | direct, google, facebook, etc. | Traffic source attribution |
| `user_agent` | string | Chrome, Firefox, Safari, bots | Browser/device identification |
| `ip_address` | string | Random valid IPv4 | Visitor identification |
| `country` | string | 10 countries, US-heavy (50%) | Geographic distribution |
| `device_type` | string | desktop (40%), mobile (50%), tablet (10%) | Mobile-first traffic patterns |
| `action` | string | page_view (dominant), click, scroll, purchase (rare) | Funnel analysis |
| `duration_ms` | integer | 100–30,000ms | Time on page |
| `http_status` | integer | 200 (67%), 301, 304, 400, 404, 500 | Error rate monitoring |

### SLED Use Cases

Six additional generators produce data for State, Local Government, and Higher Education scenarios:

| Use Case | Topic | Description | Key entities |
|----------|-------|-------------|-------------|
| `student_enrollment` | `streaming-student-enrollment` | University course enrollment events | Students, courses, departments |
| `grant_budget` | `streaming-grant-budget` | Government grant and budget transactions | Agencies, programs, vendors, funds |
| `citizen_services` | `streaming-citizen-services` | 311-style citizen service requests | Citizens, requests, departments, assets |
| `k12_early_warning` | `streaming-k12-early-warning` | K-12 student risk indicator events | Students, schools, teachers, interventions |
| `procurement` | `streaming-procurement` | Government procurement lifecycle events | Agencies, vendors, contracts |
| `case_management` | `streaming-case-management` | Social services case lifecycle events | Clients, cases, caseworkers, programs |

These use the same generator infrastructure as the core three. The schemas are richer — for example, `k12_early_warning` includes fields like `attendance_rate`, `gpa`, `behavior_incidents_ytd`, `risk_score`, and demographic flags (`free_reduced_lunch`, `english_learner`, `special_education`) with realistic probability distributions (45% free/reduced lunch, 15% English learners, 13% special education).

## Custom Generators

For ad-hoc use cases, you can POST a column specification as JSON — no code changes needed:

```python
requests.post(f"{API}/kafka/generators/custom/start", headers=HEADERS, json={
    "name": "iot_sensors",
    "topic_name": "custom-iot-data",
    "rows_per_batch": 50,
    "batch_interval_seconds": 2.0,
    "timeout_minutes": 15,
    "columns": [
        # Spark SQL expression: generates formatted device IDs
        {"name": "device_id", "type": "string",
         "expr": "concat('DEV-', lpad(cast(int(rand()*500+1) as string), 4, '0'))"},

        # Numeric range with random distribution
        {"name": "temp_celsius", "type": "decimal(5,2)",
         "min_value": -20.0, "max_value": 120.0, "random": True},

        # Categorical values with weighted probability
        {"name": "status", "type": "string",
         "values": ["online", "offline", "error"],
         "weights": [8, 1, 1]},
    ],
})
```

The column spec maps directly to dbldatagen's `withColumn()` API. You can also validate a spec without starting it (`/custom/validate`) to see the resolved schema and a sample row.

## Consuming from Databricks

### 1. Start a generator

```bash
curl -X POST -H "X-Api-Key: $KEY" -H "Content-Type: application/json" \
  -d '{"use_case": "fraud_detection", "rows_per_batch": 100, "timeout_minutes": 10}' \
  http://localhost:10800/api/v1/kafka/generators/start
```

### 2. Connect from Databricks Structured Streaming

The external Kafka listener uses SASL/PLAIN over SSL (nginx terminates TLS on port 9093, Kafka validates credentials on port 9094).

```python
KAFKA_HOST = "your-hostname:9093"
KAFKA_USER = dbutils.secrets.get(scope="kafka", key="username")
KAFKA_PASSWORD = dbutils.secrets.get(scope="kafka", key="password")

# Note: Databricks shades Kafka classes — use kafkashaded.org.apache.kafka
raw = (
    spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", KAFKA_HOST)
    .option("kafka.security.protocol", "SASL_SSL")
    .option("kafka.sasl.mechanism", "PLAIN")
    .option("kafka.sasl.jaas.config",
            'kafkashaded.org.apache.kafka.common.security.plain.PlainLoginModule required '
            f'username="{KAFKA_USER}" password="{KAFKA_PASSWORD}";')
    .option("subscribe", "streaming-fraud-transactions")
    .option("startingOffsets", "earliest")
    .load()
)
```

### 3. Parse JSON and write to Delta

```python
from pyspark.sql.functions import from_json, col

parsed = (
    raw.select(from_json(col("value").cast("string"), fraud_schema).alias("data"))
    .select("data.*")
)

# Write to a Delta table
(
    parsed.writeStream
    .format("delta")
    .outputMode("append")
    .option("checkpointLocation", "/Volumes/catalog/schema/checkpoints/fraud")
    .toTable("catalog.schema.fraud_transactions")
)
```

## How Kafka Is Configured

The Kafka broker runs in **KRaft mode** (no Zookeeper dependency) with three listeners:

| Listener | Port | Protocol | Audience |
|----------|------|----------|----------|
| `INTERNAL` | 9092 | Plaintext | Docker-internal services (spark-generator, FastAPI app) |
| `EXTERNAL` | 9094 | SASL/PLAIN | External clients via nginx TLS termination |
| `CONTROLLER` | 9093 (internal) | KRaft | Broker self-management |

**External access path**: Client → nginx (:9093, TLS) → Kafka (:9094, SASL/PLAIN)

SASL credentials are stored in `kafka_server_jaas.conf` (gitignored, mounted read-only into the container). Topics are auto-created when the first message is produced — no manual topic setup needed.
