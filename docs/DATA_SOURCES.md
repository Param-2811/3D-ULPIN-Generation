# Data sources

DoLR did not attach a dataset to this problem statement. Everything below is open data we
assemble ourselves. **Be transparent in the demo about what is real and what is synthetic**
— judges respect that more than a polished but fake demo.

## Primary demo building

| Need | Source | URL |
|---|---|---|
| Building with verified height + real unit count | 3DBAG (Netherlands) | https://3dbag.nl |
| 3DBAG documentation | | https://docs.3dbag.nl/en/ |
| Matching LiDAR tiles | AHN via GeoTiles | https://geotiles.nl |
| Aerial imagery + base layers | PDOK | https://www.pdok.nl |

Chosen because the footprint, the LiDAR, and the true number of dwelling units all exist
for the *same* building, giving us ground truth to validate against.

## Building footprints (India)

| Need | Source | URL |
|---|---|---|
| Google + Microsoft footprints, packaged for India | ramSeraph/indian_buildings | https://github.com/ramSeraph/indian_buildings |
| Building heights 2016–2023 | Google Open Buildings 2.5D Temporal | https://sites.research.google/gr/open-buildings/temporal/ |
| Same data in Earth Engine | | https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_Research_open-buildings-temporal_v1 |

Clip to a small bounding box — India-wide downloads run to hundreds of GB.

## Elevation (India)

| Need | Source | URL |
|---|---|---|
| CartoDEM / satellite data | Bhoonidhi (ISRO) | https://bhoonidhi.nrsc.gov.in/ |
| Free data download | Bhuvan | https://bhuvan.nrsc.gov.in/wiki/index.php/Free_Satellite_Data_Download |

## LiDAR / point clouds

| Need | Source | URL |
|---|---|---|
| High-rise, high-density city (closest to Indian apartments) | HRHD-HK | https://github.com/maosuli/HRHD-HK |
| City-scale drone photogrammetry | SensatUrban | https://github.com/QingyongHu/SensatUrban |
| Drone LiDAR + imagery, same platform | Hessigheim 3D | https://ifpwww.ifp.uni-stuttgart.de/benchmark/hessigheim/default.aspx |
| General catalogue | OpenTopography | https://portal.opentopography.org/datasets |

## Floor plans

| Need | Source | URL |
|---|---|---|
| Pretrained model + 5k plans | CubiCasa5k | https://github.com/CubiCasa/CubiCasa5k |
| Multi-unit building complexes | MSD | https://github.com/caspervanengelenburg/msd |
| Real site → building → floor → unit hierarchy (~42k apartments) | Swiss Dwellings | https://zenodo.org/records/7070952 |

## 3D city / cadastre reference models

| Need | Source | URL |
|---|---|---|
| Australia's national 3D cadastre model | icsm-au/3d-cadastre-model | https://github.com/icsm-au/3d-cadastre-model |
| Open 3D city models incl. Singapore HDB, NL sewers | awesome-citygml | https://github.com/OloOcki/awesome-citygml |
| TU Delft open datasets | | https://3d.bk.tudelft.nl/opendata/ |
| CityJSON format spec | | https://github.com/cityjson/specs |

## GNSS / CORS

| Need | Source | URL |
|---|---|---|
| Survey of India CORS network | | https://cors.surveyofindia.gov.in/ |

Free for government and government academic institutions. For a private college, a paid
plan applies. A sample CSV of control points is sufficient for the demo.

## Drone imagery

| Need | Source | URL |
|---|---|---|
| Community drone imagery | OpenAerialMap | https://openaerialmap.org |
| Prior SVAMITVA hackathon work | subham-ryy/SVAMITVA-Geospatial-AI | https://github.com/subham-ryy/SVAMITVA-Geospatial-AI |

SVAMITVA orthophotos are not openly downloadable.

## Standards / reference

| Need | Source | URL |
|---|---|---|
| Official ULPIN reference | DoLR | https://dolr.gov.in/en/ulpin/ |
| Existing public repo for this same problem statement | | https://github.com/Mohitsaini785/3d-cadastral-digital-twin |

