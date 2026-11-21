"""The estimator must never extrapolate: above its training height it falls back to the rule of thumb and says so."""
import geopandas as gpd
import joblib
import numpy as np
from shapely.geometry import Point

from src.models.floors import predict


class Const:
    def predict(self, X):
        return np.full(len(X), 4.0)


def test_predict_flags_source_and_range(tmp_path):
    bundle = tmp_path / "m.joblib"
    joblib.dump({"model": Const(), "band": 1, "height_max_train_m": 22.7}, bundle)
    g = gpd.GeoDataFrame({
        "pand_id": ["a", "b", "c"],
        "height_m": [12.0, 50.0, 12.0], "height_max_m": [13.0, 54.0, 13.0], "footprint_m2": [500, 2000, 500],
        "year_built": [1985, 1965, 1985], "roof_type": ["slanted", "multiple horizontal", "slanted"],
        "floors_official": [None, None, 4],
        "geometry": [Point(72.9, 22.5)] * 3}, crs="EPSG:4326")
    out = predict(bundle, g)
    assert list(out.floors_source) == ["estimated", "rule_of_thumb", "official"]
    assert list(out.floors_estimated) == [4, 17, 4]
    assert (out.floors_low[1], out.floors_high[1]) == (15, 19)
