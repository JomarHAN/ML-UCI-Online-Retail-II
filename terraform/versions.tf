# =============================================================================
# versions.tf — Terraform & provider version constraints
# =============================================================================
# Why pin versions:
#   - terraform: language syntax can break between major versions
#   - aws provider: resource arguments and defaults change between versions
#   - Without pinning, your `terraform apply` might work today and fail tomorrow
#
# The `~>` operator is "pessimistic constraint": ~> 5.0 means >= 5.0.0, < 6.0.0
# (allows patch and minor updates, blocks breaking major upgrades).
# =============================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # In production you'd configure a remote backend (S3 + DynamoDB lock) to
  # share state across a team. For a solo learning project, local state is fine.
  # Just don't lose terraform.tfstate — it's the record of what AWS resources
  # this code created. Without it, `terraform destroy` doesn't know what to destroy.
}

# Configure the AWS provider. region is the only required input; credentials
# come from ~/.aws/credentials (set by `aws configure`).
provider "aws" {
  region = var.aws_region

  # Tag every resource we create so we can attribute costs in AWS Cost Explorer.
  # This is THE most important habit for learning AWS without surprise bills.
  default_tags {
    tags = {
      Project     = var.project_name
      Environment = "dev"
      ManagedBy   = "terraform"
    }
  }
}
