# Avana V2 — ₹0 Architecture

## Cost Analysis

| Service | Purpose | Tier | Monthly Cost | Limits |
|---------|---------|------|-------------|--------|
| Vercel | Frontend hosting | Free | ₹0 | 100GB bandwidth, 6000 build min |
| Render/Fly.io | Backend API | Free | ₹0 | 512MB RAM, 1CPU, sleeps after inactivity |
| Supabase | PostgreSQL + PostGIS | Free | ₹0 | 500MB DB, 2GB bandwidth, 50K rows |
| Redis Cloud | Celery broker (optional) | Free | ₹0 | 30MB, 1 Redis instance |
| Google Gemini | AI extraction | Free | ₹0 | 60 requests/min, 1500/day |
| Nominatim (OSM) | Geocoding | Free | ₹0 | 1 req/sec rate limit |
| OSRM | Route calculation | Free | ₹0 | Public API, no auth needed |
| SendGrid | Email (SOS alerts) | Free | ₹0 | 100 emails/day |
| Total | | | **₹0** | |

## Architecture Diagram

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Browser     │────▶│  Vercel      │────▶│  FastAPI         │
│  React SPA   │     │  CDN + Proxy │     │  (Render/Fly.io) │
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                   │
                          ┌────────────────────────┼────────────────────┐
                          │                        │                     │
                          ▼                        ▼                     ▼
                   ┌──────────────┐        ┌──────────────┐     ┌──────────────┐
                   │  Supabase    │        │  Gemini API  │     │  OSRM        │
                   │  PostgreSQL  │        │  (Free Tier)  │     │  Public API  │
                   │  + PostGIS   │        └──────────────┘     └──────────────┘
                   └──────────────┘
                          │
                          ▼
                   ┌──────────────┐
                   │  Nominatim   │
                   │  (OSM Free)  │
                   └──────────────┘
```

## Intelligence Pipeline (Manual Trigger, No Celery)

```
Admin clicks "Run Intelligence Update"
  ↓
Fetch 12 RSS feeds from Karnataka news
  ↓
Parse articles (full text extraction)
  ↓
Gemini Free Tier: extract incident JSON
  ↓
Deduplicate by URL
  ↓
Geocode via Nominatim (rate-limited)
  ↓
Store in incidents table
  ↓
Recalculate affected risk scores
  ↓
Regenerate heatmap grid cells
```

## Key Design Decisions

1. **No LangGraph** — linear pipelines are async functions, not state machines
2. **No Chatbot** — removed; not part of safety platform core
3. **No Celery for MVP** — intelligence runs synchronously on admin trigger
4. **No Redis required** — rate limiting is in-process memory
5. **PostGIS for all spatial queries** — no paid GIS services
6. **Refreshed tokens** — access + refresh token pair
7. **Rate limiting** — in-process sliding window (no Redis needed)
