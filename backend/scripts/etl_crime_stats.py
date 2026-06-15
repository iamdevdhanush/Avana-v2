#!/usr/bin/env python3
"""
CLI entry point for the Karnataka Police Crime Statistics ETL.

Usage:
    python scripts/etl_crime_stats.py --file data/crime_stats_2023.csv
    python scripts/etl_crime_stats.py --file data/stats.xlsx
    python scripts/etl_crime_stats.py --status
    python scripts/etl_crime_stats.py --ingest-all
"""
import asyncio
import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

from app.pipeline.crime_stat_etl import run_etl_pipeline, ingest_to_incidents, recalc_heatmap_for_districts, get_etl_status


async def main():
    parser = argparse.ArgumentParser(description="Karnataka Police Crime Statistics ETL")
    parser.add_argument("--file", "-f", type=str, help="Path to CSV/XLSX/PDF file")
    parser.add_argument("--status", "-s", action="store_true", help="Show ETL status")
    parser.add_argument("--ingest-all", "-i", action="store_true", help="Ingest all pending crime stats as incidents")

    args = parser.parse_args()

    if args.status:
        status = await get_etl_status()
        print(f"Total records:      {status['total_records']}")
        print(f"Normalized:         {status['normalized_records']}")
        print(f"Ingested:           {status['ingested_records']}")
        print(f"Pending ingestion:  {status['pending_ingestion']}")
        if status["recent_batches"]:
            print(f"Recent batches:     {', '.join(status['recent_batches'])}")
        return

    if args.ingest_all:
        ingested = await ingest_to_incidents()
        print(f"Ingested {ingested} crime stats as incidents")
        if ingested:
            print("Recalculating heatmap...")
            await recalc_heatmap_for_districts()
            print("Done.")
        return

    if args.file:
        if not os.path.exists(args.file):
            print(f"File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        result = await run_etl_pipeline(file_path=args.file)
        print(f"Batch:       {result.get('batch_id')}")
        print(f"Status:      {result.get('status')}")
        print(f"Read:        {result.get('records_read')}")
        print(f"Stored:      {result.get('records_stored')}")
        print(f"Ingested:    {result.get('records_ingested')}")
        return

    parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
