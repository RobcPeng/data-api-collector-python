FROM python:3.13-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    curl \
    gcc \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY pyproject.toml uv.lock ./

# Install uv and dependencies
RUN pip install uv

WORKDIR /ocr_app

# Install Python dependencies
RUN uv sync --frozen

# Copy the application code
COPY . .

# Expose the port the app runs on
EXPOSE 8002

# Run the application
CMD ["uv", "run", "uvicorn", "ocr_service.main:app", "--host", "0.0.0.0", "--port", "8002"]