# Demo inputs, all open data: 5 apartment blocks, every step real

Every file here is real, open-licence data for the building named in the folder. No
synthetic files, no placeholders. Use with `http://127.0.0.1:8000/manual.html`.

```
01_Delft_apartment_block_0948_5floors_86units/
    step1_parcel/                ULPIN.txt, cadastral_parcel.geojson
    step2_outline/               outline.geojson, drone_orthophoto_25cm.tif, orthophoto_roof_point.txt
    step3_height/                DSM_50cm.tif, DTM_50cm.tif, lidar_AHN4.laz
    step4_floors_units/          floors_and_units.txt
    step5_floor_plans/           G00.png, F01.png, F02.png, F03.png, F04.png
    step6_owner_utilities_cors/  owner.txt
```

| Manual step | File | Source, all open |
|---|---|---|
| 1 The parcel | `ULPIN.txt` | 14 digits derived from the building's real cadastral parcel (Kadaster, the Dutch land registry, open map via PDOK) |
| 1 The parcel | `cadastral_parcel.geojson` | the parcel polygon with its official Kadaster ID |
| 2 Outline | `outline.geojson` | official building footprint, BAG register |
| 2 Outline, AI option | `drone_orthophoto_25cm.tif` + `orthophoto_roof_point.txt` | 25 cm aerial orthophoto (PDOK); the point file gives the lon/lat to type for "Extract from drone orthophoto" |
| 3 Height | `DSM_50cm.tif`, `DTM_50cm.tif` | national elevation model AHN, 50 cm |
| 3 Height | `lidar_AHN4.laz` | national LiDAR AHN4, clipped 30 m around the building |
| 4 Floors and units | `floors_and_units.txt` | official floor count (3DBAG) and registered unit count (BAG) |
| 5 Floor plans | one PNG per floor | real multi-apartment floor plans, MSD dataset, CC-BY-4.0 |
| 6 Owner | `owner.txt` | the Dutch owners' association name for the building |

## Why the Netherlands
It is the only country that publishes outline, parcel, height, LiDAR, orthophoto and
unit register openly for the same building. Floor plans are the one input no country
ties to a locatable building in open data; the MSD plans are real Swiss apartment
floors under an open licence. India publishes none of these six openly today; a state
government holds all of them.

## Run one, step by step
1. Parcel: `step1_parcel/ULPIN.txt` gives both values: the 14-digit ULPIN, and building number **1** (not the parcel number, which is already inside the ULPIN).
2. Outline: upload `step2_outline/outline.geojson`. Or choose "Extract from drone orthophoto", upload the `.tif`, type the lon and lat from `orthophoto_roof_point.txt`.
3. Height: "LiDAR point cloud", upload `step3_height/lidar_AHN4.laz`. Or "Drone elevation" with the DSM and DTM.
4. Floors and units: the two numbers in `step4_floors_units/floors_and_units.txt`. Basements 1 if you want parking slots shown.
5. Floor plans: "Add a floor plan" five times, G00 to F04, one PNG each.
6. Owner: the name in `step6_owner_utilities_cors/owner.txt`. Utilities and CORS: leave empty (no open source anywhere).
7. Generate. Tested on block 01: height 14.3 m from LiDAR against 14.5 m in the register, 23 flats found across the five plans, 43 volumes, nothing assumed, record marked surveyed.

## The five blocks

| Folder | Floors | Registered units | Height |
|---|---|---|---|
| 01 block 0948 | 5 | 86 | 14.5 m |
| 02 block 0016 | 5 | 84 | 14.5 m |
| 03 block 0011 | 5 | 60 | 14.5 m |
| 04 block 0019 | 5 | 84 | 13.9 m |
| 05 block 0071 | 5 | 84 | 14.0 m (the reference building used throughout the project) |
