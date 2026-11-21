# ulpin3d — 3D ULPIN generation and vertical property mapping

SIH problem statement 26011 (Ministry of Rural Development / DoLR).

India's 14-digit ULPIN identifies a land parcel in 2D. This prototype extends it into 3D so
every apartment, parking slot, common area and underground utility volume gets its own
unique, verifiable ID, and shows the result as a clickable 3D building in the browser.

```
27021500123456-B01-F05-U03-4
parcel ULPIN   bld  lvl unit check      → flat 3, 5th floor, building 1
```

The first 14 digits are the existing ULPIN, unchanged. See `docs/ULPIN_SPEC.md`.

## What is real, what is not

- Demo building: BAG pand `0503100000000071`, Delft (NL). Footprint, 14.0 m height,
  **5 official floors** and **84 registered dwelling units** come from the Dutch 3DBAG and
  BAG registers. Chosen because it is the only open building found with all three ground
  truths.
- No open floor plan exists for it, so units are equal strips per floor. The floor-plan
  model (`src/models/floorplan.py`, pending) replaces that step.
- The basement is an operator input (`--basements 1`) to demonstrate below-ground IDs.
- Floor counts are always labelled `official`, `estimated` or `rule_of_thumb`.

## Run it

```
uv venv --python 3.11 .venv && uv pip install --python .venv -r requirements.txt

.venv/Scripts/python -m src.ingest.download 0503100000000071 -o data/raw
.venv/Scripts/python -m src.ingest.align data/raw/0503100000000071.city.json data/raw/0503100000000071_units.geojson -o data/processed/0503100000000071.geojson
.venv/Scripts/python -m src.geometry.extrude data/processed/0503100000000071.geojson -o data/processed/0503100000000071_solid.geojson --basements 1
.venv/Scripts/python -m src.geometry.slice_floors data/processed/0503100000000071_solid.geojson -o data/processed/0503100000000071_floors.geojson
.venv/Scripts/python -m src.geometry.units data/processed/0503100000000071_floors.geojson --parent-ulpin 03100000000071 --units 84 -o data/processed/0503100000000071_units3d.geojson
.venv/Scripts/python -m src.validate.checks data/processed/0503100000000071_units3d.geojson data/processed/0503100000000071_floors.geojson -o data/processed/0503100000000071_report.json
.venv/Scripts/python -m src.validate.make_broken data/processed/0503100000000071

.venv/Scripts/uvicorn src.api.main:app        # then open http://127.0.0.1:8000/
```

`http://127.0.0.1:8000/?building=0503100000000071-broken` shows the validator catching
five injected faults.

**Intake** (what an officer uses): `http://127.0.0.1:8000/submit.html` offers two routes into the same
pipeline. **From map** (`from-map.html`, `mode=estimate`): click a building, gaps are filled with labelled
assumptions, the record is marked *estimated*. **Manual** (`manual.html`, `mode=manual`): every value from the
officer, the plan or survey files; any gap or map-sourced value is refused; the record is marked *surveyed*.
Manual inputs: parcel
ULPIN, building outline (GeoJSON upload or Dutch register ID), height (typed, DSM+DTM
GeoTIFFs, LAS/LAZ point cloud, or register), floors, basements, unit count, and one floor plan
image per floor. Submitting runs `src/pipeline.py` and links to the result in the viewer.
Height from survey data needs no model (`src/ingest/height.py`): on the demo building, DSM−DTM
gives 13.77 m and LiDAR gives 13.78 m against 14.01 m in the register. A 6.4 MB LiDAR clip
for the demo is produced by `src/ingest/clip_las.py` from a public AHN4 tile.

**Any building on a live map:** the intake page opens on an OpenStreetMap map. Search a place
or click a building; `src/ingest/osm.py` fetches the outline and any mapped floor count or
height (free Nominatim + Overpass, no key). Values from the map are labelled `osm`, never
`official`. Anand, Ahmedabad and Vadodara are cached offline (`src/ingest/osm_extract.py` from the
Geofabrik western-zone extract, 145k buildings) so picks there are instant; elsewhere the public
Overpass server is used and can time out. The upload route is the fallback.

**Try the model on any plan:** `http://127.0.0.1:8000/try_model.html` draws the floor-plan
model's apartment outlines over any uploaded image, with confidence, nothing stored.

Tests: `.venv/Scripts/python -m pytest -q` (58 tests: ID round-trips, every single-digit
typo rejected, one broken building per topology check).

## Pipeline

| Step | Code | Output |
|---|---|---|
| Download 3D model + unit register | `src/ingest/download.py` | raw CityJSON + GeoJSON |
| Footprint in EPSG:4326, area cross-checked | `src/ingest/align.py` | footprint + unit points |
| Extrude to a prism (basements = negative Z) | `src/geometry/extrude.py` | solid |
| Slice into levels B0n / G00 / F0n | `src/geometry/slice_floors.py` | one feature per level |
| Subdivide, order clockwise from NW, stamp ULPIN | `src/geometry/units.py` | unit volumes |
| Overlap / containment / gap / floating / duplicate / bad ID | `src/validate/checks.py` | JSON report |
| Floor-count estimator (only when no official count) | `src/models/floors.py` | `floors_estimated` + range |
| Floor plan → apartment polygons (YOLOv8s-seg fine-tuned on MSD) | `src/models/floorplan.py` | polygons for `units.py --plan-units` |
| LADM schema, CityJSON export | `src/db/` | PostGIS tables, `.city.json` |
| API + CesiumJS viewer | `src/api/main.py`, `web/` | browser demo |

Coordinates are stored in EPSG:4326 and measured in the local UTM zone (EPSG:32643 for
Gujarat). All AI is confined to steps that replace hand-drawing; IDs, checks and storage
are deterministic code.

## Models (both trained here, cost ₹0)

| Model | Data | Score on held-out data |
|---|---|---|
| Floor-count estimator, gradient boosting | 5,921 3DBAG buildings with an official floor count | MAE 0.20 floors, 99.5% within one floor (rule of thumb: 0.33, 97.5%); valid to 22.7 m, labelled fallback above |
| Apartment segmentation, YOLOv8s-seg | MSD, 4,569 plans / 16,148 apartments, 800 plans held out | mask mAP50 0.423, recall 0.50, precision 0.44 |

Floor-plan training:
```
.venv/Scripts/python -m src.models.floorplan prepare data/raw/msd -o data/processed/msd_yolo_v3
.venv/Scripts/python -m src.models.floorplan train data/processed/msd_yolo_v3/data.yaml -o data/processed/floorplan --epochs 40 --base yolov8s-seg.pt
.venv/Scripts/python -m src.models.floorplan predict data/processed/floorplan/weights/best.pt plan.png --footprint data/processed/0503100000000071.geojson --level F01 -o plan_units.geojson
```
Truth (blue) versus prediction (red): `docs/screenshots/05_floorplan_truth_vs_prediction.png`.

## Docs

- `docs/PROJECT_PLAN.md`, `docs/PROGRESS.md`, `docs/ULPIN_SPEC.md`, `docs/DATA_SOURCES.md`

## Trained models

Not stored in git (size). Download from the [Releases page](../../releases) and place them at:

- `best.pt` → `data/processed/floorplan/weights/best.pt` (apartment segmentation, YOLOv8s-seg)
- `floors_model.joblib` → `data/processed/floors_model.joblib` (floor-count estimator)

Raw and processed data (`data/`) are not included; the commands above download or rebuild them from the open sources in `docs/DATA_SOURCES.md`.

## License

[MIT](LICENSE)
