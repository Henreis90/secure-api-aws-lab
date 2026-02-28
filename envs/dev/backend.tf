terraform {
  backend "s3" {
    bucket         = "secure-api-lab-terraform-state"
    key            = "secure-api/lab/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}
