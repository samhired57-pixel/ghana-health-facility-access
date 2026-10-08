"""
Per-district aggregation using GADM v4.1 Ghana level-2 boundaries.

For each of the 261 districts (MMDAs):
  * population (zonal sum of the WorldPop grid)
  * number of health facilities (spatial join)
  * facilities per 10,000 people
  * share of the district's population living beyond 10 km of a facility

Writes outputs/district_summary.csv sorted by % beyond 10 km (most underserved
first) and prints the 15 most underserved districts.

Usage:  python src/districts.py [suffix]
  suffix matches the coverage.py output suffix, e.g. "clinical".
  Default (no suffix): uses outputs/distance_km.tif + data/facilities.geojson.
Requires: outputs/distance_km[<suffix>].tif, data/facilities[<suffix>].geojson,
          data/gadm41_GHA_shp.zip (or the extracted shapefile)
"""
import json
import os
import sys
import zipfile

import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
import geopandas as gpd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "outputs")


def load_gadm():
    zpath = os.path.join(DATA, "gadm41_GHA_shp.zip")
    extract_dir = os.path.join(DATA, "gadm41_GHA_shp")
    if not os.path.isdir(extract_dir):
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(zpath) as zf:
            zf.extractall(extract_dir)
    import glob
    shp = glob.glob(os.path.join(extract_dir, "gadm41_GHA_2.shp"))[0]  # level 2 = districts
    gdf = gpd.read_file(shp)
    print(f"GADM level-2 districts: {len(gdf)}")
    assert "NAME_2" in gdf.columns, f"unexpected columns: {list(gdf.columns)}"
    return gdf


def main():
    os.makedirs(OUT, exist_ok=True)
    suffix = f"_{sys.argv[1]}" if len(sys.argv) > 1 else ""
    fac_file = os.path.join(DATA, f"facilities{suffix}.geojson")
    print(f"using {fac_file} with distance raster outputs/distance_km{suffix}.tif")
    districts = load_gadm()
    districts = districts.reset_index(drop=True)
    districts["_did"] = np.arange(len(districts))

    with rasterio.open(os.path.join(OUT, f"distance_km{suffix}.tif")) as ds:
        dist = ds.read(1).astype(np.float32)
        transform, shape, crs = ds.transform, ds.shape, ds.crs
    with rasterio.open(os.path.join(DATA, "gha_ppp_2020.tif")) as ds:
        pop = ds.read(1, masked=True).filled(0).astype(np.float32)
    # Align population to the (possibly downsampled) distance grid.
    if pop.shape != shape:
        pop = pop[::2, ::2] * 4.0
        assert pop.shape == shape, (pop.shape, shape)
    pop = np.nan_to_num(pop, nan=0.0).clip(min=0)
    dist_valid = dist >= 0
    beyond10 = ((dist > 10) & dist_valid).astype(np.float32)

    shapes = [(g, d) for g, d in zip(districts.geometry, districts["_did"])]
    zone = rasterize(
        shapes,
        out_shape=shape, transform=transform, fill=-1, dtype=np.int32,
    )
    valid = (zone >= 0) & dist_valid
    z = zone[valid].astype(np.int64)
    p = pop[valid]
    b = beyond10[valid]
    n = len(districts)
    pop_sum = np.bincount(z, weights=p, minlength=n)
    beyond_sum = np.bincount(z, weights=b * p, minlength=n)

    fac = gpd.read_file(fac_file).to_crs(crs)
    joined = gpd.sjoin(fac[["geometry"]], districts[["_did", "geometry"]],
                       how="left", predicate="within")
    fac_count = np.bincount(joined["_did"].dropna().astype(int), minlength=n)

    name_col = "NAME_2" if "NAME_2" in districts.columns else districts.columns[2]
    df = pd.DataFrame({
        "district": districts[name_col],
        "region": districts["NAME_1"] if "NAME_1" in districts.columns else "",
        "population_2020": np.round(pop_sum).astype(int),
        "n_facilities": fac_count,
        "facilities_per_10k": np.where(pop_sum > 0, fac_count / pop_sum * 10000, np.nan).round(2),
        "pop_beyond_10km": np.round(beyond_sum).astype(int),
        "pct_beyond_10km": np.where(pop_sum > 0, beyond_sum / pop_sum * 100, np.nan).round(2),
    })
    df = df.sort_values("pct_beyond_10km", ascending=False).reset_index(drop=True)
    dest = os.path.join(OUT, f"district_summary{suffix}.csv")
    df.to_csv(dest, index=False)
    print(f"wrote {dest} ({len(df)} districts)")
    print("\n15 most underserved districts (% of population beyond 10 km):")
    print(df[["district", "region", "population_2020", "n_facilities",
              "facilities_per_10k", "pct_beyond_10km"]].head(15).to_string(index=False))
    print("\n15 best-served districts:")
    print(df[["district", "region", "population_2020", "n_facilities",
              "facilities_per_10k", "pct_beyond_10km"]].tail(15).to_string(index=False))


if __name__ == "__main__":
    main()
