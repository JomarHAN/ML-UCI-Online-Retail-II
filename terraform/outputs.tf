# =============================================================================
# outputs.tf — what Terraform prints after `apply` succeeds
# =============================================================================
# These are the values you'll need to use the deployment:
#   - api_url:    the URL to hit (http://<elastic-ip>)
#   - ssh_command: ready-to-paste SSH command
#   - ecr_uri:    the registry URI you'll docker-push to
#   - s3_bucket:  where to upload models
# =============================================================================

output "api_url" {
  description = "Base URL of the deployed API"
  value       = "http://${aws_eip.api.public_ip}"
}

output "api_docs_url" {
  description = "Interactive API documentation"
  value       = "http://${aws_eip.api.public_ip}/docs"
}

output "instance_public_ip" {
  description = "Public IP of the EC2 instance"
  value       = aws_eip.api.public_ip
}

output "ssh_command" {
  description = "Ready-to-paste SSH command (replace the key path if you used a custom one)"
  value       = "ssh -i ${var.ssh_public_key_path} ec2-user@${aws_eip.api.public_ip}"
}

output "ecr_repository_uri" {
  description = "URI of the ECR repository — used by scripts/deploy.sh"
  value       = aws_ecr_repository.api.repository_url
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket for model artifacts — used by scripts/upload_models.sh"
  value       = aws_s3_bucket.models.id
}

output "aws_region" {
  description = "AWS region (handy for scripts that need it)"
  value       = var.aws_region
}

output "estimated_monthly_cost_running" {
  description = "Rough estimate when the stack is running 24/7"
  value       = "~$0-1/mo (t3.micro free tier covers EC2; ECR storage + minor data transfer)"
}

output "estimated_monthly_cost_destroyed" {
  description = "Cost when destroyed via `terraform destroy`"
  value       = "~$0.10/mo (ECR storage of pushed images; ~$0 if no images pushed)"
}
