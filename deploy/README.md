# Deployment Guide

Deploy the Data API Collector stack to the cloud or any server with Docker.

## Option 1: AWS with Terraform (Recommended)

Provisions an EC2 instance with Docker pre-installed, the repo cloned, secrets auto-generated, and the full stack running.

### Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/downloads) >= 1.0
- AWS CLI configured (`aws configure`) with permissions for EC2, VPC, and Security Groups
- An EC2 key pair in your target region (for SSH access)

### Deploy

```bash
cd deploy/aws

# Copy and edit variables
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars — at minimum set key_name and allowed_cidr_blocks

# Deploy
terraform init
terraform plan
terraform apply
```

Terraform outputs the public IP, API URL, and SSH command:

```
api_url       = "http://54.123.45.67:10800/api/v1"
neo4j_browser = "http://54.123.45.67:7474"
kafka_broker  = "54.123.45.67:9094"
postgres_jdbc = "jdbc:postgresql://54.123.45.67:15433/data_collector?ssl=true&sslmode=require"
ssh_command   = "ssh -i ~/.ssh/my-key-pair.pem ubuntu@54.123.45.67"
```

### Post-Deploy

The bootstrap script takes 2-3 minutes. Check progress:

```bash
# Watch the setup log
ssh -i ~/.ssh/my-key-pair.pem ubuntu@<PUBLIC_IP> 'tail -f /var/log/data-api-collector-setup.log'

# View credentials
ssh -i ~/.ssh/my-key-pair.pem ubuntu@<PUBLIC_IP> './data-api-info.sh'

# Run tests
ssh -i ~/.ssh/my-key-pair.pem ubuntu@<PUBLIC_IP> 'cd /opt/data-api-collector && ./tests/test_services.sh health'
```

### Configure Databricks Secrets

Once deployed, grab the credentials and store them in Databricks:

```bash
# SSH in and get credentials
ssh -i ~/.ssh/my-key-pair.pem ubuntu@<PUBLIC_IP> './data-api-info.sh'

# Store in Databricks
databricks secrets create-scope data-api
databricks secrets put-secret data-api api-key --string-value "<SECRET_KEY from output>"
databricks secrets put-secret data-api kafka-user --string-value "<KAFKA_USER>"
databricks secrets put-secret data-api kafka-password --string-value "<KAFKA_PASSWORD>"
databricks secrets put-secret data-api neo4j-password --string-value "<NEO4J_PASSWORD>"
databricks secrets put-secret data-api postgres-password --string-value "<POSTGRES_PASSWORD>"
```

### Tear Down

```bash
terraform destroy
```

### Customization

| Variable | Default | Description |
|---|---|---|
| `aws_region` | `us-east-1` | AWS region |
| `instance_type` | `t3.medium` | EC2 instance type (use t3.large if enabling ES/OCR) |
| `volume_size` | `30` | Root volume size in GB (50+ for OCR model caches) |
| `key_name` | `""` | EC2 key pair name for SSH |
| `allowed_cidr_blocks` | `["0.0.0.0/0"]` | CIDRs allowed to access the stack |
| `git_repo` | GitHub URL | Repository to clone |
| `git_branch` | `main` | Branch to deploy |
| `enable_https` | `false` | Enable Caddy auto-TLS (requires domain) |
| `domain_name` | `""` | Domain for HTTPS |

---

## Option 2: Any Cloud VM (Manual)

Works on AWS, GCP, Azure, DigitalOcean, Linode, or any VPS with Ubuntu 22.04+.

### 1. Provision a VM

- **Minimum specs**: 2 vCPU, 4 GB RAM, 30 GB disk (default stack)
- **Recommended**: 2 vCPU, 8 GB RAM, 50 GB disk (if enabling Elasticsearch or OCR profiles)
- **OS**: Ubuntu 22.04 or 24.04
- **Ports**: Open 22, 10800, 9093, 9094, 15433, 7688

### 2. Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Verify
docker --version
docker compose version
```

### 3. Clone and Start

```bash
git clone https://github.com/RobcPeng/data-api-collector-python.git
cd data-api-collector-python

# Generate .env with random secrets
./scripts/setup-env.sh

