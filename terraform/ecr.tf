# =============================================================================
# ecr.tf — Elastic Container Registry: where our Docker image lives in AWS
# =============================================================================
# ECR is AWS's hosted Docker registry. Workflow:
#
#   Your laptop                      AWS
#   ──────────                       ───
#   docker build      ──────────▶
#   docker tag        ──────────▶    ECR repository (this resource)
#   docker push       ──────────▶            │
#                                            │
#                                            ▼
#                                    EC2 instance pulls
#                                    via IAM role (no docker login secrets)
#
# WHY not use Docker Hub?
#   - Docker Hub is fine but requires login credentials to be stored on EC2
#   - ECR authenticates via IAM (no secrets), so it's more secure by design
#   - It's the "AWS-native" answer; learning ECR is portable to any AWS job
# =============================================================================

resource "aws_ecr_repository" "api" {
  name = "${var.project_name}-api"

  # AES256 encryption of stored layers — free, no reason not to enable
  encryption_configuration {
    encryption_type = "AES256"
  }

  # Scan pushed images for known CVEs. Free, automatic, useful.
  image_scanning_configuration {
    scan_on_push = true
  }

  # Image tag mutability:
  #   - MUTABLE: pushing "latest" overwrites the previous "latest" (our choice)
  #   - IMMUTABLE: each tag can only be used once (production-grade discipline)
  # We use MUTABLE for the learning project so deploys are simpler.
  image_tag_mutability = "MUTABLE"

  # Allow Terraform destroy to delete the repo even if it has images in it.
  # WITHOUT this, `terraform destroy` would fail until you manually empty ECR.
  force_delete = true

  tags = {
    Name = "${var.project_name}-api"
  }
}

# ----------------------------------------------------------------------------
# Lifecycle policy — auto-delete old images to control storage costs
# ----------------------------------------------------------------------------
# ECR is cheap ($0.10/GB/mo) but we don't need to keep every image we ever
# pushed. This policy keeps the most recent 5 images and deletes the rest.
resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep only the 5 most recent images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 5
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
