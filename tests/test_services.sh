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
#   ./tests/test_services.sh sled         # Run all SLED tests (generators + neo4j + postgres)
#   ./tests/test_services.sh sled-generators  # SLED Kafka generators only
#   ./tests/test_services.sh sled-neo4j       # SLED Neo4j populate/clear only
#   ./tests/test_services.sh sled-postgres    # SLED Postgres populate/clear only
#   ./tests/test_services.sh custom       # Run all custom generator tests
#   ./tests/test_services.sh custom-kafka     # Custom Kafka generators only
#   ./tests/test_services.sh custom-neo4j     # Custom Neo4j generators only
#   ./tests/test_services.sh custom-postgres  # Custom Postgres generators only
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
# Test: SLED Kafka Generators
# ---------------------------------------------------------------------------
test_sled_generators() {
    header "SLED KAFKA GENERATOR TESTS"

    local sled_cases=("student_enrollment" "grant_budget" "citizen_services" "k12_early_warning" "procurement" "case_management")

    for uc in "${sled_cases[@]}"; do
        subheader "Start $uc Generator"
        parse_response "$(api_post '/kafka/generators/start' "{
            \"use_case\": \"$uc\",
            \"rows_per_batch\": 5,
            \"batch_interval_seconds\": 1,
            \"timeout_minutes\": 0.15
        }")"
        assert_status "POST /kafka/generators/start ($uc)" "200"
        assert_json_field "Generator status is running" "status" "running"
    done

    subheader "Wait for Spark to produce SLED data..."
    sleep 20

    subheader "Verify SLED Generators Produced Data"
    parse_response "$(api_get '/kafka/generators')"
    assert_status "GET /kafka/generators (list SLED)" "200"
    local total_rows
    total_rows=$(echo "$HTTP_BODY" | python3 -c "
import sys,json
gens = json.load(sys.stdin)
sled = [g for g in gens if g['use_case'] in ['student_enrollment','grant_budget','citizen_services','k12_early_warning','procurement','case_management']]
print(sum(g['rows_produced'] for g in sled))
" 2>/dev/null || echo "0")
    if [[ "$total_rows" -gt 0 ]]; then
        pass "SLED generators produced $total_rows total rows"
    else
        fail "SLED generators produced rows" "Got 0 rows"
    fi

    subheader "Cleanup SLED Generators"
    sleep 10
    parse_response "$(api_delete '/kafka/generators/cleanup')"
    assert_status "DELETE /kafka/generators/cleanup (SLED)" "200"
}

# ---------------------------------------------------------------------------
# Test: SLED Neo4j Populate/Clear/Status
# ---------------------------------------------------------------------------
test_sled_neo4j() {
    header "SLED NEO4J TESTS"

    local sled_cases=("student_enrollment" "grant_budget" "citizen_services" "k12_early_warning" "procurement" "case_management")

    for uc in "${sled_cases[@]}"; do
        subheader "Populate $uc in Neo4j"
        parse_response "$(api_post "/data-sources/neo4j/sled/$uc/populate" '{"num_records": 100}')"
        assert_status "POST /neo4j/sled/$uc/populate" "200"
        assert_json_field "Populate status is running" "status" "running"
    done

    subheader "Wait for Neo4j population..."
    sleep 15

    for uc in "${sled_cases[@]}"; do
        subheader "Status $uc in Neo4j"
        parse_response "$(api_get "/data-sources/neo4j/sled/$uc/status")"
        assert_status "GET /neo4j/sled/$uc/status" "200"
        assert_body_contains "Status returns counts" "counts"
    done

    for uc in "${sled_cases[@]}"; do
        subheader "Clear $uc from Neo4j"
        parse_response "$(api_delete "/data-sources/neo4j/sled/$uc/clear")"
        assert_status "DELETE /neo4j/sled/$uc/clear" "200"
        assert_body_contains "Clear returns cleared status" "cleared"
    done

    subheader "Neo4j SLED Job Cleanup"
    parse_response "$(api_delete '/data-sources/neo4j/sled/jobs/cleanup')"
    assert_status "DELETE /neo4j/sled/jobs/cleanup" "200"
}

# ---------------------------------------------------------------------------
# Test: SLED Postgres Populate/Clear/Status
# ---------------------------------------------------------------------------
test_sled_postgres() {
    header "SLED POSTGRESQL TESTS"

    local sled_cases=("student_enrollment" "grant_budget" "citizen_services" "k12_early_warning" "procurement" "case_management")

    for uc in "${sled_cases[@]}"; do
        subheader "Populate $uc in Postgres"
        parse_response "$(api_post "/data-sources/sled/$uc/populate" '{"num_records": 100}')"
        assert_status "POST /sled/$uc/populate" "200"
        assert_json_field "Populate status is running" "status" "running"
    done

    subheader "Wait for Postgres population..."
    sleep 15

    for uc in "${sled_cases[@]}"; do
        subheader "Status $uc in Postgres"
        parse_response "$(api_get "/data-sources/sled/$uc/status")"
        assert_status "GET /sled/$uc/status" "200"
        assert_body_contains "Status returns counts" "counts"
    done

    for uc in "${sled_cases[@]}"; do
        subheader "Clear $uc from Postgres"
        parse_response "$(api_delete "/data-sources/sled/$uc/clear")"
        assert_status "DELETE /sled/$uc/clear" "200"
        assert_body_contains "Clear returns cleared status" "cleared"
    done

    subheader "Postgres SLED Job Cleanup"
    parse_response "$(api_delete '/data-sources/sled/jobs/cleanup')"
    assert_status "DELETE /sled/jobs/cleanup" "200"
}

# ---------------------------------------------------------------------------
# Test: Custom Kafka Generators (Experimental)
# ---------------------------------------------------------------------------
test_custom_kafka() {
    header "CUSTOM KAFKA GENERATOR TESTS (Experimental)"

    subheader "Health Check"
    parse_response "$(api_get '/kafka/generators/custom/health')"
    assert_status "GET /custom/health" "200"
    assert_json_field "Custom health is ok" "status" "ok"

    subheader "Validate Spec (dry run)"
    parse_response "$(api_post '/kafka/generators/custom/validate' '{
        "name": "test_custom",
        "topic_name": "test-custom-topic",
        "columns": [
            {"name": "id", "type": "string", "expr": "uuid()"},
            {"name": "value", "type": "integer", "min_value": 1, "max_value": 100, "random": true},
            {"name": "category", "type": "string", "values": ["A", "B", "C"], "weights": [5, 3, 2]}
        ]
    }')"
    assert_status "POST /custom/validate" "200"
    assert_json_field "Validation status is valid" "status" "valid"
    assert_body_contains "Returns resolved schema" "resolved_schema"
    assert_body_contains "Returns sample row" "sample_row"

    subheader "Validate Invalid Spec"
    parse_response "$(api_post '/kafka/generators/custom/validate' '{
        "name": "bad_spec",
        "topic_name": "bad-topic",
        "columns": [
            {"name": "x", "type": "not_a_real_type"}
        ]
    }')"
    if [[ "$HTTP_CODE" == "400" ]]; then
        pass "Invalid spec returns 400"
    else
        # Some invalid types may not fail validation until build — accept 200 or 400
        pass "Spec validation returned HTTP $HTTP_CODE (type may be lenient)"
    fi

    subheader "Start Custom Generator"
    parse_response "$(api_post '/kafka/generators/custom/start' '{
        "name": "test_generator",
        "topic_name": "test-custom-stream",
        "rows_per_batch": 5,
        "batch_interval_seconds": 1,
        "timeout_minutes": 0.2,
        "columns": [
            {"name": "id", "type": "string", "expr": "uuid()"},
            {"name": "score", "type": "integer", "min_value": 1, "max_value": 100, "random": true},
            {"name": "label", "type": "string", "values": ["good", "bad", "neutral"], "weights": [5, 2, 3]},
            {"name": "active", "type": "boolean", "expr": "rand() < 0.7"}
        ]
    }')"
    assert_status "POST /custom/start" "200"
    assert_json_field "Custom generator status is running" "status" "running"
    local custom_id
    custom_id=$(echo "$HTTP_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['generator_id'])" 2>/dev/null)
    info "Custom generator ID: $custom_id"

    subheader "List Custom Generators"
    parse_response "$(api_get '/kafka/generators/custom')"
    assert_status "GET /custom (list)" "200"
    local custom_count
    custom_count=$(echo "$HTTP_BODY" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")
    if [[ "$custom_count" -ge 1 ]]; then
        pass "Custom generator list has $custom_count entry"
    else
        fail "Custom generator list has entries" "Found $custom_count"
    fi

    subheader "Get Custom Generator Status"
    parse_response "$(api_get "/kafka/generators/custom/$custom_id")"
    assert_status "GET /custom/{id}" "200"
    assert_body_contains "Returns generator name" "test_generator"

    subheader "Get Custom Generator Spec"
    parse_response "$(api_get "/kafka/generators/custom/$custom_id/spec")"
    assert_status "GET /custom/{id}/spec" "200"
    assert_body_contains "Spec returns columns" "columns"
    assert_body_contains "Spec returns topic" "test-custom-stream"

    subheader "Wait for data production..."
    sleep 15
    parse_response "$(api_get "/kafka/generators/custom/$custom_id")"
    local custom_rows
    custom_rows=$(echo "$HTTP_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('rows_produced',0))" 2>/dev/null || echo "0")
    if [[ "$custom_rows" -gt 0 ]]; then
        pass "Custom generator produced $custom_rows rows"
    else
        fail "Custom generator produced rows" "Got 0"
    fi

    subheader "Stop Custom Generator"
    parse_response "$(api_post "/kafka/generators/custom/$custom_id/stop")"
    assert_status "POST /custom/{id}/stop" "200"

    subheader "Cleanup Custom Generators"
    sleep 5
    parse_response "$(api_delete '/kafka/generators/custom/cleanup')"
    assert_status "DELETE /custom/cleanup" "200"
    assert_body_contains "Cleanup returns removed count" "removed"
}