# Update the external hostname
sed -i "s|KAFKA_EXTERNAL_HOST=.*|KAFKA_EXTERNAL_HOST=$(curl -s ifconfig.me)|" .env

# Start everything
docker compose up -d

# Verify
./tests/test_services.sh health
```

### 4. View Credentials

```bash
grep -E 'SECRET_KEY|NEO4J_PASSWORD|POSTGRES_PASSWORD' .env
```

---

## Option 3: Docker Desktop (Local Development)

Run on your laptop for local development and testing.

### macOS / Windows

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)
2. Allocate at least 8 GB RAM in Docker Desktop settings

```bash
git clone https://github.com/RobcPeng/data-api-collector-python.git
cd data-api-collector-python

./scripts/setup-env.sh
docker compose up -d
./tests/test_services.sh health
```

### Expose to Databricks

From a laptop, use one of:

**zrok** (free, open source, HTTP + TCP):
```bash
# Install: https://docs.zrok.io/docs/guides/install/
curl -sSf https://get.openziti.io/install.bash | sudo bash -s zrok
zrok invite  # one-time account setup
zrok enable <token>

# Expose services (each in a separate terminal)
zrok share public http://localhost:10800                           # API (public URL)
zrok share private --backend-mode tcpTunnel 127.0.0.1:9094        # Kafka
zrok share private --backend-mode tcpTunnel 127.0.0.1:15433       # Postgres
zrok share private --backend-mode tcpTunnel 127.0.0.1:7687        # Neo4j

# On the client machine, access private shares:
zrok access private --bind 127.0.0.1:9094 <kafka-token>
zrok access private --bind 127.0.0.1:15433 <postgres-token>
zrok access private --bind 127.0.0.1:7687 <neo4j-token>
```

**SSH tunnel** (if you have a jump host):
```bash
# From the Databricks driver or your laptop
ssh -L 10800:localhost:10800 -L 9094:localhost:9094 -L 15433:localhost:15433 -L 7687:localhost:7687 user@host
```

---

## Option 4: Databricks-Hosted (Notebook-Only)

If you only need the API endpoints (not Kafka/Neo4j/Postgres directly), you can run a lightweight version on a Databricks cluster using the notebook terminal:

```python
# In a Databricks notebook
%sh
git clone https://github.com/RobcPeng/data-api-collector-python.git /tmp/data-api
cd /tmp/data-api
pip install -r requirements.txt 2>/dev/null || pip install fastapi uvicorn sqlalchemy neo4j redis confluent-kafka
```

> **Note**: This only works for the FastAPI app itself, not the full Docker stack. For Kafka, Neo4j, and Postgres you need a proper deployment (Options 1-3).

---

## Security Recommendations

| Concern | Recommendation |
|---|---|
| **Network access** | Restrict `allowed_cidr_blocks` to your IP or Databricks NAT range |
| **Credentials** | Always use `./scripts/setup-env.sh` to generate strong random secrets |
| **SSH** | Use key-based auth only, disable password auth |
| **HTTPS** | For production, set `enable_https = true` with a domain name |
| **Firewall** | Only open ports you need. For Databricks-only access: 10800, 9093, 15433 |
| **Updates** | Pull latest code and rebuild: `git pull && docker compose up -d --build` |

---

## Port Reference

| Port | Service | Protocol | Needed For |
|---|---|---|---|
| 22 | SSH | TCP | Administration |
| 10800 | Caddy (API) | HTTP | REST API, generators, SLED endpoints |
| 10443 | Caddy (HTTPS) | HTTPS | REST API (with TLS) |
| 9093 | Kafka (nginx/SSL) | TCP | Databricks Structured Streaming |
| 9094 | Kafka (SASL) | TCP | External Kafka consumers |
| 15433 | PostgreSQL (SSL) | TCP | Databricks JDBC, Lakehouse Federation |
| 7474 | Neo4j Browser | HTTP | Neo4j web UI |
| 7688 | Neo4j Bolt (nginx/TLS) | TCP | Databricks/Python Neo4j driver |
| 9200 | Elasticsearch | HTTP | Search (localhost only by default) |
