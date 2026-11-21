"""Export unit volumes as CityJSON 2.0: one Building with one BuildingUnit Solid per 3D ULPIN.

Vertices are metres in the building's UTM zone (CityJSON needs a projected CRS); attributes carry the ULPIN.
Usage: python -m src.db.export_cityjson data/processed/<id>_units3d.geojson -o data/processed/<id>.city.json
"""
import argparse
import json
import logging
import sys
from pathlib import Path

import geopandas as gpd

log = logging.getLogger(Path(__file__).stem)


def prism_solid(ring_xy, z0, z1, vertices: list) -> list:
    """Closed solid from a footprint ring: bottom, top, one wall per edge. Returns CityJSON boundaries."""
    ring = list(ring_xy)[:-1] if ring_xy[0] == ring_xy[-1] else list(ring_xy)
    base = len(vertices)
    vertices += [[x, y, z0] for x, y in ring] + [[x, y, z1] for x, y in ring]
    n = len(ring)
    bottom = [base + i for i in range(n)][::-1]          # outward normal points down
    top = [base + n + i for i in range(n)]
    walls = [[base + i, base + (i + 1) % n, base + n + (i + 1) % n, base + n + i] for i in range(n)]
    return [[[bottom]], [[top]], *[[[w]] for w in walls]]


def to_cityjson(units: gpd.GeoDataFrame) -> dict:
    m = units.to_crs(units.estimate_utm_crs())
    epsg = m.crs.to_epsg()
    verts, objs = [], {}
    pid = str(m.pand_id.iloc[0])
    for _, u in m.iterrows():
        shell = prism_solid(list(u.geometry.exterior.coords), float(u.z_min), float(u.z_max), verts)
        objs[u.ulpin] = {"type": "BuildingUnit", "parents": [pid],
                         "attributes": {"ulpin_3d": u.ulpin, "level_code": u.level_code, "unit_code": u.unit_code,
                                        "z_min_m": float(u.z_min), "z_max_m": float(u.z_max), "area_m2": float(u.area_m2),
                                        "volume_m3": float(u.volume_m3), "floors_source": u.floors_source},
                         "geometry": [{"type": "Solid", "lod": "1.2", "boundaries": [shell]}]}
    objs[pid] = {"type": "Building", "children": list(objs), "attributes": {"pand_id": pid, "units": len(objs)}}
    scale = 0.001
    return {"type": "CityJSON", "version": "2.0",
            "metadata": {"referenceSystem": f"https://www.opengis.net/def/crs/EPSG/0/{epsg}"},
            "transform": {"scale": [scale] * 3, "translate": [0, 0, 0]},
            "CityObjects": objs,
            "vertices": [[round(v[0] / scale), round(v[1] / scale), round(v[2] / scale)] for v in verts]}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("units", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    if not a.units.exists():
        sys.exit(f"input not found: {a.units}")
    u = gpd.read_file(a.units)
    log.info("read %s (%d units)", a.units, len(u))
    cj = to_cityjson(u)
    solids = [o for o in cj["CityObjects"].values() if o["type"] == "BuildingUnit"]
    bad = [o["attributes"]["ulpin_3d"] for o in solids if len(o["geometry"][0]["boundaries"][0]) < 5]
    if bad:
        sys.exit(f"open solids (fewer than 5 faces): {bad[:3]}")
    a.output.write_text(json.dumps(cj), encoding="utf-8")
    log.info("processed %d BuildingUnit solids, %d vertices, CRS EPSG:%s; wrote %s",
             len(solids), len(cj["vertices"]), cj["metadata"]["referenceSystem"].rsplit("/", 1)[1], a.output)


if __name__ == "__main__":
    main()
