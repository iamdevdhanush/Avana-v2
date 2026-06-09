# Avana V2 — AI-Powered Karnataka Safety Intelligence Platform

> *"How safe is this area right now?"* — Answering this for every location in Karnataka.

[![CI Status](https://github.com/yourusername/avana-v2/actions/workflows/ci.yml/badge.svg)](https://github.com/yourusername/avana-v2/actions)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com)
[![React 19](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev)
[![PostGIS](https://img.shields.io/badge/PostGIS-16-336791.svg)](https://postgis.net)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Overview

Avana V2 is a production-grade safety intelligence platform that continuously monitors, analyzes, and visualizes safety across Karnataka using a multi-agent AI system. It ingests real-time data from news sources, community reports, and user inputs, processes them through a LangGraph-powered AI pipeline, and delivers actionable safety intelligence through an interactive map, route planner, chatbot, and emergency SOS system.

## Features

### AI News Intelligence
Auto-scrapes 50+ Karnataka news sources (Times of India, The Hindu, Deccan Herald) via RSS feeds. Uses Gemini AI to extract structured incident data — type, severity, location, date — from article text. Geocodes extracted locations via Nominatim/OSM and persists verified incidents into the database.

### Community Intelligence
Smart classification of user-submitted safety reports using Gemini AI. Automated duplicate detection within 100m radius using PostGIS spatial queries. Spam filtering via IP rate analysis and text signature matching. Confidence scoring that determines automatic verification or flagging for admin review.

### Live Safety Map
Interactive PostGIS-powered heatmap of Karnataka with dynamic risk overlays. Three zoom levels (district ~2km, city ~500m, ward ~100m) with adaptive grid resolution. Color-coded risk categories from Safe (green) to Critical (red). District summaries with trend analysis.

### Route Intelligence
Integrates with OSRM (Open Source Routing Machine) to fetch driving, walking, and cycling routes. Divides routes into 500m segments and scores each using the risk engine. Returns the safest, fastest, and balanced route options with per-segment risk breakdowns.

### AI Safety Chatbot
Gemini-powered contextual safety assistant. Provides location-aware safety advice, incident information, and emergency guidance. Maintains conversation history for contextual responses.

### SOS System
Emergency alerting system that notifies pre-configured emergency contacts via SMS/email with the user's GPS location. Tracks SOS status lifecycle: triggered → acknowledged → resolved → false_alarm.

### Admin Dashboard
Full moderation interface for incidents and user reports. Analytics and visualization dashboards with district breakdowns, trend charts, and recent alerts. Agent pipeline management — trigger, monitor, and inspect AI agent runs.

### Real-time Updates
WebSocket support for live incident feeds and map updates (via Supabase Realtime integration, configurable).

## Tech Stack

### Frontend
- **React 19** — Latest React with concurrent features
- **TypeScript** — Full type safety across the frontend
- **Vite** — Blazing-fast dev server and optimized builds
- **TailwindCSS v4** — Utility-first CSS with custom design system
- **ShadCN UI** — Accessible, composable React components (Radix UI primitives)
- **Leaflet + react-leaflet** — Interactive map rendering with heatmap plugin
- **Recharts** — Composable charting for analytics dashboards
- **Zustand** — Lightweight state management with TypeScript support
- **TanStack React Query** — Server state management, caching, and auto-refetch
- **Axios** — HTTP client with interceptors for auth token injection
- **React Router v7** — Declarative routing with protected route guards
- **date-fns** — Modern date utility library
- **lucide-react** — Consistent icon library

### Backend
- **Python 3.12** — Modern Python with pattern matching, improved types
- **FastAPI 0.115** — Async Python web framework with OpenAPI docs
- **SQLAlchemy 2.0** — Async ORM with PostgreSQL dialect
- **GeoAlchemy2** — Spatial ORM extension for PostGIS geometry columns
- **Celery 5.4** — Distributed task queue for agent pipelines
- **Redis 7** — Message broker for Celery, caching layer
- **Pydantic v2** — Data validation and settings management
- **LangGraph** — State graph orchestration for AI agent workflows
- **LangChain** — LLM integration framework
- **Google Gemini AI** — Incident extraction, classification, recommendations
- **Alembic** — Database migration management
- **python-jose** — JWT token creation and validation
- **httpx** — Async HTTP client for RSS feeds and web scraping
- **BeautifulSoup4** — HTML parsing for article content extraction
- **feedparser** — RSS/Atom feed parsing

### Database
- **PostgreSQL 16** — Primary database with advanced features
- **PostGIS 3.4** — Spatial extensions for geographic queries
  - GiST indexes for fast radius searches
  - ST_DWithin for proximity queries
  - ST_Distance for distance calculations
  - Geography type for accurate spherical distance
- **JSONB** — Flexible metadata storage for incidents and reports

### Infrastructure
- **Docker Compose** — Multi-container orchestration for local dev
- **GitHub Actions** — CI/CD pipeline with lint, test, build, deploy
- **Nginx** — Reverse proxy with rate limiting and SSL termination
- **GHCR** — Container registry for Docker images

## Architecture

### High-Level System Diagram

```
                    ┌─────────────┐
                    │   Nginx     │
                    │  (Reverse   │
                    │   Proxy)    │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼────┐ ┌────▼────┐ ┌─────▼─────┐
        │  React   │ │ FastAPI │ │  Celery   │
        │ Frontend │ │ Backend │ │  Workers  │
        │  (Vite)  │ │(uvicorn)│ │(4 concurr)│
        └──────────┘ └────┬────┘ └──────┬─────┘
                          │             │
                    ┌─────▼────┐ ┌──────▼──────┐
                    │PostgreSQL│ │    Redis     │
                    │ +PostGIS │ │  Cache +     │
                    │  Data    │ │  Task Broker │
                    └──────────┘ └─────────────┘

AI Agent Pipeline (Celery Beat):
  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐
  │  News    │──▶│  Gemini  │──▶│ Geocoding│──▶│  Risk    │──▶│  Update  │
  │ Scraper  │   │Extraction│   │(Nominatim│   │ Scoring  │   │ Heatmap  │
  └──────────┘   └──────────┘   │   +OSM)  │   └──────────┘   └──────────┘
                                └──────────┘
  ┌──────────┐   ┌──────────┐   ┌──────────┐
  │Community │──▶│  Gemini  │──▶│  Dedup   │──▶ to Incidents
  │ Reports  │   │Classify  │   │ + Spam   │
  └──────────┘   └──────────┘   └──────────┘
```

## Quick Start

### Prerequisites
- Docker & Docker Compose v2
- Git

### Clone and Run

```bash
# Clone the repository
git clone https://github.com/yourusername/avana-v2.git
cd avana-v2

# Create environment file
cp .env.example .env
# Edit .env — set SECRET_KEY and GEMINI_API_KEY at minimum

# Start everything with Docker
docker compose up -d

# Verify it's running
curl http://localhost:8000/health
# → {"status":"healthy","version":"2.0.0","timestamp":"..."}

# Open the app
open http://localhost:5173
```

That's it. The `docker compose up -d` command starts:
- **PostgreSQL 16 + PostGIS** on port 5432
- **Redis 7** on port 6379
- **FastAPI Backend** on port 8000
- **Celery Worker** (4 concurrent tasks)
- **Celery Beat** (scheduled task dispatcher)
- **React Frontend** on port 5173
- **Nginx** on ports 80/443

## Development Setup

### Backend

```bash
# Enter backend directory
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Start infrastructure (Postgres + Redis)
docker compose up -d postgres redis

# Run database migrations
alembic upgrade head

# Seed sample data
python -m app.seed

# Start backend server (with hot reload)
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Celery

```bash
# Start worker (terminal 1)
celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4

# Start beat scheduler (terminal 2)
celery -A app.tasks.celery_app beat --loglevel=info
```

### Verify

```bash
# Backend health check
curl http://localhost:8000/health

# API docs
open http://localhost:8000/api/docs

# Frontend
open http://localhost:5173
```

## Project Structure

```
avana-v2/
├── .github/workflows/        # CI/CD pipeline
│   └── ci.yml
├── backend/
│   ├── alembic/              # Database migrations
│   │   ├── versions/
│   │   ├── env.py
│   │   └── script.py.mako
│   ├── app/
│   │   ├── agents/           # LangGraph AI agents
│   │   │   ├── runner.py         # Pipeline orchestrator
│   │   │   ├── news_intelligence.py    # News scraping + extraction
│   │   │   ├── community_intelligence.py  # Report classification
│   │   │   ├── geocoding.py      # Location geocoding agent
│   │   │   ├── risk_scoring.py   # Risk score calculation
│   │   │   ├── heatmap.py        # Heatmap generation
│   │   │   ├── route_intelligence.py   # Safe route planning
│   │   │   └── safety_recommendation.py # Safety tips generation
│   │   ├── api/
│   │   │   ├── router.py         # API route aggregator
│   │   │   └── v1/
│   │   │       ├── auth.py       # Authentication endpoints
│   │   │       ├── incidents.py  # Incident CRUD + nearby
│   │   │       ├── risk.py       # Risk scoring + heatmap
│   │   │       ├── route.py      # Safe route calculation
│   │   │       ├── sos.py        # SOS emergency system
│   │   │       ├── community.py  # Community posts + comments
│   │   │       ├── analytics.py  # Dashboard analytics
│   │   │       ├── chat.py       # AI safety chatbot
│   │   │       ├── admin.py      # Admin moderation panel
│   │   │       └── reports.py    # User safety reports
│   │   ├── models/            # SQLAlchemy ORM models
│   │   │   ├── user.py            # User + EmergencyContact
│   │   │   ├── incident.py        # Incidents with PostGIS
│   │   │   ├── location.py        # Geocoded locations cache
│   │   │   ├── risk_score.py      # Cached risk scores
│   │   │   ├── safety_report.py   # User safety reports
│   │   │   ├── sos_event.py       # SOS emergency events
│   │   │   ├── news_article.py    # Scraped news articles
│   │   │   ├── police_station.py  # Police stations POI
│   │   │   ├── hospital.py        # Hospitals POI
│   │   │   ├── community_post.py  # Community discussion posts
│   │   │   ├── comment.py         # Post comments (nested)
│   │   │   └── audit_log.py       # Audit trail
│   │   ├── schemas/           # Pydantic request/response
│   │   │   ├── auth.py
│   │   │   ├── incident.py
│   │   │   ├── risk.py
│   │   │   ├── route.py
│   │   │   ├── sos.py
│   │   │   ├── community.py
│   │   │   ├── analytics.py
│   │   │   ├── chat.py
│   │   │   └── admin.py
│   │   ├── services/          # External service integrations
│   │   │   ├── gemini.py         # Google Gemini AI client
│   │   │   ├── news_scraper.py   # RSS feed scraper
│   │   │   ├── nominatim.py      # OSM Nominatim geocoding
│   │   │   └── osrm.py           # OSRM routing service
│   │   ├── tasks/             # Celery task definitions
│   │   │   ├── celery_app.py     # Celery app configuration
│   │   │   └── scheduled.py      # Periodic task definitions
│   │   ├── utils/
│   │   │   ├── geo.py            # Geographic helpers
│   │   │   ├── logging.py        # JSON logging setup
│   │   │   └── security.py       # JWT, rate limiting, sanitization
│   │   ├── config.py          # Pydantic settings
│   │   ├── database.py        # Async SQLAlchemy engine
│   │   ├── dependencies.py    # FastAPI DI (auth guards)
│   │   └── main.py            # FastAPI application entry
│   ├── tests/                 # Pytest test suite
│   ├── alembic.ini
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/        # Reusable UI components
│   │   │   ├── charts/           # Recharts chart components
│   │   │   ├── map/              # Leaflet map components
│   │   │   ├── ui/               # ShadCN UI primitives
│   │   │   ├── Layout.tsx        # App shell layout
│   │   │   └── ProtectedRoute.tsx # Auth guard component
│   │   ├── hooks/             # Custom React hooks
│   │   │   ├── useGeolocation.ts
│   │   │   ├── useHeatmap.ts
│   │   │   ├── useRealtime.ts
│   │   │   └── useRouteSafety.ts
│   │   ├── lib/
│   │   │   ├── geo.ts            # Client-side geo utilities
│   │   │   └── utils.ts          # Formatting, helpers
│   │   ├── screens/           # Page-level components
│   │   │   ├── admin/            # Admin dashboard screens
│   │   │   ├── auth/             # Login/Signup screens
│   │   │   ├── chat/             # AI Chat screen
│   │   │   ├── community/        # Community feed
│   │   │   ├── home/             # Home/dashboard
│   │   │   ├── map/              # Interactive map
│   │   │   └── sos/              # SOS emergency screen
│   │   ├── services/
│   │   │   └── api.ts            # Axios API client
│   │   ├── store/             # Zustand state stores
│   │   │   ├── authStore.ts
│   │   │   ├── incidentStore.ts
│   │   │   ├── mapStore.ts
│   │   │   └── uiStore.ts
│   │   ├── types/
│   │   │   └── index.ts          # TypeScript type definitions
│   │   ├── App.tsx               # Root React component
│   │   ├── main.tsx              # Entry point
│   │   └── index.css             # Tailwind imports + globals
│   ├── index.html
│   ├── package.json
│   ├── vite.config.ts
│   └── Dockerfile
├── docker-compose.yml        # Multi-container orchestration
├── init-postgis.sql           # PostGIS extension init
├── nginx.conf                 # Production Nginx config
├── nginx-frontend.conf        # Frontend Nginx config
├── .env.example               # Environment variable template
├── .dockerignore
└── .gitignore
```

## AI Agent System

### News Intelligence Agent
**Schedule**: Every 6 hours (Celery Beat)
**Pipeline**: `fetch_news_sources → parse_articles → extract_incidents → geocode_incidents → save_incidents`

1. **fetch_news_sources**: Fetches RSS feeds from 50+ Karnataka news sources across 6 cities (Bengaluru, Mysuru, Mangaluru, Hubballi, Belagavi, state-level). Uses `feedparser` + `httpx` with 30s timeout.
2. **parse_articles**: Fetches full article HTML content via BeautifulSoup, strips non-content elements (scripts, nav, ads), extracts text paragraphs.
3. **extract_incidents**: Sends article text to Gemini AI with structured prompt. Returns JSON array of incidents with type, severity, location, district, description, confidence. Handles JSON parsing with markdown code block stripping.
4. **geocode_incidents**: Uses Nominatim OSM geocoding with rate limiting (1 req/s). Queries `"{location}, Karnataka, India"` for accuracy. Falls back gracefully on failure.
5. **save_incidents**: Deduplicates by `source_url` using SQLAlchemy. Validates incident type and severity enums. Creates PostGIS `POINT` geometry. Batch commits.

### Community Intelligence Agent
**Schedule**: Every hour
**Pipeline**: `fetch_pending_reports → classify_report → check_duplicates → detect_spam → generate_confidence → save_results`

1. **fetch_pending_reports**: Queries `safety_reports` table for unprocessed reports (limit 100).
2. **classify_report**: Sends each report to Gemini AI for validation — checks if incident type/severity match description, assesses location coherence, adjusts confidence score (-0.3 to +0.3).
3. **check_duplicates**: Uses `ST_DWithin` with 100m radius to find existing nearby incidents. Flags as duplicates if matches found.
4. **detect_spam**: Multi-factor spam detection:
   - **IP velocity**: >5 reports/min from same IP
   - **Text signature**: >3 reports with identical first 10 words
   - **Content validity**: Failed Gemini validation flags as spam
5. **generate_confidence**: Combines base confidence with Gemini adjustment. Duplicate reports get 0.5x penalty. Threshold 0.4 for auto-verification.
6. **save_results**: Updates report status and optionally creates verified `Incident` records.

### Risk Scoring Agent
**Trigger**: On-demand via API
**Pipeline**: `load_context → calculate_historical_risk → calculate_recent_impact → calculate_night_factor → calculate_safety_buffers → calculate_severity_penalty → compute_final_score`

1. **load_context**: Queries PostGIS for:
   - Historical incidents within 1km radius (severity-weighted count)
   - Recent incidents within 7 days within 1km
   - Nearby police stations within 2km (safety bonus)
   - Nearby hospitals within 2km (safety bonus)
2. **calculate_historical_risk**: Density factor (max 50 incidents) × 0.6 + severity factor (weighted avg/50) × 0.4, scaled to 0-100.
3. **calculate_recent_impact**: Up to 30 points — 8 points per recent incident, capped.
4. **calculate_night_factor**: +15 penalty between 9 PM and 6 AM IST.
5. **calculate_safety_buffers**: Police presence reduces risk by up to 10 points, hospitals by up to 5 points.
6. **calculate_severity_penalty**: Weighted severity penalty — critical: 50, high: 30, medium: 15, low: 5.
7. **compute_final_score**: `score = 100 - (0.4 × historical + recent_impact + night_penalty + severity_penalty) + safety_buffers`. Categories: Safe (>70), Moderate (40-70), High Risk (20-40), Critical (<20).

### Heatmap Generation Agent
**Schedule**: Every 2 hours (per district)
**Pipeline**: `determine_grid → calculate_point_scores → aggregate_results → store_heatmap`

1. **determine_grid**: Creates grid points at adaptive resolution: district (2km steps), city (500m), ward (100m). Bounds cover 31 Karnataka districts.
2. **calculate_point_scores**: Scores each grid point using risk scoring agent. Concurrent batch processing (10 at a time via `asyncio.gather`).
3. **aggregate_results**: Normalizes scores 0-100 across the grid for consistent visualization.
4. **store_heatmap**: Persists to `risk_scores` table for fast bounded queries via the API.

### Route Intelligence Agent
**Trigger**: On-demand via API
**Pipeline**: `fetch_routes → segment_routes → score_segments → rank_routes`

1. **fetch_routes**: Calls OSRM public API for driving, walking, cycling profiles with alternatives. Decodes polyline geometry.
2. **segment_routes**: Divides each route into ~500m segments with midpoint coordinates.
3. **score_segments**: Scores each segment using risk scoring agent (batch of 10 concurrent).
4. **rank_routes**: Calculates average safety score, minimum safety score, risk exposure %. Returns safest (highest avg safety), fastest (lowest duration), balanced (60% safety + 40% duration).

### Safety Recommendation Agent
**Trigger**: On-demand via API
**Pipeline**: `load_context → generate_insights → structure_recommendations`

1. **load_context**: Queries risk score + nearby incidents (5), police stations (3), hospitals (3) within 2km. Loads user's report history.
2. **generate_insights**: Sends location context to Gemini AI for personalized safety recommendations (3-5 items). Categorizes as route_safety, time_aware, resource_alert, general_precaution, incident_awareness.
3. **structure_recommendations**: Falls back to rule-based recommendations if Gemini unavailable. Ensures priority, category, and icon fields are populated.

## Database Schema

### Tables

| Table | Description | Key Spatial Column |
|---|---|---|
| `users` | User accounts + roles | — |
| `emergency_contacts` | User emergency contacts | — |
| `incidents` | Safety incidents from all sources | `geom` (POINT, GiST indexed) |
| `safety_reports` | User-submitted safety reports | `geom` (POINT) |
| `risk_scores` | Cached risk score grid data | `geom` (POINT) |
| `news_articles` | Scraped news article store | `geom` (POINT, nullable) |
| `locations` | Geocoded location cache | `geom` (POINT) |
| `police_stations` | Karnataka police stations POI | `geom` (POINT) |
| `hospitals` | Karnataka hospitals POI | `geom` (POINT) |
| `sos_events` | SOS emergency events | `geom` (POINT) |
| `community_posts` | Community discussion posts | — (lat/lng columns) |
| `comments` | Nested post comments | — |
| `audit_logs` | Admin action audit trail | — |

### Key Relationships

```
users ──┬── emergency_contacts
        ├── safety_reports
        ├── sos_events
        ├── community_posts
        └── comments

incidents ──┬── news_articles (via source_url)
            └── safety_reports (via duplicate detection)

community_posts ── comments (self-referencing for nesting)
```

### PostGIS Indexes

```sql
CREATE INDEX idx_incidents_geom_gist ON incidents USING GIST (geom);
CREATE INDEX idx_incidents_created_at ON incidents (created_at);
CREATE INDEX idx_incidents_severity ON incidents (severity);
CREATE INDEX idx_incidents_district ON incidents (district);
```

## API Documentation

When running, full interactive API documentation is available at:
- **Swagger UI**: `http://localhost:8000/api/docs`
- **ReDoc**: `http://localhost:8000/api/redoc`

### API Groups

| Base Path | Group | Auth |
|---|---|---|
| `/api/v1/auth` | Authentication | Public / Bearer |
| `/api/v1/incidents` | Incidents | Public / Bearer |
| `/api/v1/risk` | Risk Assessment | Bearer |
| `/api/v1/route` | Route Intelligence | Bearer |
| `/api/v1/sos` | SOS Emergency | Bearer |
| `/api/v1/community` | Community | Bearer |
| `/api/v1/analytics` | Analytics | Admin |
| `/api/v1/chat` | AI Chat | Bearer |
| `/api/v1/admin` | Admin Panel | Admin |
| `/api/v1/reports` | Safety Reports | Bearer |
| `/health` | Health Check | Public |
| `/` | Service Info | Public |

## Deployment

### Docker Production

```bash
# Clone on server
git clone https://github.com/yourusername/avana-v2.git
cd avana-v2

# Configure environment
cp .env.example .env
# Edit .env for production (strong passwords, API keys, etc.)

# Build and start
docker compose build
docker compose up -d

# Check logs
docker compose logs -f backend
```

### SSL Setup (Let's Encrypt)

```bash
# Install certbot
sudo apt install certbot

# Get certificate
sudo certbot certonly --standalone -d avana.yourdomain.com

# Copy to nginx ssl directory
mkdir -p ssl
sudo cp /etc/letsencrypt/live/avana.yourdomain.com/fullchain.pem ssl/
sudo cp /etc/letsencrypt/live/avana.yourdomain.com/privkey.pem ssl/
sudo chmod 600 ssl/privkey.pem
```

### Cloud Deployment Options

- **Railway**: One-click deploy via `railway.json`
- **Render**: Blueprint deploy via `render.yaml`
- **AWS ECS**: Deploy using GitHub Actions + ECR
- **DigitalOcean App Platform**: Connect repo, auto-deploy
- **Google Cloud Run**: Build container, deploy with Cloud Run

### Production Checklist

- [ ] Strong random `SECRET_KEY` (64+ chars)
- [ ] Strong `POSTGRES_PASSWORD`
- [ ] Valid `GEMINI_API_KEY` configured
- [ ] SSL certificates installed
- [ ] PostgreSQL backup cron job configured
- [ ] Monitoring/alerting set up (Sentry DSN optional)
- [ ] Log aggregation configured
- [ ] Rate limiting tuned for production
- [ ] CORS origins updated to production domain
- [ ] Database connection pool sized appropriately

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | **Yes** | — | JWT signing secret (min 64 chars) |
| `POSTGRES_PASSWORD` | **Yes** | — | Database password |
| `GEMINI_API_KEY` | **Yes** | — | Google Gemini AI API key |
| `POSTGRES_USER` | No | `avana` | Database user |
| `POSTGRES_HOST` | No | `localhost` | Database host |
| `POSTGRES_PORT` | No | `5432` | Database port |
| `POSTGRES_DB` | No | `avana_v2` | Database name |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection |
| `CELERY_BROKER_URL` | No | `redis://localhost:6379/1` | Celery broker |
| `CELERY_RESULT_BACKEND` | No | `redis://localhost:6379/2` | Celery result backend |
| `JWT_ALGORITHM` | No | `HS256` | JWT signing algorithm |
| `JWT_EXPIRATION_HOURS` | No | `24` | Token expiry |
| `CORS_ORIGINS` | No | `http://localhost:5173,http://localhost:3000` | Allowed CORS origins |
| `NEWS_SCRAPE_INTERVAL_MINUTES` | No | `360` | News scrape frequency |
| `AGENT_RUN_INTERVAL_MINUTES` | No | `60` | Agent pipeline frequency |
| `RATE_LIMIT_MAX` | No | `100` | Max requests per window |
| `RATE_LIMIT_WINDOW` | No | `60` | Rate limit window (seconds) |
| `SUPABASE_URL` | No | — | Supabase project URL |
| `SUPABASE_ANON_KEY` | No | — | Supabase anonymous key |
| `SUPABASE_SERVICE_KEY` | No | — | Supabase service role key |
| `SENTRY_DSN` | No | — | Sentry error tracking DSN |
| `SMTP_HOST` | No | — | SMTP server for SOS emails |
| `SMTP_PORT` | No | `587` | SMTP port |
| `SMTP_USER` | No | — | SMTP username |
| `SMTP_PASSWORD` | No | — | SMTP password |

## Testing

```bash
# Backend tests
cd backend
pytest tests/ -v --cov=app --cov-report=term-missing

# Frontend lint
cd frontend
npm run lint

# Frontend build (verifies TypeScript)
npm run build
```

The CI pipeline in `.github/workflows/ci.yml` runs:
1. **lint-backend**: flake8 + black formatting check
2. **lint-frontend**: ESLint
3. **test-backend**: pytest with PostGIS + Redis services
4. **test-frontend**: TypeScript build + vitest
5. **build-and-push**: Docker images to GHCR (main only)
6. **deploy**: SSH deploy to production server (main only)

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow existing code style (Black formatter for Python, Prettier for TypeScript)
- Write tests for new features
- Update API documentation for endpoint changes
- Use conventional commits (`feat:`, `fix:`, `chore:`, `docs:`)

## License

Distributed under the MIT License. See `LICENSE` for more information.

## Roadmap

### Phase 1: Karnataka (Current)
- [x] Multi-agent AI pipeline
- [x] News scraping from 50+ sources
- [x] Community intelligence with spam/dedup
- [x] Real-time risk scoring engine
- [x] Interactive safety heatmap
- [x] Route intelligence with OSRM
- [x] AI safety chatbot
- [x] SOS emergency system
- [x] Admin moderation dashboard
- [x] PostGIS-powered spatial queries

### Phase 2: South India
- [ ] Tamil Nadu state expansion
- [ ] Kerala state expansion
- [ ] Andhra Pradesh state expansion
- [ ] Telangana state expansion
- [ ] Multi-state heatmap aggregation
- [ ] Cross-state route intelligence
- [ ] Regional language support (Kannada, Tamil, Malayalam, Telugu)

### Phase 3: All India
- [ ] Pan-India news source coverage
- [ ] All-state risk scoring models
- [ ] National heatmap with state drill-down
- [ ] Integration with national crime databases
- [ ] Mobile app (React Native)

### Phase 4: Southeast Asia
- [ ] Sri Lanka expansion
- [ ] Bangladesh expansion
- [ ] Nepal expansion
- [ ] Multilingual AI models
- [ ] International routing providers
- [ ] Local emergency service integration per country
