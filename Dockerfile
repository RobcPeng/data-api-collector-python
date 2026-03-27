FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY pyproject.toml uv.lock ./

# Install uv and dependencies
RUN pip install uv
RUN uv sync --frozen

# Copy application code
COPY . .

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Expose port
EXPOSE 8000

# Run the application
ENTRYPOINT ["/docker-entrypoint.sh"]