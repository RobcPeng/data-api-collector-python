#!/usr/bin/env bash
# =============================================================================
# Comprehensive Test Script for Data API Collector
# =============================================================================
# Usage:
#   ./tests/test_services.sh              # Run all tests
#   ./tests/test_services.sh health       # Run only health checks
#   ./tests/test_services.sh postgres     # Run only Postgres tests
#   ./tests/test_services.sh neo4j        # Run only Neo4j tests
#   ./tests/test_services.sh redis        # Run only Redis tests
#   ./tests/test_services.sh kafka        # Run only Kafka tests
#   ./tests/test_services.sh generators   # Run only Kafka generator tests
#   ./tests/test_services.sh ollama       # Run only Ollama tests
# =============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Load environment
if [[ -f "$PROJECT_DIR/.env" ]]; then
    set +u
    # shellcheck disable=SC1091
    set -a
    . "$PROJECT_DIR/.env"
    set +a
    set -u
fi

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
BASE_URL="${BASE_URL:-http://localhost:${CADDY_HTTP_PORT:-10800}}"
API_KEY="${SECRET_KEY:-}"
API_URL="$BASE_URL/api/v1"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Counters
PASSED=0
FAILED=0
SKIPPED=0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
header() {
    echo ""
    echo -e "${BOLD}${BLUE}======================================================================${NC}"
    echo -e "${BOLD}${BLUE}  $1${NC}"
    echo -e "${BOLD}${BLUE}======================================================================${NC}"
}

subheader() {
    echo ""
    echo -e "${CYAN}--- $1 ---${NC}"
}

pass() {
    echo -e "  ${GREEN}PASS${NC} $1"
    ((PASSED++))
}

fail() {
    echo -e "  ${RED}FAIL${NC} $1"
    if [[ -n "${2:-}" ]]; then
        echo -e "       ${RED}$2${NC}"
    fi
    ((FAILED++))
}

skip() {
    echo -e "  ${YELLOW}SKIP${NC} $1"
    ((SKIPPED++))
}

info() {
    echo -e "  ${CYAN}INFO${NC} $1"
}

# Authenticated GET
api_get() {
    local path="$1"
    curl -s -w "\n%{http_code}" -H "X-Api-Key: $API_KEY" "$API_URL$path" 2>/dev/null
}

# Authenticated POST with JSON body
api_post() {
    local path="$1"
    local body="${2:-"{}"}"
    curl -s -w "\n%{http_code}" \
        -X POST \
        -H "X-Api-Key: $API_KEY" \
        -H "Content-Type: application/json" \
        -d "$body" \
        "$API_URL$path" 2>/dev/null
}

# Authenticated DELETE
api_delete() {
    local path="$1"
    curl -s -w "\n%{http_code}" \
        -X DELETE \
        -H "X-Api-Key: $API_KEY" \
        "$API_URL$path" 2>/dev/null
}

# Parse response: last line is status code, rest is body
parse_response() {
    local response="$1"
    HTTP_BODY=$(echo "$response" | sed '$d')
    HTTP_CODE=$(echo "$response" | tail -1)
}

# Check if response has expected HTTP code and body contains a string
assert_status() {
    local test_name="$1"
    local expected_code="$2"
    if [[ "$HTTP_CODE" == "$expected_code" ]]; then
        pass "$test_name (HTTP $HTTP_CODE)"
    else
        fail "$test_name" "Expected HTTP $expected_code, got HTTP $HTTP_CODE"
    fi
}

assert_body_contains() {
    local test_name="$1"
    local expected="$2"
    if echo "$HTTP_BODY" | grep -q "$expected"; then
        pass "$test_name"
    else
        fail "$test_name" "Response body does not contain '$expected'"
    fi
}

