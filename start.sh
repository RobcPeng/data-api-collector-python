#!/usr/bin/env bash
# =============================================================================
# Data API Collector — Interactive Setup & Start
# =============================================================================
# Single entrypoint that walks you through everything:
#   1. Checks prerequisites (Docker, python3, optionally zrok)
#   2. Generates .env with strong random secrets (or keeps existing)
#   3. Asks: local-only or zrok-exposed?
#   4. If zrok: installs, enables, and starts tunnels
#   5. Starts the Docker stack
#   6. Runs a health check
#   7. Prints a summary with all URLs and credentials
#
# Usage:
#   ./start.sh                # interactive questionnaire
#   ./start.sh --stop         # stop everything (Docker + zrok tunnels)
#   ./start.sh --status       # show what's running
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
ENV_FILE="$PROJECT_DIR/.env"
EXAMPLE_FILE="$PROJECT_DIR/.env.example"
LOG_DIR="$PROJECT_DIR/.zrok-logs"

# --- Colors ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# Strip \r from user input (prevents ^M on some terminals)
prompt()  { local _val; read -r _val; _val="${_val//$'\r'/}"; eval "$1=\$_val"; }

info()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; }
step()    { echo -e "\n${BOLD}${CYAN}── $* ──${NC}\n"; }
ask()     { echo -en "${BOLD}$*${NC} "; }

# --- zrok tunnel services ---
declare -a ZROK_SERVICES=(
    "api|public|http://localhost:10800"
    "kafka|private|127.0.0.1:9094"
    "postgres|private|127.0.0.1:15433"
    "neo4j|private|127.0.0.1:7687"
)

# =============================================================================
# Stop everything
# =============================================================================
do_stop() {
    step "Stopping Data API Collector"

    # Stop zrok tunnels
    if [[ -d "$LOG_DIR" ]]; then
        for entry in "${ZROK_SERVICES[@]}"; do
            IFS='|' read -r name _ _ <<< "$entry"
            local pid_file="$LOG_DIR/${name}.pid"
            if [[ -f "$pid_file" ]]; then
                local pid
                pid=$(cat "$pid_file")
                if kill -0 "$pid" 2>/dev/null; then
                    kill "$pid" 2>/dev/null && info "Stopped zrok tunnel: $name (PID $pid)"
                fi
                rm -f "$pid_file"
            fi
        done
    fi

    # Catch stray zrok processes
    local strays
    strays=$(pgrep -f "zrok share" 2>/dev/null || true)
    if [[ -n "$strays" ]]; then
        echo "$strays" | while read -r pid; do
            kill "$pid" 2>/dev/null && info "Stopped stray zrok process (PID $pid)"
        done
    fi

    # Stop Docker stack
    if docker compose -f "$PROJECT_DIR/docker-compose.yml" ps -q 2>/dev/null | grep -q .; then
        info "Stopping Docker stack..."
        docker compose -f "$PROJECT_DIR/docker-compose.yml" down
        info "Docker stack stopped."
    else
        info "Docker stack is not running."
    fi

    echo ""
    info "Everything stopped."
}

# =============================================================================
# Show status
# =============================================================================
do_status() {
    step "Status"

    # Docker
    echo -e "${BOLD}Docker stack:${NC}"
    if docker compose -f "$PROJECT_DIR/docker-compose.yml" ps -q 2>/dev/null | grep -q .; then
        docker compose -f "$PROJECT_DIR/docker-compose.yml" ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null
    else
        echo "  Not running."
    fi

    # zrok
    echo ""
    echo -e "${BOLD}zrok tunnels:${NC}"
    local found=false
    if [[ -d "$LOG_DIR" ]]; then
        for entry in "${ZROK_SERVICES[@]}"; do
            IFS='|' read -r name mode backend <<< "$entry"
            local pid_file="$LOG_DIR/${name}.pid"
            local log_file="$LOG_DIR/${name}.log"
            if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
                local pid share_info
                pid=$(cat "$pid_file")
                share_info=$(grep -oE 'https://[^ ]+\.zrok\.[^ ]+' "$log_file" 2>/dev/null | head -1 || true)
                if [[ -z "$share_info" ]]; then
                    share_info=$(grep -oE 'share token is [^ ]+' "$log_file" 2>/dev/null | head -1 || true)
                fi
                echo -e "  ${GREEN}RUNNING${NC}  ${CYAN}$name${NC} ($mode) — PID $pid — $share_info"
                found=true
            fi
        done
    fi
    if [[ "$found" == false ]]; then
        echo "  No zrok tunnels running."
    fi
    echo ""
}

