# Avana V2 — Admin User Guide

*Non-technical operational guide for platform administrators.*

---

## Admin Workflow Summary

```
Dashboard → Review AI Config → Run Pipeline → Approve Incidents → Monitor Health
    │            │                  │               │
    │            │          News feeds fetched,     │
    │            │          AI extracts incidents,  │
    │            │          locations geocoded,     │
    │            │          risk scores computed    │
    │            │                                  │
    │            │        ┌─────────────────────────┘
    │            │        │  Only VERIFIED incidents
    │            │        │  appear on user-facing maps
    │            ▼        ▼
    │      Unverified incidents sit
    │      PENDING in the database
    ▼
   Check AI status, run health,
   user management, export data
```

---

## 1. After Logging In

You land on the **Admin Dashboard** (`/admin/dashboard`). You'll see:

- **System Health Bar** at the top — green/yellow/red dots for Backend, Route Engine, and AI Service. If any are red, investigate before running pipelines.
- **Data Freshness indicator** — shows when intelligence was last updated. If stale (>48 hours), run a pipeline.
- **Stat Cards** — Total Incidents, High Risk Zones, Pending Reports, Active Users. Numbers are clickable links to detailed views.
- **Charts** — Incidents by District (bar), Incidents by Type (pie), 30-day Trends (line). These update automatically.
- **Recent Alerts** — the 10 most recent high-severity incidents needing attention.
- **Last Pipeline Run** card — shows what happened the last time intelligence was gathered.

**Your first action**: Check the System Health Bar. If green, proceed to configure AI (step 2) or run the pipeline (step 4).

---

## 2. Configuring the AI Provider (OpenRouter / Gemini)

Go to **AI Configuration** (`/admin/ai-config`). This is where you tell Avana which AI service to use for extracting safety incidents from news articles.

**What you see:**
- **Current Active Config** — shows which provider and model are active.
- **Environment Config** — what's configured via server environment variables (fallback if no saved config is active).
- **Configuration List** — table of all saved configurations with provider, model, status (Active/Inactive), and last test result.

### To add a new AI provider:

1. Click **"Add Configuration"** to expand the form.
2. Choose a **Provider**:
   - `openrouter` — connects to OpenRouter.ai (supports many models like GPT, Claude, etc.)
   - `gemini` — connects directly to Google Gemini
   - `auto` — tries OpenRouter first, falls back to Gemini

3. Enter the **Model name**:
   - Common OpenRouter models: `openai/gpt-4o`, `anthropic/claude-3-opus`, `google/gemini-2.0-flash`
   - Common Gemini models: `gemini-2.0-flash`, `gemini-1.5-pro`

4. Enter the **API Key**:
   - For OpenRouter: get your key from https://openrouter.ai/keys
   - For Gemini: get your key from https://aistudio.google.com/app/apikey
   - The key is encrypted before storage and never shown in plain text.
   - You can toggle visibility with the 👁️ button while typing.

5. Click **"Test Connection"** — this sends a test prompt to verify the provider works. You'll see a green "Pass" or red "Fail" result.
6. If the test passes, click **"Save Configuration"**.

### ⚠️ Important: Always test before saving.

---

## 3. Testing and Activating an AI Configuration

### Testing

The "Test Connection" button sends a simple "Respond with only: OK" prompt to the AI provider. If the provider responds correctly, the test is marked **Pass**. Otherwise **Fail**.

**Failed test causes:**
- Wrong API key
- Exceeded rate limit / quota
- Model name incorrect
- Network issue (provider unreachable)

Make sure your API key has available quota and the model name is exactly correct.

### Activating

1. Find the saved configuration in the list.
2. Click **"Activate"** on the row.
3. The page will refresh — the new config will show "Active" and the previous one will become "Inactive".
4. The system immediately switches to the new provider for all future pipeline runs.

**Note**: Activating a configuration does NOT retest it. Only activate configurations that previously passed testing.

---

## 4. Running the Intelligence Pipeline

Go to **Intelligence Pipeline** (`/admin/intelligence`). This is the core of the system — it gathers intelligence and updates safety data.