assert_json_field() {
    local test_name="$1"
    local field="$2"
    local expected="$3"
    local actual
    actual=$(echo "$HTTP_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('$field',''))" 2>/dev/null || echo "")
    if [[ "$actual" == "$expected" ]]; then
        pass "$test_name ($field=$actual)"
    else
        fail "$test_name" "Expected $field='$expected', got '$actual'"
    fi
}

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
preflight() {
    header "PRE-FLIGHT CHECKS"

    if [[ -z "$API_KEY" ]]; then
        fail "SECRET_KEY is set in .env"
        echo -e "  ${RED}Cannot run tests without API key. Set SECRET_KEY in .env${NC}"
        exit 1
    else
        pass "SECRET_KEY loaded from .env"
    fi

    if curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health" 2>/dev/null | grep -q "200"; then
        pass "Caddy health endpoint reachable at $BASE_URL"
    else
        fail "Caddy health endpoint reachable at $BASE_URL"
        echo -e "  ${RED}Is the stack running? Try: docker compose up -d${NC}"
        exit 1
    fi

    # Check which containers are running
    local running
    running=$(docker compose ps --format '{{.Name}}' 2>/dev/null || echo "")
    for svc in data-api-app data-api-kafka data-api-postgres data-api-redis data-api-neo4j spark-generator; do
        if echo "$running" | grep -q "$svc"; then
            pass "Container $svc is running"
        else
            skip "Container $svc is NOT running (related tests may fail)"
        fi
    done
}

# ---------------------------------------------------------------------------
# Test: Health
# ---------------------------------------------------------------------------
test_health() {
    header "HEALTH CHECKS"

    subheader "Caddy Health"
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/health" 2>/dev/null)
    if [[ "$code" == "200" ]]; then
        pass "GET /health returns 200"
    else
        fail "GET /health returns 200" "Got HTTP $code"
    fi

    subheader "API Authentication"
    code=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/data-sources/orm" 2>/dev/null)
    if [[ "$code" == "401" ]]; then
        pass "Unauthenticated request returns 401"
    else
        fail "Unauthenticated request returns 401" "Got HTTP $code"
    fi

    parse_response "$(api_get '/data-sources/orm')"
    assert_status "Authenticated request succeeds" "200"
}

# ---------------------------------------------------------------------------
# Test: PostgreSQL
# ---------------------------------------------------------------------------
test_postgres() {
    header "POSTGRESQL TESTS"

    subheader "ORM Connection"
    parse_response "$(api_get '/data-sources/orm')"
    assert_status "GET /data-sources/orm" "200"
    assert_body_contains "ORM returns database version" "PostgreSQL"

    subheader "Raw SQL Connection"
    parse_response "$(api_get '/data-sources/raw/sql')"
    assert_status "GET /data-sources/raw/sql" "200"
    assert_body_contains "Raw SQL returns current database" "current_database"

    subheader "Connection Pool Info"
    parse_response "$(api_get '/data-sources/connection-info')"
    assert_status "GET /data-sources/connection-info" "200"
    assert_body_contains "Returns pool size info" "pool_size"
}

# ---------------------------------------------------------------------------
# Test: Neo4j
# ---------------------------------------------------------------------------
test_neo4j() {
    header "NEO4J TESTS"

    subheader "Health Check"
    parse_response "$(api_get '/data-sources/neo4j/health')"
    assert_status "GET /neo4j/health" "200"
    assert_body_contains "Neo4j is healthy" "success"

    subheader "Version Info"
    parse_response "$(api_get '/data-sources/neo4j/version')"
    assert_status "GET /neo4j/version" "200"
    assert_body_contains "Returns Neo4j version" "version"

    subheader "Statistics"
    parse_response "$(api_get '/data-sources/neo4j/statistics')"
    assert_status "GET /neo4j/statistics" "200"
    assert_body_contains "Returns node count" "node_count"

    subheader "Connection Info"
    parse_response "$(api_get '/data-sources/neo4j/connection-info')"
    assert_status "GET /neo4j/connection-info" "200"
    assert_body_contains "Returns connection details" "status"

    subheader "Query Test"
    parse_response "$(api_get '/data-sources/neo4j/query-test')"
    assert_status "GET /neo4j/query-test" "200"
    assert_body_contains "Returns query results" "query_time_ms"
}

# ---------------------------------------------------------------------------
# Test: Redis
# ---------------------------------------------------------------------------
test_redis() {
    header "REDIS TESTS"

    subheader "Connection Test"
    parse_response "$(api_get '/redis/test')"
    assert_status "GET /redis/test" "200"
    assert_body_contains "Redis responds with version" "version"

    subheader "Set Key (string)"
    parse_response "$(api_post '/redis/set' '{"key_store": "test:string", "value": "hello-world"}')"
    assert_status "POST /redis/set (string)" "200"

    subheader "Get Key (string)"
    parse_response "$(api_get '/redis/get?key_store=test:string')"
    assert_status "GET /redis/get (string)" "200"
    assert_body_contains "Returns stored value" "hello-world"

    subheader "Set Key (JSON object)"
    parse_response "$(api_post '/redis/set' '{"key_store": "test:json", "value": {"foo": "bar", "num": 42}}')"
    assert_status "POST /redis/set (JSON)" "200"

    subheader "Get Key (JSON object)"
    parse_response "$(api_get '/redis/get?key_store=test:json')"
    assert_status "GET /redis/get (JSON)" "200"
    assert_body_contains "Returns stored JSON" "foo"
}

