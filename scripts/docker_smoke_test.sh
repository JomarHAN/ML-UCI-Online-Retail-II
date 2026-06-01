#!/usr/bin/env bash
# ============================================================================
# scripts/docker_smoke_test.sh - verify the built container works end-to-end
# ============================================================================
# What this script does:
#   1. Builds the Docker image (or skips if --no-build)
#   2. Starts the container in the background
#   3. Polls /health until healthy (with timeout)
#   4. Hits every endpoint and verifies the response 
#   5. Stops and cleans up the container
# 
# Run from the repo root:
#   bash scripts/docker_smoke_test.sh
#   bash scripts/docker_smoke_test.sh --no-build        # skip build step
# ============================================================================

set -e  # exit on any error
set -o pipefail

IMAGE_NAME="uci-retail-api"
TAG="smoke-test"
CONTAINER_NAME="uci-retail-smoke"
PORT="8001"     # use a different port to avoid clashing with a running dev server

# Colors for pretty output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'  # No color

log()   { echo -e "${GREEN}[smoke]${NC} $*"; }
warn()  { echo -e "${YELLOW}[smoke]${NC} $*"; }
err()   { echo -e "${RED}[smoke]${NC} $*"; }

cleanup(){
    log "Cleaning up..."
    docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
    docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
}
# Always clean up when the script exits, no matter how
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Step 1: Build (optional)
# ---------------------------------------------------------------------------
if [[ "${1:-}" != "--no-build" ]]; then
    log "Building image $IMAGE_NAME:$TAG..."
    docker build -t "$IMAGE_NAME:$TAG" .
else
    log "Skipping build (--no-build)"
fi

# ---------------------------------------------------------------------------
# Step 2: Run
# ---------------------------------------------------------------------------
log "Starting container..."
docker run -d \
    --name "$CONTAINER_NAME" \
    -p "${PORT}:8000" \
    -v "$(pwd)/models:/app/models:ro" \
    -v "$(pwd)/data/processed:/app/data/processed:ro" \
    "$IMAGE_NAME:$TAG" >/dev/null

# ---------------------------------------------------------------------------
# Step 3: Wait for healthy
# ---------------------------------------------------------------------------
log "Waiting for container to become healthy..."
HEALTHY=false
for i in $(seq 1 60); do
    if curl --fail --silent --max-time 2 "http://localhost:${PORT}/health" >/dev/null 2>&1; then
        HEALTHY=true
        break
    fi
    sleep 2
done

if [[ "$HEALTHY" != "true" ]]; then
    err "Container did not become healthy in 120 seconds"
    err "Last 50 lines of logs:"
    docker logs --tail 50 "$CONTAINER_NAME"
    exit 1
fi
log "Container is healthy after ~$((i * 2))s"

# ---------------------------------------------------------------------------
# Step 4: Hit each endpoint
# ---------------------------------------------------------------------------
log "Testing endpoints..."

assert_status(){
    local url=$1
    local expected=$2
    local label=$3
    local actual
    actual=$(curl -s -o /dev/null -w "%{http_code}" "$url")
    if [[ "$actual" == "$expected" ]]; then
        log " ✔︎ $label -> $actual"
    else
        err " ✗ $label -> expected $expected, got $actual"
        exit 1
    fi
}


# Health
assert_status "http://localhost:${PORT}/health" "200" "GET /health"

# OpenAPI docs
assert_status "http://localhost:${PORT}/docs" "200" "GET /docs"
assert_status "http://localhost:${PORT}/openapi.json" "200" "GET /openapi.json"

# Top customers
assert_status "http://localhost:${PORT}/customers/top?n=5" "200" "GET /customers/top?n=5"

# Pull a real customer ID from the top-customers response
log "Fetching a real customer ID..."
CUSTOMER_ID=$(curl -fs "http://localhost:${PORT}/customers/top?n=1" \
    | python3 -c "import sys, json; print(json.load(sys.stdin)['customers'][0]['customer_id'])")
log " Using customer_id = $CUSTOMER_ID"

assert_status "http://localhost:${PORT}/customers/${CUSTOMER_ID}/recommendation" "200" \
    "GET /customers/{id}/recommendation"
assert_status "http://localhost:${PORT}/customers/${CUSTOMER_ID}/risk" "200" \
    "GET /customers/{id}/risk"


# 404 for unknown customer
assert_status "http://localhost:${PORT}/customers/not-a-real-id/recommendation" "404" \
    "GET /customers/{unknown}/recommendation (404 expected)"

# Filtered top customers
assert_status "http://localhost:${PORT}/customers/top?quadrant=2.+Urgent+Win-back&n=3" "200" \
    "GET /customers/top filtered by quadrant"

# Validation errors
assert_status "http://localhost:${PORT}/customers/top?n=0" "422" \
    "GET /customers/top?n=0 (422 expected)"

# ---------------------------------------------------------------------------
# Step 5: Print sample output
# ---------------------------------------------------------------------------
log ""
log "Sample recommendation response (truncated):"
curl -fs "http://localhost:${PORT}/customers/${CUSTOMER_ID}/recommendation" \
    | python3 -m json.tool | head -25

# ---------------------------------------------------------------------------
# Step 6: Image Size
# ---------------------------------------------------------------------------
log ""
log "Image size:"
docker images "$IMAGE_NAME:$TAG" --format " {{.Repository}}:{{.Tag}} {{.Size}}"

log ""
log "🎉 ALL CHECKS PASSED"