# Avana V2 — API Reference

> Full API documentation for the Avana V2 Safety Intelligence Platform

Base URL: `http://localhost:8000/api/v1`

All dates/times are in ISO 8601 format with UTC timezone.

---

## Table of Contents

- [Authentication](#authentication)
- [Incidents](#incidents)
- [Risk Assessment](#risk-assessment)
- [Route Intelligence](#route-intelligence)
- [SOS Emergency](#sos-emergency)
- [Community](#community)
- [Analytics](#analytics)
- [AI Chat](#ai-chat)
- [Admin](#admin)
- [Safety Reports](#safety-reports)
- [Health Check](#health-check)

---

## Authentication

**Base**: `/api/v1/auth`

### POST /auth/signup

Register a new user account.

**Authentication**: None

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "securePassword123",
  "name": "Priya Sharma"
}
```

**Response** (201):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "name": "Priya Sharma",
    "role": "user",
    "is_verified": false,
    "created_at": "2026-01-15T10:30:00Z"
  }
}
```

**Errors**:
- `409` — Email already registered

**Rate Limit**: 10 req/s

**curl**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"securePassword123","name":"Priya Sharma"}'
```

---

### POST /auth/login

Authenticate with email and password.

**Authentication**: None

**Request Body**:
```json
{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Response** (200):
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "name": "Priya Sharma",
    "role": "user",
    "is_verified": false,
    "created_at": "2026-01-15T10:30:00Z"
  }
}
```

**Errors**:
- `401` — Invalid email or password

**curl**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"securePassword123"}'
```

---

### POST /auth/logout

Invalidate current session (client-side token removal required).

**Authentication**: Bearer Token

**Response** (200):
```json
{
  "message": "Logged out successfully"
}
```

**curl**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/logout \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /auth/me

Get the currently authenticated user's profile.

**Authentication**: Bearer Token

**Response** (200):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "name": "Priya Sharma",
  "role": "user",
  "is_verified": false,
  "created_at": "2026-01-15T10:30:00Z"
}
```

**curl**:
```bash
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### PUT /auth/me

Update the authenticated user's profile.

**Authentication**: Bearer Token

**Request Body**:
```json
{
  "name": "Priya S.",
  "phone": "+91-9876543210"
}
```

**Response** (200):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "name": "Priya S.",
  "role": "user",
  "is_verified": false,
  "created_at": "2026-01-15T10:30:00Z"
}
```

**curl**:
```bash
curl -X PUT http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"name":"Priya S.","phone":"+91-9876543210"}'
```

---

### GET /auth/emergency-contacts

List emergency contacts for the authenticated user.

**Authentication**: Bearer Token

**Response** (200):
```json
[
  {
    "id": "660e8400-e29b-41d4-a716-446655440001",
    "name": "Rahul Kumar",
    "phone": "+91-9876543211",
    "relationship": "Brother",
    "is_primary": true
  }
]
```

**curl**:
```bash
curl http://localhost:8000/api/v1/auth/emergency-contacts \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### POST /auth/emergency-contacts

Add an emergency contact.

**Authentication**: Bearer Token

**Request Body**:
```json
{
  "name": "Rahul Kumar",
  "phone": "+91-9876543211",
  "relationship": "Brother",
  "is_primary": true
}
```

**Response** (201):
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "name": "Rahul Kumar",
  "phone": "+91-9876543211",
  "relationship": "Brother",
  "is_primary": true
}
```

**curl**:
```bash
curl -X POST http://localhost:8000/api/v1/auth/emergency-contacts \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"name":"Rahul Kumar","phone":"+91-9876543211","relationship":"Brother","is_primary":true}'
```

---

### DELETE /auth/emergency-contacts/{id}

Delete an emergency contact.

**Authentication**: Bearer Token

**Response** (200):
```json
{
  "message": "Contact deleted successfully"
}
```

**Errors**:
- `404` — Contact not found

**curl**:
```bash
curl -X DELETE http://localhost:8000/api/v1/auth/emergency-contacts/660e8400-e29b-41d4-a716-446655440001 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

## Incidents

**Base**: `/api/v1/incidents`

### GET /incidents

List incidents with optional filters.

**Authentication**: None (public read)

**Query Parameters**:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `incident_type` | string | — | Filter by type (theft, assault, etc.) |
| `severity` | string | — | Filter by severity (low, medium, high, critical) |
| `district` | string | — | Filter by Karnataka district |
| `city` | string | — | Filter by city |
| `status` | string | — | Filter by status (pending, verified, dismissed, duplicate, spam) |
| `start_date` | ISO 8601 | — | Filter by created_at >= start_date |
| `end_date` | ISO 8601 | — | Filter by created_at <= end_date |
| `lat` | float | — | Center latitude for proximity filter |
| `lng` | float | — | Center longitude for proximity filter |
| `radius_km` | float | 5.0 | Search radius (requires lat/lng) |
| `page` | int | 1 | Page number |
| `page_size` | int | 20 | Items per page (max 100) |

**Response** (200):
```json
{
  "items": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440002",
      "incident_type": "theft",
      "severity": "medium",
      "source": "news",
      "status": "verified",
      "confidence_score": 0.85,
      "latitude": 12.9716,
      "longitude": 77.5946,
      "description": "Chain snatching reported near MG Road metro station.",
      "title": "Chain snatching on MG Road",
      "district": "Bengaluru Urban",
      "city": "Bengaluru",
      "incident_date": "2026-01-14T18:30:00Z",
      "created_at": "2026-01-14T19:00:00Z",
      "distance": 0.5
    }
  ],
  "total": 156,
  "page": 1,
  "page_size": 20
}
```

**curl**:
```bash
curl "http://localhost:8000/api/v1/incidents?district=Bengaluru%20Urban&severity=high&page=1&page_size=10"
```

---

### GET /incidents/nearby

Find incidents near a specific location.

**Authentication**: None (public)

**Query Parameters**:

| Parameter | Type | Required | Description |
|---|---|---|---|
| `lat` | float | Yes | Latitude |
| `lng` | float | Yes | Longitude |
| `radius` | float | No | Search radius in km (default: 5.0) |
| `limit` | int | No | Max results (default: 50, max: 200) |

**Response** (200):
```json
[
  {
    "id": "770e8400-e29b-41d4-a716-446655440002",
    "incident_type": "theft",
    "severity": "medium",
    "source": "news",
    "status": "verified",
    "confidence_score": 0.85,
    "latitude": 12.9716,
    "longitude": 77.5946,
    "description": "Chain snatching reported near MG Road metro station.",
    "title": "Chain snatching on MG Road",
    "district": "Bengaluru Urban",
    "city": "Bengaluru",
    "incident_date": "2026-01-14T18:30:00Z",
    "created_at": "2026-01-14T19:00:00Z",
    "distance": 0.42
  }
]
```

**curl**:
```bash
curl "http://localhost:8000/api/v1/incidents/nearby?lat=12.9716&lng=77.5946&radius=2&limit=10"
```

---

### GET /incidents/stats

Get incident statistics with optional filters.

**Authentication**: None (public)

**Query Parameters**:

| Parameter | Type | Description |
|---|---|---|
| `district` | string | Filter by district |
| `start_date` | ISO 8601 | Start of date range |
| `end_date` | ISO 8601 | End of date range |

**Response** (200):
```json
{
  "total_incidents": 1248,
  "by_district": [
    {"district": "Bengaluru Urban", "count": 456},
    {"district": "Mysuru", "count": 123},
    {"district": "Dakshina Kannada", "count": 89}
  ],
  "by_type": [
    {"incident_type": "theft", "count": 412},
    {"incident_type": "assault", "count": 234},
    {"incident_type": "harassment", "count": 189}
  ]
}
```

**curl**:
```bash
curl "http://localhost:8000/api/v1/incidents/stats?district=Bengaluru%20Urban"
```

---

### GET /incidents/{id}

Get a single incident by ID.

**Authentication**: None (public)

**Response** (200):
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440002",
  "incident_type": "theft",
  "severity": "medium",
  "source": "news",
  "status": "verified",
  "confidence_score": 0.85,
  "latitude": 12.9716,
  "longitude": 77.5946,
  "description": "Chain snatching reported near MG Road metro station.",
  "title": "Chain snatching on MG Road",
  "district": "Bengaluru Urban",
  "city": "Bengaluru",
  "incident_date": "2026-01-14T18:30:00Z",
  "created_at": "2026-01-14T19:00:00Z"
}
```

**Errors**:
- `404` — Incident not found

**curl**:
```bash
curl http://localhost:8000/api/v1/incidents/770e8400-e29b-41d4-a716-446655440002
```

---

### POST /incidents

Create a new user-reported incident.

**Authentication**: Bearer Token (optional — anonymous reports allowed)

**Request Body**:
```json
{
  "incident_type": "harassment",
  "severity": "high",
  "latitude": 12.9716,
  "longitude": 77.5946,
  "description": "Harassment witnessed near bus stop at 8 PM",
  "title": "Harassment at bus stop",
  "address": "MG Road Bus Stop, Bengaluru",
  "district": "Bengaluru Urban",
  "city": "Bengaluru"
}
```

**Response** (201):
```json
{
  "id": "880e8400-e29b-41d4-a716-446655440003",
  "incident_type": "harassment",
  "severity": "high",
  "source": "user_report",
  "status": "pending",
  "confidence_score": 0.0,
  "latitude": 12.9716,
  "longitude": 77.5946,
  "description": "Harassment witnessed near bus stop at 8 PM",
  "title": "Harassment at bus stop",
  "district": "Bengaluru Urban",
  "city": "Bengaluru",
  "incident_date": null,
  "created_at": "2026-01-15T10:30:00Z"
}
```

**curl**:
```bash
curl -X POST http://localhost:8000/api/v1/incidents \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"incident_type":"harassment","severity":"high","latitude":12.9716,"longitude":77.5946,"description":"Harassment witnessed near bus stop at 8 PM","title":"Harassment at bus stop","district":"Bengaluru Urban","city":"Bengaluru"}'
```

---

## Risk Assessment

**Base**: `/api/v1/risk`

### POST /risk/score

Calculate a safety risk score for a location.

**Authentication**: Bearer Token

**Request Body**:
```json
{
  "latitude": 12.9716,
  "longitude": 77.5946
}
```

**Response** (200):
```json
{
  "score": 35.72,
  "category": "High Risk",
  "factors": {
    "historical_risk": 45.2,
    "recent_reports_impact": 16.0,
    "night_factor": 15.0,
    "severity_penalty": 22.5,
    "police_presence_bonus": 3.33,
    "hospital_access_bonus": 1.67,
    "population_density_factor": 0.0,
    "final_score": 35.72
  },
  "recommendations": []
}
```

**Risk Categories**:

| Score Range | Category |
|---|---|
| 70-100 | Safe |
| 40-70 | Moderate |
| 20-40 | High Risk |
| 0-20 | Critical |

**curl**:
```bash
curl -X POST http://localhost:8000/api/v1/risk/score \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"latitude":12.9716,"longitude":77.5946}'
```

---

### POST /risk/heatmap

Get heatmap data for a geographic bounding box.

**Authentication**: None (public)

**Request Body**:
```json
{
  "sw_lat": 12.8,
  "sw_lng": 77.4,
  "ne_lat": 13.2,
  "ne_lng": 77.8,
  "zoom": 12
}
```

Zoom level mapping:
- <= 8: district-level grid (~2km)
- 9-13: city-level grid (~500m)
- > 13: ward-level grid (~100m)

**Response** (200):
```json
{
  "points": [
    {
      "latitude": 12.87,
      "longitude": 77.59,
      "weight": 0.42,
      "risk_category": "Moderate"
    },
    {
      "latitude": 12.88,
      "longitude": 77.60,
      "weight": 0.75,
      "risk_category": "High Risk"
    }
  ],
  "generated_at": "2026-01-15T10:30:00.000000",
  "district_summaries": [
    {
      "district": "Bengaluru Urban",
      "avg_score": 45.6,
      "total_incidents": 456,
      "trend": "worsening"
    }
  ]
}
```

**Trend Indicators**: `improving` (avg_score < 30), `stable` (30-60), `worsening` (> 60)

**curl**:
```bash
curl -X POST http://localhost:8000/api/v1/risk/heatmap \
  -H "Content-Type: application/json" \
  -d '{"sw_lat":12.8,"sw_lng":77.4,"ne_lat":13.2,"ne_lng":77.8,"zoom":12}'
```

---

### GET /risk/district/{district}

Get risk summary for a specific Karnataka district.

**Authentication**: None (public)

**Response** (200):
```json
{
  "district": "Bengaluru Urban",
  "risk_score": 45.6,
  "risk_category": "Moderate",
  "total_incidents": 456,
  "high_risk_incidents": 89,
  "medium_risk_incidents": 201,
  "low_risk_incidents": 166,
  "generated_at": "2026-01-15T10:30:00.000000"
}
```

**Errors**:
- `404` — No data found for district

**curl**:
```bash
curl http://localhost:8000/api/v1/risk/district/Bengaluru%20Urban
```

---

## Route Intelligence

**Base**: `/api/v1/route`

### POST /route/safe

Calculate the safest route between two points.

**Authentication**: Bearer Token

**Request Body**:
```json
{
  "source_lat": 12.9716,
  "source_lng": 77.5946,
  "dest_lat": 12.2958,
  "dest_lng": 76.6394,
  "profile": "driving"
}
```

**Response** (200):
```json
{
  "source": [
    12.9716,
    77.5946
  ],
  "destination": [
    12.2958,
    76.6394
  ],
  "safest": {
    "type": "safest",
    "duration_minutes": 185.5,
    "distance_km": 152.3,
    "safety_score": 72.5,
    "segments": [
      {
        "start_lat": 12.9716,
        "start_lng": 77.5946,
        "end_lat": 12.92,
        "end_lng": 77.58,
        "safety_score": 68.2,
        "risk_category": "Moderate",
        "distance_m": 500.0
      }
    ],
    "geometry": []
  },
  "fastest": {
    "type": "fastest",
    "duration_minutes": 145.2,
    "distance_km": 148.7,
    "safety_score": 58.3,
    "segments": [],
    "geometry": []
  },
  "balanced": {
    "type": "balanced",
    "duration_minutes": 162.1,
    "distance_km": 150.1,
    "safety_score": 66.8,
    "segments": [],
    "geometry": []
  }
}
```

**Balanced Score**: `safety * 0.6 + (1 - duration/7200) * 0.4`

**curl**:
```bash
curl -X POST http://localhost:8000/api/v1/route/safe \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"source_lat":12.9716,"source_lng":77.5946,"dest_lat":12.2958,"dest_lng":76.6394,"profile":"driving"}'
```

---

### GET /route/health

Check the route intelligence service health.

**Authentication**: None (public)

**Response** (200):
```json
{
  "status": "healthy",
  "service": "Route Intelligence",
  "provider": "OSRM"
}
```

**curl**:
```bash
curl http://localhost:8000/api/v1/route/health
```

---

## SOS Emergency

**Base**: `/api/v1/sos`

### POST /sos

Trigger an SOS emergency alert. Notifies all emergency contacts.

**Authentication**: Bearer Token (required)

**Request Body**:
```json
{
  "latitude": 12.9716,
  "longitude": 77.5946,
  "message": "I feel unsafe. Someone is following me.",
  "emergency_type": "safety_threat"
}
```

**Response** (201):
```json
{
  "id": "990e8400-e29b-41d4-a716-446655440004",
  "status": "triggered",
  "message": "I feel unsafe. Someone is following me.",
  "created_at": "2026-01-15T10:30:00Z",
  "notified_contacts": [
    {"name": "Rahul Kumar", "phone": "+91-9876543211", "relationship": "Brother"},
    {"name": "Neha Sharma", "phone": "+91-9876543212", "relationship": "Sister"}
  ]
}
```

**SOS Statuses**: `triggered`, `acknowledged`, `resolved`, `false_alarm`

**curl**:
```bash
curl -X POST http://localhost:8000/api/v1/sos \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"latitude":12.9716,"longitude":77.5946,"message":"I feel unsafe. Someone is following me.","emergency_type":"safety_threat"}'
```

---

### GET /sos/history

Get the authenticated user's SOS event history.

**Authentication**: Bearer Token

**Response** (200):
```json
[
  {
    "id": "990e8400-e29b-41d4-a716-446655440004",
    "status": "resolved",
    "message": "I feel unsafe. Someone is following me.",
    "created_at": "2026-01-15T10:30:00Z",
    "notified_contacts": [
      {"name": "Rahul Kumar", "phone": "+91-9876543211", "relationship": "Brother"}
    ]
  }
]
```

**curl**:
```bash
curl http://localhost:8000/api/v1/sos/history \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /sos/{id}

Get details of a specific SOS event.

**Authentication**: Bearer Token

**Errors**:
- `404` — SOS event not found (or not owned by user)

**curl**:
```bash
curl http://localhost:8000/api/v1/sos/990e8400-e29b-41d4-a716-446655440004 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

## Community

**Base**: `/api/v1/community`

### GET /community/posts

List community discussion posts.

**Authentication**: Bearer Token

**Query Parameters**:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number |
| `page_size` | int | 20 | Items per page (max 100) |
| `post_type` | string | — | Filter by post type |

**Response** (200):
```json
[
  {
    "id": "aa0e8400-e29b-41d4-a716-446655440005",
    "content": "Noticed suspicious activity near the park after 9 PM. Stay safe everyone!",
    "latitude": 12.9716,
    "longitude": 77.5946,
    "location_name": "Cubbon Park, Bengaluru",
    "post_type": "safety_alert",
    "upvotes": 24,
    "is_verified": true,
    "user": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Priya Sharma",
      "avatar_url": null
    },
    "comment_count": 5,
    "created_at": "2026-01-15T10:30:00Z"
  }
]
```

**curl**:
```bash
curl "http://localhost:8000/api/v1/community/posts?page=1&page_size=10" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### POST /community/posts

Create a new community post.

**Authentication**: Bearer Token (required)

**Request Body**:
```json
{
  "content": "Noticed suspicious activity near the park after 9 PM.",
  "latitude": 12.9716,
  "longitude": 77.5946,
  "location_name": "Cubbon Park, Bengaluru",
  "post_type": "safety_alert"
}
```

**Response** (201):
```json
{
  "id": "aa0e8400-e29b-41d4-a716-446655440005",
  "content": "Noticed suspicious activity near the park after 9 PM.",
  "latitude": 12.9716,
  "longitude": 77.5946,
  "location_name": "Cubbon Park, Bengaluru",
  "post_type": "safety_alert",
  "upvotes": 0,
  "is_verified": false,
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Priya Sharma",
    "avatar_url": null
  },
  "comment_count": 0,
  "created_at": "2026-01-15T10:30:00Z"
}
```

**curl**:
```bash
curl -X POST http://localhost:8000/api/v1/community/posts \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"content":"Noticed suspicious activity near the park after 9 PM.","latitude":12.9716,"longitude":77.5946,"location_name":"Cubbon Park, Bengaluru","post_type":"safety_alert"}'
```

---

### GET /community/posts/{id}

Get a single community post with comments.

**Authentication**: Bearer Token

**Response** (200): Same schema as list endpoint.

**curl**:
```bash
curl http://localhost:8000/api/v1/community/posts/aa0e8400-e29b-41d4-a716-446655440005 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### POST /community/posts/{id}/vote

Upvote or downvote a community post.

**Authentication**: Bearer Token

**Query Parameters**:

| Parameter | Type | Required | Description |
|---|---|---|---|
| `vote_type` | string | Yes | "up" or "down" |

**Response** (200):
```json
{
  "id": "aa0e8400-e29b-41d4-a716-446655440005",
  "upvotes": 25,
  "downvotes": 0
}
```

**Errors**:
- `400` — Invalid vote type
- `404` — Post not found

**curl**:
```bash
curl -X POST "http://localhost:8000/api/v1/community/posts/aa0e8400-e29b-41d4-a716-446655440005/vote?vote_type=up" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /community/posts/{id}/comments

Get comments for a community post (hierarchical, parent comments with nested replies).

**Authentication**: Bearer Token

**Response** (200):
```json
[
  {
    "id": "bb0e8400-e29b-41d4-a716-446655440006",
    "content": "Thank you for alerting us! We'll be careful.",
    "upvotes": 8,
    "user": {
      "id": "cc0e8400-e29b-41d4-a716-446655440007",
      "name": "Ananya Reddy",
      "avatar_url": null
    },
    "created_at": "2026-01-15T11:00:00Z",
    "replies": [
      {
        "id": "dd0e8400-e29b-41d4-a716-446655440008",
        "content": "Yes, please stay safe everyone.",
        "upvotes": 3,
        "user": {
          "id": "550e8400-e29b-41d4-a716-446655440000",
          "name": "Priya Sharma",
          "avatar_url": null
        },
        "created_at": "2026-01-15T11:15:00Z",
        "replies": null
      }
    ]
  }
]
```

**curl**:
```bash
curl http://localhost:8000/api/v1/community/posts/aa0e8400-e29b-41d4-a716-446655440005/comments \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### POST /community/posts/{id}/comments

Add a comment to a community post (with optional nested reply via `parent_id`).

**Authentication**: Bearer Token (required)

**Request Body**:
```json
{
  "content": "Thank you for alerting us!",
  "parent_id": null
}
```

**Response** (201):
```json
{
  "id": "bb0e8400-e29b-41d4-a716-446655440006",
  "content": "Thank you for alerting us!",
  "upvotes": 0,
  "user": {
    "id": "cc0e8400-e29b-41d4-a716-446655440007",
    "name": "Ananya Reddy",
    "avatar_url": null
  },
  "created_at": "2026-01-15T11:00:00Z",
  "replies": null
}
```

**curl**:
```bash
curl -X POST http://localhost:8000/api/v1/community/posts/aa0e8400-e29b-41d4-a716-446655440005/comments \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"content":"Thank you for alerting us!","parent_id":null}'
```

---

## Analytics

**Base**: `/api/v1/analytics`

All analytics endpoints require **Admin** role.

### GET /analytics/dashboard

Get comprehensive dashboard statistics.

**Authentication**: Bearer Token (Admin)

**Response** (200):
```json
{
  "total_incidents": 1248,
  "active_users": 892,
  "sos_events": 45,
  "verified_reports": 876,
  "incidents_by_district": [
    {
      "district": "Bengaluru Urban",
      "total": 456,
      "high_risk": 89,
      "medium_risk": 201,
      "low_risk": 166,
      "avg_score": 45.6
    }
  ],
  "incidents_by_type": [
    {
      "incident_type": "theft",
      "count": 412,
      "percentage": 33.0
    }
  ],
  "risk_trend": [
    {"date": "2026-01-15", "value": 45.2}
  ],
  "incidents_trend": [
    {"date": "2026-01-15", "value": 12.0}
  ],
  "recent_alerts": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440002",
      "type": "theft",
      "severity": "high",
      "district": "Bengaluru Urban",
      "time": "2026-01-15T10:30:00Z",
      "status": "verified"
    }
  ]
}
```

**curl**:
```bash
curl http://localhost:8000/api/v1/analytics/dashboard \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /analytics/districts

