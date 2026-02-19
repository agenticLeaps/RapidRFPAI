# AWS Migration Plan: Render to AWS

## Overview

Migrate RapidRFP services from Render.com to AWS for better reliability, no cold starts, and no timeouts.

---

## Current Architecture (Render)

| Service | Runtime | Region | Purpose |
|---------|---------|--------|---------|
| noderag-worker | Python 3 | Oregon | Background RAG processing |
| noderag-api | Python 3 | Oregon | RAG API endpoints |
| noderag-scheduler | Python 3 | Oregon | Scheduled tasks |
| noderag-redis | Valkey 8 | Oregon | Caching/queues |
| RapidRFPAI | Docker | Virginia | Main AI backend |
| Rapidrfpv2 | Python 3 | Virginia | V2 AI backend (suspended) |

**Database:** Neon DB (PostgreSQL) - NO MIGRATION NEEDED

---

## Target AWS Architecture

```
                                    ┌─────────────────────────────────────────────────────┐
                                    │                      AWS Cloud                       │
                                    │                                                      │
┌──────────────┐                    │  ┌─────────────────────────────────────────────┐   │
│   Frontend   │                    │  │              Application Load Balancer       │   │
│  (Vercel/    │ ──────────────────────│                                              │   │
│   Next.js)   │                    │  │  ┌─────────────┐  ┌─────────────┐           │   │
└──────────────┘                    │  │  │ /api/*      │  │ /ws/*       │           │   │
                                    │  │  │ → ECS       │  │ → ECS       │           │   │
                                    │  │  └─────────────┘  └─────────────┘           │   │
                                    │  └─────────────────────────────────────────────┘   │
                                    │                         │                          │
                                    │           ┌─────────────┴─────────────┐            │
                                    │           ▼                           ▼            │
                                    │  ┌─────────────────┐      ┌─────────────────┐     │
                                    │  │  ECS Fargate    │      │  ECS Fargate    │     │
                                    │  │  Cluster        │      │  Cluster        │     │
                                    │  │                 │      │                 │     │
                                    │  │ ┌─────────────┐ │      │ ┌─────────────┐ │     │
                                    │  │ │RapidRFPAI   │ │      │ │noderag-api  │ │     │
                                    │  │ │Service      │ │      │ │Service      │ │     │
                                    │  │ │(2+ tasks)   │ │      │ │(2+ tasks)   │ │     │
                                    │  │ └─────────────┘ │      │ └─────────────┘ │     │
                                    │  │                 │      │                 │     │
                                    │  │ ┌─────────────┐ │      │ ┌─────────────┐ │     │
                                    │  │ │Rapidrfpv2   │ │      │ │noderag-     │ │     │
                                    │  │ │Service      │ │      │ │worker       │ │     │
                                    │  │ │(optional)   │ │      │ │(2+ tasks)   │ │     │
                                    │  │ └─────────────┘ │      │ └─────────────┘ │     │
                                    │  └────────┬────────┘      └────────┬────────┘     │
                                    │           │                        │              │
                                    │           ▼                        ▼              │
                                    │  ┌─────────────────────────────────────────┐      │
                                    │  │           Amazon ElastiCache            │      │
                                    │  │              (Redis)                    │      │
                                    │  └─────────────────────────────────────────┘      │
                                    │                         │                         │
                                    └─────────────────────────┼─────────────────────────┘
                                                              │
                                                              ▼
                                                    ┌─────────────────┐
                                                    │    Neon DB      │
                                                    │  (PostgreSQL)   │
                                                    │   - External -  │
                                                    └─────────────────┘
```

---

## AWS Services to Use

| Component | AWS Service | Why |
|-----------|-------------|-----|
| **Containers** | ECS Fargate | No server management, always-on, auto-scaling, no cold starts |
| **Load Balancer** | Application Load Balancer (ALB) | HTTP/HTTPS routing, WebSocket support, health checks |
| **Container Registry** | Amazon ECR | Store Docker images, integrated with ECS |
| **Redis Cache** | Amazon ElastiCache (Redis) | Managed Redis, replaces noderag-redis |
| **Secrets** | AWS Secrets Manager | Store API keys, DB credentials securely |
| **Logs** | CloudWatch Logs | Centralized logging, monitoring, alerts |
| **DNS** | Route 53 | DNS management, SSL certificates |
| **SSL** | AWS Certificate Manager | Free SSL certificates |
| **CI/CD** | GitHub Actions + AWS CodeDeploy | Or AWS CodePipeline |

---

## Migration Steps

### Phase 1: AWS Setup (Day 1)

#### 1.1 Create AWS Infrastructure

```bash
# Create VPC with public/private subnets
aws ec2 create-vpc --cidr-block 10.0.0.0/16

# Create ECS Cluster
aws ecs create-cluster --cluster-name rapidrfp-cluster --capacity-providers FARGATE

# Create ECR Repositories
aws ecr create-repository --repository-name rapidrfpai
aws ecr create-repository --repository-name rapidrfpv2
aws ecr create-repository --repository-name noderag-api
aws ecr create-repository --repository-name noderag-worker
aws ecr create-repository --repository-name noderag-scheduler
```

