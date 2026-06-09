# Avana V2 — Architecture Document

> *Technical architecture of the AI-Powered Karnataka Safety Intelligence Platform*

---

## 1. System Architecture

### 1.1 High-Level Architecture

Avana V2 follows a **microservices-oriented monolith** design — a single deployable unit with logically separated components running as distinct processes, communicating over well-defined interfaces.

```
┌─────────────────────────────────────────────────────────────┐
│                        Internet                              │
└────────────────────────┬────────────────────────────────────┘
                         │
                    ┌────▼────┐
                    │  Nginx  │  Reverse Proxy, SSL Termination
                    │  :80/443│  Rate Limiting, Security Headers
                    └────┬────┘
                         │
           ┌─────────────┼──────────────┐
           │             │              │
     ┌─────▼─────┐ ┌────▼──────┐ ┌─────▼──────────┐
     │  React    │ │  FastAPI  │ │  Celery         │
     │  Frontend │ │  Backend  │ │  ┌────────────┐ │
     │  :5173    │ │  :8000    │ │  │ Worker (x4)│ │
     │           │ │           │ │  ├────────────┤ │
     │  Vite     │ │  Uvicorn  │ │  │ Beat       │ │
     │  Dev/PROD │ │  ASGI     │ │  └────────────┘ │
     └───────────┘ └─────┬─────┘ └────────┬────────┘
                         │                │
                    ┌────▼─────────┐ ┌────▼──────────┐
                    │  PostgreSQL  │ │    Redis       │
                    │  + PostGIS   │ │  :6379         │
                    │  :5432       │ │                │
                    │  Async       │ │  Cache/Broker  │
                    │  SQLAlchemy  │ │  Result Backend│
                    └──────────────┘ └────────────────┘
```

### 1.2 Component Interaction Flows

#### Request Flow (API)

```
Client → Nginx → FastAPI → [Middleware Stack] → Router → Endpoint → Service/Agent → Database
                ↑              │
                └── CORS, Auth, Rate Limit, Request ID, Sanitization
```

1. Nginx terminates SSL, applies rate limiting per IP
2. FastAPI middleware stack: `CORS → Request ID → Input Sanitization`
3. Auth middleware extracts JWT from Bearer token, attaches `User` object
4. Router dispatches to versioned endpoint (`/api/v1/...`)
5. Endpoint handler calls service/agent, queries database
6. Response flows back through middleware with timing headers

#### Agent Pipeline Flow

```
Celery Beat ──→ Redis (schedule) ──→ Celery Worker
                                        │
                                   ┌────▼────┐
                                   │ LangGraph│
                                   │ StateGraph│
                                   └────┬────┘
                                        │
                              ┌─────────┼─────────┐
                         ┌────▼────┐ ┌──▼───┐ ┌───▼────┐
                         │  Node 1 │ │Node 2│ │ Node N │
                         │ (Fetch) │ │ (AI) │ │ (Save) │
                         └────┬────┘ └──┬───┘ └───┬────┘
                              │         │         │
                         ┌────▼─────────▼─────────▼────┐
                         │     External Services        │
                         │  Gemini AI / Nominatim / OSRM │
                         └──────────────────────────────┘
```

1. Celery Beat checks schedule (every 6 hours for news, hourly for community)
2. Task published to Redis broker
3. Celery Worker picks up task, executes LangGraph StateGraph
4. Each graph node performs a specific step (fetch, AI extraction, save)
5. State is passed between nodes as typed dictionaries
6. Results persisted to PostgreSQL, errors logged

### 1.3 Data Flow Diagram

```
                         ┌──────────────┐
                         │   External   │
                         │  RSS Feeds   │
                         └──────┬───────┘
                                │ fetch RSS
                                ▼
                    ┌───────────────────────┐
                    │   News Intelligence    │
                    │   LangGraph Pipeline   │
                    │                        │
                    │  fetch_news_sources ──┐│
                    │  parse_articles ──────┤│
                    │  extract_incidents ───┤│ (Gemini AI)
                    │  geocode_incidents ───┤│ (Nominatim)
                    │  save_incidents ──────┘│
                    └──────────┬────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │      Incidents       │
                    │   (PostGIS Table)    │
                    └──┬───────────────┬───┘
                       │               │
              ┌────────▼────┐    ┌─────▼─────────┐
              │ Risk Scoring │    │  Heatmap Gen  │
              │ Agent        │    │  Agent         │
              │ (on-demand)  │    │ (scheduled)    │
              └──────┬───────┘    └───────┬────────┘
                     │                    │
              ┌──────▼───────┐    ┌───────▼────────┐
              │ Risk Scores  │    │  Heatmap Grid  │
              │ (JSONB cache)│    │  (risk_scores) │
              └──────────────┘    └────────────────┘

Community Reports (User) ──→ Community Intelligence ──→ Incidents
                                       │
                              Duplicates/Spam Detection
                                       │
                              Gemini AI Classification
```

