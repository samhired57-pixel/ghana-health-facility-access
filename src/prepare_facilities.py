"""
Prepare the health-facility point layer.

- Loads the HDX "Ghana Healthsites" GeoJSON.
- Keeps point geometries with valid coordinates inside Ghana's bbox.
- Drops exact duplicate coordinates (same lon/lat rounded to 5 decimals).
- Writes data/facilities.geojson (WGS84) and prints a summary, including a
  breakdown by facility type where the source provides one.

Usage:  python src/prepare_facilities.py
"""
import json
import os

import geopandas as gpd
from shapely.geometry import Point

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
# Rough Ghana bbox (lon/lat) used only to drop obvious out-of-country junk.
GHANA_BBOX = (-3.3, 4.6, 1.2, 11.3)


def main():
    src = os.path.join(DATA, "ghana.geojson")  # HDX "Ghana Healthsites" download name
    gdf = gpd.read_file(src)
    print(f"raw features: {len(gdf)}")

    # Keep valid geometries; collapse non-point geometries (e.g. hospital campuses
    # mapped as polygons) to their representative point so they are not lost.
    gdf = gdf[gdf.geometry.notnull() & gdf.geometry.is_valid].copy()
    is_pt = gdf.geometry.type == "Point"
    print(f"non-point geometries converted to representative points: {int((~is_pt).sum())}")
    gdf.loc[~is_pt, "geometry"] = gdf.loc[~is_pt, "geometry"].representative_point()
    gdf = gdf.set_geometry("geometry")
    x, y = gdf.geometry.x, gdf.geometry.y
    inside = (x.between(*GHANA_BBOX[0::2])) & (y.between(*GHANA_BBOX[1::2]))
    dropped_outside = int((~inside).sum())
    gdf = gdf[inside]

    # Drop exact duplicate coordinates.
    gdf["_key"] = list(zip(gdf.geometry.x.round(5), gdf.geometry.y.round(5)))
    before = len(gdf)
    gdf = gdf.drop_duplicates(subset="_key").drop(columns=["_key"])
    print(f"dropped {dropped_outside} points outside Ghana bbox, "
          f"{before - len(gdf)} exact duplicate coordinates")

    # Normalize a couple of useful columns if present.
    cols = {c.lower(): c for c in gdf.columns}
    rename = {}
    if "name" in cols:
        rename[cols["name"]] = "name"
    for cand in ("amenity", "healthcare", "facility_type", "type"):
        if cand in cols:
            rename[cols[cand]] = "facility_type"
            break
    gdf = gdf.rename(columns=rename)
    keep = [c for c in ("name", "facility_type") if c in gdf.columns]
    out = gdf[keep + ["geometry"]].copy()

    dest = os.path.join(DATA, "facilities.geojson")
    out.to_file(dest, driver="GeoJSON")
    print(f"clean facilities: {len(out)} -> {dest}")
    if "facility_type" in out.columns:
        print(out["facility_type"].fillna("unknown").value_counts().head(15).to_string())

    # Clinical-only subset (hospitals, clinics, doctors, dentists — no pharmacies)
    # used for the sensitivity analysis in coverage.py.
    if "facility_type" in out.columns:
        clinical = out[~out["facility_type"].fillna("").str.lower().isin(
            {"pharmacy", "pharmacies"})].copy()
        cdest = os.path.join(DATA, "facilities_clinical.geojson")
        clinical.to_file(cdest, driver="GeoJSON")
        print(f"clinical-only facilities: {len(clinical)} -> {cdest}")


if __name__ == "__main__":
    main()
