# Seed Data — Offline-First Data Layer

This directory contains all source data for the Avana V2 platform.
The system can be fully rebuilt from these files with no external dependencies.

## Files

| File | Description | Source |
|------|-------------|--------|
| `incidents.csv` | 50 verified women-safety incidents across 31 Karnataka districts | Curated from NCRB data |
| `police_stations.csv` | 38 police stations across all districts | Karnataka Police directory |
| `hospitals.csv` | 30 hospitals with emergency services | Karnataka Health Department |
| `districts.csv` | All 31 Karnataka districts with centroids | Census data |
| `crime_stats.csv` | District-level crime statistics (2024) | NCRB compiled data |

## Usage

```bash
# Seed everything
python -m scripts.seed_all

# Force reseed
python -m scripts.seed_all --force

# Rebuild from scratch (drops all data)
python -m scripts.rebuild_database
```

## Principles

1. **Offline-first**: No AI, Gemini, or external API required
2. **Reproducible**: Same CSV → same database every time
3. **Versioned**: Seed data lives in git alongside code
4. **PostGIS compatible**: All coordinates include geom columns
