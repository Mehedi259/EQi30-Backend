#!/bin/bash
set -e

EC2_IP="16.170.225.78"
KEY_FILE="eqi30-ec2-key.pem"

echo "Copying source code to EC2..."
rsync -avz --exclude '.venv' --exclude 'venv_new' --exclude '__pycache__' --exclude '*.sqlite3' -e "ssh -o StrictHostKeyChecking=no -i ${KEY_FILE}" ./services/backend/ ubuntu@${EC2_IP}:~/eqi30-backend-src/

echo "Connecting to EC2 to build and deploy..."
ssh -o StrictHostKeyChecking=no -i ${KEY_FILE} ubuntu@${EC2_IP} << 'EOF'
  set -e
  
  echo "Building Docker image on EC2..."
  cd ~/eqi30-backend-src
  docker build -t eqi30-backend:latest -f Dockerfile .
  
  echo "Updating docker-compose.yml..."
  cd ~/eqi30
  # Replace ECR image with local image
  sed -i "s|image: 272175291634.dkr.ecr.eu-north-1.amazonaws.com/eqi30-backend:latest|image: eqi30-backend:latest|g" docker-compose.yml
  sed -i "s|image: eqi30-backend:latest|image: eqi30-backend:latest|g" docker-compose.yml
  
  echo "Restarting services..."
  docker-compose down
  docker-compose up -d
  
  echo "Waiting for services to be ready..."
  sleep 15
  
  echo "Running migrations..."
  docker exec eqi30_backend uv run python manage.py migrate
  
  echo "Running database seeding..."
  docker exec eqi30_backend uv run python seed_resources.py
  docker exec eqi30_backend uv run python seed_competency.py
  
  echo "Deployment complete!"
EOF
