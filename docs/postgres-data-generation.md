# PostgreSQL Data Generation: How It Works

This guide explains how the system populates PostgreSQL with relational data — the table schemas, how data is generated and bulk-inserted, and how to read it from Databricks via JDBC or Lakehouse Federation.

## Table of Contents

- [Architecture](#architecture)
- [Two Kinds of Postgres Data](#two-kinds-of-postgres-data)
- [How SLED Population Works](#how-sled-population-works)
- [SLED Use Cases — Table Schemas](#sled-use-cases--table-schemas)
  - [Student Enrollment](#student-enrollment)
  - [Grant & Budget](#grant--budget)
  - [Citizen Services](#citizen-services)
  - [K-12 Early Warning](#k-12-early-warning)
  - [Procurement](#procurement)
  - [Case Management](#case-management)
- [Custom Table Generators](#custom-table-generators)
- [Kafka Event Logging](#kafka-event-logging)
- [Reading from Databricks](#reading-from-databricks)
- [Database Internals](#database-internals)

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  FastAPI App Container                                            │
│                                                                   │
│  Three ways data enters PostgreSQL:                               │
│                                                                   │
│  1. Kafka produce/consume   2. SLED populate       3. Custom      │
│     events auto-logged         endpoints              generators  │
│     ┌─────────────┐         ┌─────────────┐       ┌────────────┐ │
│     │kafka.py     │         │sled.py      │       │custom_     │ │
│     │ produce msg │         │ /populate   │       │generators  │ │
│     │ → log to    │         │ → bulk      │       │.py         │ │
│     │   PG table  │         │   insert    │       │ → DDL +    │ │
│     └──────┬──────┘         └──────┬──────┘       │   insert   │ │
│            │                       │              └─────┬──────┘ │
│            │    SQLAlchemy         │   SQLAlchemy text() │        │
│            ▼                       ▼                    ▼        │
│     ┌──────────────────────────────────────────────────────┐     │
│     │                  PostgreSQL :15432                    │     │
│     │                                                      │     │
│     │  kafka_event_logs  │  sled_*  tables  │  custom_*    │     │
│     └──────────────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────┘
```

## Two Kinds of Postgres Data

### 1. Operational data (automatic)

Every Kafka message you produce through the API is automatically logged to the `kafka_event_logs` table. This happens as a side effect of the produce endpoint — it's an audit trail.

### 2. Generated data (on-demand)

When you call a SLED populate endpoint or start a custom generator, the system bulk-inserts synthetic data into purpose-built tables. This is the data you'd use for demos, POCs, and Databricks integration testing.

## How SLED Population Works

When you POST to `/data-sources/sled/{use_case}/populate`, here's what happens:

### Step 1: Create tables (idempotent)

The system runs `CREATE TABLE IF NOT EXISTS` for all tables needed by the use case. This means:
- First call: tables are created
- Subsequent calls: tables already exist, data is appended
- No Alembic migration needed — tables are managed by the endpoint code

```sql
CREATE TABLE IF NOT EXISTS sled_students (
    student_id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100),
    email VARCHAR(100),
    enrollment_year INT,
    campus VARCHAR(50),
    gpa DECIMAL(3,2),
    total_credits INT,
    status VARCHAR(20),
    major VARCHAR(100),
    advisor VARCHAR(100),
    state VARCHAR(2)
);
```

### Step 2: Generate data in Python

Data is generated using Python's `random` module with helper functions:

```python
# Helpers used across all use cases
def _rand_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def _rand_date(start="2020-01-01", end="2025-12-31"):
    # Returns a random date between start and end

def _rand_id(prefix, width):
    return f"{prefix}{random.randint(1, 10**width):0{width}d}"
```

The name pools contain 72 first names and 72 last names (5,184 possible combinations), plus 20 street names, 20 cities, and all 50 US state abbreviations.

### Step 3: Bulk insert in batches

Data is inserted using parameterized SQL in batches of 1,000 rows:

```python
def _pg_insert_batch(session, table_name, columns, rows):
    """Insert a batch of rows using SQLAlchemy text() execution."""
    placeholders = ", ".join([f":{col}" for col in columns])
    col_list = ", ".join(columns)
    query = text(f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})")

    for batch in _chunk(rows, 1000):
        session.execute(query, batch)
    session.commit()
```

Why batch inserts instead of individual INSERTs?
- **Network round trips**: 1,000 rows in one query = 1 round trip. 1,000 individual INSERTs = 1,000 round trips.
- **Transaction overhead**: Each INSERT has commit overhead. Batching amortizes it.
- **Speed**: Inserting 10,000 rows in batches of 1,000 takes ~1 second. Individual INSERTs would take ~30 seconds.

### Step 4: Background execution

Population runs as an asyncio background task so the API responds immediately with a job ID. You can check progress via the status endpoint.

```
POST /sled/student_enrollment/populate  →  {"job_id": "abc123", "status": "running"}
GET  /sled/student_enrollment/status    →  {"counts": {"sled_students": 5000, ...}}
```

## SLED Use Cases — Table Schemas

Each use case creates 2-3 normalized tables. Tables are prefixed with `sled_` to avoid colliding with any existing tables.

### Student Enrollment

**3 tables:**

**`sled_students`** — One row per student

| Column | Type | Example | Notes |
|--------|------|---------|-------|
| student_id | VARCHAR(20) PK | STU-00042 | Unique student identifier |
| name | VARCHAR(100) | Maria Johnson | Random from name pool |
| email | VARCHAR(100) | student42@university.edu | |
| enrollment_year | INT | 2023 | 2019–2025 |
| campus | VARCHAR(50) | Main | Main, North, Online, Downtown, West |
| gpa | DECIMAL(3,2) | 3.42 | 1.5–4.0 |
| total_credits | INT | 87 | 0–150 |
| status | VARCHAR(20) | active | active, graduated, withdrawn, on_leave |
| major | VARCHAR(100) | Computer Science | From 18 departments |
| advisor | VARCHAR(100) | James Smith | Random name |
| state | VARCHAR(2) | CA | US state abbreviation |

**`sled_courses`** — One row per course offering

| Column | Type | Example |
|--------|------|---------|
| course_id | VARCHAR(20) PK | CRS-0142 |
| name | VARCHAR(200) | Introduction to Biology |
| department | VARCHAR(100) | Biology |
| level | INT | 200 | 100-level through 500-level |
| credits | INT | 3 |
| max_enrollment | INT | 35 |
| semester | VARCHAR(20) | Fall 2024 |
| instructor | VARCHAR(100) | Emily Davis |
| delivery_mode | VARCHAR(20) | in_person | in_person, online, hybrid |

**`sled_enrollment_events`** — One row per enrollment action (the transaction table)

| Column | Type | Example |
|--------|------|---------|
| event_id | VARCHAR(40) PK | uuid |
| student_id | VARCHAR(20) FK | STU-00042 |
| course_id | VARCHAR(20) FK | CRS-0142 |
| action | VARCHAR(20) | enroll | enroll, drop, transfer, grade_posted, waitlist |
| semester | VARCHAR(20) | Fall 2024 |
| grade | VARCHAR(5) | B+ |
| credits | INT | 3 |
| campus | VARCHAR(50) | Main |
| gpa_impact | DECIMAL(4,2) | 0.3 |
| event_timestamp | TIMESTAMP | 2024-10-15 14:32:00 |

This three-table design follows a common pattern: **entity tables** (students, courses) hold relatively stable attributes, while the **event table** captures actions over time. This lets you do time-series analysis (enrollment trends by semester) and entity-level analysis (student GPA trajectory) from the same dataset.

### Grant & Budget

**3 tables:**

- **`sled_budget_transactions`** — Financial transaction events (allocation, expenditure, transfer, reimbursement). Includes fund_source_id, agency_id, program_id, vendor_id, amount, fiscal_year, quarter, cost_center, account_code.
- **`sled_agencies`** — Government agencies with type (state, county, municipal, federal), jurisdiction, employee count, annual budget.
- **`sled_vendors`** — Vendors with diversity flags (minority_owned, small_business, woman_owned), DUNS numbers, annual revenue.

### Citizen Services

**3 tables:**

- **`sled_service_requests`** — 311 service requests with request_type (pothole_repair, streetlight_outage, etc.), status lifecycle, priority, geo coordinates, response_time_hours, satisfaction_rating.
- **`sled_citizens`** — Registered citizens with district, preferred_language, registration date.
- **`sled_assets`** — Municipal assets (streetlights, road segments, etc.) with condition, install year, replacement cost.

### K-12 Early Warning

**3 tables:**

- **`sled_k12_events`** — Student risk events (attendance, discipline, assessment) with risk_score_delta, intervention_type.
- **`sled_k12_students`** — Students with GPA, attendance_rate, behavior_incidents_ytd, risk_score, and demographic flags (free_reduced_lunch at 45%, english_learner at 15%, special_education at 13% — based on national averages).
- **`sled_schools`** — Schools with type (elementary/middle/high), enrollment, Title I status, graduation rate.

### Procurement

**2 tables:**

- **`sled_procurement_events`** — Procurement lifecycle events (rfp_posted → bid_submitted → contract_awarded → invoice_paid). Includes procurement method, commodity code, diversity flags.
- **`sled_contracts`** — Contracts with status, value, duration, payment terms.

### Case Management

**3 tables:**

- **`sled_case_events`** — Case lifecycle events (intake, referral, eligibility_determination, benefit_disbursement, closure). Includes program (SNAP, Medicaid, TANF, etc.), household_size, income_bracket, determination.
- **`sled_clients`** — Clients with demographics, household size, veteran/disabled status, primary language.
- **`sled_cases`** — Cases with caseworker assignment, status, priority, benefit amount.

## Custom Table Generators

For ad-hoc demos, define table schemas and column generation rules via JSON:

```python
resp = requests.post(f"{API}/data-sources/custom/start", headers=HEADERS, json={
    "name": "survey",
    "table_name": "survey_responses",      # Will be created as custom_survey_responses
    "num_records": 10000,
    "drop_existing": True,                  # Drop and recreate the table
    "columns": [
        {"name": "response_id", "sql_type": "VARCHAR(40)", "primary_key": True,
         "generator_rule": {"generator": "uuid"}},
        {"name": "respondent", "sql_type": "VARCHAR(100)",
         "generator_rule": {"generator": "name"}},
        {"name": "score", "sql_type": "INT",
         "generator_rule": {"generator": "range_int", "min": 1, "max": 10}},
        {"name": "category", "sql_type": "VARCHAR(20)",
         "generator_rule": {"generator": "choice",
                            "values": ["positive", "neutral", "negative"],
                            "weights": [5, 3, 2]}},
        {"name": "submitted_at", "sql_type": "DATE",
         "generator_rule": {"generator": "date", "start": "2024-01-01", "end": "2025-12-31"}},
    ],
})
```

Tables are auto-prefixed with `custom_` to prevent collisions. You can inspect the schema and sample rows after generation:

```python
requests.get(f"{API}/data-sources/custom/{job_id}/schema", headers=HEADERS).json()
requests.get(f"{API}/data-sources/custom/{job_id}/sample?limit=5", headers=HEADERS).json()
```

## Kafka Event Logging

Every message produced through the Kafka API is automatically logged to PostgreSQL:

```
POST /kafka/producer/send-message
  → Produces message to Kafka topic
  → Inserts row into kafka_event_logs table
```

**`kafka_event_logs` table** (managed by Alembic migrations):

| Column | Type | Description |
|--------|------|-------------|
| id | INT PK | Auto-incrementing |
| event_type | VARCHAR(255) | Always "send-message" for produce events |
| user_id | VARCHAR(255) | The `source` field from the request |
| topic_name | VARCHAR(255) | Kafka topic the message was sent to |
| topic_message | TEXT | The message content |
| created_at | TIMESTAMP | Auto-set to `now()` |

This dual-write pattern (Kafka + Postgres) means you have both a real-time stream (Kafka) and a queryable audit log (Postgres) of the same events. You can use the Postgres table to verify what was produced, debug message ordering, or build dashboards on production volume.

## Reading from Databricks

### Option 1: JDBC (direct connection)

```python
pg_host = dbutils.secrets.get(scope="postgres", key="host")
pg_pass = dbutils.secrets.get(scope="postgres", key="password")

# Read a SLED table
students_df = (
    spark.read
    .format("jdbc")
    .option("url", f"jdbc:postgresql://{pg_host}:15432/data_collector")
    .option("dbtable", "sled_students")
    .option("user", "dataapi")
    .option("password", pg_pass)
    .option("driver", "org.postgresql.Driver")
    .load()
)

# For SSL connections (port 15433)
students_df = (
    spark.read
    .format("jdbc")
    .option("url", f"jdbc:postgresql://{pg_host}:15433/data_collector?ssl=true&sslmode=require")
    .option("dbtable", "sled_students")
    .option("user", "dataapi")
    .option("password", pg_pass)
    .option("driver", "org.postgresql.Driver")
    .load()
)
```

**JDBC tips:**
- Use `dbtable` for full table reads, or `query` for filtered reads with pushdown:
  ```python
  .option("query", "SELECT * FROM sled_students WHERE gpa > 3.5 AND campus = 'Main'")
  ```
- For large tables, add partitioning to parallelize reads:
  ```python
  .option("partitionColumn", "enrollment_year")
  .option("lowerBound", "2019")
  .option("upperBound", "2026")
  .option("numPartitions", "4")
  ```

### Option 2: Lakehouse Federation (Unity Catalog)

Lakehouse Federation lets you query Postgres through Unity Catalog without writing JDBC code. It's the recommended approach for governed, production-like access.

```sql
-- One-time setup: create a foreign connection
CREATE CONNECTION postgres_conn
TYPE POSTGRESQL
OPTIONS (
    host '<your-host>',
    port '15432',
    user 'dataapi',
    password secret('postgres', 'password')
);

-- Create a foreign catalog (maps Postgres databases into UC)
CREATE FOREIGN CATALOG postgres_data
USING CONNECTION postgres_conn
OPTIONS (database 'data_collector');

-- Now query directly — no JDBC boilerplate
SELECT * FROM postgres_data.public.sled_students LIMIT 10;

-- Join across SLED tables
SELECT
    s.name, s.gpa, s.campus,
    COUNT(e.event_id) AS enrollment_count,
    AVG(e.gpa_impact) AS avg_gpa_impact
FROM postgres_data.public.sled_students s
JOIN postgres_data.public.sled_enrollment_events e ON s.student_id = e.student_id
GROUP BY s.name, s.gpa, s.campus
ORDER BY enrollment_count DESC
LIMIT 20;
```

## Database Internals

### Connection setup

PostgreSQL is configured via environment variables in `.env`:

```
POSTGRES_USER=dataapi
POSTGRES_PASSWORD=<generated>
POSTGRES_DB=data_collector
```

The app connects via SQLAlchemy with a connection pool:

```python
# app/core/database.py
engine = create_engine(settings.DATABASE_URL)  # postgresql://dataapi:***@postgres:5432/data_collector
SessionLocal = sessionmaker(bind=engine)
```

### Ports

| Port | Binding | SSL | Use case |
|------|---------|-----|----------|
| 15432 | localhost only | No | Local development, internal Docker access |
| 15433 | All interfaces | Yes (Let's Encrypt) | External access from Databricks |

### Migrations

The `kafka_event_logs` table (and any future schema changes) is managed by Alembic:

```bash
# Create a new migration
alembic revision --autogenerate -m "add new column"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

Migrations run automatically on container start via `startup.sh`. The SLED tables (`sled_*`) and custom tables (`custom_*`) are **not** managed by Alembic — they're created dynamically by the endpoint code with `CREATE TABLE IF NOT EXISTS`.
