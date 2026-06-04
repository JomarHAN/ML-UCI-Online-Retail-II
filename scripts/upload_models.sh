#!/usr/bin/env bash
# =============================================================================
# scripts/upload_models.sh — sync trained models + processed data to S3
# =============================================================================
# Run this:
#   - Once initially after `terraform apply` and before `deploy.sh`
#   - Every time you retrain a model and want to push the new version
#
# `aws s3 sync` is smart: it only uploads files that changed, so re-runs
# are fast even if you have lots of data.
# =============================================================================

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'
log() { echo -e "${GREEN}[upload]${NC} $*"; }
err() { echo -e "${RED}[upload]${NC} $*" >&2; }

cd "$(dirname "$0")/.." # cd to repo root

# Read S3 bucket name from Terraform outputs
if [ ! -f terraform/terraform.tfstate ]; then
    err "No terraform state found. Run 'terraform apply' first."
    exit 1
fi

S3_BUCKET=$(cd terraform && terraform output -raw s3_bucket_name)
REGION=$(cd terraform && terraform output -raw aws_region)

log "Target: s3://$S3_BUCKET (region: $REGION)"

# -----------------------------------------------------------------------------
# Sanity check the local files exist
# -----------------------------------------------------------------------------
if [ ! -d models ] || [ -z "$(ls -A models 2>/dev/null)" ]; then
    err "No models found in ./models/. Run notebooks 05 and 06 first."
    exit 1
fi

if [ ! -d data/processed ] || [ -z "$(ls -A data/processed 2>/dev/null)" ]; then
    err "No processed data found in ./data/processed/. Run notebooks 02-04 first."
    exit 1
fi

# -----------------------------------------------------------------------------
# Sync
# -----------------------------------------------------------------------------
log "Uploading models/..."
aws s3 sync ./models/ "s3://$S3_BUCKET/models/" \
    --region "$REGION" \
    --exclude "*.pyc" \
    --exclude "__pycache__/*"

log "Uploading data/processed/..."
aws s3 sync ./data/processed/ "s3://$S3_BUCKET/data/processed/" \
    --region "$REGION" \
    --exclude "*.pyc" \
    --exclude "__pycache__/*"

log "Done. Contents of s3://$S3_BUCKET/:"
aws s3 ls "s3://$S3_BUCKET/" --recursive --human-readable --summarize --region "$REGION" | tail -20
