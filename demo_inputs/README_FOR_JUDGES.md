# Demo inputs: 25 real Indian buildings, every file labelled

Open `http://127.0.0.1:8000/manual.html`, pick any numbered folder, and choose its files
in the file dialog. Each folder is one real apartment building in Gujarat.

## What is in every site folder

Sub-folders are named after the steps on the Manual page, so the folder tells you where
the file goes. Open the building, then the step, then the file.

```
07_Centre_Point_Towers_Ahmedabad/
    READ_ME_FIRST.txt
    step1_parcel/                ULPIN.txt, village_codes.json
    step2_outline/               outline.geojson, parcel_outline_DEMO.geojson
    step3_height/                dem_copernicus_30m.tif, README.txt
    step4_floors_units/          floors_height_facts.json
    step5_floor_plans/           README.txt
    step6_owner_utilities_cors/  utilities_DEMO.geojson, cors_points_DEMO.csv
```

| Manual step | File | Real or stand-in | Source |
|---|---|---|---|
| 1 The parcel | `step1_parcel/ULPIN.txt` | Placeholder | 14-digit parent ULPIN shaped like the official one (state + district + village census code + parcel), village hierarchy, four example 3D ULPINs with real check digits. Copy the 14 digits into the form |
| 1 The parcel | `step1_parcel/village_codes.json` | **Real** | Census 2011 village / taluka / district codes (datta07/INDIAN-SHAPEFILES, 2019 boundaries) |
| 2 Building outline | `step2_outline/outline.geojson` | **Real** | OpenStreetMap (ODbL). Upload this. Its properties carry the parent ULPIN and village |
| 2 Building outline | `step2_outline/parcel_outline_DEMO.geojson` | Stand-in | the land parcel: outline + 6 m, squared. Real parcels are in BhuNaksha, not open |
| 3 Height | `step3_height/dem_copernicus_30m.tif` | **Real** | Copernicus DEM, 30 m, no login. Bare ground, too coarse for one building; the README there points to the Dutch DSM/DTM and LiDAR for a measured height |
| 4 Floors and units | `step4_floors_units/floors_height_facts.json` | **Real** where present | floors and height as mapped on OpenStreetMap, height if floors × 3 m, and two lists: what is real, what is not available for India |
| 5 Floor plans | `step5_floor_plans/README.txt` | pointer | no open Indian plans; use `00_OUT_OF_INDIA_SUBSTITUTES/floor_plans_swiss_MSD/` |
| 6 Owner, utilities, CORS | `step6_owner_utilities_cors/utilities_DEMO.geojson` | Stand-in | synthetic water and sewer lines. No open utility network for Indian cities |
| 6 Owner, utilities, CORS | `step6_owner_utilities_cors/cors_points_DEMO.csv` | Stand-in | synthetic control points on the real corners, 0.4 m / 0.2 m offset. Survey of India CORS is paid for private users |

`INDEX.csv` lists all 25 with name, city, floors, footprint and placeholder ULPIN.

## What to say to judges: data that does not exist for India at zero cost

| Input | Why not | What we do instead |
|---|---|---|
| Unit count, owner | Municipal building approvals and society registers are not open data | Type the number if known, else the form assumes from area and says so |
| Floor plans | No open dataset of Indian apartment plans exists | `00_OUT_OF_INDIA_SUBSTITUTES/floor_plans_swiss_MSD/` (Swiss, CC-BY-4.0). Our model was trained on 4,569 of these |
| LiDAR point cloud | No open city-scale LiDAR for any Indian city. TALD (Thiruvananthapuram, 2025) exists but is behind a registration wall; IIT Hyderabad has a campus sample | `00_OUT_OF_INDIA_SUBSTITUTES/lidar_point_cloud_Netherlands/` (AHN4, open). Height measured: 13.78 m vs 14.01 m in the register |
| Drone orthophoto | OpenAerialMap holds only 2 true drone flights over 16 Indian cities checked (Mumbai 5 cm, Thiruvananthapuram 6 cm), neither over an apartment block. SVAMITVA drone imagery is government-only | `00_OUT_OF_INDIA_SUBSTITUTES/drone_orthophoto_Netherlands/` (PDOK, 25 cm, open). SAM traced the roof at IoU 0.71 |
| DSM at building scale | Copernicus 30 m is bare earth only; no open sub-metre DSM for India | `00_OUT_OF_INDIA_SUBSTITUTES/dsm_dtm_elevation_Netherlands/` (AHN 50 cm). DSM minus DTM: 13.77 m |
| Utility network | Not open in India | synthetic lines in each folder, marked DEMO |
| CORS control points | Survey of India CORS: free for government, paid for private | synthetic CSV in each folder; the format is what a surveyor's receiver exports |

The sentence: "Every input the pipeline accepts is demonstrated on real data. Where India
has no open source yet, we show the same file type from a country that has one, and the
record is labelled accordingly. A state government has all of these inputs already."

## Suggested picks

- **01 Vrajdham, Anand** (5 floors on the map, village Bakrol).
- **07 Centre Point Towers, Ahmedabad** (6 floors, 1,609 m²): big footprint, good in 3D.
- **18 Aarohi Elysium Block G/H, Ahmedabad** (13 floors): tallest.
- **08 L&T residential, Vadodara** (10 floors).
- **02 Krishna Kamal, Anand** (no floor count on the map): shows the estimator labelling "estimated".

## Manual route, step by step with a site folder

1. **The parcel**: open `step1_parcel/ULPIN.txt`, copy the 14 digits into "Existing 14-digit ULPIN". Building number 1.
2. **Building outline**: "Upload outline (GeoJSON)", pick `step2_outline/outline.geojson`.
3. **Height**: "From the approved plan", type `height_m_if_floors_x3` from `step4_floors_units/floors_height_facts.json`. To show measurement instead, pick "LiDAR point cloud" and the Dutch `.laz` from `00_OUT_OF_INDIA_SUBSTITUTES/lidar_point_cloud_Netherlands/`.
4. **Floors and units**: `floors_osm` from the same facts file; basements 1; units from the approval if known, else an assumption.
5. **Floor plans**: "Add a floor plan", pick a Swiss plan from `00_OUT_OF_INDIA_SUBSTITUTES/floor_plans_swiss_MSD/`.
6. **Owner, utilities, CORS**: any society name; `step6_owner_utilities_cors/utilities_DEMO.geojson`; `step6_owner_utilities_cors/cors_points_DEMO.csv`.
7. Generate. The result lists every step and every assumption, then opens in 3D.
