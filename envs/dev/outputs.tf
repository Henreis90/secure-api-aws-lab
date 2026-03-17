#########################################
# Network Outputs
#########################################

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.network.vpc_id
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = module.network.public_subnet_ids
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.network.private_subnet_ids
}

#########################################
# ECS / ALB Outputs
#########################################

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = module.ecs.alb_dns_name
}

output "alb_arn" {
  description = "ARN of the Application Load Balancer"
  value       = module.ecs.alb_arn
}

output "ecs_cluster_name" {
  description = "ECS Cluster Name"
  value       = module.ecs.cluster_name
}

output "ecs_service_name" {
  description = "ECS Service Name"
  value       = module.ecs.service_name
}

#########################################
# RDS Outputs
#########################################

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = module.rds.endpoint
  sensitive   = true
}

output "rds_db_name" {
  description = "Database name"
  value       = module.rds.db_name
}

#########################################
# WAF
#########################################

output "waf_web_acl_arn" {
  description = "WAF Web ACL ARN"
  value       = module.waf.web_acl_arn
}

#########################################
# Logging
#########################################

output "cloudwatch_log_group" {
  description = "Application CloudWatch log group"
  value       = module.logging.app_log_group_name
}

#########################################
# ECR - Repo de Imagem
#########################################
container_image = "${module.ecr.repository_url}:latest"
