#!/bin/bash
# =============================================================================
# user_data.sh — runs ONCE when the EC2 instance first boots
# =============================================================================
# This script:
#   1. Updates system packages
#   2. Installs Docker
#   3. Configures Docker to authenticate with ECR (via IAM role, no secrets)
#   4. Sets up port forwarding from port 80 → 8000 (so users can hit the
#      site at http://<ip>/ instead of http://<ip>:8000/)
#   5. Sets up systemd to keep the container running
#   6. Logs everything to /var/log/user-data.log for debugging
#
# Variables prefilled by Terraform via templatefile():
#   - REGION:     AWS region (passed in via the EC2 resource)
#   - ECR_URI:    full URI of the ECR repository
#   - S3_BUCKET:  name of the S3 bucket holding model artifacts
#   - API_PORT:   port the container listens on (default 8000)
# =============================================================================

set -e
exec > >(tee /var/log/user-data.log | logger -t user-data -s 2>/dev/console) 2>&1

REGION="${REGION}"
ECR_URI="${ECR_URI}"
S3_BUCKET="${S3_BUCKET}"
API_PORT="${API_PORT}"

echo "[user-data] === Starting boot script at $$(date) ==="

# ----------------------------------------------------------------------------
# 1. Update packages
# ----------------------------------------------------------------------------
echo "[user-data] Updating packages..."
dnf update -y

# ----------------------------------------------------------------------------
# 2. Install Docker (and other helpers we'll want)
# ----------------------------------------------------------------------------
echo "[user-data] Installing Docker..."
dnf install -y docker
systemctl enable docker
systemctl start docker

# Add ec2-user to the docker group so they can run docker without sudo
usermod -aG docker ec2-user

# ----------------------------------------------------------------------------
# 3. Install AWS CLI v2 (Amazon Linux 2023 doesn't ship it by default)
# ----------------------------------------------------------------------------
echo "[user-data] Installing AWS CLI v2..."
dnf install -y unzip
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "/tmp/awscliv2.zip"
unzip -q /tmp/awscliv2.zip -d /tmp/
/tmp/aws/install --update
rm -rf /tmp/awscliv2.zip /tmp/aws

# ----------------------------------------------------------------------------
# 4. Download model artifacts from S3
# ----------------------------------------------------------------------------
# The IAM role on this instance allows reading the models bucket. We sync
# everything to /opt/uci-retail/models — the container will bind-mount this.
echo "[user-data] Downloading models from S3 bucket: $${S3_BUCKET}"
mkdir -p /opt/uci-retail/models /opt/uci-retail/data/processed

aws s3 sync "s3://$${S3_BUCKET}/models/" /opt/uci-retail/models/ --region "$${REGION}"
aws s3 sync "s3://$${S3_BUCKET}/data/processed/" /opt/uci-retail/data/processed/ --region "$${REGION}"

echo "[user-data] Files downloaded to /opt/uci-retail:"
ls -lh /opt/uci-retail/models/ /opt/uci-retail/data/processed/ || true

# ----------------------------------------------------------------------------
# 5. Authenticate Docker with ECR (using IAM role — no secrets)
# ----------------------------------------------------------------------------
echo "[user-data] Logging Docker into ECR..."
aws ecr get-login-password --region "$${REGION}" | \
  docker login --username AWS --password-stdin "$${ECR_URI%/*}"

# ----------------------------------------------------------------------------
# 6. Pull the image and start the container via systemd
# ----------------------------------------------------------------------------
# We use systemd so the container automatically restarts on failure or reboot.
# This is the simple production pattern: 1 instance + systemd-managed container.
echo "[user-data] Creating systemd unit for the API container..."

cat > /etc/systemd/system/uci-retail-api.service <<EOF
[Unit]
Description=UCI Retail Recommendation API
Requires=docker.service
After=docker.service

[Service]
Restart=always
RestartSec=10

# Re-authenticate with ECR before each (re)start (token expires every 12h)
ExecStartPre=/bin/bash -c '/usr/local/bin/aws ecr get-login-password --region $${REGION} | docker login --username AWS --password-stdin $${ECR_URI%/*}'

# Pull the latest image
ExecStartPre=/usr/bin/docker pull $${ECR_URI}:latest

# Remove any old container with the same name (idempotent)
ExecStartPre=-/usr/bin/docker rm -f uci-retail-api

# Run the container, mounting models and binding port 80 -> 8000
ExecStart=/usr/bin/docker run --rm \\
    --name uci-retail-api \\
    -p 80:$${API_PORT} \\
    -v /opt/uci-retail/models:/app/models:ro \\
    -v /opt/uci-retail/data/processed:/app/data/processed:ro \\
    $${ECR_URI}:latest

ExecStop=/usr/bin/docker stop uci-retail-api

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

# Note: we do NOT auto-start the service here — the image hasn't been pushed
# to ECR yet at this point (Terraform creates the EC2 BEFORE you've pushed
# the first image). The deploy.sh script will start it after pushing.
echo "[user-data] === Boot script complete at $$(date) ==="
echo "[user-data] To start the API: sudo systemctl enable --now uci-retail-api"
