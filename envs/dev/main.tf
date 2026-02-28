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
