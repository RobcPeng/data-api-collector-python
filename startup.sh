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

# Wait for Kafka to be ready (with timeout)
# echo "⏳ Waiting for Kafka to be ready..."
# kafka_ready=0
# for i in {1..60}; do
#   if nc -z kafka 9092; then
#     kafka_ready=1
#     break
#   fi
#   echo "Kafka not ready, waiting... ($i/60)"
#   sleep 2
# done

# if [ $kafka_ready -eq 1 ]; then
#   echo "✅ Kafka is ready!"
# else
#   echo "⚠️  Kafka not ready after 2 minutes, continuing anyway..."
# fi



# Start the application
echo "🚀 Starting FastAPI application..."
exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000