# =============================================================================
# Check prerequisites
# =============================================================================
check_prerequisites() {
    step "Step 1: Prerequisites"

    # Docker
    if command -v docker &>/dev/null && docker compose version &>/dev/null; then
        info "Docker + Compose found ($(docker --version | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1))"
    else
        error "Docker with Compose plugin is required."
        echo "  Install: https://www.docker.com/products/docker-desktop/"
        exit 1
    fi

    # Docker running?
    if ! docker info &>/dev/null 2>&1; then
        error "Docker daemon is not running. Start Docker Desktop and try again."
        exit 1
    fi

    # python3
    if command -v python3 &>/dev/null; then
        info "python3 found ($(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+'))"
    else
        error "python3 is required (for generating secrets)."
        exit 1
    fi

    info "All prerequisites met."
}

# =============================================================================
# Generate .env
# =============================================================================
setup_env() {
    step "Step 2: Environment Configuration"

    local regenerated=false

    if [[ -f "$ENV_FILE" ]]; then
        info ".env already exists."
        ask "Regenerate secrets? (y/N)"
        prompt reply
        if [[ "$reply" =~ ^[Yy] ]]; then
            regenerated=true
        else
            info "Keeping existing .env"
        fi
    else
        regenerated=true
    fi

    if [[ "$regenerated" == true ]]; then
        if [[ ! -f "$EXAMPLE_FILE" ]]; then
            error ".env.example not found — is this the right directory?"
            exit 1
        fi

        echo "  Generating strong random secrets..."

        local secret_key neo4j_pw postgres_pw kafka_user kafka_pw
        secret_key=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
        neo4j_pw=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
        postgres_pw=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")
        kafka_user="admin"
        kafka_pw=$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")

        cp "$EXAMPLE_FILE" "$ENV_FILE"

        # Portable sed (no -i flag differences between macOS/Linux)
        sed "s|your-secret-key-change-this-in-production|$secret_key|g" "$ENV_FILE" > "$ENV_FILE.tmp" && mv "$ENV_FILE.tmp" "$ENV_FILE"
        sed "s|your-neo4j-password|$neo4j_pw|g" "$ENV_FILE" > "$ENV_FILE.tmp" && mv "$ENV_FILE.tmp" "$ENV_FILE"
        sed "s|dataapi123|$postgres_pw|g" "$ENV_FILE" > "$ENV_FILE.tmp" && mv "$ENV_FILE.tmp" "$ENV_FILE"

        # Generate Kafka SASL config (kafka_server_jaas.conf)
        local jaas_file="$PROJECT_DIR/kafka_server_jaas.conf"
        cat > "$jaas_file" <<JAAS_EOF
KafkaServer {
    org.apache.kafka.common.security.plain.PlainLoginModule required
    username="$kafka_user"
    password="$kafka_pw"
    user_${kafka_user}="$kafka_pw";
};
JAAS_EOF

        echo ""
        echo -e "  ${DIM}SECRET_KEY      = $secret_key${NC}"
        echo -e "  ${DIM}NEO4J_PASSWORD  = $neo4j_pw${NC}"
        echo -e "  ${DIM}POSTGRES_PASS   = $postgres_pw${NC}"
        echo -e "  ${DIM}KAFKA_USER      = $kafka_user${NC}"
        echo -e "  ${DIM}KAFKA_PASSWORD  = $kafka_pw${NC}"
        echo ""
        info ".env generated with fresh secrets."
        info "kafka_server_jaas.conf generated."
    fi

    # --- Always run: SSL certs and .env SSL paths ---
    # These run even when keeping existing .env, so Postgres never crash-loops
    local cert_dir="$PROJECT_DIR/certs"
    if [[ ! -f "$cert_dir/server.crt" || ! -f "$cert_dir/server.key" ]]; then
        echo "  Generating self-signed SSL certs for Postgres..."
        mkdir -p "$cert_dir"
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout "$cert_dir/server.key" -out "$cert_dir/server.crt" \
            -subj "/CN=localhost" 2>/dev/null
        info "Self-signed certs created in certs/"
    else
        info "SSL certs already exist in certs/"
    fi

    # Fix SSL paths in .env if they still point at Let's Encrypt placeholders
    if grep -q "letsencrypt" "$ENV_FILE" 2>/dev/null; then
        sed "s|SSL_CERT_PATH=.*|SSL_CERT_PATH=./certs/server.crt|g" "$ENV_FILE" > "$ENV_FILE.tmp" && mv "$ENV_FILE.tmp" "$ENV_FILE"
        sed "s|SSL_KEY_PATH=.*|SSL_KEY_PATH=./certs/server.key|g" "$ENV_FILE" > "$ENV_FILE.tmp" && mv "$ENV_FILE.tmp" "$ENV_FILE"
        info "Updated .env SSL paths to use local certs."
    fi
}

