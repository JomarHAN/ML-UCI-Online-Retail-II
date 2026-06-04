# =============================================================================
# s3.tf — S3 bucket for trained model artifacts
# =============================================================================
# Why S3 (instead of baking models into the Docker image)?
#   - Models change more often than code; separating them means we can retrain
#     and redeploy without rebuilding the image
#   - Same image works in dev/staging/prod with different model versions
#   - S3 is essentially free at our scale (<1GB, free tier covers 5GB/mo)
#   - The pattern transfers to ANY production ML setup (this is how it's done)
#
# Flow:
#   Local laptop  ──upload──▶  S3 bucket  ──download at startup──▶  EC2 container
#                                  ▲
#                                  │
#                          scripts/upload_models.sh
# =============================================================================

# ----------------------------------------------------------------------------
# Random suffix because S3 bucket names are GLOBALLY unique across all of AWS
# ----------------------------------------------------------------------------
# If you tried `uci-retail-models` directly, you'd likely collide with someone
# else's bucket. A random suffix avoids that. Generated once, persisted in state.
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# ----------------------------------------------------------------------------
# The bucket itself
# ----------------------------------------------------------------------------
resource "aws_s3_bucket" "models" {
  bucket = "${var.project_name}-models-${random_id.bucket_suffix.hex}"

  # `terraform destroy` will fail if the bucket has objects, unless force_destroy
  # is true. For learning, we want clean teardown; for production, you'd leave
  # this false to prevent accidental data loss.
  force_destroy = true

  tags = {
    Name = "${var.project_name}-models"
  }
}

# ----------------------------------------------------------------------------
# Versioning — keep previous versions of objects when overwritten
# ----------------------------------------------------------------------------
# If you upload a new model and it's bad, S3 keeps the previous version so
# you can roll back. Costs the storage of the older versions (negligible
# at our scale). Best practice in any case.
resource "aws_s3_bucket_versioning" "models" {
  bucket = aws_s3_bucket.models.id

  versioning_configuration {
    status = "Enabled"
  }
}

# ----------------------------------------------------------------------------
# Block ALL public access — security default
# ----------------------------------------------------------------------------
# S3 bucket misconfigurations are the #1 cause of public data leaks in AWS.
# We don't want our models to be publicly downloadable. This blocks even
# accidental "make this object public" actions.
resource "aws_s3_bucket_public_access_block" "models" {
  bucket = aws_s3_bucket.models.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ----------------------------------------------------------------------------
# Server-side encryption at rest (free, no reason not to enable)
# ----------------------------------------------------------------------------
resource "aws_s3_bucket_server_side_encryption_configuration" "models" {
  bucket = aws_s3_bucket.models.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
