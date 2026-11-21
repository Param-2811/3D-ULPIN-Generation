# Progress

Tick a box only after the step ran on real data and the output was seen.
Phase order revised 2026-09-13 — see the note at the top of docs/PROJECT_PLAN.md.

## Phase 0 — Setup
- [x] Folder structure
- [x] Python 3.11 venv + requirements.txt (`import geopandas, rasterio, shapely` → ok)
- [x] .gitignore (data/, .venv/, weights)
- [x] docs/PROGRESS.md, PROJECT_LOG.md
- [x] git init (no commit yet)

## Phase 1 — ULPIN generator
- [x] src/ulpin/generate.py — generate / parse / validate / clockwise_from_northwest
- [x] tests/test_ulpin.py — 52 tests: round-trip, every single-digit typo, bad input
- [x] docs/ULPIN_SPEC.md examples updated with real computed check digits

## Phase 2 — Real data
- [x] src/ingest/download.py (3DBAG API + BAG WFS, by pand id)
- [x] Building 0503100000000071: 5 floors, 84 units, 14.0 m, recorded in docs/DATA_SOURCES.md
- [x] src/ingest/align.py: footprint + units in EPSG:4326, area matches register within 0.1%

## Phase 3 — 3D geometry
- [x] src/geometry/extrude.py
- [x] src/geometry/slice_floors.py (official > estimated > rule of thumb, source flagged)
- [x] src/geometry/units.py: 84 flats over 5 floors + 20 parking in B01 = 104 volumes, all IDs unique
- [x] Negative Z (basements) supported
- [ ] smart mode (LiDAR DBSCAN) — optional

## Phase 4 — Validation (pure Python)
- [x] src/validate/checks.py: overlap, containment, gap, floating, duplicate_id, bad_id; real building CLEAN
- [x] tests/test_validate.py: 6 tests, one broken building per check (58 tests total)

## Phase 5 — API + viewer = FIRST FULL DEMO
- [x] src/api/main.py (FastAPI over GeoJSON files, serves web/)
- [x] web/index.html CesiumJS: extruded unit volumes, coloured by level (OSM imagery, no token)
- [x] click unit → ULPIN anatomy panel (5 labelled segments) + area/volume
- [x] floor slider
- [x] underground toggle (globe translucency)
- [x] validation errors in red + broken demo building via src/validate/make_broken.py
- [ ] 2-minute demo runs in browser — FREEZE (needs Param to open it and rehearse)

## Phase 5b — Intake page (added 13 Sep after Param's question "where do we input drones/LiDAR/images?")
- [x] web/submit.html: parcel ULPIN, outline upload or register ID, height (typed / DSM+DTM / LAS / register), floors, basements, units, floor plan images
- [x] src/pipeline.py: one function chaining every step; POST /api/submit runs it
- [x] src/ingest/height.py: DSM−DTM (13.77 m) and LiDAR (13.78 m) vs register 14.01 m, real AHN data
- [x] src/ingest/clip_las.py: 6.4 MB demo LiDAR clip from the 461 MB AHN4 tile
- [x] All four intake routes tested end to end; tests/test_pipeline.py (61 tests)
- [x] "Pick on the map": src/ingest/osm.py (Nominatim search + Overpass outline, any city), map in submit.html; OSM values labelled osm, never official
- [x] Offline cache: src/ingest/osm_extract.py cuts 145,435 buildings (Anand 2,330 / Ahmedabad 103,060 / Vadodara 40,045) from the Geofabrik western-zone extract; lookups instant, no internet
- [x] Placeholder parent ULPIN derived from location fills the form on pick (labelled demo placeholder)
- [x] Two routes (Param, 13 Sep): web/from-map.html (mode=estimate: gaps filled and labelled, record "estimated") and web/manual.html (mode=manual: refuses gaps and map values, record "surveyed"); submit.html is the chooser; viewer shows the badge; tests for both modes (64)
- [x] web/try_model.html + POST /api/plan_preview: upload any floor plan, see the model's apartments live

