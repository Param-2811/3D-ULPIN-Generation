"""FastAPI over the Phase 3/4 output files. No database yet (Phase 7).

Run: .venv/Scripts/uvicorn src.api.main:app --reload   then open http://127.0.0.1:8000/
Set ULPIN3D_DATA to point elsewhere than data/processed.
"""
import json
import os
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles

DATA = Path(os.environ.get("ULPIN3D_DATA", "data/processed"))
WEB = Path(__file__).resolve().parents[2] / "web"
app = FastAPI(title="3D ULPIN API")


def _load(name: str) -> dict:
    f = DATA / name
    if not f.exists():
        raise HTTPException(404, f"{name} not found; run the pipeline first")
    return json.loads(f.read_text(encoding="utf-8"))


def _in_india(feature: dict) -> bool:
    """Rough India box; enough to put Indian buildings first and the Dutch reference last."""
    c = feature["geometry"]["coordinates"][0][0]
    return 6.0 <= c[1] <= 37.5 and 68.0 <= c[0] <= 97.5


@app.get("/api/buildings")
def buildings():
    out = []
    for f in DATA.glob("*_units3d.geojson"):
        pid = f.name.split("_")[0]
        feat = _load(f"{pid}.geojson")["features"][0]
        meta = DATA / f"{pid}_meta.json"
        note = json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else {}
        out.append({**feat["properties"], "pand_id": pid, "india": _in_india(feat), "accuracy": note.get("accuracy", "surveyed"),
                    "label": (note.get("label") or feat["properties"].get("name") or pid), "updated": f.stat().st_mtime})
    # India first, newest first within, the -broken demo copy always last
    out.sort(key=lambda b: ("-broken" in b["pand_id"], not b["india"], -b["updated"]))
    return out


@app.get("/api/buildings/{pid}/footprint")
def footprint(pid: str):
    return _load(f"{pid}.geojson")


@app.get("/api/buildings/{pid}/floors")
def floors(pid: str):
    return _load(f"{pid}_floors.geojson")


@app.get("/api/buildings/{pid}/units")
def units(pid: str):
    return _load(f"{pid}_units3d.geojson")


@app.get("/api/buildings/{pid}/report")
def report(pid: str):
    return _load(f"{pid}_report.json")


@app.get("/api/buildings/{pid}/meta")
def meta(pid: str):
    f = DATA / f"{pid}_meta.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"mode": "manual", "accuracy": "surveyed", "assumed": []}


@app.get("/api/units/{ulpin}")
def unit(ulpin: str):
    ulpin = ulpin.strip().upper()
    for f in DATA.glob("*_units3d.geojson"):
        for feat in json.loads(f.read_text(encoding="utf-8"))["features"]:
            if feat["properties"]["ulpin"] == ulpin:
                return feat
    raise HTTPException(404, f"no volume with ULPIN {ulpin}")


@app.get("/api/osm/search")
def osm_search(q: str):
    from src.ingest.osm import geocode
    return geocode(q)


@app.get("/api/osm/building")
def osm_building(lat: float, lon: float):
    from src.ingest.osm import building_at
    try:
        b = building_at(lat, lon)
    except RuntimeError as e:
        raise HTTPException(503, str(e))
    if not b:
        raise HTTPException(404, "no building outline in OpenStreetMap within 40 m of that point; click closer to a building, or upload an outline")
    return b


@app.post("/api/plan_preview")
async def plan_preview(request: Request):
    """Try the floor-plan model on any image: apartment outlines in pixel coordinates, nothing stored."""
    from ultralytics import YOLO
    form = await request.form()
    img = form.get("image")
    if img is None or not getattr(img, "filename", ""):
        raise HTTPException(400, "upload an image")
    tmp = Path("data/uploads/preview"); tmp.mkdir(parents=True, exist_ok=True)
    p = tmp / f"{int(time.time())}_{Path(img.filename).name}"
    p.write_bytes(await img.read())
    weights = Path("data/processed/floorplan/weights/best.pt")
    if not weights.exists():
        raise HTTPException(503, "floor-plan model weights not found; train it first")
    res = YOLO(str(weights)).predict(str(p), imgsz=512, conf=float(form.get("conf") or 0.25), verbose=False)[0]
    h, w = res.orig_shape
    polys = [] if res.masks is None else [{"points": seg.tolist(), "conf": round(float(c), 3)} for seg, c in zip(res.masks.xy, res.boxes.conf) if len(seg) >= 3]
    return {"width": int(w), "height": int(h), "apartments": polys}


@app.post("/api/submit")
async def submit(request: Request):
    """Intake form: saves uploads under data/uploads/<job>/ and runs the whole pipeline."""
    from src.pipeline import run
    form = await request.form()
    job = Path("data/uploads") / f"{form.get('parent_ulpin', 'x')}-{int(time.time())}"
    job.mkdir(parents=True, exist_ok=True)
    footprint_json = form.get("footprint_json")
    if footprint_json:
        (job / "footprint_osm.geojson").write_text(footprint_json, encoding="utf-8")

    async def save(field):
        f = form.get(field)
        if f is None or not getattr(f, "filename", ""):
            return None
        p = job / f"{field}_{Path(f.filename).name}"
        p.write_bytes(await f.read())
        return p

    plans = {}
    for lvl, img in zip(form.getlist("plan_level"), form.getlist("plan_image")):
        if getattr(img, "filename", ""):
            p = job / f"plan_{lvl}_{Path(img.filename).name}"
            p.write_bytes(await img.read())
            plans[lvl] = p
    num = lambda k: (float(form[k]) if form.get(k) not in (None, "") else None)
    owners = None
    if form.get("owners_json"):
        owners = json.loads(form["owners_json"])
    elif form.get("owner"):
        owners = form["owner"].strip()
    try:
        return run(form["parent_ulpin"], int(form.get("building_no") or 1),
                   footprint_geojson=(job / "footprint_osm.geojson") if footprint_json else await save("footprint"),
                   bag_id=form.get("bag_id") or None,
                   height_label=form.get("height_label") or None, floors_label=form.get("floors_label") or None,
                   units_label=form.get("units_label") or None, mode=form.get("mode") or "manual",
                   source_note=form.get("source_note") or None,
                   height_m=num("height_m"), dsm=await save("dsm"), dtm=await save("dtm"), las=await save("las"),
                   floors_official=int(num("floors_official")) if num("floors_official") else None,
                   units_official=int(num("units_official")) if num("units_official") else None,
                   plans=plans or None, basements=int(num("basements") or 0),
                   gnss_csv=await save("gnss"), utilities_geojson=await save("utilities"), owners=owners,
                   ortho=await save("ortho"), admin=json.loads(form["admin_json"]) if form.get("admin_json") else None,
                   ortho_point=[float(form["ortho_lon"]), float(form["ortho_lat"])] if form.get("ortho_lon") and form.get("ortho_lat") else None)
    except (ValueError, SystemExit) as e:
        raise HTTPException(400, str(e))


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
