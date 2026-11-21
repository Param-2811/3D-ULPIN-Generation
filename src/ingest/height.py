"""Building height from survey data, no AI needed.

dsm: surface model minus terrain model (two GeoTIFFs, e.g. drone photogrammetry or AHN) inside the footprint.
las: LiDAR points inside the footprint minus the ground around it (LAS/LAZ; uses class 2 = ground, 6 = building when present).
Usage:
  python -m src.ingest.height dsm data/processed/<id>.geojson data/raw/<id>_dsm.tif data/raw/<id>_dtm.tif
  python -m src.ingest.height las data/processed/<id>.geojson data/raw/tile.laz
Both print height_m (median roof minus ground), height_max_m and how many samples were used.
"""
import argparse
import logging
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np

log = logging.getLogger(Path(__file__).stem)


def from_dsm(footprint: gpd.GeoDataFrame, dsm_path: Path, dtm_path: Path) -> dict:
    import rasterio
    from rasterio.mask import mask
    with rasterio.open(dsm_path) as dsm, rasterio.open(dtm_path) as dtm:
        fp = footprint.to_crs(dsm.crs).geometry.iloc[0]
        roof, _ = mask(dsm, [fp.buffer(-1.0)], crop=True, nodata=np.nan, filled=True)   # 1 m in from the edge: no walls
        ring = fp.buffer(3.0).difference(fp.buffer(0.5))                                  # ground just outside the walls
        ground, _ = mask(dtm, [ring], crop=True, nodata=np.nan, filled=True)
    valid = lambda a: a[np.isfinite(a) & (np.abs(a) < 1e6)]   # AHN nodata is 3.4e38, not NaN
    roof, ground = valid(roof[0]), valid(ground[0])
    if roof.size < 10 or ground.size < 10:
        sys.exit("too few elevation samples inside/around the footprint; check the rasters cover the building")
    g = float(np.median(ground))
    return {"height_m": round(float(np.median(roof)) - g, 2), "height_max_m": round(float(np.percentile(roof, 99)) - g, 2),
            "ground_z_m": round(g, 2), "samples": int(roof.size), "height_source": "dsm_dtm"}


def from_las(footprint: gpd.GeoDataFrame, las_path: Path) -> dict:
    import laspy
    from shapely import contains_xy
    with laspy.open(las_path) as f:
        crs = f.header.parse_crs()
        fp = footprint.to_crs(crs).geometry.iloc[0] if crs else footprint.to_crs(footprint.estimate_utm_crs()).geometry.iloc[0]
        if crs is None:
            log.warning("LAS has no CRS; assuming it matches the footprint's UTM zone")
        x0, y0, x1, y1 = fp.buffer(5).bounds
        keep = []
        for pts in f.chunk_iterator(2_000_000):          # stream: a city tile is hundreds of MB, we need a 50 m box
            cx, cy = np.asarray(pts.x), np.asarray(pts.y)
            box = (cx >= x0) & (cx <= x1) & (cy >= y0) & (cy <= y1)
            if box.any():
                keep.append((cx[box], cy[box], np.asarray(pts.z)[box], np.asarray(pts.classification)[box]))
    if not keep:
        sys.exit("no LiDAR points fall within 5 m of the footprint; does the tile cover the building?")
    x, y, z, cls = (np.concatenate(a) for a in zip(*keep))
    inside = contains_xy(fp.buffer(-1.0), x, y)
    ring = contains_xy(fp.buffer(5.0), x, y) & ~contains_xy(fp.buffer(0.5), x, y)
    ground = z[ring & (cls == 2)] if (ring & (cls == 2)).any() else z[ring]
    roof = z[inside & (cls == 6)] if (inside & (cls == 6)).any() else z[inside]
    if roof.size < 20 or ground.size < 20:
        sys.exit(f"too few LiDAR points: {roof.size} on the roof, {ground.size} on the ground; does the tile cover the building?")
    g = float(np.median(ground))
    return {"height_m": round(float(np.median(roof)) - g, 2), "height_max_m": round(float(np.percentile(roof, 99)) - g, 2),
            "ground_z_m": round(g, 2), "samples": int(roof.size), "height_source": "lidar"}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("dsm"); a.add_argument("footprint", type=Path); a.add_argument("dsm", type=Path); a.add_argument("dtm", type=Path)
    b = sub.add_parser("las"); b.add_argument("footprint", type=Path); b.add_argument("las", type=Path)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    for f in [a.footprint] + ([a.dsm, a.dtm] if a.cmd == "dsm" else [a.las]):
        if not f.exists():
            sys.exit(f"input not found: {f}")
    fp = gpd.read_file(a.footprint)
    log.info("read %s", a.footprint)
    r = from_dsm(fp, a.dsm, a.dtm) if a.cmd == "dsm" else from_las(fp, a.las)
    log.info("processed %d samples; height %.2f m (max %.2f), ground %.2f, source %s", r["samples"], r["height_m"], r["height_max_m"], r["ground_z_m"], r["height_source"])
    if "height_m" in fp:
        log.info("register says %.2f m; difference %.2f m", fp.height_m.iloc[0], r["height_m"] - fp.height_m.iloc[0])
    print(r)


if __name__ == "__main__":
    main()