---

## 2. AI Agent System Deep Dive

### 2.1 LangGraph StateGraph Architecture

All agents are built using LangGraph's `StateGraph` with a shared pattern:

```python
# Pattern used by every agent:
workflow = StateGraph(StateType)
workflow.add_node("step_1", step_1_function)
workflow.add_node("step_2", step_2_function)
workflow.set_entry_point("step_1")
workflow.add_edge("step_1", "step_2")
workflow.add_edge("step_2", END)
graph = workflow.compile()
result = await graph.ainvoke(initial_state)
```

Each node receives and returns a `TypedDict` state, enabling:
- Strong typing of intermediate data
- Easy debugging by inspecting state at any point
- Simple addition of new steps (conditional edges planned for v2.1)
- Testability — each node can be tested independently

### 2.2 News Intelligence Agent

```
State: NewsState {
    sources: List[dict],
    articles: List[dict],
    extracted_incidents: List[dict],
    geocoded_incidents: List[dict],
    saved_count: int,
    errors: List[str],
}

┌─────────────────────┐
│ fetch_news_sources  │  RSS → List[Article]
│ httpx + feedparser  │  Times of India, The Hindu, Deccan Herald
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ parse_articles      │  HTML → Clean Text
│ BeautifulSoup       │  Strip scripts, nav, ads
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ extract_incidents   │  Text → Structured Incidents
│ Gemini AI           │  Prompt-engineered JSON extraction
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ geocode_incidents   │  Location Name → (lat, lng)
│ Nominatim OSM       │  Rate-limited (1 req/s)
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ save_incidents      │  Persist with dedup
│ SQLAlchemy + PostGIS│  Unique by source_url
└─────────┬───────────┘
          ▼
        END
```

**Error Handling**: Each node wraps operations in try/except. Errors are appended to `state["errors"]` without crashing the pipeline. If geocoding fails for a specific article, that article is skipped but processing continues.

**Gemini Prompt Design**: The extraction prompt explicitly lists valid enum values (`incident_type`, `severity`), reqests JSON-only responses, and provides the article title + text. Response cleaning strips markdown code fences before JSON parsing.

### 2.3 Community Intelligence Agent

```
State: CommunityState {
    pending_reports: List[dict],
    classified_reports: List[dict],
    duplicates_found: List[dict],
    spam_detected: List[dict],
    verified_reports: List[dict],
    saved_count: int,
    errors: List[str],
}

┌─────────────────────┐
│ fetch_pending_reports│  DB: safety_reports WHERE status='pending'
│ SQLAlchemy          │  Limit 100, oldest first
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ classify_report     │  Gemini: validate type/severity/coherence
│ Gemini AI           │  Returns confidence_adjustment (-0.3 to +0.3)
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ check_duplicates    │  PostGIS ST_DWithin (100m radius)
│ Spatial Query       │  Matches existing incidents
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ detect_spam         │  Multi-factor: IP velocity, text sig, content
│ Rule-based + AI     │  >5/min IP, >3 identical texts, invalid
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ generate_confidence │  Combine base + adjustment - penalties
│ Scoring Algorithm   │  Threshold 0.4 for auto-verify
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│ save_results        │  Update reports, create incidents
└─────────┬───────────┘
          ▼
        END
```

**Spam Detection Algorithm**:

```
Score = base_confidence + gemini_adjustment
if is_duplicate: Score *= 0.5
if is_spam: Score = 0.0
if Score >= 0.4 AND not spam AND not duplicate → VERIFIED
if is_spam → SPAM
if is_duplicate → DUPLICATE
else → PENDING (requires admin review)
```

### 2.4 Risk Scoring Agent

