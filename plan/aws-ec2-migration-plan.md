# AWS EC2 Migration Plan: Render to AWS (Low Cost)

## Overview

Migrate RapidRFP services from Render.com to a single AWS EC2 instance for maximum cost savings while maintaining reliability and eliminating cold starts.

---

## Cost Comparison Summary

| Platform | Monthly Cost | Annual Cost | Savings |
|----------|--------------|-------------|---------|
| **Render (Current)** | $200 | $2,400 | - |
| **AWS EC2 (On-Demand)** | $40 | $480 | **80%** |
| **AWS EC2 (Reserved 1-yr)** | $30 | $360 | **85%** |

---

## Target Architecture

```
                                    ┌─────────────────────────────────────────────────────┐
                                    │                      AWS Cloud                       │
                                    │                                                      │
┌──────────────┐                    │  ┌─────────────────────────────────────────────┐   │
│   Frontend   │                    │  │              Elastic IP                      │   │
│  (Vercel/    │ ─────────────────────→│           (Static Public IP)                │   │
│   Next.js)   │                    │  └─────────────────────────────────────────────┘   │
└──────────────┘                    │                         │                          │
                                    │                         ▼                          │
                                    │  ┌─────────────────────────────────────────────┐   │
                                    │  │              EC2 Instance                    │   │
                                    │  │           t3.medium (2 vCPU, 4GB)            │   │
                                    │  │                                              │   │
                                    │  │  ┌──────────────────────────────────────┐   │   │
                                    │  │  │           Docker Compose              │   │   │
                                    │  │  │                                       │   │   │
                                    │  │  │  ┌─────────────┐ ┌─────────────┐     │   │   │
                                    │  │  │  │ RapidRFPAI  │ │ noderag-api │     │   │   │
                                    │  │  │  │   :8002     │ │   :8003     │     │   │   │
                                    │  │  │  └─────────────┘ └─────────────┘     │   │   │
                                    │  │  │                                       │   │   │
                                    │  │  │  ┌─────────────┐ ┌─────────────┐     │   │   │
                                    │  │  │  │ noderag-    │ │ noderag-    │     │   │   │
                                    │  │  │  │ worker      │ │ scheduler   │     │   │   │
                                    │  │  │  └─────────────┘ └─────────────┘     │   │   │
                                    │  │  │                                       │   │   │
                                    │  │  │  ┌─────────────┐ ┌─────────────┐     │   │   │
                                    │  │  │  │   Redis     │ │   Nginx     │     │   │   │
                                    │  │  │  │   :6379     │ │   :80/443   │     │   │   │
                                    │  │  │  └─────────────┘ └─────────────┘     │   │   │
                                    │  │  └──────────────────────────────────────┘   │   │
                                    │  │                                              │   │
                                    │  │  ┌──────────────────────────────────────┐   │   │
                                    │  │  │         EBS Volume (30GB gp3)         │   │   │
                                    │  │  └──────────────────────────────────────┘   │   │
                                    │  └─────────────────────────────────────────────┘   │
                                    │                                                      │
                                    └──────────────────────────────────────────────────────┘
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

| Component | AWS Service | Monthly Cost |
|-----------|-------------|--------------|
| **Compute** | EC2 t3.medium (2 vCPU, 4GB) | ~$30 (on-demand) |
| **Storage** | EBS gp3 30GB | ~$2.50 |
| **Static IP** | Elastic IP | ~$3.50 |
| **Data Transfer** | 50GB outbound | ~$5 |
| **SSL** | Let's Encrypt (free) | $0 |
| **Total** | | **~$40/month** |

---

## Migration Steps

### Phase 1: Launch EC2 Instance (Day 1)

#### 1.1 Create Security Group

```bash
# Create security group
aws ec2 create-security-group \
  --group-name rapidrfp-sg \
  --description "RapidRFP security group"

# Allow SSH (restrict to your IP in production)
aws ec2 authorize-security-group-ingress \
  --group-name rapidrfp-sg \
  --protocol tcp \
  --port 22 \
  --cidr 0.0.0.0/0

# Allow HTTP
aws ec2 authorize-security-group-ingress \
  --group-name rapidrfp-sg \
  --protocol tcp \
  --port 80 \
  --cidr 0.0.0.0/0

# Allow HTTPS
aws ec2 authorize-security-group-ingress \
  --group-name rapidrfp-sg \
  --protocol tcp \
  --port 443 \
  --cidr 0.0.0.0/0

# Allow custom ports (8002, 8003) - optional, if not using Nginx
aws ec2 authorize-security-group-ingress \
  --group-name rapidrfp-sg \
  --protocol tcp \
  --port 8002 \
  --cidr 0.0.0.0/0
