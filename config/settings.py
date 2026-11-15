"""Central configuration for IGNIS.

Every path, analytical policy, period boundary and threshold used by the
processing pipeline and the Streamlit app lives here. Do not hard-code
these values elsewhere — import them from this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = PROJECT_ROOT / "data"
RAW_INCOMING_DIR: Path = DATA_DIR / "raw" / "incoming"
EXTRACTED_DIR: Path = DATA_DIR / "extracted"
GEO_DIR: Path = DATA_DIR / "geo"
PROCESSED_DIR: Path = DATA_DIR / "processed"

QUALITY_REPORT_PATH: Path = PROCESSED_DIR / "quality_report.json"
INSPECTION_REPORT_PATH: Path = PROCESSED_DIR / "inspection_report.json"


# ---------------------------------------------------------------------------
# Source archives
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SourceArchive:
    """Description of one NASA FIRMS download archive."""

    key: str                     # internal sensor key: "MODIS" or "VIIRS"
    zip_name: str                # archive filename in RAW_INCOMING_DIR
    archive_csv: str             # historical (standard-quality) CSV to use
    ignored_csvs: tuple[str, ...]  # NRT CSVs that must never be used
    collection: str              # human-readable collection label
    expected: dict = field(default_factory=dict)  # expected stats for checks

    @property
    def zip_path(self) -> Path:
        return RAW_INCOMING_DIR / self.zip_name

    @property
    def extracted_csv_path(self) -> Path:
        return EXTRACTED_DIR / self.archive_csv


MODIS_ARCHIVE = SourceArchive(
    key="MODIS",
    zip_name="MODIS C6.1.zip",
    archive_csv="fire_archive_M-C61_846942.csv",
    ignored_csvs=("fire_nrt_M-C61_846942.csv",),
    collection="MODIS Collection 6.1 (Terra + Aqua)",
    expected={
        "total_rows": 455_872,
        "first_date": "2000-11-01",
        "last_date": "2026-08-27",
        "n_columns": 15,
        "exact_duplicates": 0,
        "missing_values": 0,
        "satellite_counts": {"Terra": 100_916, "Aqua": 354_956},
        "satellite_coverage": {
            "Terra": ["2000-11-01", "2026-08-22"],
            "Aqua": ["2002-07-18", "2026-08-27"],
        },
        "confidence_class_counts": {"low": 13_685, "nominal": 374_592, "high": 67_595},
        "nominal_plus_high": 442_187,
        "type_counts": {"0": 448_918, "2": 6_954},
        "version_counts": {"6.03": 424_629, "61.03": 31_243},
    },
)

VIIRS_ARCHIVE = SourceArchive(
    key="VIIRS",
    zip_name="SUOMI VIIRS C2.zip",
    archive_csv="fire_archive_SV-C2_846954.csv",
    ignored_csvs=("fire_nrt_SV-C2_846954.csv",),
    collection="VIIRS Suomi-NPP Collection 2",
    expected={
        "total_rows": 1_291_486,
        "first_date": "2012-01-20",
        "last_date": "2026-07-31",
        "n_columns": 15,
        "exact_duplicates": 0,
        "missing_values": 0,
        "confidence_class_counts": {"low": 157_450, "nominal": 1_085_342, "high": 48_694},
        "nominal_plus_high": 1_134_036,
        "type_counts": {"0": 1_284_226, "2": 7_182, "3": 78},
    },
)

# Discrepancies between the brief's expected statistics and the actual files
# that have been investigated. They are still reported as mismatches; this
# text is attached so readers know the cause. Never edit `expected` to hide one.
DOCUMENTED_DISCREPANCIES: dict[str, dict[str, str]] = {
    "MODIS": {
        "confidence_class_counts": (
            "The file has 61,887 high (80-100) and 380,300 nominal (30-79) records. "
            "The brief expected 67,595 / 374,592. No single integer threshold "
            "reproduces 67,595, so the expected split appears to be a transcription "
            "error. The low count (13,685) and the nominal+high total (442,187) match "
            "exactly, so the Nominal + High analytical policy is unaffected."
        ),
    },
    "VIIRS": {},
}

SOURCE_ARCHIVES: dict[str, SourceArchive] = {
    MODIS_ARCHIVE.key: MODIS_ARCHIVE,
    VIIRS_ARCHIVE.key: VIIRS_ARCHIVE,
}

# Exact source column names present in both FIRMS archive CSVs.
SOURCE_COLUMNS: tuple[str, ...] = (
    "latitude", "longitude", "brightness", "scan", "track", "acq_date",
    "acq_time", "satellite", "instrument", "confidence", "version",
    "bright_t31", "frp", "daynight", "type",
)

# Explicit read dtypes. acq_time is read as a string to keep leading zeros
# (e.g. "0637"); confidence differs by sensor so it is read as string too.
SOURCE_DTYPES: dict[str, str] = {
    "latitude": "float64",
    "longitude": "float64",
    "brightness": "float64",
    "scan": "float32",
    "track": "float32",
    "acq_date": "string",
    "acq_time": "string",
    "satellite": "string",
    "instrument": "string",
    "confidence": "string",
    "version": "string",
    "bright_t31": "float64",
    "frp": "float64",
    "daynight": "string",
    "type": "Int16",
}

# ---------------------------------------------------------------------------
# Detection types (FIRMS documentation)
# ---------------------------------------------------------------------------
DETECTION_TYPE_LABELS: dict[int, str] = {
    0: "Presumed vegetation fire",
    1: "Active volcano",
    2: "Other static land source",
    3: "Offshore detection",
}

# ---------------------------------------------------------------------------
# Confidence policy
# ---------------------------------------------------------------------------
CONFIDENCE_POLICY_NAME: str = "nominal_high"
CONFIDENCE_POLICY_LABEL: str = "Nominal + High confidence"

# MODIS numeric confidence (0-100) classes.
MODIS_CONFIDENCE_BINS: dict[str, tuple[int, int]] = {
    "low": (0, 29),
    "nominal": (30, 79),
    "high": (80, 100),
}
MODIS_MIN_CONFIDENCE: int = 30

# VIIRS categorical confidence.
VIIRS_CONFIDENCE_CLASSES: dict[str, str] = {"l": "low", "n": "nominal", "h": "high"}
VIIRS_ACCEPTED_CONFIDENCE: tuple[str, ...] = ("n", "h")

# ---------------------------------------------------------------------------
# Platforms
# ---------------------------------------------------------------------------
MODIS_PLATFORMS: tuple[str, ...] = ("Terra", "Aqua")
# FIRMS labels Suomi-NPP as "N" in some products and "SNPP" in others.
VIIRS_PLATFORM_ALIASES: tuple[str, ...] = ("N", "SNPP", "Suomi-NPP", "Suomi NPP")
VIIRS_PLATFORM_LABEL: str = "Suomi-NPP"

# ---------------------------------------------------------------------------
# Study regions and geography
# ---------------------------------------------------------------------------
REGIONS: tuple[str, ...] = ("Punjab", "Haryana")
DEFAULT_REGION: str = "Punjab"
OUTSIDE_REGION_LABEL: str = "Outside study area"
REGION_BOUNDARY_FILES: dict[str, Path] = {
    "Punjab": GEO_DIR / "punjab.geojson",
    "Haryana": GEO_DIR / "haryana.geojson",
}
# ISO 3166-2 codes used to select each state from the source dataset.
REGION_ISO_CODES: dict[str, str] = {"Punjab": "IN-PB", "Haryana": "IN-HR"}
BOUNDARY_PROVENANCE_PATH: Path = GEO_DIR / "boundary_provenance.json"
BOUNDARY_SOURCE: dict[str, str] = {
    "name": "geoBoundaries gbOpen, India ADM1 (State / Union Territory)",
    "api_url": "https://www.geoboundaries.org/api/current/gbOpen/IND/ADM1/",
    # Pinned to a release commit so the geometry is reproducible.
    "download_url": ("https://github.com/wmgeolab/geoBoundaries/raw/9469f09/"
                     "releaseData/gbOpen/IND/ADM1/geoBoundaries-IND-ADM1.geojson"),
    "boundary_id": "IND-ADM1-1811400",
    "admin_level": "ADM1",
    "upstream_source": "DataMeet India community, Election Commission of India",
    "license": "Creative Commons Attribution 2.5 India (CC BY 2.5 IN)",
    "year_represented": "2011",
    "citation": ("Runfola, D. et al. (2020) geoBoundaries: A global database of "
                 "political administrative boundaries. PLoS ONE 15(4): e0231866."),
}
# The FIRMS archives were requested with a custom polygon: one simplified
# (94-vertex) outline covering Punjab + Haryana together. It cannot separate
# the two states and is too coarse for state attribution (it also contains
# Chandigarh), so it is kept for provenance and sanity checks only — never as
# a substitute for the real administrative boundaries.
DOWNLOAD_AREA_WKT_PATH: Path = GEO_DIR / "firms_download_area.wkt"
# Observed min/max coordinates of the detections (not the polygon's bounds).
DOWNLOAD_EXTENT = {"lat_min": 27.6406, "lat_max": 32.5503,
                   "lon_min": 73.81358, "lon_max": 77.66328}

SOURCE_CRS: str = "EPSG:4326"
PROJECTED_CRS: str = "EPSG:32643"   # WGS 84 / UTM zone 43N
GRID_CELL_SIZE_M: int = 1_000

# ---------------------------------------------------------------------------
# Harmonization periods (inclusive month bounds, "YYYY-MM")
# ---------------------------------------------------------------------------
TRAINING_START: str = "2012-02"
TRAINING_END: str = "2022-12"
VALIDATION_START: str = "2023-01"
VALIDATION_END: str = "2026-07"
BACKCAST_START: str = "2002-08"
BACKCAST_END: str = "2011-12"

# ---------------------------------------------------------------------------
# Calibration and uncertainty
# ---------------------------------------------------------------------------
MIN_MONTHLY_DETECTIONS: int = 5
MIN_VALID_YEAR_PAIRS: int = 5
BOOTSTRAP_ITERATIONS: int = 2_000
BOOTSTRAP_SEED: int = 42
INTERVAL_LEVEL: float = 0.95
CALIBRATION_METHOD: str = "median_of_annual_monthly_ratios"

# Supplementary leave-one-year-out cross-validation window: training years in
# which Terra/Aqua overpass times were still stable (drift visible from 2022,
# see overpass_times.csv). Diagnostic only; the primary validation is the
# independent VALIDATION_START..VALIDATION_END hold-out.
STABLE_ORBIT_CV_YEARS: tuple[int, int] = (2012, 2021)
IST_OFFSET_HOURS: float = 5.5
UNCERTAINTY_SCOPE: str = (
    "95% bootstrap calibration-factor uncertainty interval only. Does not include "
    "satellite measurement uncertainty, cloud omission, detection-algorithm "
    "uncertainty, spatial heterogeneity or temporal fire variability."
)

# ---------------------------------------------------------------------------
# Anomalies
# ---------------------------------------------------------------------------
# A month within +/- this percentage of its same-month historical median is
# labelled "Near historical median".
ANOMALY_NEAR_BAND_PCT: float = 20.0

# ---------------------------------------------------------------------------
# Visual identity
# ---------------------------------------------------------------------------
APP_NAME: str = "IGNIS"
APP_TAGLINE: str = "Harmonizing Satellite Fire Observations Across Time."
APP_SUBTITLE: str = "NASA MODIS–VIIRS Historical Fire Analysis"

COLORS: dict[str, str] = {
    "background": "#0F1115",
    "surface": "#171A21",
    "border": "#2A2F3A",
    "primary": "#FF6B1A",     # bright orange
    "secondary": "#E0A458",   # muted amber
    "text": "#FFFFFF",
    "text_muted": "#A8AEB8",
    "modis": "#FF6B1A",
    "terra": "#FF8C42",
    "aqua": "#C2410C",
    "viirs": "#F5C542",
    "positive": "#4CAF7A",
    "negative": "#E5484D",
}
MAP_MAX_POINTS: int = 20_000
