# IGNIS methodology

This document describes exactly what the pipeline computes. All settings live in
`config/settings.py`; the code is in `processing/`.

## 1. Inputs and policies

| Item | Policy |
|---|---|
| MODIS | Collection 6.1 archive, Terra + Aqua (`fire_archive_M-C61_846942.csv`) |
| VIIRS | Suomi-NPP 375 m Collection 2 archive (`fire_archive_SV-C2_846954.csv`) |
| NRT files | Ignored |
| Confidence | MODIS `30 ≤ confidence ≤ 100`; VIIRS `confidence ∈ {n, h}`. The two scales are not treated as equivalent. Original values are kept. |
| Detection types | All included (0, 2, 3 present). Unknown codes would be kept and reported. |
| Regions | Punjab and Haryana, separately, by point-in-polygon on geoBoundaries ADM1 polygons (EPSG:4326). |
| Metric | Monthly hotspot-detection counts. FRP is supplementary only. |

## 2. Monthly totals and coverage

For each region *R*, month (*y*, *m*) and platform *p* ∈ {Terra, Aqua, S-NPP}, the count
*N<sub>p</sub>(R, y, m)* is the number of retained detections.

Coverage is derived from the data: each platform's record runs from its first to its last
observation date. A month is **complete** for a platform if the record spans every day of it,
**partial** if it spans some days, **none** otherwise.

- Observed but zero detections → count `0`.
- Not observed → count missing (`NaN`). Missing is never converted to zero.
- Combined MODIS `M = N_Terra + N_Aqua`, defined only when **both** platforms observed the
  month; complete only if both are complete. Terra-only months stay Terra-only.

Gaps of 20+ days with no detection at all are listed in the quality report (mostly monsoon and
mid-winter). They may be quiet periods or outages and do not change coverage status.

## 3. Seasonal calibration

Training window: complete overlapping months, **Feb 2012 – Dec 2022** (Jan 2012 is a partial
VIIRS month and is excluded).

For each region and training month, with *V* = VIIRS S-NPP count and *M* = combined MODIS count:

$$r_{y,m} = \frac{V_{y,m}}{M_{y,m}}$$

A year pair is **valid** only if `M ≥ MIN_MONTHLY_DETECTIONS` and `V ≥ MIN_MONTHLY_DETECTIONS`
(default 5); this also prevents division by zero. The seasonal factor is

$$r_m = \operatorname{median}_y\left(r_{y,m}\right)$$

computed only when at least `MIN_VALID_YEAR_PAIRS` (default 5) valid years exist. Otherwise the
factor is `NaN`, marked *unavailable* with a reason, and no fallback is invented. A pooled ratio
`ΣV / ΣM` is stored as a diagnostic only.

**Result:** all 24 region-month factors are available (6–11 valid years each). Factors are
mostly 4–8; monsoon months are lowest and least certain (e.g. Punjab Aug 1.73, interval
0.60–2.40).

**Interpretation.** Combined Terra + Aqua (two satellites, roughly four overpasses a day) is
compared with one VIIRS satellite (roughly two). The factor therefore captures differences in
observation opportunities and overpass timing as well as detection sensitivity. It is an
empirical, regional adjustment, not a physical conversion, and VIIRS is a reference rather than
ground truth.

## 4. Harmonized series

Each month receives a `source_flag` from its coverage:

| Flag | Rule | Harmonized value *H* |
|---|---|---|
| `terra_only_unharmonized` | MODIS observed by Terra only (Nov 2000 – Jun 2002) | none |
| `partial_modis_platform_coverage` | Terra + Aqua present, not both complete (Jul 2002) | none |
| `estimated_from_modis` | Before VIIRS, combined MODIS complete, factor available | `M × r_m` |
| `estimate_unavailable_no_factor` | As above but factor unavailable | none |
| `partial_viirs_month` | VIIRS partial (Jan 2012) | none |
| `viirs_reference` | VIIRS complete | `V` |
| `modis_only_after_reference` | After the VIIRS record ends (Aug 2026) | none — not extrapolated |

