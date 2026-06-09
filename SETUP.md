# Avana V2 — Setup Guide

> Step-by-step guide for local development and production deployment

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Local Development Setup](#local-development-setup)
- [Docker Production Setup](#docker-production-setup)
- [Cloud Deployment Options](#cloud-deployment-options)
- [Post-Deployment Checklist](#post-deployment-checklist)

---

## Prerequisites

### Required Software

| Tool | Version | Purpose |
|---|---|---|
| **Docker** | 24+ | Container runtime for PostGIS, Redis, and full stack |
| **Docker Compose** | v2 | Multi-container orchestration |
| **Python** | 3.12+ | Backend runtime |
| **Node.js** | 20+ | Frontend runtime |
| **Git** | 2.x | Version control |

### Verify Installation

```bash
# Docker
docker --version              # Docker version 24.0.0+
docker compose version        # Docker Compose version v2.20+

# Python
python --version              # Python 3.12.x

# Node.js
node --version                # v20.x.x
npm --version                 # 10.x.x

# Git
git --version                 # git version 2.x
```

### Optional Tools

| Tool | Purpose |
|---|---|
| **PostgreSQL 16 + PostGIS 3.4** | Running database locally (not required with Docker) |
| **Redis 7** | Running cache/broker locally (not required with Docker) |
| **pgAdmin** | Database GUI management |
| **Postman** | API testing |

---

## Local Development Setup

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/avana-v2.git
cd avana-v2
```

### Step 2: Set Up Environment Variables

```bash
# Copy the example environment file
cp .env.example .env
```

Edit `.env` and set at minimum:

```bash
# Generate a strong random secret (64+ characters)
# On Linux/Mac: openssl rand -base64 48
# On Windows PowerShell: [Convert]::ToBase64String([byte[]]::new(64))
SECRET_KEY=your_super_secret_key_here_minimum_64_chars_long

# Set a strong database password
POSTGRES_PASSWORD=your_strong_db_password

# Set your Gemini API key (get from https://aistudio.google.com/app/apikey)
GEMINI_API_KEY=your_gemini_api_key_here
```

Full `.env.example` reference:

```bash
# App
APP_NAME=Avana V2 - Karnataka Safety Intelligence Platform
VERSION=2.0.0
DEBUG=false

# PostgreSQL / PostGIS
POSTGRES_USER=avana
POSTGRES_PASSWORD=change_me_production_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=avana_v2

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Auth
SECRET_KEY=generate_a_random_64_char_secret_key
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Supabase (optional, for auth sync)
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_KEY=

# AI APIs
GEMINI_API_KEY=
OPENAI_API_KEY=

# Rate Limiting
RATE_LIMIT_MAX=100
RATE_LIMIT_WINDOW=60

# CORS
CORS_ORIGINS=http://localhost:5173,http://localhost:3000,https://avana.app

# Agent Scheduling
NEWS_SCRAPE_INTERVAL_MINUTES=360
AGENT_RUN_INTERVAL_MINUTES=60

# Karnataka Geo Bounds
KARNATAKA_BOUNDS=11.5,13.5,74.0,78.5

# Sentry (optional)
SENTRY_DSN=

# Email (SMTP - for SOS notifications)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
```

### Step 3: Start Infrastructure (Docker)

Start only the database and cache services (no need to build the full stack for development):

```bash
docker compose up -d postgres redis
```

This starts:
- **PostgreSQL 16 + PostGIS 3.4** on port `5432`
- **Redis 7** on port `6379`

Verify they're running:

```bash
docker compose ps
# Name                 Status    Ports
# avana-v2-postgres-1  Up        5432/tcp
# avana-v2-redis-1     Up        6379/tcp

# Test Postgres
docker compose exec postgres pg_isready -U avana
# /var/run/postgresql:5432 - accepting connections

# Test Redis
docker compose exec redis redis-cli ping
# PONG
```

### Step 4: Backend Setup

```bash
# Navigate to backend
cd backend

# Create Python virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows PowerShell:
venv\Scripts\Activate.ps1
# On Windows CMD:
venv\Scripts\activate.bat

# Verify Python is from virtual env
which python    # On Linux/Mac
# or
where.exe python  # On Windows
# Should point to the venv directory

# Install Python dependencies
pip install -r requirements.txt
```

**Troubleshooting**:
- If `psycopg2` fails to compile, install `libpq-dev` (Linux) or use `pip install psycopg2-binary`
- On Windows, you may need Microsoft C++ Build Tools
- If GeoAlchemy2 fails, ensure `shapely` and `numpy` are installed first

### Step 5: Run Database Migrations

```bash
# Run all pending migrations
alembic upgrade head

# Verify migration
alembic current
# Should show the latest migration revision
```

**Troubleshooting**:
- Connection refused: Ensure `docker compose up -d postgres` is running
- Role does not exist: The `avana` user is created by the Docker container automatically
- Permission denied: Check `POSTGRES_PASSWORD` in `.env` matches `docker-compose.yml`

### Step 6: Seed Sample Data (Optional)

```bash
python -m app.seed
```

This creates:
- Sample admin user (email: `admin@avana.app`, password: printed in console)
- Sample incidents across Karnataka districts
- Sample police stations and hospitals
- Sample heatmap data

### Step 7: Start Backend Server

```bash
# Start FastAPI with hot reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Verify the backend is running:

```bash
# Health check
curl http://localhost:8000/health
# {"status":"healthy","version":"2.0.0","timestamp":"2026-01-15T10:30:00Z"}

# API docs
# Open http://localhost:8000/api/docs in browser
```

### Step 8: Frontend Setup

```bash
# Open a new terminal
cd frontend

# Install npm dependencies
npm install

# Start Vite dev server
npm run dev
```

Verify the frontend is running:
- Open `http://localhost:5173` in browser
- You should see the Avana V2 login/splash screen
- API calls from frontend are proxied to backend via Vite config

### Step 9: Celery Worker Setup

Celery is required for AI agent pipelines (news scraping, community intelligence, heatmap generation).

```bash
# Open a new terminal

# Activate backend virtual environment (same as step 4)
cd backend
source venv/bin/activate  # or venv\Scripts\activate

# Start Celery worker (processes tasks)
celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4
```

In another terminal:

```bash
# Start Celery beat (schedules periodic tasks)
celery -A app.tasks.celery_app beat --loglevel=info
```

**Optional**: Monitor Celery with Flower:

```bash
# Install flower
pip install flower

# Start flower dashboard
celery -A app.tasks.celery_app flower --port=5555

# Open http://localhost:5555
```

### Step 10: Verify Everything Works

```bash
# 1. Backend health
curl http://localhost:8000/health

# 2. Frontend
curl http://localhost:5173

# 3. API docs
curl http://localhost:8000/api/docs

# 4. Trigger test AI chat (requires GEMINI_API_KEY)
curl http://localhost:8000/api/v1/chat/test

# 5. Get incidents
curl http://localhost:8000/api/v1/incidents

# 6. Check Celery is working
celery -A app.tasks.celery_app status
```

### Step 11: (Optional) Full Docker Stack

If you prefer to run everything in Docker (including the app):

```bash
# From project root
docker compose up -d

# Wait for all services to be healthy
docker compose ps
# All services should show "Up"

# Access frontend at http://localhost:5173
# Access backend at http://localhost:8000
```

### Development Workflow Summary

```
┌─────────────────────────────────────────────────────────┐
│                   Terminal Layout                         │
├─────────────────────────────────────────────────────────┤
│ Terminal 1: docker compose up -d postgres redis          │
│ Terminal 2: uvicorn app.main:app --reload --port 8000    │
│ Terminal 3: celery worker --concurrency=4                │
│ Terminal 4: celery beat                                  │
│ Terminal 5: cd frontend && npm run dev                   │
└─────────────────────────────────────────────────────────┘
```

---

## Docker Production Setup

### Step 1: Clone on Server

```bash
# SSH into your server
ssh user@your-server.com

# Clone the repository
git clone https://github.com/yourusername/avana-v2.git
cd avana-v2
```

### Step 2: Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with production values:

```bash
# Use nano or vim
nano .env
```

**Critical production settings**:

```bash
# Security - MUST CHANGE
SECRET_KEY=$(openssl rand -base64 48)     # Strong random key
POSTGRES_PASSWORD=$(openssl rand -base64 24)  # Strong password

# Disable debug
DEBUG=false

# Set to production domain
CORS_ORIGINS=https://avana.yourdomain.com

# Production database host (Docker service name)
POSTGRES_HOST=postgres

# Production Redis URLs
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# Required AI key
GEMINI_API_KEY=your_production_gemini_key
```

### Step 3: Build and Start

```bash
# Build all Docker images
docker compose build

# Start all services in background
docker compose up -d

# Check all services are running
docker compose ps

# View logs
docker compose logs -f
```

### Step 4: Verify Production Deployment

```bash
# Health check
curl http://localhost:8000/health

# Test through Nginx
curl http://localhost/api/v1/incidents

# Check frontend is serving
curl http://localhost/

# Check Celery workers
docker compose logs celery_worker --tail=20
```

### Step 5: SSL Setup with Let's Encrypt

```bash
# Install certbot
sudo apt update
sudo apt install certbot

# Get certificate (stop Nginx first)
docker compose stop nginx
sudo certbot certonly --standalone -d avana.yourdomain.com

# Copy certificates to ssl directory
mkdir -p ssl
sudo cp /etc/letsencrypt/live/avana.yourdomain.com/fullchain.pem ssl/
sudo cp /etc/letsencrypt/live/avana.yourdomain.com/privkey.pem ssl/
sudo chmod 600 ssl/privkey.pem

# Restart Nginx
docker compose up -d nginx
```

**Auto-renewal setup**:

```bash
# Add to crontab
sudo crontab -e

# Add this line (runs weekly, Monday 3AM):
0 3 * * 1 certbot renew --quiet && docker compose -f /path/to/avana-v2/docker-compose.yml restart nginx
```

### Step 6: Monitoring Setup

**Option A: Docker logs**:

```bash
# Follow all logs
docker compose logs -f

# Follow specific service
docker compose logs -f backend
docker compose logs -f celery_worker
```

**Option B: Sentry Error Tracking**:

Set `SENTRY_DSN` in `.env` to enable automatic error reporting.

**Option C: Prometheus + Grafana** (advanced):

Add to `docker-compose.yml`:
```yaml
prometheus:
  image: prom/prometheus
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
  ports:
    - "9090:9090"

grafana:
  image: grafana/grafana
  ports:
    - "3000:3000"
```

### Step 7: Database Backup

Create a backup script `backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/backups/postgres"
DB_NAME="avana_v2"
DB_USER="avana"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

docker compose exec -T postgres pg_dump -U $DB_USER $DB_NAME | \
  gzip > $BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz

# Keep only last 30 days
find $BACKUP_DIR -name "*.sql.gz" -mtime +30 -delete

echo "Backup completed: ${DB_NAME}_${TIMESTAMP}.sql.gz"
```

Set up cron:

```bash
chmod +x backup.sh
crontab -e

# Add daily backup at 2 AM:
0 2 * * * /path/to/avana-v2/backup.sh
```

### Production Service Management

```bash
# View all services
docker compose ps

# View logs
docker compose logs -f [service]

# Restart a service
docker compose restart [service]

# Update to latest code
git pull origin main
docker compose build
docker compose up -d --force-recreate

# Stop everything
docker compose down

# Stop everything and remove volumes (destructive!)
docker compose down -v

# Scale Celery workers
docker compose up -d --scale celery_worker=4
```

---

## Cloud Deployment Options

### Railway (One-Click Deploy)

1. Fork the repository to your GitHub account
2. Create a new project on [Railway](https://railway.app)
3. Click "Deploy from GitHub repo"
4. Select your forked repository
5. Add environment variables in Railway dashboard
6. Deploy — Railway auto-detects Docker Compose

**railway.json** (create in repo root):

```json
{
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "./Dockerfile"
  },
  "deploy": {
    "startCommand": "",
    "healthcheckPath": "/health"
  }
}
```

### Render

1. Fork the repository
2. Create a new "Web Service" on [Render](https://render.com)
3. Connect your GitHub repository
4. Set:
   - **Name**: `avana-v2`
   - **Environment**: `Docker`
   - **Branch**: `main`
   - **Plan**: Starter (free) or higher
5. Add environment variables in Render dashboard
6. Click "Create Web Service"
7. Render auto-builds and deploys

**render.yaml** (create in repo root):

```yaml
services:
  - type: web
    name: avana-v2-backend
    env: docker
    repo: https://github.com/yourusername/avana-v2
    branch: main
    dockerfilePath: ./backend/Dockerfile
    envVars:
      - key: POSTGRES_HOST
        fromService:
          type: pserv
          name: avana-v2-db
          property: host

  - type: pserv
    name: avana-v2-db
    env: docker
    repo: https://github.com/yourusername/avana-v2
    dockerfilePath: ./Dockerfile.postgis
```

### AWS EC2 / ECS

**EC2 Manual**:

```bash
# Launch Ubuntu 22.04 LTS instance (t3.medium minimum)
# SSH in and follow Docker Production Setup above

# Recommended: t3.medium (2 vCPU, 4GB RAM)
# Storage: 30GB gp3 SSD
# Security group: 80, 443, 22
```

**ECS with Fargate**:

1. Push Docker images to ECR (or use GitHub Actions → GHCR)
2. Create ECS cluster
3. Create task definitions for:
   - `avana-backend`: 1 vCPU, 2GB RAM
   - `avana-celery-worker`: 1 vCPU, 2GB RAM
   - `avana-frontend`: 0.5 vCPU, 1GB RAM
4. Create RDS PostgreSQL with PostGIS extension
5. Create ElastiCache Redis
6. Set up Application Load Balancer
7. Configure ECS service auto-scaling

### DigitalOcean App Platform

1. Fork the repository
2. Create app on [DigitalOcean App Platform](https://cloud.digitalocean.com/apps)
3. Connect GitHub repository
4. Set up components:
   - **Backend**: Dockerfile at `./backend/Dockerfile`, HTTP port 8000
   - **Frontend**: Dockerfile at `./frontend/Dockerfile`, HTTP port 80
   - **Database**: Managed PostgreSQL with PostGIS
   - **Redis**: Managed Redis
5. Add environment variables
6. Deploy

### Google Cloud Run

```bash
# Build backend container
gcloud builds submit --tag gcr.io/$PROJECT_ID/avana-backend ./backend

# Build frontend container
gcloud builds submit --tag gcr.io/$PROJECT_ID/avana-frontend ./frontend

# Deploy backend
gcloud run deploy avana-backend \
  --image gcr.io/$PROJECT_ID/avana-backend \
  --platform managed \
  --region asia-south1 \
  --memory 2Gi \
  --cpu 2 \
  --concurrency 80 \
  --timeout 300 \
  --set-env-vars "POSTGRES_HOST=/cloudsql/..."

# Deploy frontend
gcloud run deploy avana-frontend \
  --image gcr.io/$PROJECT_ID/avana-frontend \
  --platform managed \
  --region asia-south1

# Use Cloud SQL for PostgreSQL + PostGIS
# Use Memorystore for Redis
```

---

## Post-Deployment Checklist

### Security

- [ ] `SECRET_KEY` is a strong random string (64+ chars, generated via `openssl rand -base64 48`)
- [ ] `POSTGRES_PASSWORD` is strong (20+ chars with mixed case, numbers, symbols)
- [ ] Debug mode is `false` in production
- [ ] CORS origins are restricted to the production domain only
- [ ] SSL certificate is valid and auto-renewal is configured
- [ ] Nginx rate limiting is enabled and tuned
- [ ] All default passwords changed
- [ ] `.env` file permissions are restricted (`chmod 600 .env`)
- [ ] `.env` is not in version control (confirmed via `.gitignore`)

### Database

- [ ] PostgreSQL backup cron job is running and tested
- [ ] Backup restore process verified
- [ ] Database connection pooling sized appropriately (default: `pool_size=20, max_overflow=10`)
- [ ] PostGIS extensions are installed (`postgis`, `postgis_topology`, `fuzzystrmatch`, `pg_trgm`)
- [ ] Database indexes are created (GiST on geometry columns, B-tree on query columns)
- [ ] `VACUUM ANALYZE` scheduled for performance

### AI Services

- [ ] Gemini API key is valid and has sufficient quota
- [ ] Nominatim OSM geocoding is accessible (rate limit: 1 req/s)
- [ ] OSRM public API is accessible (or self-hosted instance configured)
- [ ] News RSS feeds are reachable from the server

### Monitoring

- [ ] Health endpoint (`/health`) is accessible and returns `healthy`
- [ ] Sentry DSN configured (if using Sentry)
- [ ] Log aggregation set up (e.g., Grafana Loki, ELK stack, or Papertrail)
- [ ] Server CPU/memory monitoring in place
- [ ] Alerting configured for service downtime
- [ ] Celery task monitoring set up (Flower dashboard or log-based)

### Performance

- [ ] Baseline response times measured for key API endpoints
- [ ] PostGIS query performance verified with `EXPLAIN ANALYZE`
- [ ] Frontend production build is optimized (Vite build)
- [ ] CDN configured for static assets (optional but recommended)
- [ ] Database connection pool sized based on expected concurrency

### Operations

- [ ] Docker compose restart policy set to `unless-stopped`
- [ ] Health checks configured for all Docker services
- [ ] Docker logs are being rotated (default Docker behavior handles this)
- [ ] `ulimit` and file descriptor limits checked
- [ ] Server timezone set to `Asia/Kolkata` (for Celery beat scheduling)
- [ ] Node/NPM versions match expected (Node 20+)
- [ ] Python version matches expected (Python 3.12+)

### Final Verification

```bash
# Run a complete system check
echo "=== Backend Health ==="
curl -s http://localhost:8000/health | python -m json.tool

echo "=== API Docs ==="
curl -s -o /dev/null -w "HTTP %{http_code}" http://localhost:8000/api/docs

echo "=== Frontend ==="
curl -s -o /dev/null -w "HTTP %{http_code}" http://localhost:5173

echo "=== Incident API ==="
curl -s http://localhost:8000/api/v1/incidents?page_size=1 | python -m json.tool

echo "=== Statis ==="
curl -s http://localhost:8000/api/v1/incidents/stats | python -m json.tool

echo "=== Risk Score ==="
curl -s http://localhost:8000/api/v1/risk/score \
  -X POST -H "Content-Type: application/json" \
  -d '{"latitude":12.9716,"longitude":77.5946}' | python -m json.tool

echo "=== Celery Worker ==="
docker compose exec celery_worker celery -A app.tasks.celery_app status

echo "=== Redis ==="
docker compose exec redis redis-cli ping

echo "=== Postgres ==="
docker compose exec postgres pg_isready -U avana

echo "=== All checks complete ==="
```

---

## Troubleshooting

### Common Issues

**Database connection refused**
```bash
# Ensure Postgres is running
docker compose ps
# Check connection string in .env matches docker-compose.yml
# Verify POSTGRES_HOST=localhost for local or POSTGRES_HOST=postgres for Docker
```

**Migrations fail**
```bash
# Reset migrations
alembic downgrade base
alembic upgrade head

# Check alembic.ini sqlalchemy.url matches .env DATABASE_URL
```

**Celery tasks not executing**
```bash
# Check Redis connection
redis-cli -u redis://localhost:6379/1 ping

# Restart Celery
docker compose restart celery_worker celery_beat

# Check logs
docker compose logs celery_worker --tail=50
```

**Gemini AI errors**
```bash
# Verify API key is set
grep GEMINI_API_KEY .env

# Test the API
curl http://localhost:8000/api/v1/chat/test

# Check Gemini quota at https://aistudio.google.com
```

**Frontend proxying issues**
```bash
# Verify backend is running on port 8000
curl http://localhost:8000/health

# Check vite.config.ts proxy setting matches backend URL
# Default: localhost:8000
```

---

## Quick Reference

### Common Commands

```bash
# Start everything
docker compose up -d

# Stop everything
docker compose down

# Rebuild and start
docker compose up -d --build

# View logs
docker compose logs -f [service]

# Run migration
docker compose exec backend alembic upgrade head

# Open shell in backend container
docker compose exec backend /bin/sh

# Run tests
docker compose exec backend pytest

# Backup database
docker compose exec postgres pg_dump -U avana avana_v2 | gzip > backup.sql.gz

# Restore database
gunzip -c backup.sql.gz | docker compose exec -T postgres psql -U avana avana_v2
```

### Directory Structure Quick Reference

```
avana-v2/
├── .env                  # Environment variables (NOT version controlled)
├── .env.example          # Environment variable template
├── docker-compose.yml    # Multi-container Docker setup
├── init-postgis.sql      # PostGIS extension init script
├── backend/
│   ├── .env              # Backend environment (optional, uses root .env)
│   ├── requirements.txt  # Python dependencies
│   ├── Dockerfile        # Backend container build
│   ├── alembic.ini       # Migration config
│   └── app/              # Python application code
└── frontend/
    ├── package.json      # Node.js dependencies
    ├── Dockerfile        # Frontend container build
    ├── vite.config.ts    # Vite dev server config
    └── src/              # React + TypeScript source
```
