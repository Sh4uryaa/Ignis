# Data sources

## NASA FIRMS archives

Downloaded from the FIRMS archive download tool (<https://firms.modaps.eosdis.nasa.gov/download/>)
for a custom polygon covering Punjab and Haryana (saved as `data/geo/firms_download_area.wkt`).
The ZIPs are kept locally in `data/raw/incoming/` and are not committed.

### MODIS Collection 6.1 — `MODIS C6.1.zip`

| Property | Value (verified from the file) |
|---|---|
| CSV used | `fire_archive_M-C61_846942.csv` (NRT file `fire_nrt_M-C61_846942.csv` ignored) |
| Rows / columns | 455,872 / 15 |
| Coverage | 2000-11-01 → 2026-08-27 |
| Terra | 100,916 rows, 2000-11-01 → 2026-08-22 |
| Aqua | 354,956 rows, 2002-07-18 → 2026-08-27 |
| Duplicates / missing values | 0 / 0 |
| Confidence | low 13,685 · nominal (30–79) 380,300 · high (80–100) 61,887 |
| Nominal + high | 442,187 |
| Detection types | 0: 448,918 · 2: 6,954 |
| `version` field | 6.03: 424,629 · 61.03: 31,243 (Collection 6.1 was selected; both kept) |

**Documented discrepancy.** The project brief expected high = 67,595 and nominal = 374,592.
No single integer threshold reproduces 67,595, so this appears to be a transcription error. The
low count and the nominal + high total match exactly, so the analytical policy is unaffected.

### VIIRS Suomi-NPP Collection 2 — `SUOMI VIIRS C2.zip`

| Property | Value (verified from the file) |
|---|---|
| CSV used | `fire_archive_SV-C2_846954.csv` (NRT file `fire_nrt_SV-C2_846954.csv` ignored) |
| Rows / columns | 1,291,486 / 15 |
| Coverage | 2012-01-20 → 2026-07-31 |
| Satellite / instrument codes | `SNPP` / `SNPP` (displayed as Suomi-NPP) |
| Duplicates / missing values | 0 / 0 |
| Confidence | l 157,450 · n 1,085,342 · h 48,694 |
| Nominal + high | 1,134,036 |
| Detection types | 0: 1,284,226 · 2: 7,182 · 3: 78 |
| `version` field | 2 |

All checks are re-run by `python -m scripts.inspect_archives` and stored in
`data/processed/inspection_report.json` and `quality_report.json`.

## Administrative boundaries

| Item | Value |
|---|---|
| Source | geoBoundaries gbOpen, India ADM1 (`IND-ADM1-1811400`) |
| URL | <https://www.geoboundaries.org/api/current/gbOpen/IND/ADM1/> (pinned release commit `9469f09`) |
| Upstream | DataMeet India community, Election Commission of India (year represented 2011) |
| Licence | Creative Commons Attribution 2.5 India (CC BY 2.5 IN) |
| CRS | EPSG:4326 |
| Selected features | `IN-PB` Punjab (50,320 km²), `IN-HR` Haryana (44,184 km²) — within 0.1% of official areas, valid, non-overlapping |
| Files | `data/geo/punjab.geojson`, `data/geo/haryana.geojson`, provenance in `data/geo/boundary_provenance.json` (incl. download date) |
| Coverage by FIRMS polygon | 100% of both states (polygon extends ≥ 0.8 km beyond the borders) |

Rebuild with `python -m scripts.prepare_boundaries`. Citation: Runfola, D. et al. (2020)
geoBoundaries: A global database of political administrative boundaries. *PLoS ONE* 15(4):
e0231866.

## Basemap

Map tiles © OpenStreetMap contributors © CARTO (dark style), loaded by PyDeck in the browser.