### What you can run:

| Pipeline | What it does | How often |
|----------|-------------|-----------|
| **News Intelligence** | Fetches RSS feeds, AI extracts incidents, geocodes locations | Every 6 hours (or on-demand) |
| **Community Intelligence** | Processes user-submitted reports | On-demand |
| **Heatmap Engine** | Regenerates the heatmap grid | Automatic (after risk scoring) |
| **Risk Scoring** | Recalculates safety scores for all locations | Automatic (after incidents are saved) |
| **Route Intelligence** | Updates safe routing data | Automatic |
| **Safety Recommendations** | Generates safety tips | Automatic |

### To run a pipeline:

1. Click **"Run News Intelligence"** (or "Run Community Intelligence").
2. A loading spinner appears — do NOT close the page or navigate away.
3. After completion (typically 30–120 seconds), a result card shows:
   - **Articles processed** — how many news articles were fetched
   - **Incidents saved** — how many new incidents were extracted
   - **Duration** — how long it took
   - **Status**: Success, Failed, or Skipped (with reason)
4. If successful, the dashboard stats update automatically.

### ⚠️ Conflict error: "Pipeline is already running"

This means someone else (or a scheduled job) already triggered the same pipeline. Wait a few minutes and try again.

---

## 5. What Happens Internally When the Pipeline Runs

When you click "Run News Intelligence", this chain executes:

```
News Intelligence Pipeline:
  1. Fetch RSS feeds (English + Kannada news sources)
  2. AI extracts potential incidents from each article
     → Title, description, location, incident type, severity, date
  3. Geocode each location (convert place name to coordinates)
     → e.g., "Majestic, Bengaluru" → (12.977, 77.571)
  4. Deduplicate against existing incidents
     → Skips if title + location matches a known incident
  5. Save new incidents with status = PENDING
     → These do NOT yet affect user-facing maps
  6. For each saved incident, compute:
     → Intelligence confidence score (0-100)
     → Geocoding confidence (HIGH/MEDIUM/LOW)
     → Source credibility weight
  7. Recalculate risk scores for all affected locations
  8. Regenerate heatmap grid cells
```

**Key insight**: Step 5 is the "gate." Every AI-extracted incident starts as PENDING. It only affects user maps AFTER you approve it (see step 6).

---

## 6. How Incidents Move from AI Extraction to Human Review

```
                  ┌──────────────────────────────┐
                  │  News Article / User Report   │
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                     ┌─────────────────────┐
                     │ Pipeline extracts    │
                     │ incident             │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │ Status = PENDING     │
                     │ Stored in database   │
                     │ NOT on public maps   │
                     └──────────┬──────────┘
                                │
                     You review in Admin
                                │
                    ┌───────────┴───────────┐
                    │                       │
                    ▼                       ▼
          ┌─────────────────┐    ┌─────────────────┐
          │ APPROVE          │    │ REJECT           │
          │ (Set to VERIFIED)│    │ (Set to DISMISSED│
          │                  │    │  or SPAM)        │
          └────────┬────────┘    └────────┬─────────┘
                   │                      │
                   ▼                      ▼
          ┌─────────────────┐    ┌─────────────────┐
          │ Affects risk    │    │ Ignored by      │
          │ maps, scores,   │    │ system.         │
          │ routes          │    │ Remains in DB   │
          └─────────────────┘    │ for audit.      │
                                 └─────────────────┘
```

**How to find incidents to review:**

Go to **Incidents** (`/admin/incidents`). The default view shows all incidents. Filter by status `pending` to see only unverified incidents.

---

## 7. Approving or Rejecting Incidents

In the Incidents screen:

### Per-incident review:

1. Click the **checkmark** (Verify) button on a row to approve.
2. Click the **X** (Dismiss) to reject.
3. Click the **flag** (Resolve) for incidents that have been addressed.

For each action, you have the option to add **moderation notes** (why you approved/rejected). This is stored in the audit log for accountability.

### Bulk review:

1. Select multiple incidents using the checkboxes on the left.
2. Click **"Verify All"**, **"Resolve All"**, or **"Dismiss All"** in the top bar.
3. All selected incidents are updated at once.

