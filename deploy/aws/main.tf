terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# --------------------------------------------------------------------------
# Data sources
# --------------------------------------------------------------------------
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

data "aws_vpc" "default" {
  default = true
}

# --------------------------------------------------------------------------
# Security group
# --------------------------------------------------------------------------
resource "aws_security_group" "data_api" {
  name_prefix = "${var.project_name}-"
  description = "Data API Collector - API, Kafka, Postgres, Neo4j access"
  vpc_id      = data.aws_vpc.default.id

  # SSH
  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  # Caddy HTTP
  ingress {
    description = "Caddy HTTP (API)"
    from_port   = 10800
    to_port     = 10800
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  # Caddy HTTPS
  ingress {
    description = "Caddy HTTPS (API)"
    from_port   = 10443
    to_port     = 10443
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  # Kafka external (SASL/SSL via nginx)
  ingress {
    description = "Kafka external (SASL/SSL)"
    from_port   = 9093
    to_port     = 9093
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  # Kafka SASL (direct)
  ingress {
    description = "Kafka SASL (direct)"
    from_port   = 9094
    to_port     = 9094
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  # PostgreSQL SSL
  ingress {
    description = "PostgreSQL (native SSL)"
    from_port   = 15433
    to_port     = 15433
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  # Neo4j Bolt (TLS via nginx)
  ingress {
    description = "Neo4j Bolt (TLS)"
    from_port   = 7688
    to_port     = 7688
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  # Neo4j Browser
  ingress {
    description = "Neo4j Browser"
    from_port   = 7474
    to_port     = 7474
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
  }

  # Standard HTTPS (for Let's Encrypt / Caddy auto-TLS)
  dynamic "ingress" {
    for_each = var.enable_https ? [1] : []
    content {
      description = "HTTPS (Let's Encrypt)"
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
    }
  }

  dynamic "ingress" {
    for_each = var.enable_https ? [1] : []
    content {
      description = "HTTP (Let's Encrypt challenge)"
      from_port   = 80
      to_port     = 80
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
    }
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${var.project_name}-sg"
  })
}

# --------------------------------------------------------------------------
# EC2 instance
# --------------------------------------------------------------------------
resource "aws_instance" "data_api" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.instance_type
  key_name               = var.key_name != "" ? var.key_name : null
  vpc_security_group_ids = [aws_security_group.data_api.id]

  root_block_device {
    volume_size           = var.volume_size
    volume_type           = "gp3"
    delete_on_termination = true
  }

  user_data = templatefile("${path.module}/user_data.sh", {
    git_repo   = var.git_repo
    git_branch = var.git_branch
  })

  tags = merge(var.tags, {
    Name = var.project_name
  })
}
