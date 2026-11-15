"""PyDeck map of hotspot detections with real state boundaries."""
from __future__ import annotations

import pandas as pd
import pydeck as pdk

from config.settings import COLORS, REGIONS


def _rgb(hex_color: str, alpha: int = 255) -> list[int]:
    h = hex_color.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)] + [alpha]


SENSOR_RGBA = {"MODIS": _rgb(COLORS["modis"], 200), "VIIRS": _rgb(COLORS["viirs"], 190)}
HEX_RANGE = [_rgb(c) for c in ("#7A2E0B", "#A8380C", "#D9531A", "#FF6B1A", "#FFA94D", "#FFE3A3")]

POINT_TOOLTIP = {
    "html": ("<b>{sensor} · {satellite}</b><br/>{date} {time}<br/>Lat {lat_s}, Lon {lon_s}<br/>"
             "Type {dtype}<br/>Confidence (original): {confidence}<br/>FRP: {frp}"),
    "style": {"backgroundColor": COLORS["surface"], "color": COLORS["text"], "fontSize": "12px"},
}
HEX_TOOLTIP = {
    "html": "<b>{count}</b> detections in this 1 km grid cell",
    "style": {"backgroundColor": COLORS["surface"], "color": COLORS["text"], "fontSize": "12px"},
}


def boundary_layers(geojson_by_region: dict[str, dict], selected: str) -> list[pdk.Layer]:
    """Selected state in subtle orange, other study state in neutral grey."""
    layers = []
    for region in REGIONS:
        gj = geojson_by_region.get(region)
        if gj is None:
            continue
        sel = region == selected
        layers.append(pdk.Layer(
            "GeoJsonLayer", gj, id=f"boundary-{region}", stroked=True, filled=True,
            get_fill_color=_rgb(COLORS["primary"], 18) if sel else [120, 120, 120, 8],
            get_line_color=_rgb(COLORS["primary"], 230) if sel else [150, 150, 150, 160],
            line_width_min_pixels=2 if sel else 1, pickable=False))
    return layers


def point_layer(records: pd.DataFrame) -> pdk.Layer:
    return pdk.Layer("ScatterplotLayer", records, id="detections", get_position=["lon", "lat"],
                     get_fill_color="color", get_radius=350, radius_min_pixels=1.5,
                     radius_max_pixels=6, pickable=True, opacity=0.85)


def density_layer(cells: pd.DataFrame) -> pdk.Layer:
    """Common 1 km grid cells coloured by detection count (columns lon, lat, count, color)."""
    return pdk.Layer("ScatterplotLayer", cells, id="density", get_position=["lon", "lat"],
                     get_fill_color="color", get_radius=500, radius_min_pixels=1.5,
                     pickable=True, opacity=0.9)


def color_by_count(counts: pd.Series) -> tuple[list[list[int]], list[str]]:
    """Quantile bins of cell counts -> colours, plus readable bin labels."""
    import numpy as np
    qs = np.unique(np.quantile(counts, np.linspace(0, 1, len(HEX_RANGE) + 1)))
    if len(qs) < 2:
        return [HEX_RANGE[-1]] * len(counts), [f"{int(qs[0])}"]
    idx = np.clip(np.searchsorted(qs, counts, side="right") - 1, 0, len(qs) - 2)
    step = (len(HEX_RANGE) - 1) / max(len(qs) - 2, 1)
    colors = [HEX_RANGE[int(round(i * step))] for i in idx]
    labels = [f"{int(qs[i])}–{int(qs[i + 1])}" for i in range(len(qs) - 1)]
    return colors, labels


def build_deck(layers: list[pdk.Layer], bounds: list[float] | None, tooltip: dict) -> pdk.Deck:
    """Deck centred on the selected state's bounds (dark CARTO basemap)."""
    if bounds:
        lon = (bounds[0] + bounds[2]) / 2
        lat = (bounds[1] + bounds[3]) / 2
        span = max(bounds[2] - bounds[0], bounds[3] - bounds[1])
        zoom = 6.7 if span < 3.2 else 6.4  # whole state visible at ~560 px height
    else:
        lon, lat, zoom = 75.8, 30.0, 6.3
    return pdk.Deck(layers=layers, map_provider="carto", map_style="dark",
                    initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=zoom),
                    tooltip=tooltip)


def legend_html(show_modis: bool, show_viirs: bool, density: bool,
                bins: list[str] | None = None) -> str:
    items = []
    if density:
        rng = f" ({bins[0].split('–')[0]} → {bins[-1].split('–')[-1]} per cell)" if bins else ""
        items.append('<span><i style="background:linear-gradient(90deg,#7A2E0B,#FF6B1A,#FFE3A3);'
                     f'width:48px;border-radius:2px"></i>Detections per 1 km cell, quantile colours{rng}</span>')
    else:
        if show_modis:
            items.append(f'<span><i style="background:{COLORS["modis"]}"></i>MODIS (Terra/Aqua)</span>')
        if show_viirs:
            items.append(f'<span><i style="background:{COLORS["viirs"]}"></i>VIIRS Suomi-NPP</span>')
    items.append(f'<span><i class="line" style="background:{COLORS["primary"]}"></i>Selected state boundary</span>')
    items.append('<span><i class="line" style="background:#969696"></i>Other study state</span>')
    return '<div class="ignis-legend">' + "".join(items) + "</div>"
