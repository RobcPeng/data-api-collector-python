# Data API Collector

A lightweight, high-performance service for sandboxing ingestions/orchestrating data pipelines.

## Features

- Collects and records Kafka events in a PostgreSQL database
- Provides APIs to produce and consume Kafka messages
- Provides APIs for set/get of redis
- Containerized PostGRES/redis/Zookeeper&Kafka for quick stand up

## Prerequisites

- Python 3.13+
- PostgreSQL
- Redis
- Kafka & Zookeeper

## Setup

### Using Docker

The easiest way to get started is with Docker Compose:

```bash
# Clone the repository
git clone https://github.com/yourusername/data-api-collector.git
cd data-api-collector

# Create your environment file
cp .env.example .env

# maybe update 'your-hardcoded-api-key-here' in Caddyfile

# Edit .env with your settings

#might need to clear kafka volumes :X
docker volume rm $(docker volume ls -q | grep -E "(kafka|zookeeper)")

# Start services with Docker Compose
docker-compose up -d


```

## Database Migrations

This project uses Alembic for database migrations:

```bash
# Create a new migration
alembic revision --autogenerate -m "your migration message"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1
```

## API Endpoints

**Base URL:** `http://localhost:8080` (assuming Caddy is running on port 8080)

## Core Application Endpoints

### Health & Status

- `GET /` - Root endpoint with API information
- `GET /health` - Health check endpoint (handled by Caddy)

```bash
# Test root endpoint
curl "http://localhost:8080/"

# Test health check
curl "http://localhost:8080/health"
```

## Database Operations

### Database Connection Tests

- `GET /data-sources/test/orm` - Test SQLAlchemy ORM connection
- `GET /data-sources/test/raw/sql` - Test raw SQL connection
- `GET /data-sources/test/connection-info` - View database connection pool info

```bash
# Test ORM connection
curl "http://localhost:8080/data-sources/test/orm"

# Test raw SQL connection
curl "http://localhost:8080/data-sources/test/raw/sql"

# Check database connection pool info
curl "http://localhost:8080/data-sources/test/connection-info"
```

## Kafka Operations

### Message Production

- `POST /kafka/test/producer/send-message` - Send a message to Kafka topic
- `POST /kafka/test/producer/send-message-old-flush` - Send message with old flush method

```bash
# Send a message to Kafka
curl -X POST "http://localhost:8080/kafka/test/producer/send-message" \
  -H "Content-Type: application/json" \
  -d '{
    "topic_name": "user-events",
    "topic_message": "User logged in",
    "source": "auth-service"
  }'

# Send JSON message to Kafka
curl -X POST "http://localhost:8080/kafka/test/producer/send-message" \
  -H "Content-Type: application/json" \
  -d '{
    "topic_name": "api-events",
    "topic_message": "{\"event\": \"api_call\", \"endpoint\": \"/users\", \"timestamp\": \"2025-09-10T10:30:00Z\"}",
    "source": "api-gateway"
  }'
```

### Message Consumption

- `GET /kafka/test/consume/consume-message` - Consume messages from a Kafka topic

```bash
# Consume messages from a topic (default 5 messages)
curl "http://localhost:8080/kafka/test/consume/consume-message?topic_name=user-events"

# Consume specific number of messages
curl "http://localhost:8080/kafka/test/consume/consume-message?topic_name=api-events&message_limit=10"
```

### Event History

- `GET /kafka/test/events` - Retrieve stored Kafka events from database

```bash
# Get all Kafka events
curl "http://localhost:8080/kafka/test/events"

# Get events with pagination
curl "http://localhost:8080/kafka/test/events?skip=0&limit=20"

# Filter events by topic
curl "http://localhost:8080/kafka/test/events?topic_name=user-events"

# Filter events by user/source
curl "http://localhost:8080/kafka/test/events?user_id=auth-service&limit=10"

# Filter by both topic and user
curl "http://localhost:8080/kafka/test/events?topic_name=api-events&user_id=api-gateway"
```

## Redis Operations

### Redis Connection & Basic Operations

- `GET /redis/test` - Test basic Redis connection
- `POST /redis/test/set` - Store data in Redis
- `GET /redis/test/get` - Retrieve data from Redis