# =============================================================================
# Ask deployment mode
# =============================================================================
ask_deployment_mode() {
    step "Step 3: Deployment Mode"

    echo "  How will you access this stack?"
    echo ""
    echo -e "    ${BOLD}1)${NC} Local only     — services on localhost, no external access"
    echo -e "    ${BOLD}2)${NC} zrok tunnels   — expose to Databricks/external via zrok"
    echo ""
    ask "Choose [1/2]:"
    prompt mode_choice

    case "$mode_choice" in
        2) DEPLOY_MODE="zrok" ;;
        *) DEPLOY_MODE="local" ;;
    esac
}

# =============================================================================
# zrok setup
# =============================================================================
setup_zrok() {
    step "Step 4: zrok Setup"

    # Check if installed
    if ! command -v zrok &>/dev/null; then
        warn "zrok is not installed."
        echo ""
        if [[ "$(uname)" == "Darwin" ]]; then
            ask "Install via Homebrew? (Y/n)"
            prompt reply
            if [[ ! "$reply" =~ ^[Nn] ]]; then
                echo "  Installing zrok..."
                brew install zrok
                info "zrok installed."
            else
                echo ""
                echo "  Install manually:"
                echo "    brew install zrok"
                echo "    # or: curl -sSf https://get.openziti.io/install.bash | sudo bash -s zrok"
                exit 1
            fi
        else
            ask "Install via openziti script? (Y/n)"
            prompt reply
            if [[ ! "$reply" =~ ^[Nn] ]]; then
                echo "  Installing zrok..."
                curl -sSf https://get.openziti.io/install.bash | sudo bash -s zrok
                info "zrok installed."
            else
                echo ""
                echo "  Install manually: https://docs.zrok.io/docs/guides/install/"
                exit 1
            fi
        fi
    else
        info "zrok found ($(zrok version 2>/dev/null | head -1 || echo 'installed'))"
    fi

    # Check if environment is enabled
    if zrok status &>/dev/null 2>&1; then
        info "zrok environment already enabled."
    else
        echo ""
        echo "  Your zrok environment needs to be enabled."
        echo -e "  ${DIM}If you don't have an account yet, run: zrok invite${NC}"
        echo ""
        ask "Enter your zrok enable token (or 'invite' to create account):"
        prompt zrok_token

        if [[ "$zrok_token" == "invite" ]]; then
            echo ""
            echo "  Opening zrok invite..."
            zrok invite
            echo ""
            echo "  Check your email for the token, then re-run this script."
            exit 0
        fi

        if [[ -z "$zrok_token" ]]; then
            error "No token provided. Get one at https://api.zrok.io or run: zrok invite"
            exit 1
        fi

        echo "  Enabling zrok environment..."
        zrok enable "$zrok_token"
        info "zrok environment enabled."
    fi

    # Ask which services to expose
    echo ""
    echo "  Which services should zrok expose?"
    echo ""
    echo -e "    ${BOLD}1)${NC} API only        — public HTTP URL for the REST API"
    echo -e "    ${BOLD}2)${NC} All services     — API + Kafka + PostgreSQL + Neo4j"
    echo -e "    ${BOLD}3)${NC} TCP only         — Kafka + PostgreSQL + Neo4j (no API)"
    echo ""
    ask "Choose [1/2/3]:"
    prompt svc_choice

    case "$svc_choice" in
        2) ZROK_MODE="all" ;;
        3) ZROK_MODE="tcp-only" ;;
        *) ZROK_MODE="api" ;;
    esac
}