Get district-level analytics.

**Authentication**: Bearer Token (Admin)

**Response** (200):
```json
[
  {
    "district": "Bengaluru Urban",
    "total_incidents": 456,
    "high_risk": 89,
    "medium_risk": 201,
    "low_risk": 166,
    "first_incident": "2025-06-01T10:00:00",
    "last_incident": "2026-01-15T10:30:00"
  }
]
```

**curl**:
```bash
curl http://localhost:8000/api/v1/analytics/districts \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /analytics/trends

Get incident trend data over a time period.

**Authentication**: Bearer Token (Admin)

**Query Parameters**:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `days` | int | 30 | Number of days to analyze (max 365) |

**Response** (200):
```json
{
  "period_days": 30,
  "data": [
    {
      "date": "2026-01-15",
      "total": 12,
      "high_risk": 4,
      "news_sourced": 8,
      "user_reported": 3
    }
  ]
}
```

**curl**:
```bash
curl "http://localhost:8000/api/v1/analytics/trends?days=30" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /analytics/reports

Get safety report analytics over a time period.

**Authentication**: Bearer Token (Admin)

**Query Parameters**:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `days` | int | 30 | Number of days to analyze (max 365) |

**Response** (200):
```json
{
  "period_days": 30,
  "data": [
    {
      "date": "2026-01-15",
      "total": 15,
      "approved": 10,
      "rejected": 3,
      "pending": 2
    }
  ]
}
```

