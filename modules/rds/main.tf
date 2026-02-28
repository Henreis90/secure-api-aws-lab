locals {
  name = "${var.project}-${var.env}"

  common_tags = {
    Project     = var.project
    Environment = var.env
    ManagedBy   = "Terraform"
  }
}

#########################################
# DB Security Group (private, only from app SG)
#########################################

resource "aws_security_group" "db" {
  name        = "${local.name}-db-sg"
  description = "RDS PostgreSQL access only from ECS app SG"
  vpc_id      = var.vpc_id

  ingress {
    description     = "PostgreSQL from app SG"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.app_sg_id]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${local.name}-db-sg" })
}

#########################################
# DB Subnet Group (private subnets)
#########################################

resource "aws_db_subnet_group" "this" {
  name       = "${local.name}-db-subnets"
  subnet_ids = var.private_subnet_ids

  tags = merge(local.common_tags, { Name = "${local.name}-db-subnets" })
}

#########################################
# Parameter Group (basic safe defaults)
#########################################

resource "aws_db_parameter_group" "this" {
  name   = "${local.name}-pg"
  family = var.parameter_group_family

  # Lightweight logging for lab visibility
  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000" # ms
  }

  tags = merge(local.common_tags, { Name = "${local.name}-pg16" })
}

#########################################
# RDS Instance
#########################################

resource "aws_db_instance" "this" {
  identifier             = "${local.name}-db"
  engine                 = "postgres"
  engine_version         = var.engine_version
  instance_class         = var.instance_class
  allocated_storage      = var.allocated_storage
  storage_type           = "gp3"

  db_name                = var.db_name
  username               = var.db_username
  password               = var.db_password

  vpc_security_group_ids = [aws_security_group.db.id]
  db_subnet_group_name   = aws_db_subnet_group.this.name
  parameter_group_name   = aws_db_parameter_group.this.name

  publicly_accessible    = false
  multi_az               = false

  storage_encrypted      = true

  backup_retention_period = var.backup_retention_days

  deletion_protection    = var.deletion_protection
  skip_final_snapshot    = var.skip_final_snapshot

  # Reasonable for lab
  apply_immediately      = true

  tags = merge(local.common_tags, { Name = "${local.name}-db" })
}