```

#### 1.2 Launch EC2 Instance

```bash
# Launch t3.medium instance with Ubuntu 22.04
aws ec2 run-instances \
  --image-id ami-0c7217cdde317cfec \
  --instance-type t3.medium \
  --key-name your-key-pair \
  --security-groups rapidrfp-sg \
  --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":30,"VolumeType":"gp3"}}]' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=rapidrfp-server}]'
```

#### 1.3 Allocate and Associate Elastic IP

```bash
# Allocate Elastic IP
aws ec2 allocate-address --domain vpc

# Associate with instance (replace with your instance ID and allocation ID)
aws ec2 associate-address \
  --instance-id i-xxxxxxxxxx \
  --allocation-id eipalloc-xxxxxxxxxx
```

---

### Phase 2: Server Setup (Day 1-2)

#### 2.1 SSH into Instance and Install Dependencies

```bash
# SSH into the instance
ssh -i your-key.pem ubuntu@<elastic-ip>

# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker ubuntu

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Install Nginx (for reverse proxy)
sudo apt install nginx -y

# Install Certbot for SSL
sudo apt install certbot python3-certbot-nginx -y

# Logout and login again for docker group to take effect
exit
```

#### 2.2 Create Project Directory

```bash
ssh -i your-key.pem ubuntu@<elastic-ip>

# Create project directory
mkdir -p ~/rapidrfp
cd ~/rapidrfp
```

---

### Phase 3: Docker Compose Setup (Day 2-3)

#### 3.1 Create docker-compose.yml

```yaml
# ~/rapidrfp/docker-compose.yml
version: '3.8'

services:
  rapidrfpai:
    build:
      context: ./RapidRFPAI
      dockerfile: Dockerfile
    container_name: rapidrfpai
    restart: always
    ports:
      - "8002:8002"
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=${DATABASE_URL}
      - GROQ_API_KEY=${GROQ_API_KEY}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
    depends_on:
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8002/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    networks:
      - rapidrfp-network

  rapidrfpv2:
    build:
      context: ./Rapidrfpv2
      dockerfile: Dockerfile
    container_name: rapidrfpv2
    restart: always
    ports:
      - "8004:8004"
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=${DATABASE_URL}
    depends_on:
      - redis
    networks:
      - rapidrfp-network

  noderag-api:
    build:
      context: ./noderag
      dockerfile: Dockerfile.api
    container_name: noderag-api
    restart: always
    ports:
      - "8003:8003"
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=${DATABASE_URL}
    depends_on:
      - redis
    networks:
      - rapidrfp-network

  noderag-worker:
    build:
      context: ./noderag
      dockerfile: Dockerfile.worker
    container_name: noderag-worker
    restart: always
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=${DATABASE_URL}
      - WORKER_TYPE=background
    depends_on:
      - redis
    networks:
      - rapidrfp-network

  noderag-scheduler:
    build:
      context: ./noderag
      dockerfile: Dockerfile.scheduler
    container_name: noderag-scheduler
    restart: always
    environment:
      - REDIS_URL=redis://redis:6379
      - DATABASE_URL=${DATABASE_URL}
    depends_on:
      - redis
    networks:
      - rapidrfp-network

  redis:
    image: redis:7-alpine
    container_name: rapidrfp-redis
    restart: always
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes
    networks:
      - rapidrfp-network

networks:
  rapidrfp-network:
    driver: bridge

volumes:
  redis-data:
```

#### 3.2 Create Environment File

```bash
# ~/rapidrfp/.env
DATABASE_URL=postgresql://user:password@your-neon-db-host/dbname
GROQ_API_KEY=your-groq-api-key
OPENAI_API_KEY=your-openai-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
```

#### 3.3 Clone Repositories

```bash
cd ~/rapidrfp

# Clone your repositories
git clone https://github.com/your-org/RapidRFPAI.git
git clone https://github.com/your-org/Rapidrfpv2.git
git clone https://github.com/your-org/noderag.git
```

---

### Phase 4: Nginx Reverse Proxy Setup (Day 3)

#### 4.1 Create Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/rapidrfp
```

```nginx
# /etc/nginx/sites-available/rapidrfp
server {
    listen 80;
    server_name api.rapidrfp.ai;  # Replace with your domain

    # RapidRFPAI API
    location / {
        proxy_pass http://localhost:8002;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://localhost:8002/health;
    }
}

server {
    listen 80;
    server_name noderag.rapidrfp.ai;  # Replace with your domain

    location / {
        proxy_pass http://localhost:8003;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

#### 4.2 Enable Site and Get SSL Certificate

```bash
# Enable the site
sudo ln -s /etc/nginx/sites-available/rapidrfp /etc/nginx/sites-enabled/