Look at that last repo to see what has already been attempted — it generates synthetic
LiDAR rather than using real data, which is exactly the gap we intend to beat.

## Known limitation — state this openly

No open dataset provides drone imagery, LiDAR, **and** floor plans for the same building.
Our approach:
- Real geometry and heights from 3DBAG / Open Buildings
- Floor plans attached from CubiCasa or MSD
- The LiDAR model demonstrated separately on HRHD-HK

If we need a fully coherent single building, simulate drone LiDAR over an IFC building
model with HELIOS++ (https://github.com/3dgeo-heidelberg/helios), using IFC samples from
https://github.com/buildingSMART/Sample-Test-Files.

---

## CHOSEN DEMO BUILDING (Phase 2, 2026-09-13)

| | Primary demo building | Phase 8 "wow" candidate |
|---|---|---|
| BAG pand id | `0503100000000071` | `0503100000000020` |
| Place | Delft, Netherlands | Delft, Netherlands |
| Footprint centre (lon, lat) | approx 4.3460, 51.9986 | see raw file |
| Height (3DBAG median roof minus ground) | 14.0 m | 50.6 m |
| Official floor count (`b3_bouwlagen`) | **5** | not available |
| Official dwelling units (BAG verblijfsobject) | **84**, all residential | 284 (264 residential) |
| Footprint area | 1057.8 m2 (3DBAG says 1057) | 1963 m2 |
| Roof | slanted, but h50 14.0 vs hmax 14.1 so nearly flat | multiple horizontal (flat) |
| Built | 1985 | 1965 |

Why `...071`: the only apartment block found with all three ground truths (height,
floor count, unit count) in official registers. Why `...020` later: a 17-storey flat-roofed
tower with 284 units looks better in the viewer but has no official floor count.

Re-download:
```
.venv/Scripts/python -m src.ingest.download 0503100000000071 -o data/raw
.venv/Scripts/python -m src.ingest.align data/raw/0503100000000071.city.json data/raw/0503100000000071_units.geojson -o data/processed/0503100000000071.geojson
```

APIs used (free, no key):
- 3DBAG OGC API: `https://api.3dbag.nl/collections/pand/items/NL.IMBAG.Pand.<id>`, CityJSON 2.0, CRS EPSG:7415 (RD New + NAP), LoD 0 / 1.2 / 1.3 / 2.2.
- BAG WFS (PDOK): `https://service.pdok.nl/lv/bag/wfs/v2_0`, layer `bag:verblijfsobject`, filtered with an FES XML filter on `pandidentificatie` (CQL_FILTER is silently ignored). CRS EPSG:28992.


---

## ADDED 13 Sep 2026: India admin boundaries and building stock

| Need | Source | Used for | Honest status |
|---|---|---|---|
| Revenue village / taluka / district polygons for Gujarat with Census 2011 and LGD codes | datta07/INDIAN-SHAPEFILES (MIT), `STATES/GUJARAT/GUJARAT_VILLAGES.geojson` (19,296 villages, 101 MB; trimmed to `data/raw/india_admin/gujarat_villages_lite.gpkg`, 24 MB) | `src/ingest/admin.py`: which village a building is in; placeholder ULPIN shaped like the real one (state 2 + district 3 + village 6 + parcel 3) | 2019 boundaries; the repo says "verify for official or legal purposes". Placeholder is not a DoLR-issued ULPIN. |
| Per-building footprint, height, floors, land use for all India (180 M buildings) | GOBS, AEEE, https://gobs.aeee.in, per-state `.csv.gz` behind a login | Would replace the OSM cache as the "From map" source with a height for every building | **Not LiDAR.** Their About page: footprints from Google Open Buildings v3 (satellite, "not based on official surveys"), height from Google Open Buildings Temporal, floors = height / 3 m. Download needs a browser login; not yet fetched. Label any value from it `gobs_satellite`. |

Other repos suggested and assessed: none contain LiDAR for Indian cities. No open LiDAR exists for India; the LiDAR demonstration uses the Dutch AHN4 tile.
