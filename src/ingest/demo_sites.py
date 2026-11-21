"""Build the judge-facing demo folder: one sub-folder per real Indian building with every input file the Manual
route accepts, each file either real (with its source) or clearly marked as a stand-in.

Per site: 00_ULPIN.txt (parent ULPIN + village + example 3D IDs), 01_outline.geojson (OpenStreetMap, carries parent_ulpin and
codes in its properties), 01b_parcel_outline_demo.geojson (parcel = outline + 6 m squared, DEMO: no open parcel map),
Real per site:  02_village_codes.json (Census 2011), 03_dem_copernicus30m.tif
                (Copernicus DEM, no login), 04_facts.json (what the map knows: floors, height if any)
Stand-in per site (no open Indian source): 05_utilities_demo.geojson, 06_cors_points_demo.csv, floor plans (shared)
Usage: python -m src.ingest.demo_sites -o "demo_inputs" --n 25
"""
import argparse
import csv
import hashlib
import json
import logging
import re
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask
from shapely.geometry import LineString

from src.ingest.admin import placeholder_ulpin, village_at

log = logging.getLogger("demo_sites")
DEM_DIR = Path("data/raw/dem")


def sub(site: Path, name: str) -> Path:
    """One sub-folder per input type, so the judge opens building -> input -> file."""
    d = site / name; d.mkdir(parents=True, exist_ok=True); return d


def safe(s: str) -> str:
    s = re.sub(r"[^\w\- ]+", "", str(s)).strip().replace(" ", "_")
    return s[:40] or "building"


def dem_tile(lat: float, lon: float) -> Path | None:
    p = DEM_DIR / f"Copernicus_DSM_COG_10_N{int(lat):02d}_00_E{int(lon):03d}_00_DEM.tif"
    return p if p.exists() else None


def cut_dem(lat, lon, geom, out: Path) -> dict:
    tile = dem_tile(lat, lon)
    if not tile:
        return {}
    with rasterio.open(tile) as src:
        box = geom.buffer(0.004)   # ~400 m around the building
        data, tr = mask(src, [box], crop=True)
        meta = src.meta.copy(); meta.update(height=data.shape[1], width=data.shape[2], transform=tr, driver="GTiff")
        with rasterio.open(out, "w", **meta) as dst:
            dst.write(data)
        vals = data[0][data[0] > -1000]
    return {"dem_min_m": float(vals.min()), "dem_max_m": float(vals.max()), "dem_pixels": int(vals.size), "resolution_m": 30}


def utilities_for(geom_m, crs) -> gpd.GeoDataFrame:
    x0, y0, x1, y1 = geom_m.bounds; cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return gpd.GeoDataFrame({"network_type": ["water", "sewer"], "depth_m": [1.2, 2.8], "diameter_m": [0.3, 0.6],
                             "operator": ["municipal water (DEMO, not real)", "municipal sewer (DEMO, not real)"],
                             "geometry": [LineString([(x0 - 12, cy), (x1 + 12, cy)]), LineString([(cx, y0 - 12), (cx, y1 + 12)])]}, crs=crs).to_crs("EPSG:4326")