### What each status means:

| Status | Meaning | Effect on Users |
|--------|---------|-----------------|
| **Pending** | Waiting for review | Not visible |
| **Verified** | Confirmed real incident | Appears on safety maps, affects risk scores |
| **Dismissed** | Not a valid incident | Ignored |
| **Duplicate** | Already exists in system | Ignored |
| **Spam** | False/junk report | Ignored |

### What to look for when reviewing:

- **Does the location make sense?** — Check district vs. description
- **Is it clearly a women's safety issue?** — Harassment, assault, theft, suspicious activity
- **Is the description coherent?** — AI sometimes extracts nonsense
- **Is it already covered by another incident?** — Duplicate events from multiple news sources

### ⚠️ Never verify without reviewing. AI can make mistakes — especially with location names and severity.

---

## 8. How Approved Incidents Affect Heatmaps, Risk Scores, and Safe Routes

When you mark an incident as **VERIFIED**, it immediately affects three systems:

### Heatmap
- The heatmap is a color overlay on the map showing danger levels (green → yellow → orange → red).
- Each grid cell (approximately 1 km²) aggregates all VERIFIED incidents within it.
- More incidents = hotter (redder) color.
- The heatmap regenerates automatically after each pipeline run.
- **Important**: Cells with ZERO incidents show as "UNKNOWN" (gray/blank), NOT as "SAFE". This means "no data" rather than "safe."

### Risk Scores
- Every location on the map has a risk score from 0 (safest) to 100 (most dangerous).
- Risk scores are calculated from:
  - **Incident density** (how many incidents nearby) — weight: 50%
  - **Average severity** (critical incidents count more) — weight: 25%
  - **Recency** (recent incidents count more) — weight: 15%
  - **Night penalty** (higher at night) — weight: 10%
  - **Safety buffer** (police stations + hospitals nearby reduce score)
- Only VERIFIED incidents are used in this calculation.
- Scores update automatically after each pipeline run.

### Safe Routes
- When a user requests a safe route, the system computes multiple paths using the OSRM routing engine.
- Each path segment's risk is scored using nearby VERIFIED incidents.
- The system shows three route options: Safest, Fastest, and Balanced.
- Explanations include specific incident information, e.g., "Route avoids 3 recent harassment incidents."

### Effect on UNKNOWN areas
- Areas with insufficient data return a risk score of 0 and category "UNKNOWN."
- These areas are NOT shown as "safe" on the heatmap.
- The message to users: "Insufficient intelligence available" — not "this area is safe."
- **This is intentional.** No data ≠ safe data.

---

## 9. Monitoring Pipeline Health and AI Status

The **System Health Bar** at the top of every admin page shows:

### Backend Status
- **Green**: API server is running
- **Red**: Server unreachable — check server logs or restart

### Route Engine Status
- **Green**: OSRM routing service is responding
- **Yellow**: Slow response (>2 seconds)
- **Red**: Unreachable — routes will fail

### AI Service Status
- **Green**: Active AI provider is configured and responding
- **Red**: No active provider or failed health check

### Intelligence Observability

For deeper monitoring, check the **Intelligence Pipeline** page. It shows metrics from the `/admin/intelligence/observability` endpoint:

- **Articles** — how many news articles have been processed
- **Incidents** — how many are verified, pending, or rejected
- **Confidence Distribution** — how many incidents have high/medium/low confidence
- **Geocoding Success Rate** — what percentage of locations were successfully mapped to coordinates
- **Sources** — breakdown of where incidents come from (News, Police, User Reports, etc.)
- **Pipeline Runs** — total runs, success rate, and last 10 runs with details

### What to check daily:
1. System Health Bar — all green?
2. Pipeline status — when was last successful run? If >24 hours, run it.
3. Pending incidents — are there incidents waiting for review?
4. AI provider status — is the active config still working?

---

## 10. Dashboard Metrics Explained

The Admin Dashboard shows these key metrics:

| Metric | What it means |
|--------|---------------|
| **Total Incidents** | All incidents in the database (all statuses) |
| **High Risk Zones** | Locations with risk scores above 65 (HIGH_RISK or CRITICAL) |
| **Pending Reports** | Incidents waiting for your review — needs attention |
| **Active Users** | Users who have logged in recently |
| **SOS Events** | Emergency alerts triggered by users |
| **Verified Reports** | Incidents you've approved |
| **Incidents by District** | Bar chart showing which areas have the most incidents |
| **Incidents by Type** | Pie chart — harassment, theft, assault, etc. |
| **30-Day Trend** | Line chart showing incident volume over time |
| **Recent Alerts** | Latest high-severity incidents that may need immediate attention |

### What warrants attention:
- **Spike in Pending incidents** — the pipeline extracted many new ones, you have catching up to do
- **Pipeline failure** — the last intelligence run failed (red card at bottom)
- **Data freshness >48 hours old** — the intelligence is stale, run a pipeline
- **AI provider health red** — no AI will work until fixed

---

## 11. Common Errors and How to Respond

### Pipeline Errors

| Error | Likely Cause | What to Do |
|-------|-------------|------------|
| `GeminiQuotaExceeded` | AI provider ran out of API credits | Add credits or switch to a different AI config |
| `Pipeline is already running` | Concurrent execution prevented | Wait 2 minutes, try again |
| `No incidents extracted` | RSS feeds returned no new articles | Normal — check again after 6 hours |
| `Geocoding failed for N locations` | Location names couldn't be mapped to coordinates | Check incident locations in review — may need manual correction |
| `OpenRouter returned 429` | Rate limited by OpenRouter | Wait 1 minute, retry, or switch to Gemini |

### AI Configuration Errors

| Error | Likely Cause | What to Do |
|-------|-------------|------------|
| Test connection fails | Wrong API key, model name, or quota exhausted | Verify key, check model name spelling, check billing |
| `No active provider` | No saved config is active | Create and activate a config, or verify environment variables |
| `Provider not responding` | Network issue or provider outage | Try the other provider (Gemini vs OpenRouter) |

### Data Integrity Issues

The debug endpoints (`/admin/debug/data-integrity` and `/admin/debug/heatmap-state`) can help diagnose:

- **Risk scores not updating** — check if the pipeline completed successfully. If the risk agent failed, risk scores won't update.
- **Heatmap showing no data** — check if any incidents are VERIFIED. Empty heatmap = no approved incidents.
- **Safe routes showing odd values** — check if route segments have the expected nearby incidents.

### If nothing works:
1. Check the server logs (backend logs show detailed error messages).
2. Run the heatmap-state debug endpoint to see what the system sees.
3. If all else fails, trigger a full pipeline run (News Intelligence → this also recalculates risk + heatmap).

---

## 12. Admin Responsibilities

### Daily (5–10 minutes)
1. Check the **System Health Bar** — all green?
2. Review **Pending Incidents** — approve or reject any new ones (aim to clear within 24 hours).
3. Quick glance at **Dashboard Metrics** — any unusual spikes or drops?
4. If data is >24 hours stale, run the **News Intelligence** pipeline.

### Weekly (15–30 minutes)
1. Run the **News Intelligence** pipeline at least once (even if auto-scheduled, manual run ensures freshness).
2. Review and clear all remaining PENDING incidents.
3. Check **AI Configuration** — verify the active provider has sufficient quota for the coming week.
4. Audit recent **DISMISSED/SPAM** incidents — are any patterns of false positives emerging?
5. Review **Intelligence Observability** — check geocoding success rate, confidence distribution, pipeline success rate.

### Monthly (1 hour)
1. **Full pipeline audit**: Review all pipeline runs for the month. Check success rate (target >90%).
2. **Data integrity check**: Run `/admin/debug/data-integrity` and review.
3. **Source review**: Are the RSS feeds still working? Are there new local news sources to add?
4. **User review**: Check the Users page — suspend inactive accounts, promote trusted users to moderators.
5. **Config review**: Is the AI provider still optimal? Consider switching to a cheaper/faster model if appropriate.
6. **Backup check**: Verify database backups are running (coordinate with IT).

---

## Best Practices

