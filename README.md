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

### Kafka Operations

- `POST /test/kafka/producer/send-message` - Send a message to Kafka topic
- `GET /test/kafka/consume/consume-message` - Consume messages from a Kafka topic
- `GET /test/events/kafka` - Retrieve stored Kafka events from database

### System Tests

- `GET /test/orm` - Test ORM connection
- `GET /test/raw/sql` - Test raw SQL connection
- `GET /test/redis` - Test Redis connection
- `POST /test/redis/set` - Test Redis connection
- `GET /test/redis/get` - Test Redis connection
- `GET /test/connection-info` - View database connection info

## Project Structure

```
data-api-collector/
├── app/
│   ├── core/           # Core configuration
│   ├── models/         # Database models
│   ├── schemas/        # Pydantic schemas
│   └── main.py         # FastAPI application
├── migrations/         # Alembic migrations
├── docker-compose.yml  # Docker Compose configuration
├── pyproject.toml      # Project dependencies
└── .env.example        # Environment variables example
```

## 🧪 Example Usage

Send a message to Kafka:

```bash
curl -X POST http://localhost:{whatever}/test/kafka/producer/send-message \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: your-hardcoded-api-key-here" \
  -d '{"topic_name": "test-topic", "topic_message": "Hello World", "source": "test-user"}'
```

Retrieve stored messages:

```bash
curl http://localhost:{whatever}/test/events/kafka
  -H "X-Api-Key: your-hardcoded-api-key-here" \

```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
