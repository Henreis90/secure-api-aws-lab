variable "project" {
  type = string
}

variable "env" {
  type = string
}

variable "log_retention_days" {
  type    = number
  default = 7
}