**curl**:
```bash
curl "http://localhost:8000/api/v1/analytics/reports?days=30" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

## AI Chat

**Base**: `/api/v1/chat`

### POST /chat/message

Send a message to the AI safety assistant.

**Authentication**: Bearer Token

**Request Body**:
```json
{
  "message": "How safe is MG Road area at night?",
  "history": [
    {"role": "user", "content": "I am near Cubbon Park"},
    {"role": "assistant", "content": "Cubbon Park is generally safe during the day."}
  ],
  "location": {
    "latitude": 12.9716,
    "longitude": 77.5946
  }
}
```

**Response** (200):
```json
{
  "response": "MG Road has moderate safety at night (score: 48). There have been 3 reported incidents within 1km in the past month. Stay on well-lit main roads and use the metro for safer travel. Nearest police station is MG Road Police Station, 500m away.",
  "recommendations": null,
  "risk_context": {
    "latitude": 12.9716,
    "longitude": 77.5946
  }
}
```

**Errors**:
- `501` — AI chat service not configured (missing `GEMINI_API_KEY`)
- `500` — AI chat failed

**curl**:
```bash
curl -X POST http://localhost:8000/api/v1/chat/message \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"message":"How safe is MG Road area at night?","history":[],"location":{"latitude":12.9716,"longitude":77.5946}}'
```

---

### GET /chat/test

Test the AI service availability.

**Authentication**: Bearer Token

**Response** (200):
```json
{
  "status": "ok",
  "response": "Avana AI is operational",
  "model": "gemini"
}
```

Or when not configured:
```json
{
  "status": "unavailable",
  "detail": "Gemini service not configured"
}
```

**curl**:
```bash
curl http://localhost:8000/api/v1/chat/test \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

