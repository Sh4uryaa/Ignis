"""Synthetic monthly region totals for harmonization tests (not NASA data)."""
import numpy as np
import pandas as pd


def make_totals(ratio_by_month=None, modis=100, years=range(2010, 2024),
                viirs_start=(2012, 1), regions=("Punjab", "Haryana")) -> pd.DataFrame:
    """Complete MODIS every month; VIIRS from ``viirs_start`` (first month partial).

    VIIRS = MODIS x ratio_by_month[month] (default: month number), so the
    true seasonal factor is known exactly.
    """
    ratio_by_month = ratio_by_month or {m: float(m) for m in range(1, 13)}
    rows = []
    for region in regions:
        for y in years:
            for m in range(1, 13):
                p = (y, m)
                if p < viirs_start:
                    v, vcov = np.nan, "none"
                elif p == viirs_start:
                    v, vcov = modis * ratio_by_month[m] / 2, "partial"
                else:
                    v, vcov = modis * ratio_by_month[m], "complete"
                rows.append({"region": region, "year": y, "month": m,
                             "modis_terra_count": modis // 2, "modis_aqua_count": modis - modis // 2,
                             "modis_combined_count": modis, "viirs_snpp_count": v,
                             "modis_terra_coverage": "complete", "modis_aqua_coverage": "complete",
                             "modis_combined_coverage": "complete", "viirs_snpp_coverage": vcov,
                             "confidence_policy": "nominal_high"})
    return pd.DataFrame(rows)