1. **Always test AI connections before activating.** A config that passes "Test" may still fail under full pipeline load. Monitor the first pipeline run after activation.

2. **Review incidents in batches.** Use the filter to see only `pending` status incidents. Batch-verify the obviously correct ones first, then carefully review the ambiguous ones.

3. **Use moderation notes.** Notes like "Duplicate of incident #123" or "Location seems wrong — need verification" create an audit trail for future administrators.

4. **Run News Intelligence first thing on Monday.** After a weekend of no processing, there may be many new incidents. Run the pipeline, then review.

5. **Don't let PENDING incidents pile up.** A backlog of 100+ incidents means your users are missing critical safety information. If the volume is too high, consider training a moderator.

6. **Monitor AI quota weekly.** Running out of AI credits mid-week means no new incidents are extracted until you add credits. Set a weekly calendar reminder.

7. **Heatmap ≠ real-time.** The heatmap updates only when the pipeline runs. If a major incident occurs, users won't see it on the map until after the next pipeline run and your approval.

8. **UNKNOWN is not SAFE.** Remember: areas with no data show as UNKNOWN (gray), not SAFE (green). This is by design — never infer safety from absence of data.

---

## Common Mistakes to Avoid

1. **❌ Verifying without reading.** AI sometimes generates plausible-sounding but incorrect incidents. Always read the title and location before approving.

2. **❌ Running the pipeline too frequently.** RSS feeds don't update that often. Running more than once per hour wastes AI credits and server resources. Stick to every 6 hours.

3. **❌ Ignoring the UNKNOWN category.** If you see many UNKNOWN areas on the heatmap, it means the system needs more data sources or the pipeline isn't extracting enough incidents. Investigate.

4. **❌ Using the same API key for Gemini and OpenRouter.** These are different services with different keys. Make sure you're using the right key for the right provider.

5. **❌ Approving duplicates.** Always check if an incident already exists before verifying. Use the duplicate detection tools in the incidents screen.

6. **❌ Skipping weekly AI health checks.** AI providers change models, deprecate APIs, and enforce rate limits. Check weekly that your active config still works.

7. **❌ Bulk-approving everything.** Just because an incident was AI-extracted doesn't mean it's correct. Bulk approve only when you're confident about the pipeline's quality.

8. **❌ Overlooking the "auto" provider setting.** Setting provider to "auto" tries OpenRouter first, then Gemini as fallback. This is recommended for reliability but uses more quota.

---

## Intelligence Pipeline Summary

```
Pipeline: NEWS INTELLIGENCE
  Input:  RSS feeds (English + Kannada news)
  Agent:  NewsIntelligenceAgent → AI extraction
  Output: Raw incident data (title, location, type, severity)

Pipeline: GEOSPATIAL (automatic, after News)
  Input:  Raw incident data
  Agent:  GeospatialIntelligenceAgent → geocoding + dedup
  Output: Geocoded incidents with confidence scores
  
Pipeline: RISK SCORING (automatic, after Geospatial)
  Input:  Saved incidents
  Agent:  RiskIntelligenceAgent → score calculation
  Output: Updated risk scores + heatmap grid

Final:   Incidents saved with status = PENDING
         → Awaiting your approval
         → After VERIFIED: appears on user maps
```

---

## Incident Review Summary

```
Step 1: Go to Incidents → Filter by "pending"
Step 2: Read title, location, severity
Step 3: Verify location makes sense (check district)
Step 4: Click Verify (checkmark) or Dismiss (X)
Step 5: (Optional) Add moderation notes
Step 6: Verified incidents immediately affect:
          - Risk scores (0-100) at that location
          - Heatmap colors (green→red overlay)
          - Safe route calculations
          
Pro tip: Use bulk actions for similar incidents
         Use CSV export for offline auditing
```

---

## AI Configuration Summary

