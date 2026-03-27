#!/bin/bash
set -e

echo "🚀 Starting Data API Collector..."

# Wait for database to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
while ! nc -z postgres 5432; do
  sleep 1
done
echo "✅ PostgreSQL is ready!"

# Run database migrations
echo "🔄 Running database migrations..."
uv run alembic upgrade head
echo "✅ Database migrations completed!"

# Start the application
echo "🚀 Starting FastAPI application..."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000