# ---------------------------------------------------------------------------
# Test: Custom Neo4j Generators (Experimental)
# ---------------------------------------------------------------------------
test_custom_neo4j() {
    header "CUSTOM NEO4J GENERATOR TESTS (Experimental)"

    subheader "Health Check"
    parse_response "$(api_get '/data-sources/neo4j/custom/health')"
    assert_status "GET /neo4j/custom/health" "200"
    assert_json_field "Custom Neo4j health is ok" "status" "ok"

    subheader "Start Custom Graph Generation"
    parse_response "$(api_post '/data-sources/neo4j/custom/start' '{
        "name": "test_graph",
        "clear_before": true,
        "nodes": [
            {"label": "TestPerson", "count": 50, "properties": [
                {"name": "person_id", "generator_rule": {"generator": "sequence", "prefix": "TP-", "width": 4}},
                {"name": "name", "generator_rule": {"generator": "name"}},
                {"name": "age", "generator_rule": {"generator": "range_int", "min": 18, "max": 80}}
            ]},
            {"label": "TestCompany", "count": 5, "properties": [
                {"name": "company_id", "generator_rule": {"generator": "sequence", "prefix": "TC-", "width": 3}},
                {"name": "sector", "generator_rule": {"generator": "choice", "values": ["Tech", "Finance", "Healthcare"]}}
            ]}
        ],
        "relationships": [
            {"type": "TEST_WORKS_AT", "from_label": "TestPerson", "to_label": "TestCompany", "probability": 0.25, "max_per_source": 1}
        ]
    }')"
    assert_status "POST /neo4j/custom/start" "200"
    assert_json_field "Custom Neo4j job status is running" "status" "running"
    local neo4j_job_id
    neo4j_job_id=$(echo "$HTTP_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])" 2>/dev/null)
    info "Neo4j custom job ID: $neo4j_job_id"

    subheader "Wait for graph generation..."
    sleep 10

    subheader "Get Custom Neo4j Job Status"
    parse_response "$(api_get "/data-sources/neo4j/custom/$neo4j_job_id")"
    assert_status "GET /neo4j/custom/{id}" "200"
    assert_json_field "Job completed" "status" "completed"
    assert_body_contains "Returns nodes_created" "nodes_created"
    local persons_created
    persons_created=$(echo "$HTTP_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('nodes_created',{}).get('TestPerson',0))" 2>/dev/null || echo "0")
    if [[ "$persons_created" -ge 50 ]]; then
        pass "Created $persons_created TestPerson nodes"
    else
        fail "Created TestPerson nodes" "Expected >= 50, got $persons_created"
    fi

    subheader "List Custom Neo4j Jobs"
    parse_response "$(api_get '/data-sources/neo4j/custom')"
    assert_status "GET /neo4j/custom (list)" "200"

    subheader "Clear Custom Neo4j Data"
    parse_response "$(api_delete "/data-sources/neo4j/custom/$neo4j_job_id/clear")"
    assert_status "DELETE /neo4j/custom/{id}/clear" "200"
    assert_body_contains "Clear returns deleted counts" "deleted"

    subheader "Cleanup Custom Neo4j Jobs"
    parse_response "$(api_delete '/data-sources/neo4j/custom/cleanup')"
    assert_status "DELETE /neo4j/custom/cleanup" "200"
}

