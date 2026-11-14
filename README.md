# Ignis

### Harmonizing Satellite Fire Observations Across Time

Ignis is a wildfire analysis and visualization platform developed for the **NASA Space Apps Challenge 2026**. It addresses the challenge of harmonizing active-fire observations from NASA's MODIS and VIIRS satellite instruments to create a more consistent historical record of fire activity.

Different satellite instruments have different spatial resolutions and detection capabilities. Consequently, their observations cannot be directly combined without accounting for these differences.

Ignis aims to make these observations more comparable through data processing, spatial and temporal aggregation, and calibration, allowing users to explore historical fire patterns and identify periods of unusually high burning activity.

## Features

### 1. Historical Fire Analysis

- Explore historical MODIS and VIIRS fire detections.
- Select geographical regions and date ranges.
- Visualize fire hotspots on an interactive map.
- Compare satellite observations across overlapping periods.

### 2. Harmonized Burning Activity Calendar

- View historical fire activity in a month-by-year heatmap.
- Compare observations across different years and seasons.
- Explore a continuous harmonized activity record.
- Identify recurring seasonal fire patterns.

### 3. Sensor Comparison and Calibration

- Compare MODIS and VIIRS detection counts.
- Apply a regional, season-aware calibration methodology.
- Visualize raw and harmonized activity trends.
- Evaluate calibration performance using overlapping observations.

### 4. Historical Anomaly Analysis

- Compare recent fire activity against historical seasonal medians.
- Highlight unusually high or low activity.
- Identify periods that may require further investigation.

### 5. Data Export

- Download processed historical activity data as CSV.
- Access comparison and harmonization results.

### 6. Live Fire Monitoring

- Retrieve near-real-time fire detections using NASA FIRMS.
- Display recent MODIS and VIIRS observations.
- Show the last data update time.

## Data Sources

Ignis uses active-fire observations from NASA's Fire Information for Resource Management System (FIRMS).

| Satellite instrument | Dataset           | Purpose                                 |
| -------------------- | ----------------- | --------------------------------------- |
| MODIS                | MODIS C6.1        | Long-term historical fire observations  |
| VIIRS                | Suomi-NPP 375m    | Sensor overlap and harmonization        |
| VIIRS                | NOAA-20 / NOAA-21 | Optional additional recent observations |

**Data source:** https://firms.modaps.eosdis.nasa.gov/

## Harmonization Methodology

The central component of Ignis is its MODIS–VIIRS harmonization pipeline.

The proposed workflow consists of:

1. **Data acquisition:** Obtain MODIS and VIIRS active-fire datasets for a common geographical region and overlapping observation period.
2. **Data standardization:** Normalize timestamps, coordinates, column names and relevant quality information.
3. **Spatial and temporal aggregation:** Aggregate observations into common geographical grid cells and monthly periods.
4. **Sensor comparison:** Analyze differences in detection counts across the overlapping period.
5. **Calibration:** Estimate regional and seasonal adjustment factors to make historical MODIS observations more comparable with the selected VIIRS reference.
6. **Validation:** Evaluate the calibration using held-out overlapping observations.
7. **Historical reconstruction:** Generate a continuous harmonized monthly activity record.
8. **Visualization:** Present the results through interactive maps, charts and a historical activity calendar.

The calibration is an empirical estimate rather than a universal conversion between satellite instruments. Differences in spatial resolution, observation times and detection characteristics are considered when interpreting the results.

## Technology Stack

| Technology     | Purpose                           |
| -------------- | --------------------------------- |
| Python         | Main programming language         |
| Streamlit      | Interactive web application       |
| Pandas         | Data processing and manipulation  |
| NumPy          | Numerical calculations            |
| Plotly         | Interactive charts and heatmaps   |
| PyDeck         | Geographical visualization        |
| NASA FIRMS API | Near-real-time fire data          |
| Git and GitHub | Version control and collaboration |

## Project Goals

- Improve comparability between MODIS and VIIRS active-fire observations.
- Explore long-term historical burning patterns.
- Provide an accessible visualization of harmonized fire activity.
- Help researchers, environmental analysts and land managers investigate unusual fire activity.
- Demonstrate how satellite observations can support more consistent environmental monitoring.

## Limitations

- Satellite active-fire detections do not necessarily represent unique individual fires.
- MODIS and VIIRS have different detection capabilities and observation characteristics.
- Calibration factors may vary across geographical regions and seasons.
- Historical reconstruction is an estimate and must be interpreted alongside its uncertainty.
- Near-real-time observations may be revised or replaced by standard-quality products.

## Acknowledgements

Developed as part of the **NASA Space Apps Challenge 2026**.

Data provided by NASA FIRMS and its contributing satellite observation systems.

NASA FIRMS: https://firms.modaps.eosdis.nasa.gov/

---

**Ignis - See the patterns. Understand the fire.**