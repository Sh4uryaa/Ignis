# IGNIS architecture

IGNIS has two halves that only meet through files in `data/processed/`:

```
NASA ZIPs ──► processing pipeline (CLI, no Streamlit) ──► data/processed/*.csv|parquet|json
                                                                │
                                   Streamlit website ◄──────────┘  (read-only, cached)
```

The pipeline is run once (`python -m scripts.run_pipeline`); the website never recomputes
science per click.

## Folders

| Folder | Responsibility | Uses Streamlit? |
|---|---|---|
| `config/` | `settings.py`: every path, policy, period, threshold and colour token; `regions.py`: the study-region registry | No |
| `assets/` | `styles.css` (the single stylesheet / design tokens) and `earth_hero.svg` (hero illustration) | — |
| `processing/` | All data processing and scientific calculations | **No** |
| `scripts/` | Command-line entry points | No |
| `services/` | Load processed outputs (cached) and prepare page data | Loading only |
| `components/` | Reusable visual pieces (charts, map, cards, filters, exports) | Yes |
| `pages/` | One file per page: layout, calling services and components | Yes |
| `utils/` | Small shared helpers (dates, formatting, chart styling, logging) | No |
| `tests/` | Pytest suite (synthetic fixtures + checks on processed outputs) | AppTest only |
| `app.py` | Page config, styles, navigation, dispatch — nothing else | Yes |

## Pipeline (`processing/`)

| Module | Role |
|---|---|
| `extract_archives.py` | Find ZIPs, extract only `fire_archive_*.csv`, ignore NRT |
| `read_source.py` | Read CSVs, validate the 15 FIRMS columns |
| `inspect_data.py` | Raw statistics and comparison with expected values |
| `clean_data.py` | Confidence classification and the Nominal + High filter |
| `standardize.py` | Internal schema (dates, platforms, type labels; originals kept) |
| `geo_filter.py` | Boundaries, validation, point-in-polygon, download-polygon coverage |
| `coverage.py` | Per-satellite monthly coverage (complete / partial / none), gaps |
| `aggregate.py` | 1 km UTM grid, monthly counts, region totals, type breakdown |
| `harmonize.py` | Training pairs, seasonal factors, harmonized series + flags |
| `uncertainty.py` | Bootstrap factor intervals, intervals on estimated months |
| `validate.py` | Hold-out metrics, constant-factor baseline, stable-orbit CV |
| `calculate_anomalies.py` | Leave-one-out same-month anomalies |
| `diagnostics.py` | Overpass-time drift by satellite and year |
| `build_outputs.py` | Output file names, writers, quality report |

`scripts/run_pipeline.py` chains them:

```
extract → inspect → standardize → coverage → confidence filter → regions → grid
       → monthly aggregates ─► totals ─► training pairs → factors (+ bootstrap)
                                       ─► harmonized series → uncertainty
                                       ─► validation (+ stable-orbit CV) → anomalies
       → quality_report.json
```

`--skip-ingest` re-runs only the second half from `monthly_region_totals.csv`.

## Outputs (`data/processed/`)

| File | Produced by | Used by pages |
|---|---|---|
| `detections.parquet` | aggregate (retained, in-state detections; local only) | Map fallback |
| `map_detections.parquet` | build_outputs (same rows, map columns only, zstd; **committed**) | Map |
| `grid_monthly.parquet` | aggregate | (available for grid analyses) |
| `monthly_sensor_counts.csv` | aggregate | Methodology downloads |
| `monthly_region_totals.csv` | aggregate | Overview, Harmonization |
| `sensor_monthly_coverage.csv` | coverage | — (diagnostic) |
| `detection_type_breakdown.csv` | aggregate | Overview, downloads |
| `calibration_training_pairs.csv` | harmonize | Harmonization (ratio spread) |
| `calibration_factors.csv` | harmonize + uncertainty | Overview, Harmonization |
| `harmonized_monthly.csv` | harmonize | Overview, Harmonization, Calendar |
| `uncertainty_intervals.csv` | uncertainty | Overview, Harmonization, Calendar |
| `validation_results.csv`, `validation_metrics.csv` | validate | Overview, Harmonization |
| `validation_stable_orbit_cv_*.csv` | validate | Harmonization |
| `overpass_times.csv` | diagnostics | Harmonization |
| `calibrated_modis_monthly.csv` | harmonize (`calibrated_modis_series`) | Harmonization (four-series chart, export) |
| `calibrated_modis_period_metrics.csv`, `calibrated_modis_yearly_metrics.csv` | validate | Harmonization (performance by period / year) |
| `anomaly_results.csv` | calculate_anomalies | Anomalies |
| `quality_report.json` | build_outputs | Overview, Methodology |
| `inspection_report.json` | scripts.inspect_archives | — |

CSV/JSON outputs are small and committed. Parquet files are git-ignored except
`map_detections.parquet` (~25 MB), which is committed so a fresh clone has a working map
without the NASA archives.

## Website

`app.py` registers six pages with `st.navigation(position="hidden")` and draws one shared top
bar (`components/navigation.py`): brand, a searchable region dropdown
(`components/region_selector.py`, options from `config/regions.py`) and a row of page links.
The bar is in normal document flow, so it scrolls away; there is no sidebar. The selected region
lives in `st.session_state["region"]` and every page reads it via `services.region_service`.

**Adding a region:** append a `Region` to `config/regions.py`, add its boundary file, re-run the
pipeline. The dropdown, pages and pipeline pick it up without UI changes.

Overview-specific components: `hero.py` (landing hero), `historical_trend.py` (three-line
MODIS / VIIRS / harmonized chart) and `sensor_coverage.py` (two-row MODIS / VIIRS timeline).
`activity_heatmap.py` draws the GitHub-style fire calendar (quantile bins per region).

| Page | Services | Components |
|---|---|---|
| `overview.py` | data, analytics | hero, metric_cards, historical_trend, sensor_coverage, summary_charts |
| `historical_map.py` | data, region, analytics | filters, fire_map, metric_cards |
| `harmonization.py` | data, analytics | comparison_charts, calibration_charts, data_export |
| `activity_calendar.py` | data, analytics | activity_heatmap, filters, data_export |
| `anomaly_analysis.py` | data, analytics | anomaly_visuals, filters, data_export |
| `methodology.py` | data, region, analytics | metric_cards, data_export |

Caching: small CSVs use `st.cache_data` keyed on file modification time; the 1.5 M-row detection
table uses `st.cache_resource` (shared, read-only). The map filters by region and date before
rendering, aggregates to the 1 km grid above 20,000 detections, and never lets sampling change a
reported total.

Missing inputs fail gracefully: missing processed files show the pipeline command; missing
boundary files show an error and no map (a rectangle is never substituted).

## Development notes

- Streamlit does not hot-reload edited modules under `pages/`; restart `streamlit run app.py`
  after editing a page.
- Colour identity (tokens in `config/settings.py` and `assets/styles.css`): MODIS gold `#FACC15`,
  VIIRS orange `#F97316`, harmonized teal `#2DD4BF`; estimated harmonized values are also dashed.
  Activity magnitude uses the fire scale yellow → orange → red (`FIRE_SCALE`).
- `st.html` strips inline `<svg>`, so the hero globe is embedded as an image data URI; its glow
  animation lives inside the SVG and respects `prefers-reduced-motion`.
- The active nav link is marked by wrapping it in a keyed container (`ignis_nav_active`), since
  Streamlit exposes no stable active-link attribute.
