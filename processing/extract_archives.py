"""Locate NASA FIRMS ZIP archives and extract only the historical CSVs.

The original ZIP files are never modified. NRT CSVs inside the archives are
explicitly ignored.
"""
from __future__ import annotations

import logging
import shutil
import zipfile
from pathlib import Path

from config.settings import EXTRACTED_DIR, SOURCE_ARCHIVES, SourceArchive

logger = logging.getLogger(__name__)


class ArchiveError(RuntimeError):
    """Raised when a source archive is missing or malformed."""


def missing_archive_message(archive: SourceArchive) -> str:
    """Human-readable instructions for a missing archive."""
    return (
        f"{archive.key} archive not found.\n"
        f"  Expected filename : {archive.zip_name}\n"
        f"  Expected directory: {archive.zip_path.parent}\n"
        f"  Fix: download the {archive.collection} archive from NASA FIRMS "
        f"(https://firms.modaps.eosdis.nasa.gov/download/) and place the ZIP "
        f"file at the path above without renaming its contents."
    )


def list_archive_members(archive: SourceArchive) -> list[str]:
    """Return the member filenames inside an archive ZIP."""
    if not archive.zip_path.exists():
        raise ArchiveError(missing_archive_message(archive))
    with zipfile.ZipFile(archive.zip_path) as zf:
        return zf.namelist()


def classify_members(archive: SourceArchive, members: list[str]) -> dict[str, list[str]]:
    """Split ZIP members into the archive CSV, ignored NRT CSVs and others."""
    result: dict[str, list[str]] = {"archive": [], "ignored_nrt": [], "other": []}
    for name in members:
        base = Path(name).name
        if base == archive.archive_csv:
            result["archive"].append(name)
        elif base in archive.ignored_csvs or base.startswith("fire_nrt_"):
            result["ignored_nrt"].append(name)
        else:
            result["other"].append(name)
    return result


def extract_historical_csv(
    archive: SourceArchive,
    dest_dir: Path = EXTRACTED_DIR,
    overwrite: bool = False,
) -> Path:
    """Extract the historical archive CSV (never the NRT CSV) to ``dest_dir``.

    Returns the path of the extracted CSV. Uses streaming copy so large files
    are not loaded into memory. Member names are flattened to their basename,
    which also prevents path-traversal entries from escaping ``dest_dir``.
    """
    members = list_archive_members(archive)
    groups = classify_members(archive, members)
    if len(groups["archive"]) != 1:
        raise ArchiveError(
            f"{archive.zip_name}: expected exactly one '{archive.archive_csv}', "
            f"found {groups['archive'] or 'none'}. Members: {members}"
        )
    if groups["ignored_nrt"]:
        logger.info("%s: ignoring NRT members %s", archive.zip_name, groups["ignored_nrt"])

    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / archive.archive_csv
    if target.exists() and not overwrite:
        with zipfile.ZipFile(archive.zip_path) as zf:
            if zf.getinfo(groups["archive"][0]).file_size == target.stat().st_size:
                logger.info("Using existing extracted file %s", target)
                return target

    with zipfile.ZipFile(archive.zip_path) as zf, zf.open(groups["archive"][0]) as src, \
            open(target, "wb") as dst:
        shutil.copyfileobj(src, dst, length=1 << 20)
    logger.info("Extracted %s -> %s", groups["archive"][0], target)
    return target


def extract_all(overwrite: bool = False) -> dict[str, Path]:
    """Extract every configured archive. Raises on the first missing archive."""
    return {key: extract_historical_csv(a, overwrite=overwrite)
            for key, a in SOURCE_ARCHIVES.items()}