# Test nginx config
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx

# Get SSL certificate (after DNS is pointed to your Elastic IP)
sudo certbot --nginx -d api.rapidrfp.ai -d noderag.rapidrfp.ai
```

---

### Phase 5: Deploy and Start Services (Day 3-4)

#### 5.1 Build and Start All Services

```bash
cd ~/rapidrfp

# Build all images
docker compose build

# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f
```

#### 5.2 Verify Services

```bash
# Check all containers are running
docker ps

# Test endpoints
curl http://localhost:8002/health
curl http://localhost:8003/health

# Check resource usage
docker stats
```

---

### Phase 6: Setup Auto-Start and Monitoring (Day 4)

#### 6.1 Create Systemd Service for Docker Compose

```bash
sudo nano /etc/systemd/system/rapidrfp.service
```

```ini
[Unit]
Description=RapidRFP Docker Compose Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/ubuntu/rapidrfp
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
User=ubuntu

[Install]
WantedBy=multi-user.target
```

```bash
# Enable auto-start on boot
sudo systemctl enable rapidrfp.service
sudo systemctl start rapidrfp.service
```

#### 6.2 Setup Basic Monitoring with CloudWatch Agent (Optional)

```bash
# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i amazon-cloudwatch-agent.deb

# Configure (basic memory and disk monitoring)
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-config-wizard
```

#### 6.3 Setup Log Rotation

```bash
sudo nano /etc/logrotate.d/docker-containers
```

```
/var/lib/docker/containers/*/*.log {
    rotate 7
    daily
    compress
    missingok
    delaycompress
    copytruncate
}
```

---

### Phase 7: CI/CD with GitHub Actions (Day 5)

#### 7.1 Create Deploy Script on Server

```bash
# ~/rapidrfp/deploy.sh
#!/bin/bash
set -e

cd /home/ubuntu/rapidrfp

# Pull latest changes
git -C RapidRFPAI pull origin main
git -C Rapidrfpv2 pull origin main
git -C noderag pull origin main

# Rebuild and restart services
docker compose build
docker compose up -d

# Cleanup old images
docker image prune -f

echo "Deployment completed at $(date)"
```

```bash
chmod +x ~/rapidrfp/deploy.sh
```

#### 7.2 GitHub Actions Workflow

Create `.github/workflows/deploy.yml` in each repository:

```yaml
name: Deploy to EC2

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
    - name: Deploy to EC2
      uses: appleboy/ssh-action@v1.0.3
      with:
        host: ${{ secrets.EC2_HOST }}
        username: ubuntu
        key: ${{ secrets.EC2_SSH_KEY }}
        script: |
          cd /home/ubuntu/rapidrfp
          git -C RapidRFPAI pull origin main
          docker compose build rapidrfpai
          docker compose up -d rapidrfpai
          docker image prune -f
```

#### 7.3 Add GitHub Secrets

In each repository, add these secrets:
- `EC2_HOST`: Your Elastic IP address
- `EC2_SSH_KEY`: Your private SSH key

---

### Phase 8: DNS and Final Cutover (Day 5-6)

#### 8.1 Update DNS Records

Point your domain to the Elastic IP:
```
api.rapidrfp.ai    A    <elastic-ip>
noderag.rapidrfp.ai    A    <elastic-ip>
```

#### 8.2 Update Frontend Environment

```bash
# In your Next.js frontend .env
NEXT_PUBLIC_AI_BASE_URL=https://api.rapidrfp.ai
```

---

## Cost Breakdown

### EC2 On-Demand Pricing

| Resource | Specification | Monthly Cost |
|----------|---------------|--------------|
| EC2 t3.medium | 2 vCPU, 4GB RAM | $30.37 |
| EBS gp3 | 30GB | $2.40 |
| Elastic IP | 1 (attached) | $0 (free when attached) |
| Elastic IP | 1 (if detached) | $3.60 |
| Data Transfer | First 100GB | $0 |
| Data Transfer | 50GB additional | $4.50 |
| **Total** | | **~$37-40/month** |

### EC2 Reserved Instance (1-Year)

| Resource | Specification | Monthly Cost |
|----------|---------------|--------------|
| EC2 t3.medium | 1-year reserved, no upfront | $19.27 |
| EBS gp3 | 30GB | $2.40 |
| Data Transfer | 50GB | $4.50 |
| **Total** | | **~$26-30/month** |

### EC2 Reserved Instance (3-Year)

| Resource | Specification | Monthly Cost |
|----------|---------------|--------------|
| EC2 t3.medium | 3-year reserved, no upfront | $12.41 |
| EBS gp3 | 30GB | $2.40 |
| Data Transfer | 50GB | $4.50 |
| **Total** | | **~$19-22/month** |

---

## Comparison: All Options

| Option | Monthly | Annual | Savings vs Render |
|--------|---------|--------|-------------------|
| Render (current) | $200 | $2,400 | - |
| AWS ECS Fargate | $175 | $2,100 | 12% |
| **EC2 On-Demand** | **$40** | **$480** | **80%** |
| **EC2 Reserved 1-yr** | **$30** | **$360** | **85%** |
| **EC2 Reserved 3-yr** | **$22** | **$264** | **89%** |

---

## Scaling Options

### Vertical Scaling (Quick)

If you need more resources, upgrade the instance:

| Instance Type | vCPU | RAM | Monthly Cost |
|---------------|------|-----|--------------|
| t3.medium | 2 | 4GB | $30 |
| t3.large | 2 | 8GB | $60 |
| t3.xlarge | 4 | 16GB | $120 |
| m6i.large | 2 | 8GB | $70 |

```bash
# Stop instance, change type, start
aws ec2 stop-instances --instance-ids i-xxxxx
aws ec2 modify-instance-attribute --instance-id i-xxxxx --instance-type t3.large
aws ec2 start-instances --instance-ids i-xxxxx
```

### Horizontal Scaling (Future)

If you outgrow single instance:
1. Add Application Load Balancer (~$22/month)
2. Create AMI from current instance
3. Launch additional instances
4. Or migrate to ECS Fargate

---

## Backup Strategy

#### Daily Automated Snapshots

```bash
# Create snapshot script
cat > ~/rapidrfp/backup.sh << 'EOF'
#!/bin/bash
INSTANCE_ID=$(curl -s http://169.254.169.254/latest/meta-data/instance-id)
VOLUME_ID=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --query 'Reservations[0].Instances[0].BlockDeviceMappings[0].Ebs.VolumeId' --output text)
aws ec2 create-snapshot --volume-id $VOLUME_ID --description "RapidRFP backup $(date +%Y-%m-%d)"
EOF

chmod +x ~/rapidrfp/backup.sh

# Add to cron (daily at 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * /home/ubuntu/rapidrfp/backup.sh") | crontab -
```

---

## Migration Checklist

### Pre-Migration
- [ ] Create AWS account (if not exists)
- [ ] Create SSH key pair
- [ ] Create security group
- [ ] Launch EC2 instance
- [ ] Allocate Elastic IP
- [ ] Point DNS to Elastic IP

### Server Setup
- [ ] Install Docker and Docker Compose
- [ ] Install Nginx
- [ ] Clone repositories
- [ ] Create docker-compose.yml
- [ ] Create .env file with secrets
- [ ] Configure Nginx reverse proxy
- [ ] Setup SSL with Let's Encrypt

### Deployment
- [ ] Build Docker images
- [ ] Start all services
- [ ] Verify all endpoints
- [ ] Setup systemd auto-start
- [ ] Configure log rotation
- [ ] Setup GitHub Actions CI/CD

### Post-Migration
- [ ] Update frontend environment variables
- [ ] Test all API endpoints
- [ ] Monitor for 24-48 hours
- [ ] Setup CloudWatch alerts (optional)
- [ ] Shut down Render services

---

## Rollback Plan

If issues occur:
1. Keep Render services running during migration (parallel run)
2. DNS switch back is instant
3. EC2 snapshots available for quick recovery
4. All code in Git for redeployment

---

## Maintenance Tasks

### Weekly
- Check Docker logs for errors
- Verify disk space usage
- Review CloudWatch metrics

### Monthly
- Apply OS security updates
- Update Docker images
- Review and rotate credentials
- Clean up old Docker images

### Commands

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Clean Docker
docker system prune -af

# Check disk space
df -h

# Check memory
free -m

# View logs
docker compose logs --tail=100

# Restart all services
docker compose restart
```

---

## Timeline

| Day | Tasks |
|-----|-------|
| 1 | Launch EC2, install Docker, setup security |
| 2 | Clone repos, create docker-compose.yml, configure env |
| 3 | Setup Nginx, SSL, deploy services |
| 4 | Setup auto-start, monitoring, backups |
| 5 | Setup CI/CD, DNS cutover |
| 6 | Testing, monitoring, shut down Render |

**Total: ~1 week for full migration**

---

## Support Commands Reference

```bash
# SSH into server
ssh -i your-key.pem ubuntu@<elastic-ip>

# View running containers
docker ps

# View logs
docker compose logs -f [service-name]

# Restart a service
docker compose restart rapidrfpai

# Rebuild and restart
docker compose up -d --build rapidrfpai

# Check resource usage
docker stats

# View nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```