```
State: RiskScoreState {
    latitude: float,
    longitude: float,
    district: Optional[str],
    score: Optional[float],
    category: Optional[str],
    factors: dict,
}

┌──────────────────────┐
│ load_context         │  PostGIS spatial queries
│                      │  - Incidents within 1km
│                      │  - Recent (7d) incidents within 1km
│                      │  - Police stations within 2km
│                      │  - Hospitals within 2km
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ calculate_historical │  Score = density(0.6) + severity(0.4)
│ risk                 │  Density: min(count/50, 1.0)
│                      │  Severity: avg_severity/50
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ calculate_recent     │  Impact = min(count * 8, 30)
│ impact               │  8 points per recent incident
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ calculate_night      │  Penalty = 15 if 21:00-06:00 IST
│ factor               │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ calculate_safety     │  Police: +10 max (3.33 each)
│ buffers              │  Hospital: +5 max (1.67 each)
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ calculate_severity   │  Weighted avg by type
│ penalty              │  critical=50, high=30, medium=15, low=5
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│ compute_final_score  │  Formula:
│                      │  raw = 100 - (0.4*hist + recent
│                      │        + night + severity) + buffers
│                      │  score = clamp(raw, 0, 100)
└──────────┬───────────┘
           ▼
         END
```

**Risk Categories**:

| Score Range | Category |
|---|---|
| 0-20 | Critical |
| 20-40 | High Risk |
| 40-70 | Moderate |
| 70-100 | Safe |

### 2.5 Multi-Agent Orchestration

The `runner.py` module provides the orchestration layer:

```python
async def run_all_agents() -> dict:
    results = {}
    results["news"] = await run_news_pipeline()
    results["community"] = await run_community_pipeline()
    results["heatmap_district"] = await run_heatmap_pipeline("district")
    return results
```

