# =============================================================================
# network.tf — VPC, subnet, IGW, route table, security group
# =============================================================================
# What this creates:
#
#   Internet  ─────  Internet Gateway  ─────  VPC (10.0.0.0/16)
#                                              │
#                                              └── Public Subnet (10.0.1.0/24)
#                                                    │
#                                                    └── EC2 instance
#                                                          ▲
#                                                          │
#                                                  Security Group (firewall)
#                                                          │
#                                                  ┌───────┴────────┐
#                                                  │                │
#                                                Port 80         Port 22
#                                              from anyone     from your IP only
#
# WHY only ONE subnet (instead of multi-AZ)?
#   A real production deployment uses multiple subnets in different availability
#   zones for fault tolerance. We don't need that for a learning project — if
#   AWS us-east-1a goes down, our demo is down for an hour. Acceptable.
#   Single subnet keeps everything simpler and costs less.
#
# WHY a custom VPC (instead of the default VPC)?
#   The default VPC works, but it's "magical" — it has subnets and IGWs that
#   you don't see in code. Building our own makes the architecture explicit
#   and is what you'd do in production.
# =============================================================================

# ----------------------------------------------------------------------------
# Discover the AZs available in our region (varies by region)
# ----------------------------------------------------------------------------
data "aws_availability_zones" "available" {
  state = "available"
}

# ----------------------------------------------------------------------------
# The VPC itself — an isolated network in AWS
# ----------------------------------------------------------------------------
# CIDR 10.0.0.0/16 gives us 65,536 IPs. Massive overkill for one EC2 instance,
# but the convention is to leave room to grow. 10.x.x.x is RFC 1918 private space.
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true # so EC2 instances get DNS names like ip-10-0-1-42.ec2.internal
  enable_dns_support   = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

# ----------------------------------------------------------------------------
# Internet Gateway — the door between our VPC and the public internet
# ----------------------------------------------------------------------------
# Without an IGW, the VPC is isolated. Resources inside can talk to each
# other but not to anything outside. The IGW changes that.
# IGWs are free; only the data going through them is metered (and minimal).
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-igw"
  }
}

# ----------------------------------------------------------------------------
# Public subnet — one /24 carved out of the /16 VPC
# ----------------------------------------------------------------------------
# "Public" just means "has a route to the Internet Gateway." We achieve that
# with the route table below. The subnet itself is just an IP range.
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24" # 256 IPs, plenty
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true # auto-assign a public IP to instances launched here

  tags = {
    Name = "${var.project_name}-public-subnet"
  }
}

# ----------------------------------------------------------------------------
# Route table — tells the subnet "to reach the internet, go through the IGW"
# ----------------------------------------------------------------------------
# A route table is a list of "destination -> target" rules. 0.0.0.0/0 means
# "any destination not matched by a more specific rule" — i.e., the public
# internet. We route it to the IGW.
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.project_name}-public-rt"
  }
}

# Associate the route table with our subnet. Without this, the subnet has no
# routes and instances inside can't reach the internet (silent failure).
resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# ----------------------------------------------------------------------------
# Security group — the firewall around our EC2 instance
# ----------------------------------------------------------------------------
# Security groups are stateful: if you allow inbound on port X, the response
# packets are automatically allowed out. We only have to think about inbound.
#
# Two rules:
#   1. SSH (port 22) — only from YOUR IP (so only you can shell in)
#   2. HTTP (port 80) — from anywhere (so anyone can hit the API)
#
# We do NOT open port 8000 (the FastAPI port). Instead, we'll set up port
# forwarding from 80 → 8000 in the EC2 user_data script. Why?
#   - Port 80 is the standard HTTP port — no `:8000` needed in URLs
#   - Lets us add HTTPS later (port 443) without changing client URLs
#   - Standard practice
resource "aws_security_group" "ec2" {
  name        = "${var.project_name}-ec2-sg"
  description = "Allow SSH from my IP, HTTP from anywhere"
  vpc_id      = aws_vpc.main.id

  # Inbound: SSH from your IP only
  ingress {
    description = "SSH from my IP"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }

  # Inbound: HTTP from anywhere
  ingress {
    description = "HTTP from internet"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Outbound: everything (so the instance can reach the internet to apt-update,
  # pull Docker images from ECR, download from S3, etc.). This is the default
  # but explicit is better than implicit.
  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1" # all protocols
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-ec2-sg"
  }
}
