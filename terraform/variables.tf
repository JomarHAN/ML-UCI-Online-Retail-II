# =============================================================================
# variables.tf — inputs to this Terraform configuration
# =============================================================================
# Every value that might differ between environments or developers lives here.
# Values are provided via terraform.tfvars (gitignored) or -var flags.
#
# Why variables matter:
#   - Same code can deploy to dev/staging/prod with different inputs
#   - Sensitive values stay out of git
#   - Documentation: this file is the "what knobs can I turn" reference
# =============================================================================

variable "aws_region" {
  description = "AWS region to deploy into. Stick with us-east-1 unless you have a reason to change."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short name used as a prefix for all resources. Lowercase, hyphens, no spaces."
  type        = string
  default     = "uci-retail"

  validation {
    condition     = can(regex("^[a-z0-9-]+$", var.project_name))
    error_message = "project_name must be lowercase letters, numbers, and hyphens only."
  }
}

variable "my_ip_cidr" {
  description = <<-EOT
    Your home/office IP in CIDR notation (e.g., "203.0.113.42/32") for SSH access.
    Find your IP at https://checkip.amazonaws.com — append /32 for a single host.
    
    SECURITY: never set this to 0.0.0.0/0 (the whole internet) — that's a free invite
    for bots to brute-force your SSH key. /32 = "exactly this one IP".
  EOT
  type        = string

  validation {
    condition     = can(cidrhost(var.my_ip_cidr, 0))
    error_message = "my_ip_cidr must be a valid CIDR like \"203.0.113.42/32\"."
  }
}

variable "ssh_public_key_path" {
  description = "Path to the SSH public key generated for AWS (e.g., ~/.ssh/aws-ec2.pub)."
  type        = string
  default     = "~/.ssh/aws-ec2.pub"
}

variable "instance_type" {
  description = <<-EOT
    EC2 instance type. t3.micro is free tier eligible (12 months, 750 hrs/mo).
    
    If the API runs out of memory, bump to t3.small (~$15/mo) — XGBoost + SHAP
    on 5000 customers should fit in 1GB but we're close to the edge.
  EOT
  type        = string
  default     = "t3.micro"
}

variable "api_port" {
  description = "Port the FastAPI container listens on. Should match Dockerfile EXPOSE."
  type        = number
  default     = 8000
}
