#!/usr/bin/env bash
# =============================================================================
# Generate a .env file with strong random secrets from .env.example
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

ENV_FILE="$PROJECT_DIR/.env"
EXAMPLE_FILE="$PROJECT_DIR/.env.example"

if [[ -f "$ENV_FILE" ]]; then
    echo "WARNING: .env already exists."
    read -p "Overwrite? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
fi

if [[ ! -f "$EXAMPLE_FILE" ]]; then
    echo "ERROR: .env.example not found at $EXAMPLE_FILE"
    exit 1
fi

# Generate strong random values
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
NEO4J_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
POSTGRES_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")

# Copy template
cp "$EXAMPLE_FILE" "$ENV_FILE"

# Replace placeholder values with generated secrets
sed -i "s|your-secret-key-change-this-in-production|$SECRET_KEY|g" "$ENV_FILE"
sed -i "s|your-neo4j-password|$NEO4J_PASSWORD|g" "$ENV_FILE"
sed -i "s|dataapi123|$POSTGRES_PASSWORD|g" "$ENV_FILE"

echo ""
echo "Generated .env with strong secrets:"
echo "  SECRET_KEY     = $SECRET_KEY"
echo "  NEO4J_PASSWORD = $NEO4J_PASSWORD"
echo "  POSTGRES_PASS  = $POSTGRES_PASSWORD"
echo ""
echo "Review $ENV_FILE and adjust host/port values for your environment."
echo "Then run: docker compose up -d"
