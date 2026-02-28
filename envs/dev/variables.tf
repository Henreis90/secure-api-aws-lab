variable "aws_region" { type = string }
variable "project"    { type = string }
variable "env"        { type = string }
variable "db_password" {
  type      = string
  sensitive = true
}
