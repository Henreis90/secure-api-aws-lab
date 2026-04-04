variable "aws_region" { type = string }
variable "project"    { type = string }
variable "env"        { type = string }
variable "db_password" {
  type      = string
  sensitive = true
}
variable "api_domain_name" {
  default = "api.cibita.com.br"
}
variable "route53_zone_id" {
  default = "Z07365072A02CW8J97LV3"
}

variable "jwt_secret" {
  type      = string
  sensitive = true
}