#### 1.2 Create ElastiCache Redis

```bash
# Create Redis cluster (replaces noderag-redis)
aws elasticache create-cache-cluster \
  --cache-cluster-id rapidrfp-redis \
  --engine redis \
  --cache-node-type cache.t3.micro \
  --num-cache-nodes 1
```

#### 1.3 Create Application Load Balancer

```bash
# Create ALB for routing traffic
aws elbv2 create-load-balancer \
  --name rapidrfp-alb \
  --subnets subnet-xxx subnet-yyy \
  --security-groups sg-xxx
```

---

### Phase 2: Containerize Services (Day 2-3)

#### 2.1 RapidRFPAI Dockerfile (if not exists)

```dockerfile
# RapidRFPAI/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8002/health || exit 1

# Run with gunicorn for production
CMD ["gunicorn", "--bind", "0.0.0.0:8002", "--workers", "4", "--threads", "2", "app:app"]
```

#### 2.2 Build and Push to ECR

```bash
# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com

# Build and push RapidRFPAI
cd RapidRFPAI
docker build -t rapidrfpai .
docker tag rapidrfpai:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/rapidrfpai:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/rapidrfpai:latest

# Repeat for other services...
```

---

### Phase 3: Create ECS Task Definitions (Day 3-4)

#### 3.1 RapidRFPAI Task Definition

```json
{
  "family": "rapidrfpai",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::xxx:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::xxx:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "rapidrfpai",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/rapidrfpai:latest",
      "portMappings": [
        {
          "containerPort": 8002,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {"name": "REDIS_URL", "value": "redis://rapidrfp-redis.xxx.cache.amazonaws.com:6379"},
        {"name": "DATABASE_URL", "value": "from-secrets-manager"}
      ],
      "secrets": [
        {
          "name": "GROQ_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:xxx:secret:rapidrfp/groq-api-key"
        },
        {
          "name": "OPENAI_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:xxx:secret:rapidrfp/openai-api-key"
        },
        {
          "name": "DATABASE_URL",
          "valueFrom": "arn:aws:secretsmanager:us-east-1:xxx:secret:rapidrfp/neon-db-url"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/rapidrfpai",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8002/health || exit 1"],
        "interval": 30,
        "timeout": 5,
        "retries": 3,
        "startPeriod": 60
      }
    }
  ]
}
```

#### 3.2 noderag-worker Task Definition (Background Worker)

```json
{
  "family": "noderag-worker",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "noderag-worker",
      "image": "<account-id>.dkr.ecr.us-east-1.amazonaws.com/noderag-worker:latest",
      "environment": [
        {"name": "WORKER_TYPE", "value": "background"}
      ],
      "secrets": [
        {"name": "DATABASE_URL", "valueFrom": "..."},
        {"name": "REDIS_URL", "valueFrom": "..."}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/noderag-worker",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

---

### Phase 4: Create ECS Services (Day 4-5)

#### 4.1 Create Always-On Services

```bash
# RapidRFPAI Service - Always running, no cold starts
aws ecs create-service \
  --cluster rapidrfp-cluster \
  --service-name rapidrfpai-service \
  --task-definition rapidrfpai:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx],assignPublicIp=ENABLED}" \
  --load-balancers "targetGroupArn=arn:aws:elasticloadbalancing:...,containerName=rapidrfpai,containerPort=8002"

# noderag-api Service
aws ecs create-service \
  --cluster rapidrfp-cluster \
  --service-name noderag-api-service \
  --task-definition noderag-api:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "..."

# noderag-worker Service (background processing)
aws ecs create-service \
  --cluster rapidrfp-cluster \
  --service-name noderag-worker-service \
  --task-definition noderag-worker:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "..."

# noderag-scheduler Service
aws ecs create-service \
  --cluster rapidrfp-cluster \
  --service-name noderag-scheduler-service \
  --task-definition noderag-scheduler:1 \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "..."
```

---

### Phase 5: Configure Auto-Scaling (Day 5)

```bash
# Register scalable target
aws application-autoscaling register-scalable-target \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/rapidrfp-cluster/rapidrfpai-service \
  --min-capacity 2 \
  --max-capacity 10

# Create scaling policy (scale on CPU)
aws application-autoscaling put-scaling-policy \
  --service-namespace ecs \
  --scalable-dimension ecs:service:DesiredCount \
  --resource-id service/rapidrfp-cluster/rapidrfpai-service \
  --policy-name cpu-scaling \
  --policy-type TargetTrackingScaling \
  --target-tracking-scaling-policy-configuration '{
    "TargetValue": 70.0,
    "PredefinedMetricSpecification": {
      "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
    },
    "ScaleOutCooldown": 60,
    "ScaleInCooldown": 120
  }'
