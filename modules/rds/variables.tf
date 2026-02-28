variable "project" { type = string }
variable "env"     { type = string }

variable "vpc_id" { type = string }

variable "private_subnet_ids" {
  type = list(string)
}

# Security group of the application (ECS tasks) that will connect to the DB
variable "app_sg_id" {
  type = string
}

variable "db_name" {
  type    = string
  default = "appdb"
}

variable "db_username" {
  type    = string
  default = "appuser"
}

# For lab simplicity. You can rotate later.
variable "db_password" {
  type      = string
  sensitive = true
}

variable "instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "allocated_storage" {
  type    = number
  default = 20
}

variable "engine_version" {
  type    = string
  default = "16.2"
}

variable "backup_retention_days" {
  type    = number
  default = 1
}

variable "deletion_protection" {
  type    = bool
  default = false
}

variable "skip_final_snapshot" {
  type    = bool
  default = true
}
