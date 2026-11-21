"""Underground utility volumes: a pipe, tunnel or metro corridor crossing the parcel gets its own 3D ULPIN.

Spec: building B00 (not attached to a building), level B0n by depth, unit T0n. The volume is the line
buffered by half its diameter, from -depth-diameter/2 to -depth+diameter/2, in metres.
Input GeoJSON: LineString features with properties network_type (water|sewer|gas|power|telecom|metro|tunnel),
depth_m (to the centre line, positive down), diameter_m, operator (optional).
Usage: python -m src.geometry.utilities utilities.geojson --parent-ulpin 27021500123456 -o <id>_utilities3d.geojson
"""
import argparse
import logging
import sys
from pathlib import Path

import geopandas as gpd

from src.ulpin.generate import clockwise_from_northwest, generate

log = logging.getLogger(Path(__file__).stem)
LEVEL_M = 3.0          # a basement level is ~3 m; a pipe 4 m down is in B02


def make_utilities(lines: gpd.GeoDataFrame, parent_ulpin: str) -> gpd.GeoDataFrame:
    m = lines.to_crs(lines.estimate_utm_crs())
    for col in ("network_type", "depth_m", "diameter_m"):
        if col not in m or m[col].isna().any():
            raise ValueError(f"every utility needs {col}")
    m["geometry"] = m.geometry.buffer(m.diameter_m / 2, cap_style="flat")
    m["z_min"] = -(m.depth_m + m.diameter_m / 2)
    m["z_max"] = -(m.depth_m - m.diameter_m / 2)
    m["level_code"] = m.depth_m.apply(lambda d: f"B{min(9, max(1, int(d // LEVEL_M) + 1)):02d}")
    order = clockwise_from_northwest([(g.centroid.x, g.centroid.y) for g in m.geometry])
    rows = []
    for seq, idx in enumerate(order, start=1):
        r = m.iloc[idx]
        unit_code = f"T{seq:02d}"
        rows.append({"building_no": 0, "level_code": r.level_code, "unit_code": unit_code,
                     "ulpin": generate(parent_ulpin, 0, r.level_code, unit_code),
                     "network_type": r.network_type, "operator": r.get("operator"),
                     "z_min": round(float(r.z_min), 2), "z_max": round(float(r.z_max), 2),
                     "area_m2": round(float(r.geometry.area), 1), "volume_m3": round(float(r.geometry.area * r.diameter_m), 1),
                     "floors_source": "surveyed", "geometry": r.geometry})
    return gpd.GeoDataFrame(rows, crs=m.crs).to_crs("EPSG:4326")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("lines", type=Path)
    p.add_argument("--parent-ulpin", required=True)
    p.add_argument("-o", "--output", type=Path, required=True)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    if not a.lines.exists():
        sys.exit(f"input not found: {a.lines}")
    g = gpd.read_file(a.lines)
    if g.crs is None:
        sys.exit("utility file has no CRS")
    log.info("read %s (%d lines)", a.lines, len(g))
    out = make_utilities(g, a.parent_ulpin)
    out.to_file(a.output, driver="GeoJSON")
    log.info("processed %d utility volumes: %s; wrote %s", len(out), ", ".join(f"{r.ulpin} {r.network_type}" for r in out.itertuples()), a.output)


if __name__ == "__main__":
    main()
