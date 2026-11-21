"""Footprint + height -> one 3D prism (footprint, z_min, z_max), heights relative to ground.

Usage: python -m src.geometry.extrude data/processed/<id>.geojson -o data/processed/<id>_solid.geojson [--basements 1 --basement-depth 3.0]
"""
import argparse
import logging
import sys
from pathlib import Path

import geopandas as gpd

log = logging.getLogger(Path(__file__).stem)


def extrude(building: gpd.GeoDataFrame, basements: int = 0, basement_depth: float = 3.0) -> gpd.GeoDataFrame:
    out = building.copy()
    out["z_min"] = -basements * basement_depth
    out["z_max"] = out["height_m"]
    out["basements"] = basements
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("footprint", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("--basements", type=int, default=0)
    p.add_argument("--basement-depth", type=float, default=3.0)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    if not a.footprint.exists():
        sys.exit(f"input not found: {a.footprint}")
    b = gpd.read_file(a.footprint)
    if "height_m" not in b or b["height_m"].isna().any():
        sys.exit("footprint has no height_m; cannot extrude")
    log.info("read %s (%d buildings, CRS %s)", a.footprint, len(b), b.crs)
    out = extrude(b, a.basements, a.basement_depth)
    out.to_file(a.output, driver="GeoJSON")
    log.info("processed %d solids: z %.1f to %.1f m", len(out), out.z_min.iloc[0], out.z_max.iloc[0])
    log.info("wrote %s", a.output)


if __name__ == "__main__":
    main()