def cors_for(geom_m, crs, out: Path):
    verts = list(geom_m.exterior.coords)[:-1]
    idx = np.linspace(0, len(verts) - 1, min(3, len(verts)), dtype=int)
    pts = gpd.GeoSeries.from_xy([verts[i][0] + 0.4 for i in idx], [verts[i][1] + 0.2 for i in idx], crs=crs).to_crs("EPSG:4326")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["name", "lat", "lon"])
        for i, p in enumerate(pts): w.writerow([f"CP{i+1}", f"{p.y:.8f}", f"{p.x:.8f}"])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-o", "--output", type=Path, required=True)
    p.add_argument("--n", type=int, default=25)
    p.add_argument("--cache", type=Path, default=Path("data/raw/osm/buildings_cache.geojson"))
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
    g = gpd.read_file(a.cache)
    g["area_m2"] = g.to_crs("EPSG:32643").area.round(0)
    apt = g[g.building.isin(["apartments", "residential"]) & g.name.notna() & (g.area_m2 > 250)].copy()
    apt["has_levels"] = apt.levels.notna()
    # all Anand, then the rest by floor-count-known first, spread across cities, deterministic
    apt["rank"] = apt.apply(lambda r: (r.city != "anand", not r.has_levels, int(hashlib.md5(str(r.osm_id).encode()).hexdigest(), 16) % 1000), axis=1)
    pick = apt.sort_values("rank").groupby("city", group_keys=False).head(12).sort_values("rank").head(a.n)
    log.info("read %s; picked %d named apartment buildings: %s", a.cache, len(pick), pick.city.value_counts().to_dict())

    index = []
    for i, (_, r) in enumerate(pick.iterrows(), start=1):
        c = r.geometry.centroid; lat, lon = c.y, c.x
        v = village_at(lat, lon); ulpin, how = placeholder_ulpin(lat, lon, v)
        site = a.output / f"{i:02d}_{safe(r['name'])}_{r.city.title()}"
        site.mkdir(parents=True, exist_ok=True)
        adm = v or {}
        props = {"name": r["name"], "osm_id": int(r.osm_id), "source": "OpenStreetMap (ODbL), local extract",
                 "parent_ulpin": ulpin, "parent_ulpin_status": "placeholder: state+district+village census code+parcel seq; DoLR issues the real one",
                 "building_no": 1, "state": adm.get("state"), "district": adm.get("district"), "subdistrict": adm.get("subdistrict"), "village": adm.get("village"),
                 "village_code": adm.get("village_code")}
        gpd.GeoDataFrame([{**props, "geometry": r.geometry}], crs="EPSG:4326").to_file(sub(site, "step2_outline") / "outline.geojson", driver="GeoJSON")
        # the land parcel the building stands on: the outline buffered 6 m and squared, since no open parcel map exists for Gujarat
        gm_ = gpd.GeoSeries([r.geometry], crs="EPSG:4326").to_crs("EPSG:32643").iloc[0]
        parcel = gm_.buffer(6.0, join_style="mitre").minimum_rotated_rectangle
        gpd.GeoDataFrame([{"parent_ulpin": ulpin, "parcel_of": r["name"], "parcel_source": "DEMO: building outline + 6 m, squared. Real parcel boundaries come from BhuNaksha",
                           **{k: adm.get(k) for k in ("state", "district", "subdistrict", "village", "village_code")}, "geometry": parcel}],
                         crs="EPSG:32643").to_crs("EPSG:4326").to_file(sub(site, "step2_outline") / "parcel_outline_DEMO.geojson", driver="GeoJSON")
        from src.ulpin.generate import generate
        ex = [(generate(ulpin, 1, "G00", "U01"), "flat 1, ground floor"), (generate(ulpin, 1, "F02", "U03"), "flat 3, floor 2"),
              (generate(ulpin, 1, "B01", "P05"), "parking slot 5, basement 1"), (generate(ulpin, 0, "B01", "T01"), "water main under the parcel, no building")]
        txt = [f"PARENT ULPIN (14-digit, parcel):  {ulpin}", f"  = {how}",
               "  status: placeholder shaped like the official ULPIN; the real number is issued by DoLR via the state land-records system", "",
               f"BUILDING:  {r['name']}  (building B01 on this parcel)",
               f"VILLAGE:   {adm.get('village')}  |  taluka {adm.get('subdistrict')}  |  district {adm.get('district')}  |  {adm.get('state')}",
               f"CENSUS CODES:  state {adm.get('state_code')}  district {adm.get('district_code')}  sub-district {adm.get('subdistrict_code')}  village {adm.get('village_code')}", "",
               "3D ULPINs this building will get (real check digits):"] + [f"  {u}   {d}" for u, d in ex]
        (sub(site, "step1_parcel") / "ULPIN.txt").write_text(chr(10).join(txt) + chr(10), encoding="utf-8")
        (sub(site, "step1_parcel") / "village_codes.json").write_text(json.dumps(v or {"note": "outside village layer"}, indent=2, ensure_ascii=False), encoding="utf-8")
        dem = cut_dem(lat, lon, r.geometry, sub(site, "step3_height") / "dem_copernicus_30m.tif")
        lv = int(re.match(r"\d+", str(r.levels)).group()) if r.has_levels and re.match(r"\d+", str(r.levels)) else None
        h = float(re.match(r"[\d.]+", str(r.height)).group()) if r.height and re.match(r"[\d.]+", str(r.height)) else None
        facts = {"name": r["name"], "city": r.city, "building_type": r.building, "lat": round(lat, 6), "lon": round(lon, 6),
                 "footprint_m2_osm": int(r.area_m2), "floors_osm": lv, "height_m_osm": h, "height_m_if_floors_x3": lv * 3.0 if lv else None,
                 "placeholder_parent_ulpin": ulpin, "placeholder_how": how,
                 "REAL": ["outline (OpenStreetMap)", "village and Census codes", "DEM 30 m (Copernicus)"] + (["floor count (OpenStreetMap volunteers)"] if lv else []) + (["height (OpenStreetMap)"] if h else []),
                 "NOT_AVAILABLE_FOR_INDIA_AT_ZERO_COST": ["unit count (municipal approval, not open)", "floor plans (no open Indian dataset)", "owner (not open)",
                                                          "LiDAR point cloud (no open city LiDAR)", "drone orthophoto for this building (OpenAerialMap has none here)",
                                                          "utility network (not open)", "CORS control points (Survey of India, paid for private users)"],
                 "STAND_INS_IN_THIS_FOLDER": ["step6_owner_utilities_cors/utilities_DEMO.geojson (synthetic lines)", "step6_owner_utilities_cors/cors_points_DEMO.csv (synthetic, 0.4 m E / 0.2 m N offset on real corners)", "step2_outline/parcel_outline_DEMO.geojson (parcel = outline + 6 m, no open parcel map)",
                                              "floor plans: see step5_floor_plans/README.txt"],
                 **dem}
        (sub(site, "step4_floors_units") / "floors_height_facts.json").write_text(json.dumps(facts, indent=2, ensure_ascii=False), encoding="utf-8")
        gm = gpd.GeoSeries([r.geometry], crs="EPSG:4326").to_crs("EPSG:32643").iloc[0]
        utilities_for(gm, "EPSG:32643").to_file(sub(site, "step6_owner_utilities_cors") / "utilities_DEMO.geojson", driver="GeoJSON")
        cors_for(gm, "EPSG:32643", sub(site, "step6_owner_utilities_cors") / "cors_points_DEMO.csv")
        NL = chr(10)
        (sub(site, "step3_height") / "README.txt").write_text(NL.join([
            "Step 3, Height.",
            "dem_copernicus_30m.tif is REAL (Copernicus DEM, 30 m, no login) but it is bare ground at 30 m pixels: it cannot",
            "measure one building. For the demo, type the height from step4_floors_units/floors_height_facts.json",
            "(height_m_if_floors_x3), OR show measurement with the out-of-India files:",
            "  DSM + DTM:  ../../00_OUT_OF_INDIA_SUBSTITUTES/dsm_dtm_elevation_Netherlands/",
            "  LiDAR:      ../../00_OUT_OF_INDIA_SUBSTITUTES/lidar_point_cloud_Netherlands/",
            "No open sub-metre DSM or city LiDAR exists for India at zero cost.", ""]), encoding="utf-8")
        (sub(site, "step5_floor_plans") / "README.txt").write_text(NL.join([
            "Step 5, Floor plans.",
            "No open dataset of Indian apartment floor plans exists. Use the Swiss MSD plans (CC-BY-4.0), which our model",
            "was trained on:  ../../00_OUT_OF_INDIA_SUBSTITUTES/floor_plans_swiss_MSD/",
            "Pick one image per floor; the model draws the flats. Without plans, flats are equal strips and the result says so.", ""]), encoding="utf-8")
        (site / "READ_ME_FIRST.txt").write_text(NL.join([
            f"{r['name']}, {r.city.title()}", "", "Folders match the steps on the Manual page (manual.html):",
            "  step1_parcel/               ULPIN.txt (copy the 14 digits), village_codes.json",
            "  step2_outline/              outline.geojson (upload this), parcel_outline_DEMO.geojson",
            "  step3_height/               dem_copernicus_30m.tif + README (where to get a measurable height)",
            "  step4_floors_units/         floors_height_facts.json (floors, height, what is real)",
            "  step5_floor_plans/          README (points to the Swiss plans)",
            "  step6_owner_utilities_cors/ utilities_DEMO.geojson, cors_points_DEMO.csv", ""]), encoding="utf-8")
        index.append({"folder": site.name, **{k: facts[k] for k in ("name", "city", "floors_osm", "footprint_m2_osm", "placeholder_parent_ulpin")}, "village": (v or {}).get("village")})
        log.info("wrote %s (floors %s, %s m2, village %s)", site.name, lv, int(r.area_m2), (v or {}).get("village"))
    pd.DataFrame(index).to_csv(a.output / "INDEX.csv", index=False, encoding="utf-8-sig")
    log.info("processed %d sites; wrote %s", len(index), a.output / "INDEX.csv")


if __name__ == "__main__":
    main()
