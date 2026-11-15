# IGNIS
### Harmonizing Satellite Fire Observations Across Time

**Live Website:** https://ignisearth.wiki

IGNIS is a satellite fire-data harmonization and visualization platform developed for the **NASA Space Apps Challenge 2026**. It addresses the inconsistencies between MODIS and VIIRS satellite observations to make historical hotspot activity more comparable across time.

## Overview

Different satellite sensors detect fires at different spatial resolutions and with different detection capabilities. Consequently, changes in recorded hotspot counts do not necessarily represent actual changes in fire activity.

IGNIS addresses this problem by harmonizing historical MODIS observations against VIIRS reference observations, creating a more consistent historical record for analysis.

The platform focuses on **Punjab and Haryana, India**, with independent regional selection.

## Key Features

- **Historical Fire Map:** Geographical visualization of satellite hotspot detections across Punjab and Haryana.
- **Harmonization & Comparison:** Compare raw MODIS observations, VIIRS observations and calibrated MODIS estimates.
- **Burning Activity Calendar:** Explore monthly hotspot activity through a year-by-year heatmap.
- **Anomaly Analysis:** Identify months with unusually high or low detection activity relative to historical seasonal patterns.
- **Historical Trends:** Examine long-term changes in satellite-observed hotspot activity.
- **Methodology & Data Quality:** Explore sensor characteristics, confidence filtering, data coverage, calibration methodology and limitations.

## Data Sources

IGNIS uses historical satellite active-fire archives from **NASA FIRMS (Fire Information for Resource Management System)**.

| Satellite sensor | Dataset | Coverage |
|---|---|---|
| MODIS | Collection 6.1 (Terra + Aqua) | 2000–2026 |
| VIIRS | Suomi-NPP Collection 2 | 2012–2026 |

Both datasets are standardized and processed to enable regional and monthly comparisons.

## Harmonization Methodology

IGNIS uses an empirical calibration approach to account for differences in detection counts between MODIS and VIIRS.

The calibration process:

1. Standardizes observations from both satellite datasets.
2. Aggregates hotspot detections by region and calendar month.
3. Compares MODIS and VIIRS observations during their overlapping period.
4. Calculates monthly calibration factors using the median of year-specific VIIRS-to-MODIS ratios.
5. Applies these factors to historical MODIS observations to estimate activity on the VIIRS reference scale.


The calibration factor is:

$$
r_m = \operatorname{median}_y
\left(
\frac{VIIRS_{y,m}}{MODIS_{y,m}}
\right)
$$

The harmonized estimate is:

$$
H_{y,m} = MODIS_{y,m} \times r_m
$$


Calibration factors are trained using February 2012–December 2022 and independently evaluated against January 2023–July 2026 observations.

The final harmonized record uses calibrated MODIS estimates for the pre-VIIRS period and actual VIIRS observations from February 2012 onward.

## Technology Stack

- **Language:** Python
- **Application:** Streamlit
- **Data Processing:** Pandas, NumPy, GeoPandas, PyArrow
- **Geospatial Analysis:** Shapely
- **Visualization:** Plotly, PyDeck
- **Testing:** Pytest

## Data Interpretation & Limitations

- Hotspot detections represent satellite-observed thermal anomalies, not unique fires or confirmed wildfire incidents.
- MODIS and VIIRS have different spatial resolutions and detection characteristics.
- Harmonization improves historical comparability but does not make the sensors identical.
- Calibration is empirical and specific to the selected regions and datasets.
- Calibration uncertainty is considered for historical estimates.
- Partial observation months are identified separately to avoid misleading comparisons.
- Only historical archive data is included; near-real-time monitoring is outside the current project scope.


## License

The IGNIS source code is licensed under the **MIT License**. See the [LICENSE](LICENSE) file for details.

Third-party datasets, including NASA FIRMS satellite observations, remain subject to their respective terms of use and attribution requirements.

---

*IGNIS aims to make long-term satellite fire observations more consistent, interpretable and useful for historical analysis.*
