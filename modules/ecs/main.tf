locals {
  name = "${var.project}-${var.env}"

  common_tags = {
    Project     = var.project
    Environment = var.env
    ManagedBy   = "Terraform"
  }
}

#########################################
# Security Groups
#########################################

resource "aws_security_group" "alb" {
  name        = "${local.name}-alb-sg"
  description = "ALB security group"
  vpc_id      = var.vpc_id

  ingress {
    description = "HTTP from Internet (lab)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${local.name}-alb-sg" })
}

resource "aws_security_group" "app" {
  name        = "${local.name}-app-sg"
  description = "ECS tasks security group"
  vpc_id      = var.vpc_id

  ingress {
    description     = "App traffic from ALB"
    from_port       = var.container_port
    to_port         = var.container_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    description = "All outbound (via NAT)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.common_tags, { Name = "${local.name}-app-sg" })
}

#########################################
# ALB
#########################################

resource "aws_lb" "this" {
  name               = replace("${local.name}-alb", "/[^a-zA-Z0-9-]/", "-")
  load_balancer_type = "application"
  subnets            = var.public_subnet_ids
  security_groups    = [aws_security_group.alb.id]

  tags = merge(local.common_tags, { Name = "${local.name}-alb" })
}

resource "aws_lb_target_group" "this" {
  name        = replace("${local.name}-tg", "/[^a-zA-Z0-9-]/", "-")
  port        = var.container_port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = "/"
    matcher             = "200-399"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }

  tags = merge(local.common_tags, { Name = "${local.name}-tg" })
}

#########################################
# Listener HTTP -> redirect
#########################################

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

#########################################
# Listener HTTPS
#########################################

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-2016-08"
  certificate_arn   = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.this.arn
  }
}

#########################################
# ECS Cluster
#########################################

resource "aws_ecs_cluster" "this" {
  name = "${local.name}-cluster"

  tags = merge(local.common_tags, { Name = "${local.name}-cluster" })
}

#########################################
# IAM Roles
#########################################

data "aws_iam_policy_document" "ecs_task_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${local.name}-ecs-exec-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json
  tags               = local.common_tags
}

resource "aws_iam_role_policy_attachment" "execution_attach" {
  role       = aws_iam_role.execution.name
  policy_arn  = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "task" {
  name               = "${local.name}-ecs-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json
  tags               = local.common_tags
}

#########################################
# Task Definition
#########################################

resource "aws_ecs_task_definition" "this" {
  family                   = "${local.name}-task"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = tostring(var.cpu)
  memory                   = tostring(var.memory)
  execution_role_arn        = aws_iam_role.execution.arn
  task_role_arn             = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "nginx"
      image     = var.container_image
      essential = true
      portMappings = [
        {
          containerPort = var.container_port
          protocol      = "tcp"
        }
      ]
      environment = [
        { name = "ENV", value = var.env }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = var.log_group_name
          awslogs-region        = "us-east-1"
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])

  tags = merge(local.common_tags, { Name = "${local.name}-taskdef" })
}

#########################################
# ECS Service
#########################################

resource "aws_ecs_service" "this" {
  name            = "${local.name}-svc"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.this.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = var.private_subnet_ids
    security_groups = [aws_security_group.app.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.this.arn
    container_name   = "nginx"
    container_port   = var.container_port
  }

  depends_on = [
    aws_lb_listener.http,
    aws_lb_listener.https
  ]

  tags = merge(local.common_tags, { Name = "${local.name}-svc" })
}
