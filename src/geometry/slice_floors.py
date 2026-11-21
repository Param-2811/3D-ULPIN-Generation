"""Split a 3D prism into level slabs: B0n basements, G00 ground, F0n floors. One feature per level.

Floor count: official (floors_official) > estimated (floors_estimated, from src/models/floors.py) > rule of thumb (height / floor_height).
Usage: python -m src.geometry.slice_floors data/processed/<id>_solid.geojson -o data/processed/<id>_floors.geojson
"""
import argparse
import logging
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

log = logging.getLogger(Path(__file__).stem)


def floor_count(row, floor_height: float) -> tuple[int, str]:
    if pd.notna(row.get("floors_official")):
        return int(row["floors_official"]), "official"
    if pd.notna(row.get("floors_estimated")):
        return int(row["floors_estimated"]), "estimated"
    return max(1, round(row["height_m"] / floor_height)), "rule_of_thumb"


def slice_floors(solid: gpd.GeoDataFrame, floor_height: float = 3.0) -> gpd.GeoDataFrame:
    rows = []
    for _, b in solid.iterrows():
        n, src = floor_count(b, floor_height)
        slab = b["height_m"] / n
        basements = int(b.get("basements", 0) or 0)
        depth = -b["z_min"] / basements if basements else 0
        levels = [(f"B{k:02d}", -k * depth, -(k - 1) * depth) for k in range(basements, 0, -1)]
        levels += [("G00" if i == 0 else f"F{i:02d}", i * slab, (i + 1) * slab) for i in range(n)]
        for code, z0, z1 in levels:
            rows.append({"pand_id": b["pand_id"], "level_code": code, "z_min": round(z0, 2), "z_max": round(z1, 2),
                         "floors": n, "floors_source": src, "geometry": b.geometry})
    return gpd.GeoDataFrame(rows, crs=solid.crs)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("solid", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("--floor-height", type=float, default=3.0)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    if not a.solid.exists():
        sys.exit(f"input not found: {a.solid}")
    s = gpd.read_file(a.solid)
    log.info("read %s (%d solids)", a.solid, len(s))
    out = slice_floors(s, a.floor_height)
    out.to_file(a.output, driver="GeoJSON")
    for pid, g in out.groupby("pand_id"):
        log.info("%s: %d levels (%s), codes %s", pid, len(g), g.floors_source.iloc[0], " ".join(g.level_code))
    log.info("processed %d levels; wrote %s", len(out), a.output)


if __name__ == "__main__":
    main()
