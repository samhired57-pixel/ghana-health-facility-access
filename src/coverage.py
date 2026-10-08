"""
Population-weighted coverage analysis.

For every WorldPop 100 m cell in Ghana, compute the Euclidean distance to the
nearest health facility, then aggregate:

  * national share of population within 5 km / 10 km of a facility
  * population-weighted mean and median distance to a facility
  * a distance raster saved for the district-level step

Method notes (stated plainly — this is a screening metric, not a travel-time
model):
  - Distances are straight-line (Euclidean), computed on the WGS84 grid with
    per-axis metre sampling (mean-latitude correction). Road quality, terrain,
    rivers and transport mode are NOT modelled.
  - Facility points are OSM/healthsites.io community-mapped locations; rural
    coverage is likely under-mapped, so "beyond 10 km" areas are a lower bound
    on the true underserved population.
  - WorldPop 2020 is a modelled estimate, not a census count.

Memory: the distance transform allocates one float64 array the size of the
population grid (~a few hundred MB at 100 m). If the grid exceeds 60M cells
the script downsamples by 2 and records that fact in the outputs.

Usage:  python src/coverage.py [facilities_geojson] [output_prefix]
  Defaults: data/facilities.geojson -> outputs/{distance_km.tif, coverage_summary.json}
  Example:  python src/coverage.py data/facilities_clinical.geojson clinical
            -> outputs/{distance_km_clinical.tif, coverage_summary_clinical.json}
"""
import json
import os
import sys

import numpy as np
import rasterio
from rasterio.features import rasterize
from scipy.ndimage import distance_transform_edt
import geopandas as gpd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "outputs")

MAX_CELLS = 60_000_000
M_PER_DEG_LAT = 111_320.0


def main():
    os.makedirs(OUT, exist_ok=True)
    fac_file = sys.argv[1] if len(sys.argv) > 1 else os.path.join(DATA, "facilities.geojson")
    prefix = sys.argv[2] if len(sys.argv) > 2 else ""
    suffix = f"_{prefix}" if prefix else ""
    print(f"facilities: {fac_file}  (output suffix: '{suffix}')")
    pop_path = os.path.join(DATA, "gha_ppp_2020.tif")
    with rasterio.open(pop_path) as ds:
        pop = ds.read(1, masked=True).filled(0).astype(np.float32)
        transform, crs, shape = ds.transform, ds.crs, ds.shape
        res_deg = abs(transform.a)
        bounds = ds.bounds
    print(f"population grid: {shape[0]} x {shape[1]} = {shape[0]*shape[1]/1e6:.1f}M cells, "
          f"res {res_deg:.5f} deg, CRS {crs}")

    downsampled = False
    if shape[0] * shape[1] > MAX_CELLS:
        pop = pop[::2, ::2] * 4.0  # conserve persons when aggregating 2x2
        res_deg *= 2
        transform = rasterio.Affine(transform.a * 2, transform.b, transform.c,
                                    transform.d, transform.e * 2, transform.f)
        downsampled = True
        print(f"downsampled 2x for memory -> {pop.shape}")

    pop = np.nan_to_num(pop, nan=0.0).clip(min=0)
    total_pop = float(pop.sum())
    print(f"total population in raster: {total_pop:,.0f}")

    # Burn facility points onto the same grid.
    fac = gpd.read_file(fac_file).to_crs(crs)
    shapes = [(geom, 1) for geom in fac.geometry if geom is not None and not geom.is_empty]
    mask = rasterize(shapes, out_shape=pop.shape, transform=transform,
                     fill=0, dtype=np.uint8)
    print(f"facility cells burned: {int(mask.sum())} of {len(shapes)} points")

    # Euclidean distance (metres) to nearest facility cell.
    mean_lat = (bounds.bottom + bounds.top) / 2.0
    sampling = (res_deg * M_PER_DEG_LAT, res_deg * M_PER_DEG_LAT * np.cos(np.radians(mean_lat)))
    print(f"metre sampling per cell (y, x): ({sampling[0]:.1f}, {sampling[1]:.1f})")
    dist_m = distance_transform_edt(mask == 0, sampling=sampling).astype(np.float64)
    del mask

    dist_km = dist_m / 1000.0
    pop_w = pop.ravel().astype(np.float64)
    d_w = (dist_m.ravel() / 1000.0).astype(np.float64)
    within_5 = float(pop_w[d_w <= 5].sum())
    within_10 = float(pop_w[d_w <= 10].sum())
    # population-weighted quantiles of distance (float64 cumsum: float32 loses
    # precision once the running total exceeds ~16M people)
    order = np.argsort(d_w, kind="stable")
    cum = np.cumsum(pop_w[order])
    def q(p):
        idx = min(int(np.searchsorted(cum, p * total_pop)), len(d_w) - 1)
        return float(d_w[order[idx]])
    summary = {
        "facilities_file": os.path.basename(fac_file),
        "total_population": round(total_pop),
        "n_facilities": len(fac),
        "pct_within_5km": round(100 * within_5 / total_pop, 2),
        "pct_within_10km": round(100 * within_10 / total_pop, 2),
        "pop_beyond_10km": round(total_pop - within_10),
        "pop_weighted_mean_km": round(float(np.average(d_w, weights=pop_w)), 2),
        "pop_weighted_median_km": round(q(0.5), 2),
        "pop_weighted_p90_km": round(q(0.9), 2),
        "grid_resolution_m": round(sampling[0], 1),
        "grid_downsampled_2x": downsampled,
        "distance_metric": "Euclidean (straight-line); screening metric, not travel time",
    }
    with open(os.path.join(OUT, f"coverage_summary{suffix}.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    print(json.dumps(summary, indent=2))

    # Save distance raster for the district step (float32 km, LZW).
    with rasterio.open(pop_path) as ds:
        profile = ds.profile.copy()
    if downsampled:
        profile.update(width=dist_km.shape[1], height=dist_km.shape[0], transform=transform)
    profile.update(dtype=rasterio.float32, count=1, compress="lzw", nodata=-1)
    with rasterio.open(os.path.join(OUT, f"distance_km{suffix}.tif"), "w", **profile) as ds:
        ds.write(dist_km.astype(np.float32), 1)
    print(f"wrote outputs/distance_km{suffix}.tif and outputs/coverage_summary{suffix}.json")


if __name__ == "__main__":
    main()
