"""Rule-based topology checks on unit prisms. Pure Python; PostGIS cross-check comes in Phase 7.

Every finding: {"check": ..., "ulpin": ..., "message": ...}. Empty list = clean.
Usage: python -m src.validate.checks data/processed/<id>_units3d.geojson data/processed/<id>_floors.geojson -o data/processed/<id>_report.json
"""
import argparse
import json
import logging
import sys
from pathlib import Path

import geopandas as gpd

from src.ulpin.generate import validate as ulpin_ok

log = logging.getLogger(Path(__file__).stem)
AREA_TOL = 0.5      # m2 of footprint overlap tolerated (floating-point slivers)
GAP_TOL = 0.02      # 2% of a level's area may be unassigned (walls, lift core)
EDGE_TOL = 0.05     # m a unit may poke outside the building outline


def _z_overlap(a, b) -> bool:
    return a.z_min < b.z_max and b.z_min < a.z_max


def run_checks(units: gpd.GeoDataFrame, floors: gpd.GeoDataFrame) -> list[dict]:
    crs = units.estimate_utm_crs()
    u, f = units.to_crs(crs), floors.to_crs(crs)
    out = []

    dup = u.ulpin[u.ulpin.duplicated()].unique()
    out += [{"check": "duplicate_id", "ulpin": d, "message": "ULPIN assigned to more than one volume"} for d in dup]
    out += [{"check": "bad_id", "ulpin": x, "message": "ULPIN fails format or check digit"} for x in u.ulpin if not ulpin_ok(x)]

    sidx = u.sindex
    seen = set()
    for i, a in u.iterrows():
        for j in sidx.query(a.geometry, predicate="intersects"):
            b = u.iloc[j]
            key = tuple(sorted((a.ulpin, b.ulpin)))
            if a.ulpin == b.ulpin or key in seen or not _z_overlap(a, b):
                continue
            seen.add(key)
            ov = a.geometry.intersection(b.geometry).area
            if ov > AREA_TOL:
                out.append({"check": "overlap", "ulpin": a.ulpin, "message": f"overlaps {b.ulpin} by {ov:.1f} m2 on shared height range"})

    env = f.dissolve().geometry.iloc[0].buffer(EDGE_TOL)
    zmin, zmax = f.z_min.min(), f.z_max.max()
    slab_levels = sorted(set(f.z_min.round(2)))
    for _, a in u.iterrows():
        if not a.geometry.within(env):
            out.append({"check": "containment", "ulpin": a.ulpin, "message": "footprint extends outside the building outline"})
        if a.z_min < zmin - 1e-6 or a.z_max > zmax + 1e-6:
            out.append({"check": "containment", "ulpin": a.ulpin, "message": f"height {a.z_min}-{a.z_max} outside building {zmin}-{zmax}"})
        if round(a.z_min, 2) not in slab_levels:
            out.append({"check": "floating", "ulpin": a.ulpin, "message": f"z_min {a.z_min} matches no floor slab {slab_levels}"})

    for _, lv in f.iterrows():
        on_level = u[u.level_code == lv.level_code]
        ratio = on_level.area.sum() / lv.geometry.area if lv.geometry.area else 0
        if ratio < 1 - GAP_TOL:
            out.append({"check": "gap", "ulpin": None, "level": lv.level_code, "message": f"units cover only {ratio:.1%} of level {lv.level_code}"})
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("units", type=Path)
    p.add_argument("floors", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    for x in (a.units, a.floors):
        if not x.exists():
            sys.exit(f"input not found: {x}")
    u, f = gpd.read_file(a.units), gpd.read_file(a.floors)
    log.info("read %d units, %d levels", len(u), len(f))
    findings = run_checks(u, f)
    a.output.write_text(json.dumps({"units": len(u), "levels": len(f), "findings": findings}, indent=2), encoding="utf-8")
    log.info("processed %d units: %d findings; wrote %s", len(u), len(findings), a.output)
    for x in findings[:10]:
        print(x)
    print("CLEAN" if not findings else f"{len(findings)} PROBLEMS")


if __name__ == "__main__":
    main()
