#!/usr/bin/env bash
# =============================================================================
# scripts/deploy.sh — build, push, and roll out a new version of the API
# =============================================================================
# This script does what would normally be three steps in production:
#   1. Build the Docker image locally
#   2. Push it to ECR
#   3. SSH into the EC2 instance and force it to pull and restart the container
#
# Run from the repo root:
#   bash scripts/deploy.sh
#
# Prerequisites:
#   - terraform apply has succeeded (so ECR + EC2 exist)
#   - AWS CLI is configured (~/.aws/credentials)
#   - Docker Desktop is running on your laptop
# =============================================================================

set -euo pipefail  # exit on any error, undefined var, or pipe failure

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log()  { echo -e "${GREEN}[deploy]${NC} $*"; }
warn() { echo -e "${YELLOW}[deploy]${NC} $*"; }
err()  { echo -e "${RED}[deploy]${NC} $*" >&2; }

# -----------------------------------------------------------------------------
# Read the Terraform outputs (so we don't hardcode anything)
# -----------------------------------------------------------------------------
cd "$(dirname "$0")/.." # cd to repo root

if [ ! -f terraform/terraform.tfstate ]; then
    err "No terraform state found. Run 'terraform apply' in ./terraform first."
    exit 1
fi

log "Reading Terraform outputs..."
ECR_URI=$(cd terraform && terraform output -raw ecr_repository_uri)
EC2_IP=$(cd terraform && terraform output -raw instance_public_ip)
REGION=$(cd terraform && terraform output -raw aws_region)
SSH_KEY="${SSH_KEY:-$HOME/.ssh/aws-ec2}"  # override with `SSH_KEY=... bash scripts/deploy.sh`

log "  ECR:    $ECR_URI"
log "  EC2 IP: $EC2_IP"
log "  Region: $REGION"
log "  SSH key: $SSH_KEY"

# -----------------------------------------------------------------------------
# Step 1: Authenticate Docker with ECR
# -----------------------------------------------------------------------------
log "Logging Docker into ECR..."
aws ecr get-login-password --region "$REGION" \
    | docker login --username AWS --password-stdin "${ECR_URI%/*}"

# -----------------------------------------------------------------------------
# Step 2: Build the image with two tags: 'latest' and a timestamp
# -----------------------------------------------------------------------------
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
log "Building image (this may take 2-5 minutes on first build)..."
docker build \
    --platform linux/amd64 \
    -t "$ECR_URI:latest" \
    -t "$ECR_URI:$TIMESTAMP" \
    .

# IMPORTANT: --platform linux/amd64 is critical if you're on Apple Silicon.
# Without it, you build an arm64 image that won't run on the x86 EC2 instance.
# Symptom: "exec format error" in container logs after deploy.

# -----------------------------------------------------------------------------
# Step 3: Push both tags
# -----------------------------------------------------------------------------
log "Pushing image to ECR..."
docker push "$ECR_URI:latest"
docker push "$ECR_URI:$TIMESTAMP"

log "Image pushed:"
log "  $ECR_URI:latest"
log "  $ECR_URI:$TIMESTAMP"

# -----------------------------------------------------------------------------
# Step 4: SSH into EC2 and restart the systemd service
# -----------------------------------------------------------------------------
# The systemd unit (from user_data.sh) does `docker pull` + `docker run` on
# each start. Restarting it picks up the new image.
log "Triggering service restart on EC2..."

ssh -o StrictHostKeyChecking=accept-new \
    -i "$SSH_KEY" \
    "ec2-user@$EC2_IP" <<'EOF'
set -e
echo "[remote] Restarting uci-retail-api service..."
sudo systemctl enable uci-retail-api
sudo systemctl restart uci-retail-api
echo "[remote] Service status:"
sudo systemctl status uci-retail-api --no-pager --lines=5 || true
EOF

# -----------------------------------------------------------------------------
# Step 5: Wait for the API to come back up
# -----------------------------------------------------------------------------
log "Waiting for /health to return 200..."
for i in $(seq 1 60); do
    if curl --fail --silent --max-time 2 "http://$EC2_IP/health" > /dev/null 2>&1; then
        log "✓ API is healthy"
        log ""
        log "🎉 Deployment complete!"
        log "   API:  http://$EC2_IP"
        log "   Docs: http://$EC2_IP/docs"
        log ""
        log "Try it:"
        log "   curl http://$EC2_IP/health"
        log "   curl 'http://$EC2_IP/customers/top?n=3'"
        exit 0
    fi
    sleep 2
done

err "API did not become healthy in 120s. Check container logs:"
err "   ssh -i $SSH_KEY ec2-user@$EC2_IP 'sudo journalctl -u uci-retail-api -n 100'"
exit 1