## Admin

**Base**: `/api/v1/admin`

All admin endpoints require **Admin** role.

### GET /admin/dashboard

Comprehensive admin dashboard statistics.

**Authentication**: Bearer Token (Admin)

**Response** (200): Same schema as `GET /analytics/dashboard`.

**curl**:
```bash
curl http://localhost:8000/api/v1/admin/dashboard \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /admin/incidents

List all incidents with moderation filters.

**Authentication**: Bearer Token (Admin)

**Query Parameters**:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `status` | string | — | Filter by status |
| `page` | int | 1 | Page number |
| `page_size` | int | 20 | Items per page (max 100) |

**Response** (200):
```json
{
  "items": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440002",
      "incident_type": "theft",
      "severity": "medium",
      "source": "news",
      "status": "pending",
      "latitude": 12.9716,
      "longitude": 77.5946,
      "description": "Chain snatching reported near MG Road metro station.",
      "district": "Bengaluru Urban",
      "city": "Bengaluru",
      "confidence_score": 0.85,
      "created_at": "2026-01-14T19:00:00"
    }
  ],
  "total": 156,
  "page": 1,
  "page_size": 20
}
```

**curl**:
```bash
curl "http://localhost:8000/api/v1/admin/incidents?status=pending" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### PUT /admin/incidents/{id}/moderate