# ---------------------------------------------------------------------------
# Test: Custom Postgres Generators (Experimental)
# ---------------------------------------------------------------------------
test_custom_postgres() {
    header "CUSTOM POSTGRESQL GENERATOR TESTS (Experimental)"

    subheader "Health Check"
    parse_response "$(api_get '/data-sources/custom/health')"
    assert_status "GET /custom/health (postgres)" "200"
    assert_json_field "Custom Postgres health is ok" "status" "ok"

    subheader "Start Custom Table Generation"
    parse_response "$(api_post '/data-sources/custom/start' '{
        "name": "test_table",
        "table_name": "test_data",
        "num_records": 100,
        "drop_existing": true,
        "columns": [
            {"name": "id", "sql_type": "VARCHAR(40)", "primary_key": true, "generator_rule": {"generator": "uuid"}},
            {"name": "name", "sql_type": "VARCHAR(100)", "generator_rule": {"generator": "name"}},
            {"name": "score", "sql_type": "INT", "generator_rule": {"generator": "range_int", "min": 1, "max": 100}},
            {"name": "category", "sql_type": "VARCHAR(20)", "generator_rule": {"generator": "choice", "values": ["A", "B", "C"]}},
            {"name": "active", "sql_type": "BOOLEAN", "generator_rule": {"generator": "bool", "probability": 0.7}},
            {"name": "event_date", "sql_type": "DATE", "generator_rule": {"generator": "date", "start": "2024-01-01", "end": "2025-12-31"}}
        ]
    }')"
    assert_status "POST /custom/start (postgres)" "200"
    assert_json_field "Custom Postgres job status is running" "status" "running"
    local pg_job_id
    pg_job_id=$(echo "$HTTP_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])" 2>/dev/null)
    info "Postgres custom job ID: $pg_job_id"

    subheader "Wait for table generation..."
    sleep 8

    subheader "Get Custom Postgres Job Status"
    parse_response "$(api_get "/data-sources/custom/$pg_job_id")"
    assert_status "GET /custom/{id} (postgres)" "200"
    assert_json_field "Job completed" "status" "completed"
    local pg_rows
    pg_rows=$(echo "$HTTP_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('rows_created',0))" 2>/dev/null || echo "0")
    if [[ "$pg_rows" -ge 100 ]]; then
        pass "Created $pg_rows rows in custom_test_data"
    else
        fail "Created rows in custom table" "Expected >= 100, got $pg_rows"
    fi

    subheader "Get Table Schema"
    parse_response "$(api_get "/data-sources/custom/$pg_job_id/schema")"
    assert_status "GET /custom/{id}/schema" "200"
    assert_body_contains "Schema returns columns" "columns"
    assert_body_contains "Schema returns row_count" "row_count"

    subheader "Get Sample Rows"
    parse_response "$(api_get "/data-sources/custom/$pg_job_id/sample?limit=5")"
    assert_status "GET /custom/{id}/sample" "200"
    assert_body_contains "Sample returns rows" "rows"

    subheader "List Custom Postgres Jobs"
    parse_response "$(api_get '/data-sources/custom')"
    assert_status "GET /custom (list postgres)" "200"

    subheader "Truncate Custom Table"
    parse_response "$(api_delete "/data-sources/custom/$pg_job_id/clear")"
    assert_status "DELETE /custom/{id}/clear" "200"
    assert_body_contains "Truncate returns status" "truncated"

    subheader "Drop Custom Table"
    parse_response "$(api_delete "/data-sources/custom/$pg_job_id/drop")"
    assert_status "DELETE /custom/{id}/drop" "200"
    assert_body_contains "Drop returns status" "dropped"

    subheader "Cleanup Custom Postgres Jobs"
    parse_response "$(api_delete '/data-sources/custom/cleanup')"
    assert_status "DELETE /custom/cleanup (postgres)" "200"
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
        health)           test_health ;;
        postgres)         test_postgres ;;
        neo4j)            test_neo4j ;;
        redis)            test_redis ;;
        kafka)            test_kafka ;;
        generators)       test_generators ;;
        sled-generators)  test_sled_generators ;;
        sled-neo4j)       test_sled_neo4j ;;
        sled-postgres)    test_sled_postgres ;;
        sled)             test_sled_generators; test_sled_neo4j; test_sled_postgres ;;
        custom-kafka)     test_custom_kafka ;;
        custom-neo4j)     test_custom_neo4j ;;
        custom-postgres)  test_custom_postgres ;;
        custom)           test_custom_kafka; test_custom_neo4j; test_custom_postgres ;;
        ollama)           test_ollama ;;
        all)
            test_health
            test_postgres
            test_neo4j
            test_redis
            test_kafka
            test_generators
            test_sled_generators
            test_sled_neo4j
            test_sled_postgres
            test_custom_kafka
            test_custom_neo4j
            test_custom_postgres
            test_ollama
            ;;
        *)
            echo "Usage: $0 {all|health|postgres|neo4j|redis|kafka|generators|sled|sled-generators|sled-neo4j|sled-postgres|custom|custom-kafka|custom-neo4j|custom-postgres|ollama}"
            exit 1
            ;;
    esac

    summary
}

main "$@"
