# Secure API Lab in AWS
Laboratório de API segura na AWS

## Pre-requisitos AWS
1. Criar DNS Zone Público com domínio próprio

## Pre-requisitos Workstation Linux EC2
1. Configurar Role com as permissões da política em IamRolePolicy.json
2. Instalar Terraform
3. Instalar Docker

## 1. Rodar o terraform inicial
  $ terraform init
  
  $ terraform plan


## 2. Rodar terraform para criar ECR
  $ terraform apply -target=module.ecr -auto-approve

## 3. Fazer build e push da Imagem
  $ sudo aws ecr get-login-password --region us-east-1 | sudo docker login --username AWS --password-stdin 441819341895.dkr.ecr.us-east-1.amazonaws.com
  
  $ sudo docker build -t secure-api-python ~/projects/secure-api-aws-lab/app
  
  $ sudo docker tag secure-api-python:latest 441819341895.dkr.ecr.us-east-1.amazonaws.com/secure-api-python:latest
  
  $ sudo docker push 441819341895.dkr.ecr.us-east-1.amazonaws.com/secure-api-python:latest
   
## 4. Rodar terraform denovo completo
  $ terraform apply -auto-approve

## 5. Rodar terraform destroy
  $ terraform destroy 