Moderate an incident — change its status.

**Authentication**: Bearer Token (Admin)

**Request Body**:
```json
{
  "incident_id": "770e8400-e29b-41d4-a716-446655440002",
  "status": "verified",
  "moderation_notes": "Verified against multiple news sources"
}
```

**Valid Statuses**: `pending`, `verified`, `dismissed`, `duplicate`, `spam`

**Response** (200):
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440002",
  "status": "verified",
  "moderated_by": "550e8400-e29b-41d4-a716-446655440009",
  "moderation_notes": "Verified against multiple news sources"
}
```

**Errors**:
- `400` — Invalid status value
- `404` — Incident not found

**curl**:
```bash
curl -X PUT http://localhost:8000/api/v1/admin/incidents/770e8400-e29b-41d4-a716-446655440002/moderate \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"incident_id":"770e8400-e29b-41d4-a716-446655440002","status":"verified","moderation_notes":"Verified against multiple news sources"}'
```

---

### GET /admin/users

List all users with pagination.

**Authentication**: Bearer Token (Admin)

**Query Parameters**:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number |
| `page_size` | int | 20 | Items per page (max 100) |

**Response** (200):
```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "email": "user@example.com",
      "name": "Priya Sharma",
      "role": "user",
      "is_active": true,
      "is_verified": false,
      "total_reports": 3,
      "created_at": "2026-01-15T10:30:00Z"
    }
  ],
  "total": 50,
  "page": 1,
  "page_size": 20
}
```

**curl**:
```bash
curl "http://localhost:8000/api/v1/admin/users?page=1&page_size=20" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### PUT /admin/users/{id}/role

