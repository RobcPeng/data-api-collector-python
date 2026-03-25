#!/bin/bash
set -euo pipefail

# =============================================================================
# Data API Collector — EC2 Bootstrap Script
# =============================================================================
# This runs once on first boot via cloud-init user_data.
# Installs Docker, clones the repo, generates secrets, and starts the stack.
# =============================================================================

exec > /var/log/data-api-collector-setup.log 2>&1
echo "=== Data API Collector setup started at $(date) ==="

# --------------------------------------------------------------------------
# Install Docker
# --------------------------------------------------------------------------
apt-get update -y
apt-get install -y ca-certificates curl gnupg git

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

apt-get update -y
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

systemctl enable docker
systemctl start docker

# Allow ubuntu user to run docker without sudo
usermod -aG docker ubuntu

# --------------------------------------------------------------------------
# Clone repository
# --------------------------------------------------------------------------
cd /opt
git clone --branch "${git_branch}" "${git_repo}" data-api-collector
cd data-api-collector

# --------------------------------------------------------------------------
# Generate environment file with strong secrets
# --------------------------------------------------------------------------
if [[ -f ./scripts/setup-env.sh ]]; then
    chmod +x ./scripts/setup-env.sh
    ./scripts/setup-env.sh
else
    cp .env.example .env
    # Generate random secrets
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
    NEO4J_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
    POSTGRES_PASSWORD=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")

    sed -i "s|SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|" .env
    sed -i "s|NEO4J_PASSWORD=.*|NEO4J_PASSWORD=$NEO4J_PASSWORD|" .env
    sed -i "s|POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$POSTGRES_PASSWORD|" .env
fi

# Set the external hostname to the EC2 public IP
TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
PUBLIC_IP=$(curl -s -H "X-aws-ec2-metadata-token: $TOKEN" http://169.254.169.254/latest/meta-data/public-ipv4 || echo "localhost")

if [[ -n "$PUBLIC_IP" && "$PUBLIC_IP" != "localhost" ]]; then
    sed -i "s|KAFKA_EXTERNAL_HOST=.*|KAFKA_EXTERNAL_HOST=$PUBLIC_IP|" .env
fi

# --------------------------------------------------------------------------
# Start the stack
# --------------------------------------------------------------------------
docker compose up -d

# --------------------------------------------------------------------------
# Wait for services and run health check
# --------------------------------------------------------------------------
echo "Waiting for services to start..."
sleep 30

if docker compose ps | grep -q "Up"; then
    echo "=== Stack is running ==="
    docker compose ps
else
    echo "=== WARNING: Some services may not have started ==="
    docker compose ps
    docker compose logs --tail 20
fi

# Create a convenience script for the ubuntu user
cat > /home/ubuntu/data-api-info.sh << 'INFOEOF'
#!/bin/bash
cd /opt/data-api-collector
source .env
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "localhost")
echo ""
echo "====================================="
echo "  Data API Collector"
echo "====================================="
echo ""
echo "  API:      http://$PUBLIC_IP:10800"
echo "  API Key:  $SECRET_KEY"
echo "  Neo4j:    http://$PUBLIC_IP:7474  (user: neo4j, pass: $NEO4J_PASSWORD)"
echo "  Postgres: $PUBLIC_IP:15433        (user: dataapi, pass: $POSTGRES_PASSWORD)"
echo "  Kafka:    $PUBLIC_IP:9094         (SASL)"
echo ""
echo "  Test:     cd /opt/data-api-collector && ./tests/test_services.sh health"
echo ""
INFOEOF
chmod +x /home/ubuntu/data-api-info.sh
chown ubuntu:ubuntu /home/ubuntu/data-api-info.sh

echo "=== Data API Collector setup completed at $(date) ==="
