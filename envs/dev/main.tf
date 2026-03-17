module "network" {
  source  = "../../modules/network"
  project = var.project
  env     = var.env
  region  = var.aws_region
}

module "logging" {
  source  = "../../modules/logging"
  project = var.project
  env     = var.env
}

module "rds" {
  source             = "../../modules/rds"
  project            = var.project
  env                = var.env
  vpc_id             = module.network.vpc_id
  private_subnet_ids = module.network.private_subnet_ids
  app_sg_id          = module.ecs.app_sg_id
  db_password        = var.db_password
  engine_version        = "17.2"
  parameter_group_family = "postgres17"
}

module "ecs" {
  source             = "../../modules/ecs"
  project            = var.project
  env                = var.env
  vpc_id             = module.network.vpc_id
  private_subnet_ids = module.network.private_subnet_ids
  public_subnet_ids  = module.network.public_subnet_ids
  log_group_name     = module.logging.app_log_group_name
}

module "waf" {
  source      = "../../modules/waf"
  project     = var.project
  env         = var.env
  alb_arn     = module.ecs.alb_arn
}

resource "aws_acm_certificate" "api" {
  domain_name       = var.api_domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.api.domain_validation_options :
    dvo.domain_name => {
      name   = dvo.resource_record_name
      type   = dvo.resource_record_type
      record = dvo.resource_record_value
    }
  }

  zone_id = var.route53_zone_id
  name    = each.value.name
  type    = each.value.type
  ttl     = 60
  records = [each.value.record]
}

resource "aws_acm_certificate_validation" "api" {
  certificate_arn         = aws_acm_certificate.api.arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]
}

module "ecs" {
  source = "../../modules/ecs"

  # ... suas configs

  certificate_arn = aws_acm_certificate_validation.api.certificate_arn
}

resource "aws_route53_record" "api" {
  zone_id = var.route53_zone_id
  name    = var.api_domain_name
  type    = "A"

  alias {
    name                   = module.ecs.alb_dns_name
    zone_id                = module.ecs.alb_zone_id
    evaluate_target_health = true
  }
}
