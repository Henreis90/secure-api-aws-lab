aws ecr get-login-password --region us-east-1 | sudo docker login --username AWS --password-stdin 441819341895.dkr.ecr.us-east-1.amazonaws.com
sudo docker build -t secure-api-python ~/projects/secure-api-aws-lab/app
sudo docker tag secure-api-python:latest 441819341895.dkr.ecr.us-east-1.amazonaws.com/secure-api-python:latest
sudo docker push 441819341895.dkr.ecr.us-east-1.amazonaws.com/secure-api-python:latest