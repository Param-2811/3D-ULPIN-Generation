"""Cut a small LAS/LAZ around a building out of a city-sized tile, so the demo upload is megabytes, not gigabytes.

Usage: python -m src.ingest.clip_las data/raw/37EN1_19.LAZ data/processed/<id>.geojson -o data/raw/<id>_lidar.laz --margin 30
"""
import argparse
import logging
import sys
from pathlib import Path

import geopandas as gpd
import laspy
import numpy as np

log = logging.getLogger(Path(__file__).stem)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("las", type=Path)
    p.add_argument("footprint", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("--margin", type=float, default=30.0, help="metres around the footprint to keep")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    for f in (a.las, a.footprint):
        if not f.exists():
            sys.exit(f"input not found: {f}")
    with laspy.open(a.las) as src:
        crs = src.header.parse_crs()
        if crs is None:
            sys.exit("LAS has no CRS; cannot place the footprint on it")
        x0, y0, x1, y1 = gpd.read_file(a.footprint).to_crs(crs).total_bounds
        x0, y0, x1, y1 = x0 - a.margin, y0 - a.margin, x1 + a.margin, y1 + a.margin
        log.info("read %s (%d points, CRS %s); clipping to %.0f-%.0f, %.0f-%.0f", a.las, src.header.point_count, crs.to_epsg(), x0, x1, y0, y1)
        n_in = n_out = 0
        with laspy.open(a.output, mode="w", header=src.header) as dst:
            for pts in src.chunk_iterator(2_000_000):
                n_in += len(pts)
                m = (pts.x >= x0) & (pts.x <= x1) & (pts.y >= y0) & (pts.y <= y1)
                if np.any(m):
                    dst.write_points(pts[m]); n_out += int(m.sum())
    log.info("processed %d points, kept %d; wrote %s", n_in, n_out, a.output)


if __name__ == "__main__":
    main()
