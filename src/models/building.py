"""Automated building extraction: an outline from a drone or aerial orthophoto (GeoTIFF) with the pretrained
Segment Anything Model (SAM) via segment-geospatial. No training: SAM is a general 'find the object here' model,
and a building roof is an object. We point at the roof, take that mask, vectorise it, simplify and square the corners.

point: a lon/lat inside the building (the officer's click). Without it, the largest mask touching the image centre.
Output: one polygon in EPSG:4326 with source='sam_orthophoto', plus the raw mask for inspection.
Usage: python -m src.models.building data/raw/demo/ortho_delft.tif --at 4.3461 51.9982 -o data/processed/extracted_outline.geojson
Weights (~375 MB, sam_vit_b) download once to ~/.cache on first use.
"""
import argparse
import logging
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
from shapely.geometry import Point, Polygon, shape

log = logging.getLogger(Path(__file__).stem)


def orthogonalise(poly: Polygon, tol_m: float = 1.5) -> Polygon:
    """Straighten a SAM mask into a wall-like outline: rotate to the building's main axis, snap every vertex
    to a grid, drop tiny steps, rotate back. tol_m is the smallest jog kept (balconies are ~1 m)."""
    from shapely import affinity
    import math
    rect = poly.minimum_rotated_rectangle
    xs, ys = rect.exterior.coords.xy
    ang = math.degrees(math.atan2(ys[1] - ys[0], xs[1] - xs[0]))
    flat = affinity.rotate(poly.buffer(0.5).buffer(-0.5), -ang, origin=rect.centroid)   # close pixel notches first
    flat = flat.simplify(tol_m, preserve_topology=True)
    pts = [(round(x / tol_m) * tol_m, round(y / tol_m) * tol_m) for x, y in flat.exterior.coords]   # snap to grid
    out = [pts[0]]
    for x1, y1 in pts[1:]:
        x0, y0 = out[-1]
        if (x1, y1) == (x0, y0):
            continue
        if x1 != x0 and y1 != y0:          # diagonal: turn into an L via the longer leg first
            out.append((x1, y0) if abs(x1 - x0) >= abs(y1 - y0) else (x0, y1))
        out.append((x1, y1))
    sq = Polygon(out).buffer(0)
    if sq.geom_type == "MultiPolygon":
        sq = max(sq.geoms, key=lambda g: g.area)
    sq = sq.simplify(0.01, preserve_topology=True)   # merge collinear points
    return affinity.rotate(sq, ang, origin=rect.centroid)


def extract(ortho: Path, point_lonlat: tuple[float, float] | None = None, model: str = "vit_b", min_area_m2: float = 40.0) -> tuple[gpd.GeoDataFrame, dict]:
    import rasterio
    from samgeo import SamGeo
    with rasterio.open(ortho) as src:
        crs, transform = src.crs, src.transform
        if crs is None:
            raise ValueError("orthophoto has no CRS; export it georeferenced (GeoTIFF with coordinates)")
    sam = SamGeo(model_type=model, automatic=point_lonlat is None, sam_kwargs=None)
    mask_path = ortho.with_name(ortho.stem + "_mask.tif")
    if point_lonlat is not None:
        sam.set_image(str(ortho))
        sam.predict(point_coords=[list(point_lonlat)], point_labels=[1], point_crs="EPSG:4326", output=str(mask_path))
    else:
        sam.generate(str(ortho), output=str(mask_path), foreground=True, unique=True)
    polys = gpd.read_file(sam.tiff_to_gpkg(str(mask_path), str(mask_path.with_suffix(".gpkg")), simplify_tolerance=None) or mask_path.with_suffix(".gpkg"))
    polys = polys[polys.geometry.notna()].set_crs(crs, allow_override=True)
    m = polys.to_crs(polys.estimate_utm_crs())
    m = m[m.geometry.area >= min_area_m2]
    if m.empty:
        raise ValueError("SAM found no building-sized region; try a point inside the roof")
    if point_lonlat is not None:
        pt = gpd.GeoSeries([Point(point_lonlat)], crs="EPSG:4326").to_crs(m.crs).iloc[0]
        hit = m[m.geometry.contains(pt)]
        chosen = hit.iloc[0].geometry if not hit.empty else m.iloc[m.geometry.distance(pt).argmin()].geometry
    else:
        chosen = m.iloc[m.geometry.area.argmax()].geometry
    if chosen.geom_type == "MultiPolygon":
        chosen = max(chosen.geoms, key=lambda g: g.area)
    raw_area = float(chosen.area)
    squared = orthogonalise(chosen)
    out = gpd.GeoDataFrame([{"outline_source": "sam_orthophoto", "raw_area_m2": round(raw_area, 1), "area_m2": round(float(squared.area), 1),
                             "vertices": len(squared.exterior.coords) - 1, "geometry": squared}], crs=m.crs).to_crs("EPSG:4326")
    rep = {"masks": int(len(polys)), "candidates_over_min_area": int(len(m)), "raw_area_m2": round(raw_area, 1),
           "squared_area_m2": round(float(squared.area), 1), "vertices": int(len(squared.exterior.coords) - 1)}
    return out, rep


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("ortho", type=Path)
    p.add_argument("--at", nargs=2, type=float, metavar=("LON", "LAT"), help="a point inside the roof")
    p.add_argument("--model", default="vit_b", choices=["vit_b", "vit_l", "vit_h"])
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("--compare", type=Path, help="known outline GeoJSON to score against (IoU)")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    if not a.ortho.exists():
        sys.exit(f"input not found: {a.ortho}")
    log.info("read %s", a.ortho)
    out, rep = extract(a.ortho, tuple(a.at) if a.at else None, a.model)
    out.to_file(a.output, driver="GeoJSON")
    log.info("processed 1 outline from %d SAM masks: %.0f m2 raw, %.0f m2 squared, %d corners; wrote %s", rep["masks"], rep["raw_area_m2"], rep["squared_area_m2"], rep["vertices"], a.output)
    if a.compare and a.compare.exists():
        ref = gpd.read_file(a.compare).to_crs(out.estimate_utm_crs()).geometry.iloc[0]
        got = out.to_crs(ref.crs if hasattr(ref, "crs") else out.estimate_utm_crs()).geometry.iloc[0]
        iou = got.intersection(ref).area / got.union(ref).area
        log.info("IoU against %s: %.3f (1.0 = identical outline)", a.compare, iou)
        print({**rep, "iou_vs_reference": round(float(iou), 3)})
    else:
        print(rep)


if __name__ == "__main__":
    main()