```bash
# Test Redis connection
curl "http://localhost:8080/redis/test"

# Store a simple string value
curl -X POST "http://localhost:8080/redis/test/set" \
  -H "Content-Type: application/json" \
  -d '{
    "key_store": "user_session",
    "value": "abc123xyz"
  }'

# Store JSON data
curl -X POST "http://localhost:8080/redis/test/set" \
  -H "Content-Type: application/json" \
  -d '{
    "key_store": "user_profile",
    "value": {
      "user_id": 12345,
      "name": "John Doe",
      "role": "admin",
      "last_login": "2025-09-10T10:30:00Z"
    }
  }'

# Store array data
curl -X POST "http://localhost:8080/redis/test/set" \
  -H "Content-Type: application/json" \
  -d '{
    "key_store": "user_permissions",
    "value": ["read", "write", "delete", "admin"]
  }'

# Retrieve stored data
curl "http://localhost:8080/redis/test/get?key_store=user_session"
curl "http://localhost:8080/redis/test/get?key_store=user_profile"
curl "http://localhost:8080/redis/test/get?key_store=user_permissions"
```

## Protected Endpoints (API Key Required)

Some endpoints under `/test/*` require API key authentication:

```bash
# Access protected test endpoints with API key
curl -H "X-Api-Key: api-key-here" "http://localhost:8080/test/orm"
curl -H "X-Api-Key: api-key-here" "http://localhost:8080/test/raw/sql"
```

## Elasticsearch Operations (Protected)

- `GET /elasticsearch/*` - Access Elasticsearch endpoints (requires API key)

```bash
# Access Elasticsearch cluster info (requires API key)
curl -H "X-Api-Key: api-key-here" "http://localhost:8080/elasticsearch/"

# Check Elasticsearch health
curl -H "X-Api-Key: api-key-here" "http://localhost:8080/elasticsearch/_health"
```

## API Documentation

- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation (ReDoc)
- `GET /openapi.json` - OpenAPI schema

```bash
# View API schema
curl "http://localhost:8080/openapi.json"
```

## Testing Workflows

### Complete System Test

```bash
#!/bin/bash
# Complete API test workflow

echo "Testing API health..."
curl "http://localhost:8080/health"

echo -e "\nTesting database..."
curl "http://localhost:8080/data-sources/test/orm"

echo -e "\nTesting Redis..."
curl "http://localhost:8080/redis/test"

echo -e "\nStoring data in Redis..."
curl -X POST "http://localhost:8080/redis/test/set" \
  -H "Content-Type: application/json" \
  -d '{"key_store": "test_key", "value": "API test successful"}'

echo -e "\nRetrieving data from Redis..."
curl "http://localhost:8080/redis/test/get?key_store=test_key"

echo -e "\nSending message to Kafka..."
curl -X POST "http://localhost:8080/kafka/test/producer/send-message" \
  -H "Content-Type: application/json" \
  -d '{"topic_name": "test-topic", "topic_message": "API test message", "source": "test-script"}'

echo -e "\nChecking Kafka events..."
curl "http://localhost:8080/kafka/test/events?limit=5"

echo -e "\nAPI test completed!"
```

### Load Testing Example

```bash
# Send multiple messages rapidly
for i in {1..10}; do
  curl -X POST "http://localhost:8080/kafka/test/producer/send-message" \
    -H "Content-Type: application/json" \
    -d "{\"topic_name\": \"load-test\", \"topic_message\": \"Message $i\", \"source\": \"load-test\"}"
  sleep 0.1
done

# Check all events
curl "http://localhost:8080/kafka/test/events?topic_name=load-test"
```

## Project Structure

```
data-api-collector/
├── docker-compose.yml          # Docker services configuration
├── Caddyfile                  # Reverse proxy and API key auth
├── .env                       # Environment variables
├── Dockerfile                 # Application container build
├── requirements.txt           # Python dependencies
├── startup.sh                # Container startup script
├── app/
│   ├── main.py               # FastAPI application entry point
│   ├── core/
│   │   ├── config.py         # Settings and configuration
│   │   └── database.py       # Database connection setup
│   ├── models/
│   │   └── events.py         # SQLAlchemy models
│   ├── schemas/
│   │   └── events.py         # Pydantic schemas
│   └── api/
│       └── endpoints/
│           ├── __init__.py   # Router aggregation
│           ├── data_sources.py  # Database testing endpoints
│           ├── kafka.py      # Kafka operations
│           └── redis.py      # Redis operations
├── migrations/               # Alembic database migrations
└── volumes/                  # Persistent data storage
    ├── postgres_data/
    ├── redis_data/
    ├── kafka_data/
    └── elasticsearch_data/
```

## Response Formats

All endpoints return JSON responses with consistent structure:

### Success Response

```json
{
  "status": "success",
  "data": { ... },
  "message": "Optional message"
}
```

### Error Response

```json
{
  "status": "error",
  "message": "Error description"
}
```

### Kafka Events Response

```json
{
  "total": 25,
  "events": [
    {
      "id": 1,
      "event_type": "send-message",
      "user_id": "auth-service",
      "topic_name": "user-events",
      "message": "User logged in",
      "timestamp": "2025-09-10T10:30:00Z"
    }
  ]
}
```