Individual pipeline functions wrap each LangGraph execution with:
- Structured logging (pipeline start/end with timestamps)
- Error isolation (one pipeline failure doesn't affect others)
- Duration tracking
- Result summary for monitoring

### 2.6 Scheduled Pipeline Design

Celery Beat schedules (defined in `scheduled.py:setup_periodic_tasks()`):

| Task | Schedule | Queue | Description |
|---|---|---|---|
| `run_news_agent` | Every 6 hours | `agents` | Scrape news, extract incidents |
| `run_community_agent` | Every hour | `agents` | Process pending reports |
| `update_heatmaps` | Every 2 hours | `heatmap` | Regenerate per-district heatmaps |
| `calculate_risk_scores` | Every 6 hours | `scoring` | Batch recalculate stale scores |
| `cleanup_old_data` | Daily at 3AM | `maintenance` | Archive old articles, purge sessions |
| `run_all_agents` | Every 12 hours | `agents` | Full pipeline run |

Each task has:
- `max_retries` (2-3) with exponential backoff
- `default_retry_delay` (30-300 seconds)
- Isolated error handling per subtask
- Structured logging for monitoring

### 2.7 Error Handling and Fallbacks

| Failure Mode | Handling Strategy |
|---|---|
| Gemini API unavailable | Log warning, return empty/fallback results |
| RSS feed timeout | Skip feed, continue with others |
| Geocoding failure | Skip incident, log error |
| Database connection lost | Retry with backoff, surface in health check |
| OSRM timeout | Return error to client, retry supported |
| Rate limit exceeded | Graceful degradation, cache hit fallback |

---

## 3. Database Architecture

### 3.1 PostGIS Spatial Indexing Strategy

The platform uses **GiST (Generalized Search Tree)** indexes on geometry columns for efficient spatial queries:

```sql
-- Primary spatial index for incident proximity searches
CREATE INDEX idx_incidents_geom_gist ON incidents USING GIST (geom);

-- Query pattern: find incidents within radius
SELECT * FROM incidents
WHERE ST_DWithin(
    geom::geography,
    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography,
    :radius_meters
);
```

**Why GiST?**: GiST indexes support `ST_DWithin`, `ST_Distance`, and `ST_Intersects` operators. They partition space into overlapping bounding boxes, enabling fast nearest-neighbor and radius searches. For a 50K incident table, radius queries complete in <50ms.

**Geography vs Geometry**: The platform uses `Geography` type (via `::geography` cast) for accurate spherical distance calculations. While slightly slower than planar `Geometry`, it provides correct results across Karnataka's extent (11.5°N to 18°N).

### 3.2 Entity-Relationship Diagram (Text)

```
┌───────────────────┐       ┌──────────────────────┐
│      users        │       │  emergency_contacts   │
│───────────────────│       │──────────────────────│
│ id (PK, UUID)     │──┐   │ id (PK, UUID)        │
│ email (UNIQUE)    │  └──>│ user_id (FK)          │
│ name              │       │ name                  │
│ role (enum)       │       │ phone                 │
│ phone             │       │ relationship          │
│ is_verified       │       │ is_primary            │
│ is_active         │       └──────────────────────┘
│ supabase_uid      │
│ created_at        │       ┌──────────────────────┐
│ last_login        │       │   incidents           │
└───────────────────┘       │──────────────────────│
       │                    │ id (PK, UUID)        │
       │  ┌────────────────>│ incident_type (enum)  │
       │  │                 │ severity (enum)       │
       │  │                 │ source (enum)         │
       │  │                 │ status (enum)         │
       │  │                 │ confidence_score      │
       │  │                 │ latitude, longitude   │
       │  │                 │ geom (POINT, GiST)    │
       │  │                 │ description           │
       │  │                 │ district              │
       │  │                 │ city                  │
       │  │                 │ incident_date         │
       │  │                 │ source_url            │
       │  │                 │ metadata (JSONB)      │
       │  │                 │ user_id (FK)          │
       │  │                 │ is_duplicate          │
       │  │                 │ created_at            │
       │  │                 │ updated_at            │
       │  │                 └──────────────────────┘
       │  │
       │  │                 ┌──────────────────────┐
       │  │                 │   risk_scores        │
       │  │                 │──────────────────────│
       │  └────────────────>│ id (PK, UUID)        │
       │                    │ location_id (FK)      │
       │  ┌────────────────>│ latitude, longitude   │
       │  │                 │ geom (POINT)          │
       │  │                 │ score                 │
       │  │                 │ category (enum)       │
       │  │                 │ district/city/taluk   │
       │  │                 │ police_presence       │
       │  │                 │ night_factor          │
       │  │                 │ metadata (JSONB)      │
       │  │                 │ calculated_at         │
       │  │                 └──────────────────────┘
       │  │
       │  │                 ┌──────────────────────┐
       │  │                 │   safety_reports     │
       │  └────────────────>│──────────────────────│
       │                    │ id (PK, UUID)        │
       │  ┌────────────────>│ user_id (FK)          │
       │  │                 │ incident_type (enum)  │
       │  │                 │ severity (enum)       │
       │  │                 │ latitude, longitude   │
       │  │                 │ geom (POINT)          │
       │  │                 │ description           │
       │  │                 │ status (enum)         │
       │  │                 │ is_anonymous          │
       │  │                 │ is_verified           │
       │  │                 │ confidence_score      │
       │  │                 │ moderated_by          │
       │  │                 └──────────────────────┘
       │  │
       │  │                 ┌──────────────────────┐
       │  │                 │    sos_events         │
       │  └────────────────>│──────────────────────│
       │                    │ id (PK, UUID)        │
       │  ┌────────────────>│ user_id (FK)          │
       │  │                 │ latitude, longitude   │
       │  │                 │ geom (POINT)          │
       │  │                 │ message               │
       │  │                 │ status (enum)         │
       │  │                 │ emergency_type        │
       │  │                 │ notified_contacts     │
       │  │                 │ created_at            │
       │  │                 └──────────────────────┘
       │  │
       │  │                 ┌──────────────────────┐
       │  │                 │   community_posts    │
       │  └────────────────>│──────────────────────│
       │                    │ id (PK, UUID)        │
       │                    │ user_id (FK)          │
       │                    │ content               │
       │                    │ latitude, longitude   │
       │                    │ post_type             │
       │                    │ upvotes/downvotes     │
       │                    │ is_verified           │
       │                    │ status (enum)         │
       │                    │ created_at            │
       │                    └──────────┬───────────┘
       │                               │
       │                    ┌──────────▼───────────┐
       │                    │      comments         │
       │                    │──────────────────────│
       │                    │ id (PK, UUID)        │
       │                    │ post_id (FK)          │
       │                    │ user_id (FK)          │
       │                    │ parent_id (FK, self)  │
       │                    │ content               │
       │                    │ upvotes               │
       │                    └──────────────────────┘
       │
       │                 ┌──────────────────────┐
       │                 │    news_articles      │
       │                 │──────────────────────│
       │                 │ id (PK, UUID)        │
       │                 │ title, url (UNIQUE)   │
       │                 │ source, source_type   │
       │                 │ published_at          │
       │                 │ content, summary      │
       │                 │ incident_type         │
       │                 │ latitude, longitude   │
       │                 │ geom (POINT)          │
       │                 │ is_processed          │
       │                 │ confidence_score      │
       │                 └──────────────────────┘
       │
       │                 ┌──────────────────────┐
       │                 │      locations        │
       │                 │──────────────────────│
       │                 │ id (PK, UUID)        │
       │                 │ name, address         │
       │                 │ place_id              │
       │                 │ latitude, longitude   │
       │                 │ geom (POINT)          │
       │                 │ district/city/taluk   │
       │                 │ pincode               │
       │                 │ metadata (JSONB)      │
       │                 └──────────────────────┘
       │
       │                 ┌──────────────────────┐
       │                 │   police_stations     │
       │                 │──────────────────────│
       │                 │ id (PK, UUID)        │
       │                 │ name, address         │
       │                 │ latitude, longitude   │
       │                 │ geom (POINT)          │
       │                 │ phone, email          │
       │                 │ district/city/taluk   │
       │                 │ station_type          │
       │                 └──────────────────────┘
       │
       │                 ┌──────────────────────┐
       │                 │     hospitals         │
       │                 │──────────────────────│
       │                 │ id (PK, UUID)        │
       │                 │ name, address         │
       │                 │ latitude, longitude   │
       │                 │ geom (POINT)          │
       │                 │ phone, email          │
       │                 │ hospital_type         │
       │                 │ emergency_services    │
       │                 │ beds_available        │
       │                 └──────────────────────┘
       │
       │                 ┌──────────────────────┐
       │                 │     audit_logs        │
       │                 │──────────────────────│
       │                 │ id (PK, UUID)        │
       │                 │ user_id               │
       │                 │ action                │
       │                 │ resource_type         │
       │                 │ resource_id           │
       │                 │ details (JSONB)       │
       │                 │ ip_address            │
       │                 │ created_at            │
       │                 └──────────────────────┘
```

### 3.3 Query Optimization Patterns

**Spatial Proximity Search** (used by risk scoring):
```sql
-- Uses GiST index, <50ms on 50K rows
SELECT COUNT(*) FROM incidents
WHERE ST_DWithin(geom::geography,
    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography, :radius)
AND status != 'dismissed';
```

**Distance-Ordered Nearest Neighbor** (used by nearby incidents):
```sql
-- GiST index supports ORDER BY distance
SELECT id, ST_Distance(geom::geography,
    ST_SetSRID(ST_MakePoint(:lng, :lat), 4326)::geography) as dist
FROM incidents
WHERE ST_DWithin(geom::geography, ...)
ORDER BY dist ASC
LIMIT 50;
```

**Heatmap Bounded Query** (used by frontend):
```sql
-- Uses composite index on (zoom_level, latitude, longitude) via risk_scores
SELECT DISTINCT ON (latitude, longitude) latitude, longitude, score, category
FROM risk_scores
WHERE latitude BETWEEN :sw_lat AND :ne_lat
  AND longitude BETWEEN :sw_lng AND :ne_lng
  AND zoom_level = :zoom
ORDER BY latitude, longitude, generated_at DESC;
```

**District Aggregation** (used by analytics):
```sql
-- Sequential scan on indexed district column
SELECT district, COUNT(*) as cnt
FROM incidents WHERE district IS NOT NULL
GROUP BY district ORDER BY cnt DESC;
```

### 3.4 Partitioning Strategy

For production scale (>1M incidents), the platform is designed to support:

**Time-based Partitioning**: Partition `incidents` by `created_at` month:
```sql
CREATE TABLE incidents_2026_01 PARTITION OF incidents
FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
```

**Spatial Partitioning**: Partition `risk_scores` by district bounding box for parallel heatmap generation.

---

## 4. API Design

### 4.1 RESTful Resource Naming

| Pattern | Example |
|---|---|
| `/api/v1/{resource}` | `/api/v1/incidents` |
| `/api/v1/{resource}/{id}` | `/api/v1/incidents/{id}` |
| `/api/v1/{resource}/nested` | `/api/v1/incidents/nearby` |
| `/api/v1/{resource}/{id}/action` | `/api/v1/incidents/{id}/moderate` |

### 4.2 Authentication Flow

```
Client                    Server
  │                         │
  │  POST /auth/signup      │
  │  {email, password, name}│
  │────────────────────────>│
  │                         │  Check email uniqueness
  │                         │  Create User record
  │                         │  Generate JWT (sub=user_id)
  │  {access_token, user}   │  exp: 24h, iat: now
  │<────────────────────────│
  │                         │
  │  GET /incidents         │
  │  Authorization: Bearer  │
  │  <token>                │
  │────────────────────────>│
  │                         │  Decode JWT, extract sub
  │                         │  Query user from DB
  │                         │  Attach to request.state
  │  {incidents[]}          │
  │<────────────────────────│
```

**JWT Payload**:
```json
{
  "sub": "uuid-user-id",
  "exp": 1712345678,
  "iat": 1712259278
}
```

**Auth Guards**:
- `get_current_user`: Optional — returns `None` if no valid token
- `require_user`: Required — returns 401 if no token
- `require_admin`: Role check — returns 403 if not admin

### 4.3 Rate Limiting Strategy

Two-layer rate limiting:

1. **Nginx Level** (production): 30 req/s per IP to `/api`, 10 req/s to `/auth`
2. **Application Level** (all environments): Configurable via `RATE_LIMIT_MAX` per `RATE_LIMIT_WINDOW` seconds

429 Response:
```json
{
  "detail": "Rate limit exceeded. Try again later."
}
```

### 4.4 Error Response Format

```json
{
  "detail": "Human-readable error message",
  "request_id": "a1b2c3d4"
}
```

Status codes:
- `200` — Success
- `201` — Created
- `400` — Bad Request (validation error)
- `401` — Unauthenticated
- `403` — Forbidden (insufficient role)
- `404` — Not Found
- `409` — Conflict (duplicate email, etc.)
- `429` — Rate Limit Exceeded
- `500` — Internal Server Error (with `request_id` for tracing)

### 4.5 Pagination Conventions

All list endpoints use cursor-style pagination:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number (1-indexed) |
| `page_size` | int | 20 | Items per page (max 100) |

Response:
```json
{
  "items": [...],
  "total": 156,
  "page": 1,
  "page_size": 20
}
```

---

## 5. Frontend Architecture

### 5.1 Component Hierarchy

```
<App>
  <QueryClientProvider>
    <BrowserRouter>
      <Routes>
        <LoginScreen />
        <SignupScreen />
        <ProtectedRoute>
          <Layout>
            <Sidebar />
            <MainContent>
              <Outlet>  <!-- React Router -->
                <HomeScreen />
                <MapScreen />
                <CommunityScreen />
                <SOSScreen />
                <ChatScreen />
                <AdminDashboard />
                <AdminIncidents />
                <AdminUsers />
                <AdminAgents />
              </Outlet>
            </MainContent>
          </Layout>
        </ProtectedRoute>
      </Routes>
      <Toaster />  <!-- Global toast notifications -->
    </BrowserRouter>
  </QueryClientProvider>
</App>
```

### 5.2 State Management with Zustand

Four Zustand stores with TypeScript support:

**authStore**: User session, JWT token, login/signup/logout actions
```typescript
interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  loadUser: () => Promise<void>;
}
```

**incidentStore**: Incident list, filters, pagination
```typescript
interface IncidentState {
  incidents: Incident[];
  filters: { type, severity, status, search, dateFrom, dateTo };
  pagination: { page, limit, total, totalPages };
  fetchIncidents: (page?: number) => Promise<void>;
  setFilters: (filters: Partial<IncidentFilters>) => void;
}
```

**mapStore**: Map center, zoom, bounds, heatmap points, markers
```typescript
interface MapState {
  center: [number, number];
  zoom: number;
  bounds: MapBounds | null;
  mapType: MapType;
  heatmapPoints: HeatmapPoint[];
  markers: Marker[];
  setCenter, setZoom, setBounds, setMapType, setHeatmapPoints;
}
```

**uiStore**: Theme, sidebar, modals, toasts, online status
```typescript
interface UIState {
  theme: 'dark' | 'light';
  sidebarOpen: boolean;
  toasts: Toast[];
  isOnline: boolean;
  toggleTheme, toggleSidebar, addToast, removeToast;
}
```

### 5.3 React Query Caching Strategy

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      refetchOnWindowFocus: false,
      staleTime: 30000,        // 30s before refetch
      gcTime: 5 * 60 * 1000,  // 5min garbage collection
    },
  },
});
```

- **StaleTime: 30s** — Frequent updates for live map data without excessive refetches
- **gcTime: 5min** — Keep data cached for navigation without loading states
- **retry: 2** — Automatic retry on network failures
- **refetchOnWindowFocus: false** — Prevent unnecessary API calls

### 5.4 Real-Time Updates Architecture

WebSocket connections via Supabase Realtime (configurable):

```typescript
// useRealtime hook pattern
const channel = supabase
  .channel('incidents')
  .on('postgres_changes',
    { event: 'INSERT', schema: 'public', table: 'incidents' },
    (payload) => { store.addIncident(payload.new); }
  )
  .subscribe();
