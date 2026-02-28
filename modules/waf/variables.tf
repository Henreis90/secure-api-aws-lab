variable "project" { type = string }
variable "env"     { type = string }

variable "alb_arn" {
  type = string
}

variable "rate_limit" {
  type    = number
  default = 1000
}