Change a user's role.

**Authentication**: Bearer Token (Admin)

**Query Parameters**:

| Parameter | Type | Required | Description |
|---|---|---|---|
| `role` | string | Yes | New role: `user`, `admin`, or `moderator` |

**Response** (200):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "role": "moderator"
}
```

**Errors**:
- `400` — Invalid role value
- `404` — User not found

**curl**:
```bash
curl -X PUT "http://localhost:8000/api/v1/admin/users/550e8400-e29b-41d4-a716-446655440000/role?role=moderator" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### PUT /admin/users/{id}/status

Activate or deactivate a user.

**Authentication**: Bearer Token (Admin)

**Query Parameters**:

| Parameter | Type | Required | Description |
|---|---|---|---|
| `is_active` | bool | Yes | Set user active (`true`) or inactive (`false`) |

**Response** (200):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "is_active": false
}
```

**Errors**:
- `404` — User not found

**curl**:
```bash
curl -X PUT "http://localhost:8000/api/v1/admin/users/550e8400-e29b-41d4-a716-446655440000/status?is_active=false" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /admin/agents/status

Get the status of all AI agents.

**Authentication**: Bearer Token (Admin)

**Response** (200):
```json
{
  "agents": [
    {"name": "news_intelligence", "status": "idle", "schedule_minutes": 360},
    {"name": "community_intelligence", "status": "idle", "schedule_minutes": 5},
    {"name": "risk_scoring", "status": "available", "schedule_minutes": null},
    {"name": "heatmap", "status": "idle", "schedule_minutes": 360},
    {"name": "route_intelligence", "status": "available", "schedule_minutes": null},
    {"name": "safety_recommendation", "status": "available", "schedule_minutes": null}
  ],
  "pipeline": "operational"
}
```