# =============================================================================
# Start Docker stack
# =============================================================================
start_docker() {
    local step_num="$1"
    step "Step $step_num: Starting Docker Stack"

    # Check if already running
    if docker compose -f "$PROJECT_DIR/docker-compose.yml" ps --status running 2>/dev/null | grep -q "caddy"; then
        info "Docker stack is already running."
        ask "Restart it? (y/N)"
        prompt reply
        if [[ "$reply" =~ ^[Yy] ]]; then
            docker compose -f "$PROJECT_DIR/docker-compose.yml" down
            docker compose -f "$PROJECT_DIR/docker-compose.yml" up -d
        fi
    else
        docker compose -f "$PROJECT_DIR/docker-compose.yml" up -d
    fi

    echo ""
    info "Waiting for services to initialize..."
    sleep 8

    # Health check
    echo ""
    local health_url="http://localhost:10800/health"
    local retries=5
    local healthy=false
    for ((i=1; i<=retries; i++)); do
        if curl -sf "$health_url" &>/dev/null; then
            healthy=true
            break
        fi
        echo -e "  ${DIM}Waiting for API... ($i/$retries)${NC}"
        sleep 3
    done

    if [[ "$healthy" == true ]]; then
        info "API is healthy."
    else
        warn "API health check didn't respond yet. It may still be starting."
        echo "  Check manually: curl $health_url"
    fi
}

# =============================================================================
# Start zrok tunnels
# =============================================================================
start_zrok_tunnels() {
    step "Step 5: Starting zrok Tunnels"

    mkdir -p "$LOG_DIR"

    start_one_tunnel() {
        local name="$1" mode="$2" backend="$3"
        local log_file="$LOG_DIR/${name}.log"
        local pid_file="$LOG_DIR/${name}.pid"

        # Already running?
        if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
            warn "$name tunnel already running (PID $(cat "$pid_file")). Skipping."
            return 0
        fi

        if [[ "$mode" == "public" ]]; then
            nohup zrok share public "$backend" > "$log_file" 2>&1 &
        else
            nohup zrok share private --backend-mode tcpTunnel "$backend" > "$log_file" 2>&1 &
        fi

        local pid=$!
        echo "$pid" > "$pid_file"
        sleep 3

        if ! kill -0 "$pid" 2>/dev/null; then
            error "$name tunnel failed to start. Check $log_file"
            return 1
        fi

        local share_info
        share_info=$(grep -oE 'https://[^ ]+\.zrok\.[^ ]+' "$log_file" 2>/dev/null | head -1 || true)
        if [[ -z "$share_info" ]]; then
            share_info=$(grep -oE 'share token is [^ ]+' "$log_file" 2>/dev/null | head -1 || true)
        fi
        if [[ -z "$share_info" ]]; then
            share_info="(starting... check $log_file)"
        fi

        echo -e "  ${GREEN}RUNNING${NC}  ${CYAN}$name${NC} ($mode) — PID $pid — $share_info"
    }

    case "$ZROK_MODE" in
        all)
            for entry in "${ZROK_SERVICES[@]}"; do
                IFS='|' read -r name mode backend <<< "$entry"
                start_one_tunnel "$name" "$mode" "$backend"
            done
            ;;
        tcp-only)
            for entry in "${ZROK_SERVICES[@]}"; do
                IFS='|' read -r name mode backend <<< "$entry"
                [[ "$mode" == "private" ]] && start_one_tunnel "$name" "$mode" "$backend"
            done
            ;;
        *)
            start_one_tunnel "api" "public" "http://localhost:10800"
            ;;
    esac

    echo ""
    info "Tunnel logs: $LOG_DIR/"
}

