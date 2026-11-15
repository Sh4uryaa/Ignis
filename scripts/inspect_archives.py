"""Inspect the NASA FIRMS source archives and write an inspection report.

Usage::

    python -m scripts.inspect_archives

Extracts only the historical archive CSVs (NRT CSVs are ignored), computes
record counts, coverage, platform/confidence/type/version distributions,
duplicate and missing-value counts, compares them with the expected values
in ``config.settings`` and writes ``data/processed/inspection_report.json``.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from config.settings import INSPECTION_REPORT_PATH, PROCESSED_DIR, SOURCE_ARCHIVES
from processing.extract_archives import (
    ArchiveError,
    classify_members,
    extract_historical_csv,
    list_archive_members,
)
from processing.inspect_data import inspect_archive
from processing.read_source import read_raw_strings
from utils.logging_config import configure_logging

logger = logging.getLogger("inspect_archives")


def run() -> dict:
    """Inspect every configured archive and return the combined report."""
    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "archives": {},
        "warnings": [],
    }
    for key, archive in SOURCE_ARCHIVES.items():
        members = list_archive_members(archive)
        groups = classify_members(archive, members)
        csv_path = extract_historical_csv(archive)
        logger.info("Reading %s ...", csv_path.name)
        df = read_raw_strings(csv_path)
        result = inspect_archive(archive, df)
        result["zip_members"] = groups
        report["archives"][key] = result
        report["warnings"].extend(result["warnings"])
    return report


def _print_summary(report: dict) -> None:
    for key, res in report["archives"].items():
        s = res["statistics"]
        print(f"\n=== {key}: {res['archive_csv']} ===")
        print(f"rows={s['total_rows']:,}  cols={s['n_columns']}  "
              f"dates={s['first_date']}..{s['last_date']}  "
              f"dups={s['exact_duplicates']}  missing={s['missing_values']}")
        print(f"satellites={s['satellite_counts']}  coverage={s['satellite_coverage']}")
        print(f"confidence={s['confidence_class_counts']}  nominal+high={s['nominal_plus_high']:,}")
        print(f"types={s['type_counts']}  versions={s['version_counts']}")
        print(f"ignored NRT members: {res['zip_members']['ignored_nrt']}")
        for c in res["expectation_checks"]:
            mark = "OK  " if c["match"] else "DIFF"
            print(f"  [{mark}] {c['check']}" + ("" if c["match"]
                  else f": expected {c['expected']} | actual {c['actual']}"))
    print(f"\nWarnings: {len(report['warnings'])}")


def main() -> int:
    configure_logging()
    try:
        report = run()
    except ArchiveError as exc:
        logger.error("%s", exc)
        return 1
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    INSPECTION_REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _print_summary(report)
    print(f"Report written to {INSPECTION_REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
