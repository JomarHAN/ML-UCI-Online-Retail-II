# Terraform — UCI Retail API on AWS

This directory provisions everything needed to run the UCI Online Retail API on AWS:

- VPC + subnet + security group
- ECR repository for the Docker image
- S3 bucket for trained model artifacts
- EC2 t3.micro instance (free tier eligible)
- IAM role giving the instance least-privilege access to ECR and S3
- Elastic IP for a stable public URL

End state: a live, public URL like `http://44.123.45.67/docs` serving the API.

## Architecture

```
                                Internet
                                   │
                                   ▼
                          ┌────────────────┐
                          │ Elastic IP     │
                          │ (stable URL)   │
                          └────────┬───────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │ VPC (10.0.0.0/16)  │                    │
              │                    │                    │
              │     ┌──────────────▼───────────────┐    │
              │     │ Public Subnet (10.0.1.0/24)  │    │
              │     │                              │    │
              │     │   ┌──────────────────────┐   │    │
              │     │   │ EC2 t3.micro         │   │    │
              │     │   │  - Docker container  │   │    │
              │     │   │  - port 80 → 8000    │   │    │
              │     │   └──────────────────────┘   │    │
              │     │            ▲                 │    │
              │     │            │ pulls image     │    │
              │     │            ▼                 │    │
              │     │       ┌────────┐             │    │
              │     │       │  ECR   │             │    │
              │     │       └────────┘             │    │
              │     │            ▲                 │    │
              │     │            │ pulls models    │    │
              │     │            ▼                 │    │
              │     │       ┌────────┐             │    │
              │     │       │   S3   │             │    │
              │     │       └────────┘             │    │
              │     └──────────────────────────────┘    │
              └────────────────────────────────────────┘
```

## Cost summary

| State | Cost |
|---|---|
| Running 24/7 | ~$0-1/month (free tier) |
| Destroyed via `terraform destroy` | ~$0.10/month (just ECR image storage) |
| ⚠️ EC2 stopped but EIP attached | ~$3.60/month (EIP idle fee) |

**The destroy-when-done pattern saves the most money.** Always destroy after demoing.

## Prerequisites

1. **AWS account** + IAM admin user with access keys
2. **AWS CLI** configured: `aws configure`, then verify with `aws sts get-caller-identity`
3. **Terraform** installed: `terraform --version` (need 1.5+)
4. **SSH key pair** for EC2 access:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/aws-ec2 -C "aws-ec2-uci-retail"
   ```
5. **Docker Desktop** running (for the deploy step)
6. **Trained models** in `../models/` and processed data in `../data/processed/`
   (run notebooks 01-08 once if you haven't)
7. **AWS billing alarm** set at $5 (Billing Console → Budgets → Create budget)

## One-time setup

```bash
# 1. Copy the example tfvars and fill in YOUR values
cp terraform.tfvars.example terraform.tfvars

# 2. Edit terraform.tfvars — set my_ip_cidr to YOUR public IP
#    Find your IP: curl -s https://checkip.amazonaws.com
#    Append /32: "203.0.113.42/32"

# 3. Initialize Terraform (downloads the AWS provider)
terraform init

# 4. Preview what will be created
terraform plan
```

`terraform plan` shows about 20 resources to be created. Read the output. Nothing is created yet at this point — `plan` is read-only.

## First deployment

```bash
# 1. Provision AWS infrastructure (takes ~3 minutes)
terraform apply
# Type `yes` when prompted.

# 2. Upload trained models to S3 (from repo root)
cd ..
bash scripts/upload_models.sh

# 3. Build, push, and deploy the API
bash scripts/deploy.sh
```

After these three steps you'll have a live URL. Test it:

```bash
# Get the URL from Terraform outputs
cd terraform
terraform output api_url

# Hit it
curl $(terraform output -raw api_url)/health
```

## Redeploying after code changes

Just rebuild and push — Terraform infrastructure stays as-is:

```bash
bash scripts/deploy.sh
```

The script builds the image, pushes to ECR, and restarts the systemd service on EC2. Takes about 2 minutes.

## Redeploying after model retraining

```bash
bash scripts/upload_models.sh    # uploads new models to S3
bash scripts/deploy.sh           # restarts container, which re-syncs from S3
```

## Destroying everything

When you're done demoing:

```bash
cd terraform
terraform destroy
# Type `yes` when prompted.
```

Tears down everything in ~2 minutes. Cost drops to ~$0.10/month (the only thing left is the ECR image storage). To get to fully zero, also delete the ECR repository manually, but at $0.10/mo it's not worth the friction.

## Common issues

**`terraform apply` fails with "InvalidClientTokenId"**
→ AWS CLI credentials aren't configured. Run `aws configure` and verify with `aws sts get-caller-identity`.

**`terraform apply` fails on `aws_key_pair` saying "key not found"**
→ The SSH public key path in `terraform.tfvars` is wrong. Run `ls ~/.ssh/aws-ec2.pub` to confirm the file exists, fix the path in `terraform.tfvars`.

**SSH connection times out**
→ Your IP changed (e.g., you moved networks). Find your new IP, update `my_ip_cidr` in `terraform.tfvars`, then `terraform apply` to update the security group. Or use SSM Session Manager from the AWS console (works regardless of IP).

**`deploy.sh` fails with "exec format error" in container logs**
→ You built an arm64 image (Apple Silicon) but the EC2 is x86. The script includes `--platform linux/amd64` to prevent this; make sure you haven't removed it.

**Container starts but `/health` returns connection refused**
→ The container failed to load models. SSH in and check logs:
```bash
ssh -i ~/.ssh/aws-ec2 ec2-user@$(terraform output -raw instance_public_ip)
sudo journalctl -u uci-retail-api -n 100
```
Usually means S3 sync didn't run, or the models bucket is empty. Re-run `upload_models.sh`.

## What this does NOT include

These are deliberately deferred to Step 13b:

- **HTTPS / SSL certificates** — requires a domain you own
- **API key authentication** — anyone with the URL can hit the API
- **Structured JSON logging** to CloudWatch
- **Auto-scaling** — one instance only
- **Multi-AZ redundancy** — single AZ means single point of failure
- **DynamoDB for customer features** — still using parquet
- **Drift monitoring** — Step 14 territory

If this deployment serves your portfolio needs, you may never need 13b. If it goes into actual production, 13b becomes mandatory.

## Reading the code

Files in this directory, in suggested reading order:

1. `versions.tf` — provider versions + AWS region setup
2. `variables.tf` — all configurable inputs
3. `network.tf` — VPC, subnet, security group
4. `iam.tf` — IAM role for EC2
5. `ecr.tf` — Docker image registry
6. `s3.tf` — model artifact bucket
7. `user_data.sh` — script that runs on EC2 first boot
8. `ec2.tf` — the instance itself
9. `outputs.tf` — what gets printed after apply

Each file has extensive comments explaining the why, not just the what.