```

The Nginx config includes WebSocket proxy support:
```
location /ws {
    proxy_pass http://backend:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

### 5.5 Map Rendering Optimization

- **Leaflet with Canvas renderer**: Faster than SVG for many markers
- **Heatmap layer**: `leaflet.heat` for GPU-accelerated heatmap rendering
- **Tile caching**: Browser cache for map tiles
- **Viewport-based loading**: Only fetch incident data for visible bounds
- **Debounced bounds change**: 300ms debounce on map pan/zoom to prevent API spam
- **Zoom-dependent detail**: District-level at zoom < 10, city at zoom 10-13, ward at zoom > 13

---

## 6. Security Architecture

### 6.1 JWT Token Lifecycle

```
Signup/Login → Token Generated (exp: 24h) → Stored in localStorage
                                                    │
                                           ┌────────▼────────┐
                                           │  Axios Interceptor │
                                           │  Header: Bearer   │
                                           └────────┬────────┘
                                                    │
                                           ┌────────▼────────┐
                                           │  FastAPI         │
                                           │  decode JWT      │
                                           │  extract sub     │
                                           │  query User      │
                                           └────────┬────────┘
                                                    │
                                           ┌────────▼────────┐
                                           │  401 on          │
                                           │  expired/invalid │
                                           │  → redirect login│
                                           └─────────────────┘
```

### 6.2 RBAC Implementation

Three roles defined as `UserRole` enum:

| Role | Permissions | Used For |
|---|---|---|
| `user` | Report incidents, community posts, SOS, chat | General users |
| `moderator` | Moderate incidents and reports | Trusted community members |
| `admin` | Full access (dashboard, users, agents, settings) | Platform operators |

Role enforcement at the endpoint level:
```python
@app.get("/admin/dashboard")
async def admin_dashboard(admin: User = Depends(require_admin)):
    pass  # Only reaches here if role == 'admin'
```

### 6.3 Input Sanitization Pipeline

Every `POST/PUT/PATCH` request passes through a middleware that:

1. Reads the raw request body
2. Applies regex-based sanitization:
   - Strips `<script>` tags and content
   - Removes HTML tags entirely
   - Removes `javascript:` protocol handlers
   - Strips inline event handlers (`onclick=`, `onerror=`, etc.)
3. Replaces the request body with sanitized version
4. Normalizes whitespace

```python
def sanitize_input(text: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]*>", "", text)
    text = re.sub(r"javascript\s*:", "", text, flags=re.IGNORECASE)
    text = re.sub(r"on\w+\s*=\s*[\"'][^\"']*[\"']", "", text, flags=re.IGNORECASE)
    # ...
```

### 6.4 Rate Limiting Layers

| Layer | Scope | Limit | Response |
|---|---|---|---|
| Nginx | Per IP | 30 req/s (api), 10 req/s (auth) | 429 |
| Application | Per IP | Configurable (default 100/60s) | 429 |
| Nominatim API | Application-wide | 1 req/s by design | Internal skip |

### 6.5 Audit Logging

Admin actions are logged to `audit_logs` table:

```json
{
  "user_id": "uuid",
  "action": "moderate_incident",
  "resource_type": "incident",
  "resource_id": "uuid",
  "details": {"new_status": "verified", "previous_status": "pending"},
  "ip_address": "203.0.113.1",
  "user_agent": "Mozilla/5.0...",
  "severity": "info",
  "created_at": "2026-01-15T10:30:00Z"
}
```

### 6.6 CORS Configuration

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),  # Configurable via env
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Default allowed origins: `http://localhost:5173,http://localhost:3000`

