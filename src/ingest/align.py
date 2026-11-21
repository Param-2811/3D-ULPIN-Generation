"""Turn a raw 3DBAG CityJSON + BAG units file into one footprint GeoJSON in EPSG:4326.

Usage: python -m src.ingest.align data/raw/0503100000000071.city.json data/raw/0503100000000071_units.geojson -o data/processed/0503100000000071.geojson
"""
import argparse
import json
import logging
import sys
from pathlib import Path

import geopandas as gpd
from shapely.geometry import Polygon
from shapely.ops import unary_union

log = logging.getLogger(Path(__file__).stem)

STORE_CRS = "EPSG:4326"
# 3DBAG is EPSG:7415 = RD New (28992) + NAP heights. Horizontal maths happens in 28992 (metres).
NATIVE_CRS = "EPSG:28992"


def lod0_footprint(city: dict, pid: str) -> Polygon:
    s, t = city["transform"]["scale"], city["transform"]["translate"]
    xy = [(v[0] * s[0] + t[0], v[1] * s[1] + t[1]) for v in city["vertices"]]
    geom = next(g for g in city["CityObjects"][f"NL.IMBAG.Pand.{pid}"]["geometry"] if g["lod"] == "0")
    if geom["type"] != "MultiSurface":
        sys.exit(f"expected LoD0 MultiSurface, got {geom['type']}")
    polys = [Polygon([xy[i] for i in surf[0]], [[xy[i] for i in ring] for ring in surf[1:]])
             for surf in geom["boundaries"]]
    return unary_union(polys)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("city_json", type=Path)
    p.add_argument("units_geojson", type=Path)
    p.add_argument("-o", "--output", type=Path, required=True)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    for f in (a.city_json, a.units_geojson):
        if not f.exists():
            sys.exit(f"input not found: {f}")

    pid = a.city_json.name.split(".")[0]
    city = json.loads(a.city_json.read_text(encoding="utf-8"))
    ref = city["metadata"]["referenceSystem"]
    if not ref.endswith("/7415"):
        sys.exit(f"unexpected CRS in CityJSON: {ref}")
    attrs = city["CityObjects"][f"NL.IMBAG.Pand.{pid}"]["attributes"]
    log.info("read %s (CRS EPSG:7415)", a.city_json)

    units = gpd.read_file(a.units_geojson)
    if units.crs is None:
        sys.exit(f"{a.units_geojson} has no CRS; refusing to guess")
    log.info("read %s (%d units, CRS %s)", a.units_geojson, len(units), units.crs.to_string())

    fp = lod0_footprint(city, pid)
    area_m2 = fp.area
    drift = abs(area_m2 - attrs["b3_opp_grond"]) / attrs["b3_opp_grond"]
    if drift > 0.02:
        sys.exit(f"footprint area {area_m2:.0f} m2 differs from 3DBAG's {attrs['b3_opp_grond']:.0f} by {drift:.0%}")

    building = gpd.GeoDataFrame([{
        "pand_id": pid,
        "ground_z_m": attrs["b3_h_maaiveld"],
        "height_m": attrs["b3_h_dak_50p"] - attrs["b3_h_maaiveld"],
        "height_max_m": attrs["b3_h_dak_max"] - attrs["b3_h_maaiveld"],
        "floors_official": attrs.get("b3_bouwlagen"),
        "footprint_m2": round(area_m2, 1),
        "units_official": int(len(units)),
        "units_residential": int((units["gebruiksdoel"] == "woonfunctie").sum()),
        "roof_type": attrs.get("b3_dak_type"),
        "year_built": attrs.get("oorspronkelijkbouwjaar"),
        "geometry": fp,
    }], crs=NATIVE_CRS).to_crs(STORE_CRS)

    units_out = units.to_crs(STORE_CRS)
    inside = units_out.within(building.geometry.iloc[0]).sum()
    log.info("%d/%d unit address points fall inside the footprint", inside, len(units_out))

    a.output.parent.mkdir(parents=True, exist_ok=True)
    building.to_file(a.output, driver="GeoJSON")
    units_path = a.output.with_name(a.output.stem + "_units.geojson")
    units_out.to_file(units_path, driver="GeoJSON")
    log.info("processed 1 building, %d units; all layers now %s", len(units_out), STORE_CRS)
    log.info("wrote %s and %s", a.output, units_path)
    print(building.drop(columns="geometry").iloc[0].to_string())


if __name__ == "__main__":
    main()
