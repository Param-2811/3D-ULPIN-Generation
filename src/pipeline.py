"""One call that runs the whole pipeline for one building: the thing the intake page and the API use.

Inputs (all optional except parent_ulpin and a footprint source):
  footprint_geojson | bag_id          outline (GeoJSON in any CRS) or a Dutch BAG pand id for the demo
  height_m | (dsm, dtm) | las         a number, two GeoTIFFs, or a LAS/LAZ file
  floors_official                     int; if missing the estimator fills floors_estimated
  units_official                      int; used when no floor plans are given
  plans                               {level_code: image_path}; each goes through the floor-plan model
  basements, building_no
Writes the same files the CLI scripts write (data/processed/<id>*.geojson, _report.json) so the viewer works unchanged.
"""
import json
import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd

from src.geometry.extrude import extrude
from src.geometry.slice_floors import slice_floors
from src.geometry.units import make_units
from src.validate.checks import run_checks

log = logging.getLogger("pipeline")
DATA = Path("data/processed")
FLOORS_MODEL = DATA / "floors_model.joblib"
PLAN_MODEL = DATA / "floorplan" / "weights" / "best.pt"


def footprint_from_geojson(path: Path, pid: str) -> gpd.GeoDataFrame:
    g = gpd.read_file(path)
    if g.crs is None:
        raise ValueError("footprint GeoJSON has no CRS; export it with one (EPSG:4326 preferred)")
    geom = g.to_crs("EPSG:4326").geometry.union_all() if len(g) > 1 else g.to_crs("EPSG:4326").geometry.iloc[0]
    m = gpd.GeoSeries([geom], crs="EPSG:4326").to_crs(gpd.GeoSeries([geom], crs="EPSG:4326").estimate_utm_crs())
    return gpd.GeoDataFrame([{"pand_id": pid, "footprint_m2": round(float(m.area.iloc[0]), 1), "geometry": geom}], crs="EPSG:4326")


def footprint_from_bag(bag_id: str, raw: Path) -> gpd.GeoDataFrame:
    from src.ingest import align, download
    download.main([bag_id, "-o", str(raw)])
    out = DATA / f"{bag_id}.geojson"
    align.main([str(raw / f"{bag_id}.city.json"), str(raw / f"{bag_id}_units.geojson"), "-o", str(out)])
    return gpd.read_file(out)


