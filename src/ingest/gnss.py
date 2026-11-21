"""GNSS/CORS control points: shift an outline onto surveyed coordinates.

A CORS network (Survey of India) gives centimetre-accurate positions. A surveyor records a few corners of the
building with a GNSS rover; this module compares them to the same corners on the map outline and applies the
average shift, so the recorded volumes sit where the ground truth is, not where the map volunteer drew them.
CSV columns: name, lat, lon  (WGS84 / EPSG:4326, as CORS-corrected receivers report). Matched to the nearest
outline vertex within max_match_m; the mean residual after shifting is reported as the fit quality.
Usage: python -m src.ingest.gnss outline.geojson points.csv -o outline_gnss.geojson
"""
import argparse
import logging
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import affinity
from shapely.geometry import Point

log = logging.getLogger(Path(__file__).stem)


def apply_control_points(footprint: gpd.GeoDataFrame, points: pd.DataFrame, max_match_m: float = 5.0) -> tuple[gpd.GeoDataFrame, dict]:
    for col in ("lat", "lon"):
        if col not in points:
            raise ValueError("control point CSV needs columns name, lat, lon")
    crs = footprint.estimate_utm_crs()
    m = footprint.to_crs(crs)
    pts = gpd.GeoSeries([Point(x, y) for x, y in zip(points.lon, points.lat)], crs="EPSG:4326").to_crs(crs)
    verts = np.array(m.geometry.iloc[0].exterior.coords[:-1])
    dx, dy, used = [], [], []
    for i, p in enumerate(pts):
        d = np.hypot(verts[:, 0] - p.x, verts[:, 1] - p.y)
        j = int(d.argmin())
        if d[j] <= max_match_m:
            dx.append(p.x - verts[j, 0]); dy.append(p.y - verts[j, 1]); used.append(i)
    if len(used) < 2:
        raise ValueError(f"only {len(used)} control points matched an outline corner within {max_match_m} m; need at least 2")
    sx, sy = float(np.mean(dx)), float(np.mean(dy))
    resid = float(np.mean(np.hypot(np.array(dx) - sx, np.array(dy) - sy)))
    m["geometry"] = m.geometry.apply(lambda g: affinity.translate(g, sx, sy))
    out = m.to_crs("EPSG:4326")
    out["outline_source"] = "gnss_adjusted"
    rep = {"points_used": len(used), "shift_east_m": round(sx, 3), "shift_north_m": round(sy, 3), "residual_m": round(resid, 3)}
    return out, rep


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("outline", type=Path)
    p.add_argument("csv", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    for f in (a.outline, a.csv):
        if not f.exists():
            sys.exit(f"input not found: {f}")
    fp, pts = gpd.read_file(a.outline), pd.read_csv(a.csv)
    log.info("read %s and %s (%d control points)", a.outline, a.csv, len(pts))
    out, rep = apply_control_points(fp, pts)
    out.to_file(a.output, driver="GeoJSON")
    log.info("processed: %s; wrote %s", rep, a.output)


if __name__ == "__main__":
    main()
