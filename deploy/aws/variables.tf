variable "aws_region" {
  description = "AWS region to deploy into"
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance type. t3.medium (2 vCPU, 4 GB) works for the default stack. Use t3.large if enabling Elasticsearch or OCR profiles."
  type        = string
  default     = "t3.medium"
}

variable "volume_size" {
  description = "Root EBS volume size in GB. 30 GB is sufficient for the default stack. Increase to 50+ if enabling OCR (model caches)."
  type        = number
  default     = 30
}

variable "key_name" {
  description = "Name of an existing EC2 key pair for SSH access. Leave empty to skip SSH key."
  type        = string
  default     = ""
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access the stack (API, Kafka, Postgres, Neo4j). Use your IP or Databricks NAT range."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "project_name" {
  description = "Name prefix for all resources"
  type        = string
  default     = "data-api-collector"
}

variable "git_repo" {
  description = "Git repository URL to clone"
  type        = string
  default     = "https://github.com/RobcPeng/data-api-collector-python.git"
}

variable "git_branch" {
  description = "Git branch to deploy"
  type        = string
  default     = "main"
}

variable "enable_https" {
  description = "Enable HTTPS via Caddy automatic TLS. Requires a domain name pointed at the instance."
  type        = bool
  default     = false
}

variable "domain_name" {
  description = "Domain name for HTTPS (only used if enable_https = true)"
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional tags for all resources"
  type        = map(string)
  default     = {}
}
