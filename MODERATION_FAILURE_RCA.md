# MODERATION FAILURE — ROOT CAUSE ANALYSIS

---

## ROOT CAUSE

**Frontend sends lowercase action names (`'verify'`, `'dismiss'`, `'resolve'`) but backend expects UPPERCASE enum values (`'VERIFIED'`, `'DISMISSED'`). The `'resolve'` action has no backend enum member at all.**

---

## Complete Request Trace

### Step 1: Button Click

**FILE**: `frontend/src/screens/admin/AdminIncidents.tsx`
**LINE**: 268
```typescript
onClick={() => handleModerate(incident.id, 'verify')}
```

Three actions are sent:

| Button | Line | Action Sent |
|--------|------|-------------|
| Verify | 268 | `'verify'` |
| Resolve | 276 | `'resolve'` |
| Dismiss | 284 | `'dismiss'` |

### Step 2: handleModerate

**FILE**: `frontend/src/screens/admin/AdminIncidents.tsx`
**LINE**: 39–50
```typescript
const handleModerate = async (incidentId: string, action: 'verify' | 'dismiss' | 'resolve') => {
    ...
    await adminApi.moderateIncident(incidentId, action)  // passes action directly
    ...
}
```

### Step 3: API Call

**FILE**: `frontend/src/services/api.ts`
**LINE**: 702–708
```typescript
moderateIncident: async (incidentId: string, action: string, notes?: string): Promise<Incident> => {
    const { data } = await api.put(`/admin/incidents/${incidentId}/moderate`, {
        incident_id: incidentId,
        status: action,            // <-- sends lowercase: 'verify', 'dismiss', 'resolve'
        moderation_notes: notes,
    })
```

### Step 4: HTTP Request

```
PUT /admin/incidents/{uuid}/moderate
Body: { "incident_id": "...", "status": "verify", "moderation_notes": null }
```

### Step 5: Backend Router

**FILE**: `backend/app/api/v1/admin.py`
**LINE**: 252
```python
@router.put("/incidents/{id}/moderate")
```

**Router prefix** (line 27): `prefix="/admin"`
**Full URL**: `/admin/incidents/{id}/moderate` ✅ — matches frontend URL at `api.ts:704`

### Step 6: ModerateAction Schema

**FILE**: `backend/app/schemas/admin.py`
**LINE**: 8–11
```python
class ModerateAction(BaseModel):
    incident_id: UUID
    status: str              # <-- receives the lowercase string
    moderation_notes: Optional[str] = None
```

### Step 7: Backend Handler

**FILE**: `backend/app/api/v1/admin.py`
**LINE**: 253–268
```python
async def moderate_incident(id, request, body, db, admin):
    result = await db.execute(select(Incident).where(Incident.id == id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    try:
        incident.status = IncidentStatus(body.status)  # <-- FAILS HERE
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {body.status}")
```

### Step 8: IncidentStatus Enum

**FILE**: `backend/app/models/incident.py`
**LINE**: 48–54
```python
class IncidentStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    DISMISSED = "DISMISSED"
    DUPLICATE = "DUPLICATE"
    SPAM = "SPAM"
    # ⚠️ NOTE: NO 'RESOLVED' member exists
```

When `IncidentStatus("verify")` is called, Python looks for a member whose **value** equals `"verify"`. No member has that value → `ValueError`.

### Step 9: Error Returns to Frontend

Backend returns HTTP 400 with `{"detail": "Invalid status: verify"}`.

Frontend catch block:
```typescript
} catch {
    addToast({ title: 'Failed to moderate incident', variant: 'destructive' })
}
```

User sees: ❌ "Failed to moderate incident"

### Step 10: Database State

No database change occurs. The `get_db()` dependency (in `database.py:46–49`) catches the exception from the 400 error and calls `await session.rollback()`. The incident stays PENDING.

---

## Why It Fails — Summary

| Action | Frontend Sends | Backend Expects | Enum Member Exists? | Result |
|--------|---------------|-----------------|---------------------|--------|
| Verify | `'verify'` | `'VERIFIED'` | ✅ `VERIFIED = "VERIFIED"` | ❌ `ValueError` — case mismatch |
| Dismiss | `'dismiss'` | `'DISMISSED'` | ✅ `DISMISSED = "DISMISSED"` | ❌ `ValueError` — case mismatch |
| Resolve | `'resolve'` | no expectation | ❌ No `RESOLVED` in enum | ❌ `ValueError` — no member |

---

## Required Fixes

### Fix 1: Map frontend action names to backend enum values in `api.ts`

**FILE**: `frontend/src/services/api.ts`
**LINE**: 702–708

```typescript
moderateIncident: async (incidentId: string, action: string, notes?: string): Promise<Incident> => {
    const statusMap: Record<string, string> = {
        verify: 'VERIFIED',
        dismiss: 'DISMISSED',
        resolve: 'RESOLVED',
    }
    const { data } = await api.put(`/admin/incidents/${incidentId}/moderate`, {
        incident_id: incidentId,
        status: statusMap[action] || action,   // <-- map to UPPERCASE
        moderation_notes: notes,
    })
```

### Fix 2: Add `RESOLVED` to backend `IncidentStatus` enum

**FILE**: `backend/app/models/incident.py`
**LINE**: 48–54

```python
class IncidentStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    DISMISSED = "DISMISSED"
    DUPLICATE = "DUPLICATE"
    SPAM = "SPAM"
    RESOLVED = "RESOLVED"       # <-- ADD THIS
```

### Fix 3: Add `RESOLVED` to the PostgreSQL `incidentstatus` enum

**FILE**: `backend/alembic/versions/012_add_resolved_to_incidentstatus_enum.py` (new file)

```python
def upgrade() -> None:
    op.execute("ALTER TYPE incidentstatus ADD VALUE IF NOT EXISTS 'RESOLVED'")

def downgrade() -> None:
    pass
```

---

## Debugging Additions

Add these log lines to the moderate endpoint to make future failures visible immediately:

**FILE**: `backend/app/api/v1/admin.py`
**LINE**: after 259

```python
logger.info(
    f"[MODERATE] admin={admin.email} incident={id} "
    f"requested_status={body.status} current_status={incident.status.value}"
)
```

**LINE**: after 266 (success path)

```python
logger.info(
    f"[MODERATE] SUCCESS: incident={id} "
    f"from={incident.status.value} to={body.status} "
    f"by={admin.email}"
)
```

---

## Verification

After applying the fixes:

1. Click Verify → sends `status: "VERIFIED"` → `IncidentStatus("VERIFIED")` → ✅ matches enum member
2. Click Dismiss → sends `status: "DISMISSED"` → `IncidentStatus("DISMISSED")` → ✅ matches enum member
3. Click Resolve → sends `status: "RESOLVED"` → `IncidentStatus("RESOLVED")` → ✅ matches enum member (after adding RESOLVED)
4. Status changes persist to database via `get_db()` commit on successful return
5. `refreshIncidents()` fetches updated list showing the new status
