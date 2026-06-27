variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "Target deployment region"
}

variable "environment" {
  type        = string
  default     = "production"
  description = "Target execution environment"
}

variable "db_password" {
  type        = string
  default     = "secure_production_password_must_change"
  sensitive   = true
}

variable "redis_password" {
  type        = string
  default     = "secure_redis_password_must_change"
  sensitive   = true
}
