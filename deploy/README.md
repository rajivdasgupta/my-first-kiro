# FinXCloud Deployment Guide

## Local Docker

```bash
cd deploy
docker-compose up --build
# Dashboard at http://localhost:8000
```

## AWS ECS/Fargate

### 1. Build and push Docker image
```bash
aws ecr create-repository --repository-name finxcloud
aws ecr get-login-password | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com
docker build -f deploy/Dockerfile -t finxcloud .
docker tag finxcloud:latest ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/finxcloud:latest
docker push ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/finxcloud:latest
```

### 2. Deploy with ECS task definition
```bash
# Update ACCOUNT_ID and REGION in ecs-task-definition.json
aws ecs register-task-definition --cli-input-json file://deploy/ecs-task-definition.json
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| FINXCLOUD_ADMIN_USER | admin | Dashboard username |
| FINXCLOUD_ADMIN_PASS | changeme | Dashboard password |
| FINXCLOUD_JWT_SECRET | auto-generated | JWT signing secret |
