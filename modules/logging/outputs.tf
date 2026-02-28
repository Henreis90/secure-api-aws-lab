output "app_log_group_name" {
  description = "CloudWatch Log Group name for the application"
  value       = aws_cloudwatch_log_group.app.name
}