### 6.7 Secrets Management

All secrets are managed via environment variables:
- `SECRET_KEY` — JWT signing key (minimum 64 characters)
- `POSTGRES_PASSWORD` — Database password
- `GEMINI_API_KEY` — Google AI API key
- `SUPABASE_SERVICE_KEY` — Supabase service role key

Secrets are loaded via Pydantic Settings from `.env` file, which is excluded from version control via `.gitignore`.

---

## 7. Deployment Architecture

### 7.1 Docker Multi-Container Setup

```yaml
services:
  postgres:      # PostGIS 16-3.4
  redis:         # Redis 7-alpine
  backend:       # FastAPI + Uvicorn
  celery_worker: # Celery worker (4 concurrent)
  celery_beat:   # Celery beat scheduler
  frontend:      # Nginx-served React SPA
  nginx:         # Reverse proxy with SSL
```

Dependency chain:
```
nginx → frontend → backend → postgres, redis
celery_worker → backend → postgres, redis
celery_beat → backend → postgres, redis
```

### 7.2 Horizontal Scaling Strategy

| Component | Scaling Strategy |
|---|---|
| **FastAPI Backend** | Multiple Uvicorn workers (behind Nginx) |
| **Celery Workers** | Increase `--concurrency` or add containers |
| **PostgreSQL** | Read replicas for analytics queries |
| **Redis** | Redis Cluster for high-availability |
| **Frontend** | Stateless, multiple Nginx + CDN |

