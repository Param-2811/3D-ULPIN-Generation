# Two-minute demo script

Rehearse this three times. Every number below is real output from the pipeline.

## Before the judges arrive

```
.venv\Scripts\uvicorn src.api.main:app --port 8000
```
Open two browser tabs and zoom to the building in both:
- Tab A: `http://127.0.0.1:8000/`
- Tab B: `http://127.0.0.1:8000/?building=0503100000000071-broken`

Have a terminal ready with `.venv\Scripts\python -m pytest -q` already run (59 passed).

Also open Tab C: `http://127.0.0.1:8000/submit.html` with the file
`data/raw/0503100000000071_lidar.laz` ready in a folder window.

## When a judge says "do it for a building in MY city"
Tab C, `submit.html`, shows two cards: **From map** (estimated, nothing to type) and
**Manual** (surveyed, every value required). Pick From map; it opens on a map. Type the building or area name and press
Search, or scroll the map to it and click the building. The outline turns red and the
form fills with whatever OpenStreetMap knows (floors, sometimes height), each value
labelled "osm". Type the parcel's ULPIN (any 14 digits for a demo), a unit count or
upload plans, press Generate, open in 3D. Say out loud: "outline and floor count come
from OpenStreetMap volunteers here; in production they come from BhuNaksha and the
building approval, which is why every number carries its source."
Anand, Ahmedabad and Vadodara are cached on disk, so clicks there are instant and need
no internet. Good Anand picks: scroll to 22.5505, 72.9312 (Narayan and Vrajdham
apartments, 6 and 5 floors from the map), or Krishna Kamal Apartments near
22.5492, 72.9674. Ahmedabad: "Prerna Arbour Complex" (6 floors). Other cities go to the
public OpenStreetMap server, which can time out; if it does, or a click finds no
outline, switch to "Upload outline" and say so. The parent ULPIN box fills with a
location-based placeholder; say "real ULPINs are issued by DoLR, this stands in".

## When a judge says "try your model on THIS plan"
Open `http://127.0.0.1:8000/try_model.html`, upload the image, press "Find apartments".
Outlines appear with unit numbers and confidence. Sample unseen plans are listed on the
page. A clean wall drawing works best; a photo of a paper plan will do worse, say so.

## Optional opener (adds 30 s): show the input side first
On Tab C: type the ULPIN, choose "Dutch register ID" and enter 0503100000000071,
pick "LiDAR point cloud" and upload the .laz file, basements 1, press "Generate 3D
ULPINs". Read the steps aloud as they appear: "height 13.8 m measured from 25,000
laser points, register says 14.0; six levels; 104 volumes; validator clean." Click
the link to open it in the viewer. Then continue below from 0:15.

## 0:00 — The problem (one sentence)
"India's ULPIN identifies a plot of land. It cannot name flat 302 on the third floor,
a basement parking slot, or the water main under the plot. We extend it so it can."

## 0:15 — The ID (Tab A, click any flat)
Point at the panel: "First 14 digits are the existing ULPIN, unchanged. Then building,
level, unit, and a check digit. An officer reads B01-F02-U05 and knows: building 1,
floor 2, flat 5. Mistype one digit and the ID is rejected."

## 0:40 — Real data, real answers
"This is a real building in Delft: 14 metres tall, 5 floors and 84 flats on official
record. Our outline measures 1,057.8 square metres against the register's 1,057.
Every one of the 104 volumes has a unique ID."
Drag the floor slider down to G00 and back up. Click "Show underground": "Basement
parking slots get P codes below ground."

## 1:05 — The validator (Tab B)
"Same building, five faults injected on purpose: a flat slid onto its neighbour, one
pushed outside, one deleted, one lifted off its slab, one duplicate ID."
Point at the red list: "Eight findings, all five kinds caught, each one clickable."

## 1:30 — AI where it helps, rules where it matters
"Two models we trained ourselves, at zero cost: one finds each flat on a floor plan,
one estimates the floor count when the register is silent and labels it as an
estimate. IDs, checks and storage are exact code, because an ID that is 'probably
right' is useless for a land record."

## 1:50 — Close
"Backward compatible, human readable, error resistant, deterministic, validated in
3D, exported to CityJSON and an LADM database. One building today; the pipeline is
one parcel, one building, one run, so a state can process buildings as plans arrive."

## Demo files and where they came from

| What | File | Source |
|---|---|---|
| 3D model of the building | `data/raw/0503100000000071.city.json` | 3DBAG API, https://api.3dbag.nl |
| 84 registered dwelling units | `data/raw/0503100000000071_units.geojson` | BAG via PDOK WFS |
| Clean outline with facts | `data/processed/0503100000000071.geojson` | our `align.py` |
| DSM and DTM rasters | `data/raw/0503100000000071_dsm.tif`, `_dtm.tif` | AHN via PDOK WCS |
| LiDAR clip to upload (6.4 MB) | `data/raw/0503100000000071_lidar.laz` | AHN4 tile 37EN1_19, GeoTiles TU Delft, clipped by `clip_las.py` |
| Floor plan images to upload | `data/processed/msd_yolo_v3/images/val/5848.png`, `41005.png` | MSD on HuggingFace, CC-BY-4.0 |
| Trained models | `data/processed/floorplan/weights/best.pt`, `data/processed/floors_model.joblib` | trained on this laptop |
| 17-storey tower (no official floor count) | `data/raw/0503100000000020.*` | 3DBAG and BAG |

If `data/` is missing on the demo machine: run the two download lines in the README,
then `clip_las.py` needs the 461 MB tile from GeoTiles (or copy the 6.4 MB clip).

## Likely questions

- **How does this scale to all of India?** It never touches a city-wide dataset. One
  parcel per run. Footprints and heights for India exist in Google Open Buildings
  2.5D; floor plans sit with every municipality's approval department.
- **Integration with existing records?** The parent ULPIN is the existing one. The
  database follows LADM (ISO 19152). The API returns any unit by ID.
- **What if a building is modified?** Re-run the pipeline. Unchanged units keep their
  IDs because numbering is deterministic (clockwise from the north-west corner).
- **Why a Dutch building?** It is the only open building found with height, floor
  count and unit count all on official record, so we can prove accuracy. Say it before
  they ask.
- **What is not real?** Flat shapes are equal strips (no public floor plan for this
  building); the basement is an operator input; owners are not linked yet.