# ---------------------------------------------------------------------------
# Test: Kafka (basic produce/consume)
# ---------------------------------------------------------------------------
test_kafka() {
    header "KAFKA TESTS"

    local test_topic="test-topic-$(date +%s)"
    local test_msg="test-message-$(date +%s)"

    subheader "Produce Message"
    parse_response "$(api_post '/kafka/producer/send-message' "{\"topic_name\": \"$test_topic\", \"topic_message\": \"$test_msg\", \"source\": \"test-script\"}")"
    assert_status "POST /kafka/producer/send-message" "200"
    assert_json_field "Producer returns success" "status" "success"

    subheader "Consume Message"
    sleep 2  # Allow message to be available
    parse_response "$(api_get "/kafka/consume/consume-message?topic_name=$test_topic&message_limit=5")"
    assert_status "GET /kafka/consume/consume-message" "200"
    assert_json_field "Consumer returns success" "status" "success"

    subheader "Event Log"
    parse_response "$(api_get '/kafka/events?limit=5')"
    assert_status "GET /kafka/events" "200"
    assert_body_contains "Events endpoint returns total" "total"
}

# ---------------------------------------------------------------------------
# Test: Kafka Generators (Spark service)
# ---------------------------------------------------------------------------
test_generators() {
    header "KAFKA GENERATOR TESTS (Spark Service)"

    subheader "List Generators (empty)"
    parse_response "$(api_get '/kafka/generators')"
    assert_status "GET /kafka/generators (list)" "200"

    # --- Fraud Detection ---
    subheader "Start Fraud Detection Generator"
    parse_response "$(api_post '/kafka/generators/start' '{
        "use_case": "fraud_detection",
        "rows_per_batch": 5,
        "batch_interval_seconds": 1,
        "timeout_minutes": 0.25
    }')"
    assert_status "POST /kafka/generators/start (fraud)" "200"
    assert_json_field "Generator status is running" "status" "running"
    local fraud_id
    fraud_id=$(echo "$HTTP_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['generator_id'])" 2>/dev/null)
    info "Fraud generator ID: $fraud_id"

    # --- Telemetry ---
    subheader "Start Telemetry Generator"
    parse_response "$(api_post '/kafka/generators/start' '{
        "use_case": "telemetry",
        "rows_per_batch": 5,
        "batch_interval_seconds": 1,
        "timeout_minutes": 0.25
    }')"
    assert_status "POST /kafka/generators/start (telemetry)" "200"
    local telemetry_id
    telemetry_id=$(echo "$HTTP_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['generator_id'])" 2>/dev/null)
    info "Telemetry generator ID: $telemetry_id"

    # --- Web Traffic ---
    subheader "Start Web Traffic Generator"
    parse_response "$(api_post '/kafka/generators/start' '{
        "use_case": "web_traffic",
        "rows_per_batch": 5,
        "batch_interval_seconds": 1,
        "timeout_minutes": 0.25
    }')"
    assert_status "POST /kafka/generators/start (web_traffic)" "200"
    local web_id
    web_id=$(echo "$HTTP_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['generator_id'])" 2>/dev/null)
    info "Web traffic generator ID: $web_id"

    # --- Wait for Spark to produce data ---
    subheader "Waiting for Spark to initialize and produce data..."
    info "Spark JVM startup can take 10-15 seconds on first run"
    local attempts=0
    local max_attempts=30
    local rows=0
    while [[ $attempts -lt $max_attempts ]]; do
        sleep 2
        parse_response "$(api_get "/kafka/generators/$fraud_id")"
        rows=$(echo "$HTTP_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('rows_produced',0))" 2>/dev/null || echo "0")
        if [[ "$rows" -gt 0 ]]; then
            break
        fi
        ((attempts++))
    done

    if [[ "$rows" -gt 0 ]]; then
        pass "Fraud generator produced $rows rows"
    else
        fail "Fraud generator produced rows within timeout"
    fi

    # --- Check all generators running ---
    subheader "List Active Generators"
    parse_response "$(api_get '/kafka/generators')"
    assert_status "GET /kafka/generators (list active)" "200"
    local count
    count=$(echo "$HTTP_BODY" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    if [[ "$count" -ge 3 ]]; then
        pass "All 3 generators visible in list (found $count)"
    else
        fail "All 3 generators visible in list" "Found $count"
    fi

    # --- Stop one generator ---
    subheader "Stop Fraud Generator"
    parse_response "$(api_post "/kafka/generators/$fraud_id/stop")"
    assert_status "POST /kafka/generators/{id}/stop" "200"
    assert_json_field "Generator status is stopped" "status" "stopped"

    # --- Verify Kafka topics have data ---
    subheader "Verify Kafka Topics Have Data"
    for topic in streaming-fraud-transactions streaming-device-telemetry streaming-web-traffic; do
        local msg
        msg=$(docker exec data-api-kafka kafka-console-consumer \
            --bootstrap-server localhost:9092 \
            --topic "$topic" \
            --from-beginning \
            --max-messages 1 \
            --timeout-ms 10000 2>/dev/null || echo "")
        if [[ -n "$msg" ]] && echo "$msg" | python3 -c "import sys,json; json.load(sys.stdin)" 2>/dev/null; then
            pass "Topic '$topic' contains valid JSON data"
        else
            fail "Topic '$topic' contains valid JSON data"
        fi
    done

    # --- Custom topic name ---
    subheader "Start Generator with Custom Topic"
    parse_response "$(api_post '/kafka/generators/start' '{
        "use_case": "fraud_detection",
        "topic_name": "custom-test-topic",
        "rows_per_batch": 5,
        "batch_interval_seconds": 1,
        "timeout_minutes": 0.1
    }')"
    assert_status "POST /kafka/generators/start (custom topic)" "200"
    assert_body_contains "Uses custom topic name" "custom-test-topic"

    # --- Cleanup ---
    subheader "Wait for generators to complete then cleanup"
    sleep 20  # Wait for 0.25 min timeout generators to finish
    parse_response "$(api_delete '/kafka/generators/cleanup')"
    assert_status "DELETE /kafka/generators/cleanup" "200"
    assert_body_contains "Cleanup returns removed count" "removed"
    info "Cleanup response: $HTTP_BODY"
}

