terraform {
  backend "s3" {
    bucket         = "terraform-state"
    key            = "secure-api/lab/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}