### 7.3 Database Replication

For production scale:
- **Primary**: Read-write for incident ingestion and agent pipelines
- **Replicas**: Read-only for analytics queries and heatmap API
- SQLAlchemy session routing: read/write sessions to primary, read-only to replicas

### 7.4 Cache Invalidation

| Cache Type | Invalidation Strategy |
|---|---|
| Geocoding cache (locations table) | TTL: indefinite (append-only, never stale) |
| Risk scores (risk_scores table) | Regenerated every 6 hours |
| Heatmap data | Regenerated every 2 hours per district |
| React Query client cache | Stale time: 30s, GC: 5min |

### 7.5 Monitoring and Alerting

- **Sentry** (optional): Error tracking for backend exceptions
- **Structured JSON Logging**: All logs in JSON format for log aggregation
- **Health Endpoint**: `GET /health` returns status + version
- **Celery Monitoring**: Flower dashboard (optional sidecar)
- **Heartbeat**: Request ID and process time headers on every response

### 7.6 Backup Strategy

```bash
# Daily PostgreSQL backup (cron job)
pg_dump -U avana -h localhost avana_v2 | gzip > /backups/avana_$(date +%Y%m%d).sql.gz

# Retain 30 days of backups
find /backups -name "avana_*.sql.gz" -mtime +30 -delete
```

