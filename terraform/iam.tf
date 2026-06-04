# =============================================================================
# iam.tf — IAM role that lets the EC2 instance talk to ECR and S3
# =============================================================================
# WHY use IAM roles instead of access keys?
#   - We could put AWS credentials on the EC2 instance, but that's a leak waiting
#     to happen. If the instance is compromised, the keys are stolen too.
#   - IAM roles attach permissions to the instance itself. The EC2 metadata
#     service automatically rotates short-lived credentials. No keys to manage.
#
# The chain looks like this:
#   IAM Policy        → defines what's allowed (e.g., "pull from ECR")
#       ↓
#   IAM Role          → bundles policies, identity that AWS services can assume
#       ↓
#   Instance Profile  → the wrapper EC2 needs to use a role (legacy quirk)
#       ↓
#   EC2 instance      → attaches the instance profile at boot
# =============================================================================

# ----------------------------------------------------------------------------
# Trust policy: who is allowed to ASSUME this role?
# ----------------------------------------------------------------------------
# Answer: only the EC2 service. This makes the role usable from EC2 instances
# but not from random users or other services.
data "aws_iam_policy_document" "ec2_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "ec2" {
  name               = "${var.project_name}-ec2-role"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume_role.json

  tags = {
    Name = "${var.project_name}-ec2-role"
  }
}

# ----------------------------------------------------------------------------
# Permission 1: pull Docker images from ECR
# ----------------------------------------------------------------------------
# ECR pulls require multiple actions:
#   - GetAuthorizationToken: get a temporary docker login token
#   - BatchGetImage / GetDownloadUrlForLayer: actually pull layers
# We use the AWS-managed policy AmazonEC2ContainerRegistryReadOnly which
# bundles these. Using a managed policy is the secure default — AWS keeps it
# up to date with new actions as ECR evolves.
resource "aws_iam_role_policy_attachment" "ecr_read" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

# ----------------------------------------------------------------------------
# Permission 2: read trained models from our S3 bucket
# ----------------------------------------------------------------------------
# Custom inline policy because we want to limit access to ONLY our bucket,
# not all S3 (which the AWS-managed policy would do). This is "least privilege"
# in practice.
data "aws_iam_policy_document" "s3_read_models" {
  statement {
    sid    = "ReadModelArtifacts"
    effect = "Allow"
    actions = [
      "s3:GetObject",
      "s3:ListBucket",
    ]
    resources = [
      aws_s3_bucket.models.arn,
      "${aws_s3_bucket.models.arn}/*",
    ]
  }
}

resource "aws_iam_policy" "s3_read_models" {
  name        = "${var.project_name}-s3-read-models"
  description = "Read access to the model artifacts bucket"
  policy      = data.aws_iam_policy_document.s3_read_models.json
}

resource "aws_iam_role_policy_attachment" "s3_read_models" {
  role       = aws_iam_role.ec2.name
  policy_arn = aws_iam_policy.s3_read_models.arn
}

# ----------------------------------------------------------------------------
# Permission 3: write logs to CloudWatch (useful for debugging via console)
# ----------------------------------------------------------------------------
# Optional but cheap — lets us see container logs in the AWS Console without
# SSH'ing in. AWS-managed policy is fine here.
resource "aws_iam_role_policy_attachment" "cloudwatch_agent" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

# ----------------------------------------------------------------------------
# Permission 4: SSM Session Manager (browser-based SSH alternative)
# ----------------------------------------------------------------------------
# Lets you "SSH" to the instance from the AWS Console without managing
# SSH keys or opening port 22. Great fallback when you're traveling and your
# IP changes (so the SSH security group rule doesn't match).
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

# ----------------------------------------------------------------------------
# Instance profile — the wrapper EC2 uses to attach the role
# ----------------------------------------------------------------------------
# This is a legacy quirk: EC2 can't attach IAM roles directly, it has to
# attach an instance profile, which is just a thin wrapper around a role.
# You'll never use the instance profile name except in the aws_instance config.
resource "aws_iam_instance_profile" "ec2" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2.name
}