Flags are derived from the data, not hard-coded dates; the dates above are what the supplied
archives produce.

## 5. Uncertainty

For each region and calendar month with enough valid years:

1. Take the valid training ratios *r<sub>y,m</sub>*.
2. Resample them with replacement and take the median; repeat `BOOTSTRAP_ITERATIONS` (2,000)
   times with a generator seeded from (`BOOTSTRAP_SEED` = 42, region, month).
3. The 2.5th and 97.5th percentiles give *r<sub>m,lower</sub>*, *r<sub>m,upper</sub>*.

Estimated months get the interval

$$\left[M_{y,m}\, r_{m,\text{lower}},\; M_{y,m}\, r_{m,\text{upper}}\right]$$

This is a **95% bootstrap calibration-factor uncertainty interval**. It excludes satellite
measurement uncertainty, cloud-related omission, detection-algorithm uncertainty, spatial
heterogeneity, temporal fire variability and other instrument differences, and it is not a
prediction interval. No interval is produced for VIIRS reference months or when too few valid
years exist.

## 6. Validation

Validation window: complete overlapping months **Jan 2023 – Jul 2026**, never used for fitting.
For each month: observed *V*, raw MODIS *M*, and prediction *V̂ = M × r<sub>m</sub>*.

$$\text{MAE}=\frac1n\sum|V_i-\hat V_i| \qquad \text{RMSE}=\sqrt{\frac1n\sum(V_i-\hat V_i)^2}$$

$$\text{WAPE}=\frac{\sum|V_i-\hat V_i|}{\sum V_i}\times100 \qquad \text{Bias}=\frac{\sum(\hat V_i-V_i)}{\sum V_i}\times100$$

Zero denominators give `NaN`. The same metrics are reported for raw MODIS (*V̂ = M*) and for a
single constant factor per region (diagnostic baseline).

| | Punjab | Haryana |
|---|---|---|
| Months | 43 | 43 |
| WAPE raw → seasonal | 75.0% → 49.1% | 81.2% → 34.0% |
| Bias seasonal | +15.4% | −15.0% |
| WAPE constant factor | 44.5% | 32.9% |

### Orbit drift

`overpass_times.csv` gives the median daytime detection time per satellite and year. Terra and
Aqua were stable until about 2021 and then drifted (Aqua ~13:45 → ~15:07 IST in 2025; Terra
~11:20 → ~10:06 IST), while Suomi-NPP stayed near 13:40. In Punjab the burning-season V/M ratio
was 4.3–5.3 every training year and fell to 3.6, 2.2 and 1.3 in 2023–2025. The validation window
therefore tests the factors under observing conditions different from training. The backcast
period (2002–2011) has overpass times matching the training years.

### Supplementary stable-orbit check

A leave-one-year-out cross-validation over 2012–2021 refits the factors without the held-out
year and predicts it. Seasonal WAPE is **12.5% (Punjab) and 11.3% (Haryana)** with bias near 0,
versus 14.6% / 13.6% for a constant factor. Because it re-uses training-period data, it is
labelled supplementary and does not replace the independent hold-out.

## 7. Anomalies

For each complete harmonized month (estimated or observed):

$$A_{y,m} = H_{y,m} - \operatorname{median}\left(H_{y',m} : y' \ne y\right) \qquad A_{\%} = \frac{A_{y,m}}{\operatorname{median}(\cdot)}\times 100$$

The baseline is the same calendar month in all other years (leave-one-out), requiring at least 5
years. `A%` is undefined for a zero baseline. Labels: *above* if `A% > +20`, *below* if
`A% < −20`, otherwise *near* (zero baseline: *near* if `H = 0`, else *above*). Partial,
Terra-only and unavailable months are excluded. Baselines mix estimated and observed years; the
number of estimated baseline years is reported. An unusual count is not, by itself, an emergency.

## 8. Common grid

Detections are also assigned to ~1 km square cells in UTM zone 43N (EPSG:32643; the whole study
area lies within the zone's 72–78°E band, which is checked). The grid is for maps only;
calibration uses state-level monthly totals. Cell counts are detections, not unique fires.