---

## 8. Performance

### 8.1 PostGIS Query Optimization

- **GiST indexes** on `geom` columns for all spatial queries
- **B-tree indexes** on `created_at`, `severity`, `district`, `status` for filtering
- **Composite queries** use index intersections
- **Geography casts** for accurate but fast bounding box pre-filtering
- **`LIMIT`** on all nearest-neighbor queries to prevent full scans
- **`DISTINCT ON`** for latest heatmap data per grid cell

### 8.2 Celery Task Deduplication

- News articles deduplicated by `source_url` (UNIQUE constraint)
- Community reports processed once (state machine: pending → processed)
- Heatmap generation uses upsert pattern
- Risk scores recalculated only for stale locations

### 8.3 Redis Caching Strategy

```
redis://host:6379/0 → General cache (not yet implemented for API responses)
redis://host:6379/1 → Celery broker (task queue)
redis://host:6379/2 → Celery result backend (task results)
```

Future caching: API response caching for expensive risk score calculations.

### 8.4 Frontend Bundle Optimization

- **Vite** tree-shaking in production builds
- **Code splitting** via React Router lazy loading
- **TailwindCSS** purge of unused classes
- **Leaflet** dynamic imports (map component only)
- **Recharts** dynamic imports (chart components only)
- **Compression**: Nginx gzip for static assets

### 8.5 Image Optimization for Maps

- Map tiles served via CDN (OpenStreetMap tile servers)
- No custom tile generation (uses standard OSM tiles)
- Marker clustering for high-density areas (planned)
- Canvas rendering for heatmap layer

---

## 9. Scaling Roadmap

### Phase 1: Karnataka (Current)
Production deployment covering all 31 districts of Karnataka. Core ML pipeline operational with 50+ news sources. Community intelligence with moderation.

### Phase 2: South India
Scale to Tamil Nadu, Kerala, Andhra Pradesh, and Telangana:
- Add regional news sources for each state (est. 200+ total sources)
- Multi-language NLP models for 4 additional languages
- Cross-state route intelligence
- Unified heatmap across 5 states
- State-specific police station and hospital databases

**Estimated Scale**: 5M incidents/year, 10M heatmap grid points, 100K active users

### Phase 3: All India
Pan-India coverage:
- State-wise risk scoring model calibration
- National incident categorization taxonomy
- Integration with national crime databases (NCRB)
- 500+ news sources across 28 states and 8 UTs
- Mobile application (React Native)
- 10+ language support

**Estimated Scale**: 50M incidents/year, 100M grid points, 1M active users

### Phase 4: Southeast Asia
International expansion:
- SAARC nation coverage (Sri Lanka, Bangladesh, Nepal, Bhutan, Maldives)
- Local emergency service integration per country
- Multilingual AI models (Hindi, Tamil, Sinhala, Bengali, Nepali, Dhivehi)
- International routing providers (Google Maps, Mapbox alternatives)
- Cross-border safety intelligence sharing

**Estimated Scale**: 500M incidents/year, 1B grid points, 10M active users
