variable "project" { type = string }
variable "env"     { type = string }

variable "vpc_id" { type = string }

variable "public_subnet_ids" {
  type = list(string)
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "log_group_name" {
  type = string
}

variable "desired_count" {
  type    = number
  default = 1
}

variable "cpu" {
  type    = number
  default = 256
}

variable "memory" {
  type    = number
  default = 512
}

variable "container_image" {
  type    = string
  default = "nginx:1.25-alpine"
}

variable "container_port" {
  type    = number
  default = 80
}
