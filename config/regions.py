"""Registry of supported study regions.

To add a region: append a ``Region`` here, add its boundary file to
``data/geo/`` (see ``scripts/prepare_boundaries.py``) and re-run the
pipeline. Pages, the region selector and the pipeline all read this list,
so nothing else needs editing.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_GEO_DIR = Path(__file__).resolve().parent.parent / "data" / "geo"


@dataclass(frozen=True)
class Region:
    key: str            # internal identifier stored in every processed output
    name: str           # display name
    country: str
    iso_code: str       # ISO 3166-2 code used to pick the boundary polygon
    boundary_file: Path

    @property
    def label(self) -> str:
        """Searchable label shown in the region selector."""
        return f"{self.name}, {self.country}"


REGION_REGISTRY: tuple[Region, ...] = (
    Region("Punjab", "Punjab", "India", "IN-PB", _GEO_DIR / "punjab.geojson"),
    Region("Haryana", "Haryana", "India", "IN-HR", _GEO_DIR / "haryana.geojson"),
)

REGIONS_BY_KEY: dict[str, Region] = {r.key: r for r in REGION_REGISTRY}


def region_label(key: str) -> str:
    """Display label for a region key (falls back to the key itself)."""
    r = REGIONS_BY_KEY.get(key)
    return r.label if r else key