# ---------------------------------------------------------------------------
# Test: Ollama (may not be available)
# ---------------------------------------------------------------------------
test_ollama() {
    header "OLLAMA TESTS"

    subheader "Environment Info"
    parse_response "$(api_get '/ollama-test/environment')"
    assert_status "GET /ollama-test/environment" "200"

    subheader "Connectivity Test"
    parse_response "$(api_get '/ollama-test/connectivity')"
    if [[ "$HTTP_CODE" == "200" ]]; then
        pass "GET /ollama-test/connectivity"
        if echo "$HTTP_BODY" | grep -q '"success": true'; then
            pass "Ollama is reachable"
        else
            skip "Ollama is not reachable (service may not be running)"
        fi
    else
        skip "Ollama connectivity test returned HTTP $HTTP_CODE"
    fi
}

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
summary() {
    header "TEST SUMMARY"
    echo ""
    echo -e "  ${GREEN}Passed:  $PASSED${NC}"
    echo -e "  ${RED}Failed:  $FAILED${NC}"
    echo -e "  ${YELLOW}Skipped: $SKIPPED${NC}"
    echo ""

    local total=$((PASSED + FAILED))
    if [[ $FAILED -eq 0 ]]; then
        echo -e "  ${GREEN}${BOLD}All $total tests passed!${NC}"
    else
        echo -e "  ${RED}${BOLD}$FAILED of $total tests failed.${NC}"
    fi
    echo ""

    return $FAILED
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    local target="${1:-all}"

    preflight

    case "$target" in
        health)     test_health ;;
        postgres)   test_postgres ;;
        neo4j)      test_neo4j ;;
        redis)      test_redis ;;
        kafka)      test_kafka ;;
        generators) test_generators ;;
        ollama)     test_ollama ;;
        all)
            test_health
            test_postgres
            test_neo4j
            test_redis
            test_kafka
            test_generators
            test_ollama
            ;;
        *)
            echo "Usage: $0 {all|health|postgres|neo4j|redis|kafka|generators|ollama}"
            exit 1
            ;;
    esac

    summary
}

main "$@"