**curl**:
```bash
curl http://localhost:8000/api/v1/admin/agents/status \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### POST /admin/agents/run/{agent_name}

Trigger an agent pipeline run manually.

**Authentication**: Bearer Token (Admin)

**Valid Agent Names**: `news`, `community`, `heatmap`

**Response** (200):
```json
{
  "agent": "news",
  "status": "triggered",
  "result": {
    "pipeline": "news",
    "status": "completed",
    "incidents_saved": 12,
    "errors": [],
    "duration_seconds": 45.2
  }
}
```

**Errors**:
- `400` — Unknown agent name
- `500` — Agent run failed

**curl**:
```bash
curl -X POST http://localhost:8000/api/v1/admin/agents/run/news \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

## Safety Reports

**Base**: `/api/v1/reports`

### POST /reports

Submit a new safety report.

**Authentication**: Bearer Token (required)

**Query Parameters**:

| Parameter | Type | Required | Description |
|---|---|---|---|
| `incident_type` | string | Yes | Type of incident |
| `severity` | string | Yes | Severity level |
| `latitude` | float | Yes | Latitude |
| `longitude` | float | Yes | Longitude |
| `description` | string | No | Incident description |
| `address` | string | No | Address text |
| `district` | string | No | Karnataka district |
| `city` | string | No | City name |
| `is_anonymous` | bool | No | Anonymous submission (default: false) |

