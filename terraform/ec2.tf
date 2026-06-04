# =============================================================================
# ec2.tf — the actual server, SSH key registration, Elastic IP
# =============================================================================
# Three resources here:
#   1. Key pair      — register our SSH public key with AWS
#   2. AMI lookup    — find the latest Amazon Linux 2023 AMI ID
#   3. EC2 instance  — the server itself, with our user_data script
#   4. Elastic IP    — a stable public IP that survives reboots
# =============================================================================

# ----------------------------------------------------------------------------
# 1. SSH key pair — uploads our PUBLIC key so we can SSH in
# ----------------------------------------------------------------------------
# Important: this uploads ONLY the .pub (public) half. Your private key
# stays on your laptop and never touches AWS.
resource "aws_key_pair" "main" {
  key_name   = "${var.project_name}-key"
  public_key = file(pathexpand(var.ssh_public_key_path))

  tags = {
    Name = "${var.project_name}-key"
  }
}

# ----------------------------------------------------------------------------
# 2. Find the latest Amazon Linux 2023 AMI
# ----------------------------------------------------------------------------
# AMI IDs differ by region and change over time as Amazon publishes updates.
# Using a data source means we always get the freshest one, automatically.
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }

  filter {
    name   = "architecture"
    values = ["x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ----------------------------------------------------------------------------
# 3. EC2 instance — the actual server
# ----------------------------------------------------------------------------
resource "aws_instance" "api" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.ec2.id]
  key_name               = aws_key_pair.main.key_name
  iam_instance_profile   = aws_iam_instance_profile.ec2.name

  # Root volume — 20 GB is generous for our ~1GB image + models + logs.
  # gp3 is the cheapest and fastest general-purpose volume.
  root_block_device {
    volume_size = 20
    volume_type = "gp3"
    encrypted   = true
  }

  # user_data: the bash script that runs on first boot. We use templatefile()
  # to substitute Terraform variables into the script.
  user_data = templatefile("${path.module}/user_data.sh", {
    REGION    = var.aws_region
    ECR_URI   = aws_ecr_repository.api.repository_url
    S3_BUCKET = aws_s3_bucket.models.id
    API_PORT  = var.api_port
  })

  # When user_data changes, force the instance to be recreated. Otherwise
  # `terraform apply` would silently leave the old instance running with old
  # user_data — confusing and dangerous.
  user_data_replace_on_change = true

  # IMDSv2 enforcement — closes a metadata-service vulnerability class
  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required" # forces IMDSv2
    http_put_response_hop_limit = 2          # allow Docker containers to access (default is 1)
  }

  tags = {
    Name = "${var.project_name}-ec2"
  }
}

# ----------------------------------------------------------------------------
# 4. Elastic IP — a stable public address
# ----------------------------------------------------------------------------
# Without an EIP, the public IP changes every time the instance stops/starts.
# With an EIP, the IP is yours until you release it. Two important details:
#   - EIP is FREE while attached to a running instance
#   - EIP costs $3.60/mo if it's NOT attached (e.g., instance stopped)
#   - When you `terraform destroy`, the EIP is released and the cost stops
resource "aws_eip" "api" {
  instance = aws_instance.api.id
  domain   = "vpc"

  # Make sure the IGW exists before allocating the EIP (otherwise the EIP
  # has no internet to attach to and the apply fails with a vague error)
  depends_on = [aws_internet_gateway.main]

  tags = {
    Name = "${var.project_name}-eip"
  }
}