# =============================================================================
# Print summary
# =============================================================================
print_summary() {
    step "Ready"

    # Load credentials from .env and kafka_server_jaas.conf
    local secret_key neo4j_pw postgres_pw kafka_user kafka_pw
    secret_key=$(grep '^SECRET_KEY=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "(unknown)")
    neo4j_pw=$(grep '^NEO4J_PASSWORD=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "(unknown)")
    postgres_pw=$(grep '^POSTGRES_PASSWORD=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 || echo "(unknown)")
    kafka_user=$(grep 'username=' "$PROJECT_DIR/kafka_server_jaas.conf" 2>/dev/null | head -1 | sed 's/.*username="//;s/".*//' || echo "(unknown)")
    kafka_pw=$(grep 'password=' "$PROJECT_DIR/kafka_server_jaas.conf" 2>/dev/null | head -1 | sed 's/.*password="//;s/".*//' || echo "(unknown)")

    echo -e "${BOLD}Local endpoints:${NC}"
    echo "  API:        http://localhost:10800/api/v1"
    echo "  Health:     http://localhost:10800/health"
    echo "  Neo4j:      http://localhost:7474  (browser)"
    echo "  Neo4j Bolt: bolt://localhost:7687"
    echo "  Postgres:   postgresql://dataapi:***@localhost:15432/data_collector"
    echo "  Redis:      redis://localhost:16379"
    echo "  Kafka:      localhost:9094 (SASL)"

    if [[ "${DEPLOY_MODE:-local}" == "zrok" ]]; then
        echo ""
        echo -e "${BOLD}zrok tunnels:${NC}"
        for entry in "${ZROK_SERVICES[@]}"; do
            IFS='|' read -r name mode backend <<< "$entry"
            local pid_file="$LOG_DIR/${name}.pid"
            local log_file="$LOG_DIR/${name}.log"
            if [[ -f "$pid_file" ]] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
                local share_info
                share_info=$(grep -oE 'https://[^ ]+\.zrok\.[^ ]+' "$log_file" 2>/dev/null | head -1 || true)
                if [[ -z "$share_info" ]]; then
                    share_info=$(grep -oE 'share token is [^ ]+' "$log_file" 2>/dev/null | head -1 || true)
                fi
                [[ -z "$share_info" ]] && share_info="(check $log_file)"
                echo -e "  ${CYAN}$name${NC} ($mode): $share_info"
            fi
        done
        echo ""
        echo -e "${BOLD}Client-side access (for private TCP tunnels):${NC}"
        echo "  zrok access private --bind 127.0.0.1:9094  <kafka-token>"
        echo "  zrok access private --bind 127.0.0.1:15433 <postgres-token>"
        echo "  zrok access private --bind 127.0.0.1:7687  <neo4j-token>"
    fi

    echo ""
    echo -e "${BOLD}Credentials:${NC}"
    echo "  API Key:         $secret_key"
    echo "  Neo4j:           neo4j / $neo4j_pw"
    echo "  Postgres:        dataapi / $postgres_pw"
    echo "  Kafka SASL:      $kafka_user / $kafka_pw"

    echo ""
    echo -e "${BOLD}Quick test:${NC}"
    echo "  curl -H \"X-Api-Key: $secret_key\" http://localhost:10800/api/v1/data-sources/orm"

    # Databricks secrets — matches examples/_config.ipynb scope and key names
    echo ""
    echo -e "${BOLD}Databricks secrets setup (copy-paste into terminal):${NC}"
    echo -e "${DIM}# Creates the secret scope and stores all credentials for the example notebooks${NC}"
    echo ""
    echo "  databricks secrets create-scope data-api"
    echo "  databricks secrets put-secret data-api api-key --string-value \"$secret_key\""
    echo "  databricks secrets put-secret data-api kafka-user --string-value \"$kafka_user\""
    echo "  databricks secrets put-secret data-api kafka-password --string-value \"$kafka_pw\""
    echo "  databricks secrets put-secret data-api neo4j-password --string-value \"$neo4j_pw\""
    echo "  databricks secrets put-secret data-api postgres-password --string-value \"$postgres_pw\""

    # _config.ipynb snippet with real values
    echo ""
    echo -e "${BOLD}Databricks _config.ipynb quick-paste (hardcoded for testing):${NC}"
    echo -e "${DIM}# Replace the secrets section in examples/_config.ipynb with this${NC}"
    echo ""

    # Determine HOST value
    local host_val="localhost"
    if [[ "${DEPLOY_MODE:-local}" == "zrok" ]]; then
        local api_log="$LOG_DIR/api.log"
        local zrok_url
        zrok_url=$(grep -oE 'https://[^ ]+\.share\.zrok\.[^ ]+' "$api_log" 2>/dev/null | head -1 || true)
        if [[ -n "$zrok_url" ]]; then
            # Strip https:// and any trailing characters
            host_val=$(echo "$zrok_url" | sed 's|https://||;s|[^a-zA-Z0-9._-].*||')
        fi
    fi

    echo "  HOST = \"$host_val\""
    echo ""
    echo "  API_KEY           = \"$secret_key\""
    echo "  KAFKA_USER        = \"$kafka_user\""
    echo "  KAFKA_PASSWORD    = \"$kafka_pw\""
    echo "  NEO4J_USER        = \"neo4j\""
    echo "  NEO4J_PASSWORD    = \"$neo4j_pw\""
    echo "  POSTGRES_USER     = \"dataapi\""
    echo "  POSTGRES_PASSWORD = \"$postgres_pw\""
    echo ""
    echo "  API_URL       = f\"https://{HOST}/api/v1\""
    echo "  KAFKA_BROKER  = f\"{HOST}:9093\""
    echo "  NEO4J_URI     = f\"bolt+s://{HOST}:7688\""
    echo "  POSTGRES_JDBC = f\"jdbc:postgresql://{HOST}:15433/data_collector?ssl=true&sslmode=require\""
    echo "  HEADERS       = {\"X-Api-Key\": API_KEY}"

    echo ""
    echo -e "${BOLD}Management:${NC}"
    echo "  ./start.sh --status    # show what's running"
    echo "  ./start.sh --stop      # stop everything"
    echo "  ./tests/test_services.sh  # run full test suite"
    echo ""
}

# =============================================================================
# Main
# =============================================================================
main() {
    local arg="${1:-}"

    case "$arg" in
        --stop|-s)
            do_stop
            exit 0
            ;;
        --status|-S)
            do_status
            exit 0
            ;;
        --help|-h)
            echo "Usage: ./start.sh [--stop|--status|--help]"
            echo ""
            echo "  (no args)   Interactive setup and start"
            echo "  --stop      Stop Docker stack and all zrok tunnels"
            echo "  --status    Show what's running"
            exit 0
            ;;
    esac

    echo ""
    echo -e "${BOLD}${CYAN}╔═══════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║   Data API Collector — Setup & Start  ║${NC}"
    echo -e "${BOLD}${CYAN}╚═══════════════════════════════════════╝${NC}"

    check_prerequisites
    setup_env
    ask_deployment_mode

    if [[ "$DEPLOY_MODE" == "zrok" ]]; then
        setup_zrok
        start_docker 5
        start_zrok_tunnels
    else
        start_docker 4
    fi

    print_summary
}

main "$@"
