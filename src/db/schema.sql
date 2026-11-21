-- 3D ULPIN storage, modelled on LADM (ISO 19152) so it plugs into existing land-administration systems.
-- Requires: CREATE EXTENSION postgis; CREATE EXTENSION postgis_sfcgal;
-- Geometry is stored in EPSG:4326 (project rule); measure in a metric CRS via ST_Transform.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_sfcgal;

-- LA_Party: who holds rights (owner, tenant, bank, government)
CREATE TABLE IF NOT EXISTS la_party (
    party_id    SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    party_type  TEXT NOT NULL CHECK (party_type IN ('natural_person', 'organisation', 'government')),
    identifier  TEXT                           -- Aadhaar / PAN / CIN, hashed in production
);

-- LA_SpatialUnit: one row per 3D volume. The 3D ULPIN is the primary key.
CREATE TABLE IF NOT EXISTS la_spatialunit (
    ulpin_3d      TEXT PRIMARY KEY CHECK (ulpin_3d ~ '^\d{14}-B\d{2}-(G00|F(0[1-9]|[1-9]\d)|B0[1-9]|R00|A0[1-9])-[UPCT]\d{2}-\d$'),
    parent_ulpin  CHAR(14) NOT NULL,           -- India's existing 2D ULPIN, unchanged
    building_no   SMALLINT NOT NULL,
    level_code    CHAR(3) NOT NULL,
    unit_code     CHAR(3) NOT NULL,
    z_min_m       NUMERIC(7,2) NOT NULL,       -- relative to ground; negative = below ground
    z_max_m       NUMERIC(7,2) NOT NULL CHECK (z_max_m > z_min_m),
    footprint     geometry(Polygon, 4326) NOT NULL,
    solid         geometry(PolyhedralSurfaceZ, 4326),   -- built by ST_Extrude in load step; SFCGAL checks use it
    area_m2       NUMERIC(10,1),
    volume_m3     NUMERIC(12,1),
    floors_source TEXT NOT NULL CHECK (floors_source IN ('official', 'estimated', 'rule_of_thumb'))
);
CREATE INDEX IF NOT EXISTS la_spatialunit_footprint_gix ON la_spatialunit USING GIST (footprint);
CREATE INDEX IF NOT EXISTS la_spatialunit_parent_idx ON la_spatialunit (parent_ulpin, building_no, level_code);

-- LA_BuildingUnit: the apartment / shop as a legal object, pointing at its volume
CREATE TABLE IF NOT EXISTS la_building_unit (
    unit_id      SERIAL PRIMARY KEY,
    ulpin_3d     TEXT NOT NULL UNIQUE REFERENCES la_spatialunit (ulpin_3d),
    use_type     TEXT NOT NULL CHECK (use_type IN ('residential', 'commercial', 'parking', 'common', 'utility')),
    address      TEXT,
    carpet_area_m2 NUMERIC(10,1)
);

-- LA_RRR: rights, restrictions, responsibilities linking a party to a volume
CREATE TABLE IF NOT EXISTS la_rrr (
    rrr_id      SERIAL PRIMARY KEY,
    ulpin_3d    TEXT NOT NULL REFERENCES la_spatialunit (ulpin_3d),
    party_id    INTEGER NOT NULL REFERENCES la_party (party_id),
    rrr_type    TEXT NOT NULL CHECK (rrr_type IN ('ownership', 'lease', 'mortgage', 'easement', 'restriction')),
    share       NUMERIC(5,4) DEFAULT 1.0 CHECK (share > 0 AND share <= 1),
    valid_from  DATE NOT NULL DEFAULT CURRENT_DATE,
    valid_to    DATE
);

-- LA_UtilityNetwork: pipes, tunnels, metro corridors crossing under a parcel (building_no = 0, unit prefix T)
CREATE TABLE IF NOT EXISTS la_utility_network (
    utility_id   SERIAL PRIMARY KEY,
    ulpin_3d     TEXT NOT NULL UNIQUE REFERENCES la_spatialunit (ulpin_3d),
    network_type TEXT NOT NULL CHECK (network_type IN ('water', 'sewer', 'gas', 'power', 'telecom', 'metro', 'tunnel')),
    operator     TEXT
);

-- Cross-check of the Python validator: any two volumes on the same parcel whose solids intersect in 3D.
CREATE OR REPLACE VIEW v_overlaps AS
SELECT a.ulpin_3d AS ulpin_a, b.ulpin_3d AS ulpin_b
FROM la_spatialunit a
JOIN la_spatialunit b ON a.parent_ulpin = b.parent_ulpin AND a.ulpin_3d < b.ulpin_3d
WHERE a.solid IS NOT NULL AND b.solid IS NOT NULL
  AND ST_3DIntersects(a.solid, b.solid)
  AND ST_Volume(ST_3DIntersection(a.solid, b.solid)) > 0.5;