## Phase 6 — AI models (additive)
- [x] 6a src/models/floorplan.py: YOLOv8s-seg fine-tuned on MSD (4,569 train / 800 val plans); mask mAP50 0.423, recall 0.50 (baseline 0.152 before the label fix); wired into units.py --plan-units
- [x] 6b src/models/building.py: SAM (vit_b, pretrained) on a real 25 cm PDOK orthophoto, roof traced + squared to 14 corners, IoU 0.71 vs register; wired into manual.html "Extract from drone orthophoto"
- [ ] 6c src/models/pointcloud.py — optional, cut first
- [x] 6d src/models/floors.py: trained on 5,921 official counts, MAE 0.20 floors, 99.5% within 1; valid only <= 22.7 m (training max), falls back to rule of thumb above

## Phase 6e — SIH gap closure (Param's audit, 13 Sep)
- [x] Underground utilities: src/geometry/utilities.py, B00 + T codes, depth → level; 2 demo corridors under the Delft block; shown in the viewer (grey)
- [x] Ownership: owner field on both intake pages, recorded on every volume, shown in the viewer panel
- [x] GNSS/CORS: src/ingest/gnss.py shifts the outline onto control points (demo CSV: 3 points, residual 0.04 m)
- [x] All four combined in one manual run: 106 volumes, surveyed, validator clean (tests: 69)

- [x] Revenue-village hierarchy (Param's link, datta07/INDIAN-SHAPEFILES): src/ingest/admin.py; placeholder ULPIN now state+district+village census code+parcel; village shown in the form, the record and the viewer
- [ ] GOBS building stock (AEEE): satellite estimates, not LiDAR; needs a browser login to download; join as `gobs_satellite` source when the Gujarat CSV is available

- [x] demo_inputs/: 25 real Gujarat apartment buildings (12 Ahmedabad, 10 Vadodara, 3 Anand), each with real outline, Census codes, Copernicus 30 m DEM cut, facts.json listing what is real vs unavailable; synthetic utilities + CORS marked DEMO; 00_OUT_OF_INDIA_SUBSTITUTES/ for LiDAR, orthophoto, DSM/DTM, floor plans; README_FOR_JUDGES.md; site 07 run end to end with every file (58 volumes)
- [x] Research (agent-reach: Exa + OpenAerialMap API + figshare API): no open city LiDAR for India (TALD Thiruvananthapuram is registration-gated), only 2 true drone flights over 16 Indian cities on OpenAerialMap, Copernicus DEM 30 m is the only no-login India DEM

- [x] demo_inputs_open/: 5 Delft apartment blocks, every Manual step a real open file (Kadaster parcel + derived 14-digit ULPIN, BAG outline, PDOK orthophoto, AHN DSM/DTM, AHN4 LiDAR clip, official floors/units, MSD plans per floor, owner). Block 01 run end to end: 43 volumes, nothing assumed. `src/ingest/demo_open.py`
- [x] Research (agent-reach Exa): no country ties open floor plans to a locatable building; Netherlands is the only one with all other five inputs open for the same building

## Phase 7 — PostGIS + LADM + CityJSON
- [ ] PostgreSQL + PostGIS + SFCGAL installed, db `ulpin3d` (needs admin)
- [x] src/db/schema.sql (LADM tables + v_overlaps SFCGAL cross-check view) — untested until PostgreSQL exists
- [ ] PostGIS cross-check of validator
- [x] CityJSON export: src/db/export_cityjson.py, 104 BuildingUnit solids
- [ ] Isolation Forest — optional

## Phase 8 — Scale (optional)
- [ ] 3–4 more 3DBAG buildings
- [x] Indian buildings: any OSM-mapped building via the map picker (Ahmedabad Prerna Arbour Complex run end to end; Anand coverage patchy)

## Final
- [x] README with screenshots (docs/screenshots/)
- [x] Presentation deck: docs/deck/3D_ULPIN_SIH26011.pptx (12 slides, validated, rendered and reviewed)
- [ ] Demo rehearsed 3×
