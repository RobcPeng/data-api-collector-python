# Data API Collector

A lightweight, high-performance service for sandboxing ingestions for data pipelines and storing it in PostgreSQL.

[![Python 3.13](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/downloads/release/python-3130/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116.1-green.svg)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0.43-blue.svg)](https://www.sqlalchemy.org/)

## Features

- Collects and records Kafka events in a PostgreSQL database
- Provides APIs to produce and consume Kafka messages
- Implements database migration with Alembic
- Supports Redis for caching capabilities
- Containerized setup with Docker Compose

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
# Edit .env with your settings

# Start services with Docker Compose
docker-compose up -d
```

### Manual Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install .

# Apply database migrations
alembic upgrade head

# Run the application
uvicorn app.main:app --reload
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
curl -X POST http://localhost:8000/test/kafka/producer/send-message \
  -H "Content-Type: application/json" \
  -d '{"topic_name": "test-topic", "topic_message": "Hello World", "source": "test-user"}'
```

Retrieve stored messages:

```bash
curl http://localhost:8000/test/events/kafka
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
