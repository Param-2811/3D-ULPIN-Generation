"""Subdivide each level slab into unit volumes and stamp each with a 3D ULPIN.

Units per level = official unit count spread over above-ground levels (no floor plan available);
basements get parking slots (P). Each level is cut into equal-area strips along its long axis.
Measurement happens in the local UTM zone (metres); output stays EPSG:4326.
Usage: python -m src.geometry.units data/processed/<id>_floors.geojson --parent-ulpin 03100000000071 --units 84 -o data/processed/<id>_units3d.geojson
"""
import argparse
import logging
import math
import sys
from pathlib import Path

import geopandas as gpd
from shapely import affinity
from shapely.geometry import box

from src.ulpin.generate import clockwise_from_northwest, generate

log = logging.getLogger(Path(__file__).stem)


def split_strips(poly, k: int) -> list:
    """Cut poly into k equal-width strips along the long side of its minimum rotated rectangle."""
    if k <= 1:
        return [poly]
    rect = poly.minimum_rotated_rectangle
    xs, ys = rect.exterior.coords.xy
    # ponytail: strips by width, not area; equal enough for a rectangular block, fix with area bisection if needed
    dx, dy = xs[1] - xs[0], ys[1] - ys[0]
    angle = math.degrees(math.atan2(dy, dx))
    flat = affinity.rotate(poly, -angle, origin=rect.centroid)
    x0, y0, x1, y1 = flat.bounds
    if (x1 - x0) < (y1 - y0):
        flat = affinity.rotate(flat, 90, origin=rect.centroid)
        angle += 90
        x0, y0, x1, y1 = flat.bounds
    w = (x1 - x0) / k
    pieces = [flat.intersection(box(x0 + i * w, y0, x0 + (i + 1) * w, y1)) for i in range(k)]
    return [affinity.rotate(pc, angle, origin=rect.centroid) for pc in pieces if not pc.is_empty]


def make_units(floors: gpd.GeoDataFrame, parent_ulpin: str, total_units: int, building_no: int = 1,
               parking_per_basement: int = 20, plan_units: gpd.GeoDataFrame | None = None) -> gpd.GeoDataFrame:
    """plan_units: polygons from src/models/floorplan.py predict (any CRS). When given, every above-ground
    level uses those shapes instead of equal strips; total_units is then ignored."""
    m = floors.to_crs(floors.estimate_utm_crs())
    above = [c for c in m.level_code if not c.startswith("B")]
    plan = plan_units.to_crs(m.crs) if plan_units is not None else None
    # spread the unit count over the levels that have no plan of their own
    planned = set(plan.level_code) if plan is not None and "level_code" in plan else set()
    strip_levels = [c for c in above if c not in planned] or above
    per_level = {c: (total_units // len(strip_levels) + (i < total_units % len(strip_levels))) if c in strip_levels else 0 for i, c in enumerate(above)}
    # the ID format has two digits for the unit, so 99 per level is the ceiling (spec: U01-U99)
    worst = max(per_level.values(), default=0)
    if worst > 99:
        raise ValueError(f"{total_units} units over {len(strip_levels)} level(s) is {worst} on one level; the 3D ULPIN allows 99 per level. "
                         f"Check the floor count (a {total_units}-unit building usually has more floors), or upload floor plans")
    if parking_per_basement > 99:
        raise ValueError("at most 99 parking slots per basement level")
    rows = []
    for _, lv in m.iterrows():
        code = lv.level_code
        is_base = code.startswith("B")
        k = parking_per_basement if is_base else per_level[code]
        on_level = plan[plan.level_code == code] if plan is not None and "level_code" in plan else plan
        if on_level is not None and not is_base and len(on_level):
            # a unit is one piece: clipping to the outline can split a drawn flat, keep its largest part
            pieces = [max(g.geoms, key=lambda q: q.area) if g.geom_type == "MultiPolygon" else g
                      for g in on_level.geometry.intersection(lv.geometry) if not g.is_empty and g.area > 1]
            pieces = [g for g in pieces if g.geom_type == "Polygon"]
        else:
            pieces = split_strips(lv.geometry, k)   # no plan for this level: equal strips (k=0 -> one volume for the whole floor)
        if len(pieces) > 99:
            raise ValueError(f"level {code}: {len(pieces)} units drawn, the 3D ULPIN allows 99 per level")
        order = clockwise_from_northwest([(pc.centroid.x, pc.centroid.y) for pc in pieces])
        for seq, idx in enumerate(order, start=1):
            pc = pieces[idx]
            unit_code = f"{'P' if is_base else 'U'}{seq:02d}"
            h = lv.z_max - lv.z_min
            rows.append({"pand_id": lv.pand_id, "building_no": building_no, "level_code": code, "unit_code": unit_code,
                         "ulpin": generate(parent_ulpin, building_no, code, unit_code),
                         "z_min": lv.z_min, "z_max": lv.z_max, "area_m2": round(pc.area, 1),
                         "volume_m3": round(pc.area * h, 1), "floors_source": lv.floors_source, "geometry": pc})
    return gpd.GeoDataFrame(rows, crs=m.crs).to_crs("EPSG:4326")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("floors", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("--parent-ulpin", required=True, help="14-digit parent ULPIN")
    p.add_argument("--units", type=int, required=True, help="official unit count for the building")
    p.add_argument("--building-no", type=int, default=1)
    p.add_argument("--plan-units", type=Path, help="GeoJSON from src.models.floorplan predict; replaces equal strips")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    if not a.floors.exists():
        sys.exit(f"input not found: {a.floors}")
    f = gpd.read_file(a.floors)
    log.info("read %s (%d levels)", a.floors, len(f))
    plan = None
    if a.plan_units:
        if not a.plan_units.exists():
            sys.exit(f"input not found: {a.plan_units}")
        plan = gpd.read_file(a.plan_units)
        if len(plan) == 0:
            sys.exit(f"{a.plan_units} has no apartment polygons; refusing to produce a building with empty floors")
        log.info("read %s (%d apartment polygons from the floor-plan model)", a.plan_units, len(plan))
    out = make_units(f, a.parent_ulpin, a.units, a.building_no, plan_units=plan)
    if out.ulpin.duplicated().any():
        sys.exit("duplicate ULPINs generated; ordering rule broken")
    out.to_file(a.output, driver="GeoJSON")
    log.info("processed %d unit volumes on %d levels, all ULPINs unique", len(out), out.level_code.nunique())
    log.info("wrote %s", a.output)
    print(out.drop(columns="geometry").head(6).to_string())


if __name__ == "__main__":
    main()