def run(parent_ulpin: str, building_no: int = 1, *, footprint_geojson=None, bag_id=None, height_m=None, dsm=None, dtm=None,
        las=None, floors_official=None, units_official=None, plans: dict | None = None, basements: int = 0,
        raw_dir: Path = Path("data/raw"), height_label: str | None = None, floors_label: str | None = None,
        units_label: str | None = None, source_note: str | None = None, mode: str = "manual",
        gnss_csv=None, utilities_geojson=None, owners=None, ortho=None, ortho_point=None, admin: dict | None = None) -> dict:
    """Two routes, same pipeline:
      mode="manual"   every value comes from the officer or a survey file; anything missing is an error;
                      result flagged accuracy="surveyed". The record can be trusted.
      mode="estimate" ("from map") gaps are filled with labelled assumptions: height from floors x 3 m or 9 m,
                      floor count from the estimator, unit count from footprint area; accuracy="estimated".
    height_label / floors_label / units_label say where a typed number really came from (e.g. 'osm'),
    so a volunteer-mapped value is never recorded as 'official'.
    gnss_csv: CORS control points (name,lat,lon) that shift the outline onto surveyed positions.
    utilities_geojson: LineStrings with network_type/depth_m/diameter_m -> B00 T-coded volumes under the parcel.
    owners: {ulpin_3d: owner name} or a single name for the whole building (recorded on every unit)."""
    if mode not in ("manual", "estimate"):
        raise ValueError("mode must be 'manual' or 'estimate'")
    steps = []
    assumed = []                                   # every assumption made, so the result can list them
    pid = bag_id or f"{parent_ulpin}B{building_no:02d}"
    if source_note:
        steps.append(source_note)
    if bag_id:
        fp = footprint_from_bag(bag_id, raw_dir); steps.append(f"footprint + register facts fetched for BAG {bag_id}")
    elif ortho:
        from src.models.building import extract
        out, rep = extract(Path(ortho), tuple(ortho_point) if ortho_point else None)
        tmp = DATA / f"{pid}_extracted_outline.geojson"; out.to_file(tmp, driver="GeoJSON")
        fp = footprint_from_geojson(tmp, pid); fp["outline_source"] = "sam_orthophoto"
        steps.append(f"outline extracted from the orthophoto by SAM: {rep['squared_area_m2']:.0f} m2, {rep['vertices']} corners (from {rep['masks']} candidate masks)")
        assumed.append("outline traced by AI from the orthophoto, not surveyed")
    elif footprint_geojson:
        fp = footprint_from_geojson(Path(footprint_geojson), pid); steps.append(f"footprint read from upload, {fp.footprint_m2.iloc[0]} m2")
    else:
        raise ValueError("need a footprint: upload a GeoJSON or give a BAG id")
    if gnss_csv:
        from src.ingest.gnss import apply_control_points
        fp, rep = apply_control_points(fp, pd.read_csv(gnss_csv))
        steps.append(f"outline shifted onto {rep['points_used']} GNSS/CORS control points: {rep['shift_east_m']:+.2f} m east, {rep['shift_north_m']:+.2f} m north, residual {rep['residual_m']:.2f} m")

    if height_m is not None:
        fp["height_m"], fp["height_source"] = float(height_m), height_label or "entered"
    elif dsm and dtm:
        from src.ingest.height import from_dsm
        h = from_dsm(fp, Path(dsm), Path(dtm)); fp["height_m"], fp["height_max_m"], fp["height_source"] = h["height_m"], h["height_max_m"], "dsm_dtm"
    elif las:
        from src.ingest.height import from_las
        h = from_las(fp, Path(las)); fp["height_m"], fp["height_max_m"], fp["height_source"] = h["height_m"], h["height_max_m"], "lidar"
    elif "height_m" in fp and pd.notna(fp.height_m.iloc[0]):
        fp["height_source"] = "register"
    elif mode == "estimate":
        lv = floors_official or (fp.floors_official.iloc[0] if "floors_official" in fp and pd.notna(fp.floors_official.iloc[0]) else None)
        fp["height_m"], fp["height_source"] = (float(lv) * 3.0, "floors_x3") if lv else (9.0, "assumed_9m")
        assumed.append(f"height {float(fp.height_m.iloc[0]):.1f} m ({fp.height_source.iloc[0]})")
    else:
        raise ValueError("manual mode needs a height: a number, DSM+DTM rasters, or a LiDAR file")
    if mode == "manual" and str(fp.height_source.iloc[0]).startswith(("osm", "assumed")):
        raise ValueError("manual mode does not accept a map-estimated height; enter a measured one or upload survey files")
    steps.append(f"height {float(fp.height_m.iloc[0]):.1f} m ({fp.height_source.iloc[0]})")
    for col, default in (("height_max_m", fp.height_m), ("roof_type", "unknown"), ("year_built", None)):
        if col not in fp:
            fp[col] = default

    if floors_official is not None:
        fp["floors_official"] = int(floors_official)
    elif "floors_official" not in fp or pd.isna(fp.floors_official.iloc[0]):
        fp["floors_official"] = None
        if mode == "manual":
            raise ValueError("manual mode needs the floor count from the approved plan")
        if FLOORS_MODEL.exists():
            from src.models.floors import predict
            fp = predict(FLOORS_MODEL, fp); steps.append(f"floor count {int(fp.floors_estimated.iloc[0])} ({fp.floors_source.iloc[0]})")
            assumed.append(f"floor count {int(fp.floors_estimated.iloc[0])} ({fp.floors_source.iloc[0]})")
    if units_official is not None:
        fp["units_official"] = int(units_official)
        fp["units_source"] = units_label or "entered"
    elif "units_official" not in fp:
        fp["units_official"] = None
    else:
        fp["units_source"] = "register"

    fp.to_file(DATA / f"{pid}.geojson", driver="GeoJSON")
    solid = extrude(fp, basements)
    solid.to_file(DATA / f"{pid}_solid.geojson", driver="GeoJSON")
    floors = slice_floors(solid)
    if floors_label and floors_official is not None:
        floors["floors_source"] = floors_label
    floors.to_file(DATA / f"{pid}_floors.geojson", driver="GeoJSON")
    steps.append(f"{len(floors)} levels: {' '.join(floors.level_code)} (floor count {floors.floors_source.iloc[0]})")

    plan_units = None
    if plans:
        from src.models.floorplan import predict as plan_predict
        if not PLAN_MODEL.exists():
            raise ValueError("floor-plan model weights not found; train it or omit floor plans")
        parts = []
        for level, img in plans.items():
            g = plan_predict(PLAN_MODEL, Path(img), fp, level)
            steps.append(f"floor plan for {level}: model found {len(g)} apartments")
            parts.append(g)
        plan_units = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs="EPSG:4326")
        if len(plan_units) == 0:
            raise ValueError("the floor-plan model found no apartments in the uploaded plans")
        n_fallback = int(fp.units_official.iloc[0]) if pd.notna(fp.units_official.iloc[0]) else 0
        units = make_units(floors, parent_ulpin, n_fallback, building_no, plan_units=plan_units)
        missing = [c for c in floors.level_code if not c.startswith("B") and c not in set(plan_units.level_code)]
        if missing:
            steps.append(f"no plan for {' '.join(missing)}: " + (f"{n_fallback} units spread as equal strips there" if n_fallback else "those levels are one volume each"))
            assumed.append(f"levels {' '.join(missing)} have no floor plan (equal strips)")
    else:
        n = fp.units_official.iloc[0]
        if n is None or pd.isna(n):
            if mode == "manual":
                raise ValueError("manual mode needs the unit count from the plan or register, or floor plan images")
            n_floors = int(floors.level_code.str.match(r"^(G|F)").sum())
            n = min(99, max(1, round(float(fp.footprint_m2.iloc[0]) / 90))) * n_floors      # ponytail: 90 m2 per flat, 99/level ceiling; a state can tune this
            fp["units_official"], fp["units_source"] = int(n), "assumed_from_area"
            assumed.append(f"unit count {int(n)} (footprint / 90 m2 x {n_floors} floors)")
        src = fp.get("units_source", pd.Series(["entered"])).iloc[0]
        if mode == "manual" and src.startswith("assumed"):
            raise ValueError("manual mode does not accept an assumed unit count")
        n_above = int(floors.level_code.str.match(r"^(G|F)").sum())
        if int(n) > 99 * n_above:
            raise ValueError(f"{int(n)} units cannot fit on {n_above} level(s): the 3D ULPIN allows 99 units per level, so this needs at least {-(-int(n) // 99)} floors. Check the floor count")
        units = make_units(floors, parent_ulpin, int(n), building_no)
        steps.append(f"{int(n)} units ({src}) spread as equal strips; no floor plan given")
        if mode == "manual":
            assumed.append("unit shapes are equal strips (no floor plan uploaded)")
    if utilities_geojson:
        from src.geometry.utilities import make_utilities
        ut = gpd.read_file(utilities_geojson)
        if ut.crs is None:
            raise ValueError("utility file has no CRS")
        ut3d = make_utilities(ut, parent_ulpin)
        for col in ("pand_id", "floors_source"):
            ut3d[col] = pid if col == "pand_id" else "surveyed"
        units = gpd.GeoDataFrame(pd.concat([units, ut3d[units.columns.intersection(ut3d.columns).tolist() + ["network_type", "operator"]]], ignore_index=True), crs="EPSG:4326")
        steps.append(f"{len(ut3d)} underground utility volumes under the parcel (building B00): " + ", ".join(f"{r.unit_code} {r.network_type} at {r.z_max}..{r.z_min} m" for r in ut3d.itertuples()))
    if owners:
        if isinstance(owners, str):
            units["owner"] = owners
        else:
            units["owner"] = units.ulpin.map(owners)
        n_own = int(units.owner.notna().sum())
        steps.append(f"owner recorded on {n_own} of {len(units)} volumes (LADM la_rrr: ownership)")
    units.to_file(DATA / f"{pid}_units3d.geojson", driver="GeoJSON")
    findings = run_checks(units[units.building_no != 0], floors)      # utilities sit outside the building envelope by design
    (DATA / f"{pid}_report.json").write_text(json.dumps({"units": len(units), "levels": len(floors), "findings": findings}, indent=2), encoding="utf-8")
    steps.append(f"{len(units)} volumes with unique IDs, validator: {len(findings)} findings")
    accuracy = "estimated" if mode == "estimate" else "surveyed"
    if admin is None:
        from src.ingest.admin import village_at
        c = fp.geometry.iloc[0].centroid
        admin = village_at(c.y, c.x)
    if admin:
        steps.append(f"revenue village {admin['village']} ({admin['village_code']}), {admin['subdistrict']} taluka, {admin['district']} district, {admin['state']}")
    meta = {"mode": mode, "accuracy": accuracy, "assumed": assumed, "label": (source_note or "").split(",")[0][:60] or pid, "admin": admin}
    (DATA / f"{pid}_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {"pand_id": pid, "units": len(units), "levels": len(floors), "findings": len(findings), "steps": steps, **meta}
