# Project plan — build in this order

Rule: **finish a phase completely before starting the next.** Each phase has an exit
criterion. If the exit criterion is not met, do not move on.

> **Revised 2026-09-13 (Session 2).** The original order was
> Setup → Data → Geometry → ULPIN → AI → Validation+DB → Viewer.
> Changed because: (1) the ULPIN generator needs no data, so it was blocked for no reason;
> (2) the AI phase (3–4 days) sat *before* the validator and viewer, which the plan itself
> says can never be cut — if time ran out mid-AI there would be no demo; (3) validation was
> tied to PostGIS, which is not installed, yet our units are extruded prisms so the checks
> run in plain shapely. New principle: **get one building end-to-end in the browser first,
> then add AI and the database on top.** The original text is in git history.

---

## Phase 0 — Setup ✅ (DB deferred)

- Folder structure, Python 3.11 venv via uv, `requirements.txt`, `.gitignore`
- `docs/PROGRESS.md`, `PROJECT_LOG.md`
- PostgreSQL + PostGIS + SFCGAL → moved to Phase 7; not needed before then

**Exit criterion:** `python -c "import geopandas, rasterio, shapely; print('ok')"` runs. ✅

---

## Phase 1 — The ULPIN generator ✅ (half a day)

`src/ulpin/generate.py` following `docs/ULPIN_SPEC.md` exactly: `generate`, `parse`,
`validate`, plus `clockwise_from_northwest` for the stable unit-ordering rule.
Deterministic, Luhn check digit, full pytest coverage incl. bad input and every
single-digit typo.

**Exit criterion:** `parse(generate(x)) == x` for every level and unit prefix; any one
mistyped digit is rejected; tests pass. ✅ (52 tests)

---

## Phase 2 — Get real data (1 day)

- `src/ingest/download.py` — fetches one building from the 3DBAG API
  (`https://api.3dbag.nl`), which ships footprint + verified height + roof geometry.
  Dwelling-unit count comes from the Dutch BAG register (PDOK) for the same building ID
  — if that lookup is unavailable, say so in DATA_SOURCES.md rather than inventing a count.
- Record the chosen building's ID and coordinates in `docs/DATA_SOURCES.md`.
- `src/ingest/align.py` — reprojects every input to EPSG:4326 for storage; measurements
  in EPSG:32643. Note: the Dutch building's *native* metric CRS
  is EPSG:28992; measure the Dutch demo building in that, and Indian buildings in 32643.
  The rule is "measure in metres", the zone follows the building.

**Exit criterion:** one building footprint (GeoJSON) + height + (if available) true unit
count in `data/raw/`; `align.py` reports all layers share one CRS.

---

## Phase 3 — 3D geometry engine (2 days)

- `src/geometry/extrude.py` — 2D footprint + height → 3D prism (floor polygon,
  `z_min`, `z_max`)
- `src/geometry/slice_floors.py` — simple mode `floors = round(height / 3.0)`;
  smart mode (LiDAR Z histogram + DBSCAN) only if time allows
- `src/geometry/units.py` — subdivide a floor into unit polygons, number them with
  `clockwise_from_northwest`, stamp each with its 3D ULPIN
- Negative Z for basements from day one

**Exit criterion:** the Phase 2 building yields a list of unit volumes with `z_min`/`z_max`
and unique ULPINs; floor count close to the real one.

---

## Phase 4 — Validation (1 day)

`src/validate/checks.py`, pure Python on prisms (2D shapely + Z-interval maths):
- **Overlap** — two units on overlapping Z ranges must not have intersecting footprints
- **Containment** — every unit footprint inside the building footprint, Z within envelope
- **Gaps** — sum of unit areas vs floor area
- **Floating units** — `z_min` must equal a floor slab level
- **Duplicate IDs** — bijection check
- 2–3 deliberately broken buildings as pytest fixtures — the "we catch errors" demo moment

Isolation Forest → Phase 7 (nice-to-have).

**Exit criterion:** clean building passes; each broken fixture produces a specific,
named error; `tests/test_validate.py` passes.

---

## Phase 5 — API + 3D viewer = FIRST FULL DEMO (2–3 days)

- `src/api/main.py` — FastAPI: list buildings, units of a building, one unit by ULPIN,
  validation report. Reads the Phase 3/4 output files directly (no DB yet).
- `web/` — CesiumJS, using the entity API with extruded polygons (`height` /
  `extrudedHeight`). No 3D Tiles conversion — one building does not need it.
  1. building rendered, each unit a coloured volume
  2. click unit → ULPIN, floor, area, volume
  3. floor slider
  4. underground toggle
  5. validation errors in red

**Exit criterion — DEMO CHECKPOINT:** a 2-minute demo runs end to end in a browser.
Freeze this. Everything after is additive; if it breaks, roll back to here.

---

## Phase 6 — AI models (2–3 days, additive)

Pretrained weights only. Each model replaces a manual step in Phases 2–3:
- 6a `src/models/floorplan.py` — CubiCasa5k → unit polygons (replaces hand subdivision
  in `units.py`)
- 6b `src/models/building.py` — SAM via segment-geospatial → footprint from aerial
  GeoTIFF (replaces the downloaded footprint)
- 6c `src/models/pointcloud.py` — OPTIONAL, cut first
- 6d `src/models/floors.py` — **floor-count estimator** (Param's suggestion, 13 Sep).
  Gradient boosting (scikit-learn) trained on 3DBAG buildings that carry an official
  `b3_bouwlagen`, features: height, max height, ground area, wall area, roof type, year,
  unit count. Used only when the official count is missing; output is stored with
  `floors_source = official | estimated | rule_of_thumb` and a confidence range, never as
  a bare number. Fallback: height / 3 m. Trains in seconds, no GPU, cost 0.

**Exit criterion:** 6a and 6b output feeds Phase 3 without manual editing.

---

## Phase 7 — Interoperability: PostGIS + LADM + CityJSON (1–2 days)

- Install PostgreSQL + PostGIS + SFCGAL, database `ulpin3d`
- `src/db/schema.sql` on LADM (ISO 19152): `la_party`, `la_rrr`, `la_spatialunit`,
  `la_building_unit`, `la_utility_network`
- Load Phase 3 output; re-run Phase 4 checks with `ST_3DIntersects` / `ST_Volume` as a
  cross-check of the Python validator
- CityJSON export with ULPIN as attribute
- Isolation Forest anomaly flag, if time

**Exit criterion:** data round-trips through PostGIS without geometry loss; CityJSON
validates.

---

## Phase 8 — Scale demo (optional, 1 day)

- Run the pipeline on 3–4 more 3DBAG buildings unchanged
- One Indian building (Anand, Gujarat if footprints + height exist in Google Open
  Buildings 2.5D / ramSeraph) to show the pipeline on Indian data with EPSG:32643

---

## Final 1–2 days — do not skip

- Fix bugs; freeze the code
- README with screenshots
- Presentation deck
- Rehearse the demo at least 3 times
- Prepare answers for: scale to all of India? integration with existing records? what
  happens when a building is modified?

## If we fall behind — cut in this order

1. Phase 8 (scale demo)
2. Phase 6c, then 6b (keep 6a floor plans — the most visual)
3. Isolation Forest
4. Floor slider

**Never cut:** Phases 1, 3, 4, 5. Those *are* the project.
