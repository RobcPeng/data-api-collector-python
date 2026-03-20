FROM python:3.13-slim

RUN apt-get update && apt-get install -y \
    gcc \
    default-jre-headless \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64

WORKDIR /spark_app

COPY pyproject.toml uv.lock ./

RUN pip install uv
RUN uv sync --frozen

COPY . .

EXPOSE 8003

CMD ["uv", "run", "uvicorn", "spark_generator.main:app", "--host", "0.0.0.0", "--port", "8003"]