```

---

### Phase 6: Setup CI/CD with GitHub Actions (Day 6)

#### 6.1 GitHub Actions Workflow

Create `.github/workflows/deploy.yml` in each repository:

```yaml
name: Deploy to AWS ECS

on:
  push:
    branches: [main]

env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: rapidrfpai
  ECS_CLUSTER: rapidrfp-cluster
  ECS_SERVICE: rapidrfpai-service
  CONTAINER_NAME: rapidrfpai

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
    - name: Checkout
      uses: actions/checkout@v4

    - name: Configure AWS credentials
      uses: aws-actions/configure-aws-credentials@v4
      with:
        aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
        aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        aws-region: ${{ env.AWS_REGION }}

    - name: Login to Amazon ECR
      id: login-ecr
      uses: aws-actions/amazon-ecr-login@v2

    - name: Build, tag, and push image to Amazon ECR
      id: build-image
      env:
        ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
        IMAGE_TAG: ${{ github.sha }}
      run: |
        docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
        docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
        echo "image=$ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG" >> $GITHUB_OUTPUT

    - name: Update ECS service
      run: |
        aws ecs update-service \
          --cluster $ECS_CLUSTER \
          --service $ECS_SERVICE \
          --force-new-deployment
```

---

### Phase 7: Update Frontend Environment (Day 7)

Update the Next.js frontend `.env`:

```bash
# Old (Render)
NEXT_PUBLIC_AI_BASE_URL=https://rapidrfpai.onrender.com

# New (AWS)
NEXT_PUBLIC_AI_BASE_URL=https://api.rapidrfp.ai
```

---

## Cost Comparison: Render vs AWS

### Current Render Costs: ~$200/month

### Projected AWS Costs

| Service | Specification | Est. Cost |
|---------|---------------|-----------|
| ECS Fargate (RapidRFPAI) | 2 tasks x 0.5 vCPU, 1GB | ~$30 |
| ECS Fargate (noderag-api) | 2 tasks x 0.5 vCPU, 1GB | ~$30 |
| ECS Fargate (noderag-worker) | 2 tasks x 1 vCPU, 2GB | ~$60 |
| ECS Fargate (noderag-scheduler) | 1 task x 0.25 vCPU, 0.5GB | ~$10 |
| ElastiCache Redis | cache.t3.micro | ~$13 |
| Application Load Balancer | 1 ALB | ~$22 |
| CloudWatch Logs | 10GB/month | ~$5 |
| ECR Storage | 5GB | ~$0.50 |
| Data Transfer | 50GB/month | ~$5 |
| **AWS Total** | | **~$175/month** |

### Cost Savings Summary

| Platform | Monthly Cost | Annual Cost |
|----------|--------------|-------------|
| Render (Current) | $200 | $2,400 |
| AWS (Projected) | $175 | $2,100 |
| **Savings** | **$25/month** | **$300/year** |

**Additional AWS Savings Options:**
- **Savings Plans (1-year):** Up to 40% savings -> ~$105/month
- **Savings Plans (3-year):** Up to 60% savings -> ~$70/month
- **Spot Instances (for workers):** Up to 70% savings on noderag-worker

**With 1-year Savings Plan:** ~$105/month = **$1,260/year** (47% savings vs Render)

---

## Migration Checklist

### Pre-Migration
- [ ] Create AWS account (if not exists)
- [ ] Set up IAM roles and policies
- [ ] Create VPC with subnets
- [ ] Set up secrets in AWS Secrets Manager
- [ ] Create ECR repositories

### Migration
- [ ] Build and push Docker images to ECR
- [ ] Create ECS task definitions
- [ ] Create ElastiCache Redis cluster
- [ ] Create Application Load Balancer
- [ ] Create ECS services
- [ ] Configure auto-scaling
- [ ] Set up CloudWatch alarms

### Post-Migration
- [ ] Update DNS records (Route 53)
- [ ] Update frontend environment variables
- [ ] Test all endpoints
- [ ] Monitor for 24-48 hours
- [ ] Shut down Render services

---

## Rollback Plan

If issues occur:
1. Keep Render services running during migration
2. DNS switch back is instant via Route 53
3. All Docker images tagged with git SHA for easy rollback
4. ECS supports instant rollback to previous task definition

---

## Files to Modify in Frontend (agenticleaps)

| File | Change |
|------|--------|
| `.env` | Update `NEXT_PUBLIC_AI_BASE_URL` to AWS endpoint |
| `.env.production` | Add production AWS URLs |
| `vercel.json` | Update environment variables if needed |

---

## Timeline

| Day | Tasks |
|-----|-------|
| 1 | AWS infrastructure setup (VPC, ECS cluster, ECR, ElastiCache) |
| 2-3 | Containerize services, create Dockerfiles, push to ECR |
| 3-4 | Create ECS task definitions |
| 4-5 | Create ECS services, configure ALB |
| 5 | Configure auto-scaling |
| 6 | Setup CI/CD with GitHub Actions |
| 7 | DNS cutover, testing, monitoring |

**Total: ~1 week for full migration**