**Response** (201):
```json
{
  "id": "ee0e8400-e29b-41d4-a716-446655440010",
  "incident_type": "harassment",
  "severity": "high",
  "status": "pending",
  "latitude": 12.9716,
  "longitude": 77.5946,
  "description": "Harassment incident near bus stop",
  "district": "Bengaluru Urban",
  "city": "Bengaluru",
  "is_anonymous": false,
  "created_at": "2026-01-15T10:30:00"
}
```

**curl**:
```bash
curl -X POST "http://localhost:8000/api/v1/reports?incident_type=harassment&severity=high&latitude=12.9716&longitude=77.5946&description=Harassment+incident+near+bus+stop&district=Bengaluru+Urban&city=Bengaluru" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /reports

List the authenticated user's safety reports.

**Authentication**: Bearer Token

**Query Parameters**:

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number |
| `page_size` | int | 20 | Items per page (max 100) |

**Response** (200):
```json
{
  "items": [
    {
      "id": "ee0e8400-e29b-41d4-a716-446655440010",
      "incident_type": "harassment",
      "severity": "high",
      "status": "pending",
      "latitude": 12.9716,
      "longitude": 77.5946,
      "description": "Harassment incident near bus stop",
      "district": "Bengaluru Urban",
      "city": "Bengaluru",
      "is_anonymous": false,
      "is_verified": false,
      "created_at": "2026-01-15T10:30:00"
    }
  ],
  "total": 5,
  "page": 1,
  "page_size": 20
}
```

**curl**:
```bash
curl "http://localhost:8000/api/v1/reports?page=1" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /reports/{id}

Get a specific safety report detail.

**Authentication**: Bearer Token

**Response** (200):
```json
{
  "id": "ee0e8400-e29b-41d4-a716-446655440010",
  "incident_type": "harassment",
  "severity": "high",
  "status": "pending",
  "latitude": 12.9716,
  "longitude": 77.5946,
  "description": "Harassment incident near bus stop",
  "address": "MG Road Bus Stop, Bengaluru",
  "district": "Bengaluru Urban",
  "city": "Bengaluru",
  "is_anonymous": false,
  "is_verified": false,
  "confidence_score": 0.0,
  "moderation_notes": null,
  "created_at": "2026-01-15T10:30:00",
  "updated_at": "2026-01-15T10:30:00"
}
```

**Errors**:
- `404` — Report not found or not owned by user

**curl**:
```bash
curl http://localhost:8000/api/v1/reports/ee0e8400-e29b-41d4-a716-446655440010 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

## Health Check

### GET /health

Check if the service is running.

**Authentication**: None

**Response** (200):
```json
{
  "status": "healthy",
  "version": "2.0.0",
  "timestamp": "2026-01-15T10:30:00Z"
}
```

**curl**:
```bash
curl http://localhost:8000/health
```

---

### GET /

Get service information.

**Authentication**: None

**Response** (200):
```json
{
  "service": "Avana V2 - Karnataka Safety Intelligence",
  "version": "2.0.0",
  "status": "running",
  "docs": "/api/docs",
  "api": "/api/v1"
}
```

**curl**:
```bash
curl http://localhost:8000/
```

---

## Standard Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid incident type: unknown_type"
}
```

### 401 Unauthorized
```json
{
  "detail": "Not authenticated"
}
```

### 403 Forbidden
```json
{
  "detail": "Admin access required"
}
```

### 404 Not Found
```json
{
  "detail": "Incident not found"
}

### 409 Conflict
```json
{
  "detail": "Email already registered"
}
```

### 429 Rate Limit
```json
{
  "detail": "Rate limit exceeded. Try again later."
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error",
  "request_id": "a1b2c3d4"
}
```

## Pagination

All list endpoints follow the same pagination convention:

**Request Parameters**: `page` (default: 1), `page_size` (default: 20, max: 100)

**Response Format**:
```json
{
  "items": [...],
  "total": 156,
  "page": 1,
  "page_size": 20
}
```

---

> **Note**: The full interactive API documentation with request/response examples, schemas, and the ability to test endpoints directly is available at `/api/docs` when the backend is running.