```
Create:
  1. Choose provider (OpenRouter / Gemini / Auto)
  2. Enter model name (e.g., gpt-4o, gemini-2.0-flash)
  3. Enter API key (encrypted before storage)
  4. Test connection (always test!)
  5. Save

Activate:
  1. Find saved config in list
  2. Click "Activate"
  3. System switches immediately
  4. Next pipeline run uses new provider

Monitor:
  - Check AI status in System Health Bar
  - Run intelligence observability check
  - Review test results weekly
  - Add credits before quota runs out

Fallback chain: OpenRouter → Gemini → (fails with error)
```

---

## How Avana Works From an Admin's Perspective

Imagine you're the safety officer for a city. You have a team of AI assistants that scan news, read police reports, and listen to community reports 24/7. Every time they find something relevant, they write it on a sticky note and put it on your desk. Your job: review each sticky note, decide if it's real, and if approved, pin it to the official city safety map.

**Here's the complete flow:**

### 1. Data Collection (Automatic)

Every 6 hours (or whenever you click "Run"), Avana's News Intelligence Agent reads dozens of RSS feeds — English news, Kannada news, and police blotters. It collects every article that mentions a safety incident: harassment, theft, assault, suspicious activity, and more.

### 2. AI Extraction (Automatic)

The AI (either OpenRouter or Gemini — you choose which) reads each article and extracts the facts:
- **What happened** — incident type (theft, harassment, etc.)
- **Where** — location name (e.g., "KR Market, Bengaluru")
- **How bad** — severity (Low, Medium, High, Critical)
- **When** — date of the incident
- **Details** — description, source URL

### 3. Geocoding (Automatic)

The Geospatial Agent takes each location name and converts it to map coordinates. "KR Market, Bengaluru" becomes `(12.960, 77.575)`. It also checks: does this location match the expected district? If the AI says "Mysuru" but the coordinates point to "Dakshina Kannada," the system flags the mismatch and uses the actual coordinates.

### 4. Confidence Scoring (Automatic)

Every incident gets a confidence score from 0-100:
- **AI confidence** (25%): How sure was the AI about this extraction?
- **Source credibility** (25%): Police reports are weighted higher than news articles; English news higher than Kannada news.
- **Geocoding confidence** (20%): Did the location match the expected district?
- **Deduplication** (10%): Is this a new incident or a repeat?
- **Human review** (20%): Has an admin reviewed it yet?

### 5. The Gate: PENDING Status (Where You Come In)

Every AI-extracted incident starts as **PENDING**. It sits in the database but is invisible to users. The system deliberately does NOT show AI output directly to the public. This is your quality gate.

At this point, the risk scores and heatmap are updated — but ONLY for incidents that have been previously verified. The new PENDING incidents don't change anything on the map yet.

### 6. Your Review (Manual)

You log in, go to Incidents, and see a list of PENDING incidents. For each one:
- **Read** the title and description
- **Check** the location and district
- **Decide**: Is this real? Is it relevant? Is it duplicate?

If **real** → click **Verify**. The incident is now VERIFIED.
If **fake, duplicate, or spam** → click **Dismiss** or mark as **Duplicate/Spam**.
If **uncertain** → leave as PENDING and come back later.

### 7. Published to Users (Immediate)

The moment you click Verify:
- ✅ The incident appears on the **safety map** for all users in that area
- ✅ The **risk score** for that location recalculates (or will on next pipeline run)
- ✅ The **heatmap** updates to reflect the new incident
- ✅ **Safe route calculations** now consider this incident

### 8. Users See Safety Intelligence

A user opens the app and sees:
- **Their current risk score** — "Your area is MODERATE (35/100)"
- **A heatmap** — color overlay showing which areas have more incidents
- **Nearby incidents** — "3 incidents reported near you"
- **Safe routes** — "Walking route avoids 2 high-risk zones"
- **Safety explanations** — "This area has 5 recent harassment incidents and is near 2 police stations"

### 9. Continuous Improvement

As more articles are processed and more incidents are verified, the system becomes smarter:
- More data points → more accurate risk scores
- More verified incidents → better heatmap coverage
- Your review patterns teach the system what to prioritize

**And that's the complete cycle:** AI collects → extracts → geocodes → scores → you gatekeep → approve → users see safety intelligence. Your judgment is the most important part of the system. The AI does the heavy lifting; you do the quality control.
