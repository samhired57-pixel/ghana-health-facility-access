"""
Publication-style maps for the Ghana health-facility accessibility analysis.

Figure 1 — facilities_map.png: WorldPop 2020 population density (log scale)
  with health-facility points overlaid.
Figure 2 — underserved_districts.png: choropleth of % of district population
  living beyond 10 km of a facility; the 10 most underserved districts labelled.

Usage:  python src/maps.py
Requires: data/facilities.geojson, data/gha_ppp_2020.tif,
          outputs/district_summary.csv, data/gadm41_GHA_shp/ (extracted)
"""
import os

import numpy as np
import pandas as pd
import rasterio
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
OUT = os.path.join(BASE, "outputs")

plt.rcParams.update({"font.size": 9, "figure.dpi": 150})


def main():
    os.makedirs(OUT, exist_ok=True)
    fac = gpd.read_file(os.path.join(DATA, "facilities.geojson"))

    with rasterio.open(os.path.join(DATA, "gha_ppp_2020.tif")) as ds:
        pop = ds.read(1, masked=True).filled(0).astype(np.float32)
        extent = [ds.bounds.left, ds.bounds.right, ds.bounds.bottom, ds.bounds.top]
    pop = np.nan_to_num(pop, nan=0.0).clip(min=0)

    # ---- Figure 1: population + facilities ----
    fig, ax = plt.subplots(figsize=(8.5, 9))
    im = ax.imshow(pop, extent=extent, origin="upper", cmap="YlOrRd",
                   norm=LogNorm(vmin=1, vmax=np.nanpercentile(pop[pop > 0], 99.9)))
    hw_path = os.path.join(DATA, "highways.geojson")
    if os.path.exists(hw_path):
        hw = gpd.read_file(hw_path)
        hw.plot(ax=ax, color="#444444", linewidth=0.3, alpha=0.5)
    ax.scatter(fac.geometry.x, fac.geometry.y, s=4, c="#1f5c3d", alpha=0.55,
               linewidths=0, label=f"Health facilities (n={len(fac):,})")
    ax.set_title("Ghana — population density (WorldPop 2020, 100 m) and health facilities\n"
                 "(HDX Ghana Healthsites, healthsites.io)", fontsize=11, pad=10)
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
    cbar = fig.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Persons per 100 m cell (log scale)")
    ax.legend(loc="lower left", framealpha=0.9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "facilities_map.png"), bbox_inches="tight")
    plt.close(fig)
    print("wrote outputs/facilities_map.png")

    # ---- Figure 2: underserved districts choropleth ----
    import glob
    shp = glob.glob(os.path.join(DATA, "gadm41_GHA_shp", "gadm41_GHA_2.shp"))[0]
    districts = gpd.read_file(shp)
    name_col = "NAME_2" if "NAME_2" in districts.columns else districts.columns[2]
    summary = pd.read_csv(os.path.join(OUT, "district_summary.csv"))
    merged = districts.merge(summary, left_on=name_col, right_on="district", how="left")

    fig, ax = plt.subplots(figsize=(8.5, 9))
    merged.plot(column="pct_beyond_10km", cmap="Reds", linewidth=0.2, edgecolor="white",
                legend=True, ax=ax, missing_kwds={"color": "lightgrey"},
                legend_kwds={"label": "% of population beyond 10 km of a facility",
                             "shrink": 0.8})
    # Label the 10 most underserved districts.
    top10 = summary.head(10)
    lab = merged[merged["district"].isin(top10["district"])].copy()
    lab["coords"] = lab.geometry.representative_point()
    for _, row in lab.iterrows():
        ax.annotate(row["district"], xy=(row["coords"].x, row["coords"].y),
                    fontsize=6.5, ha="center",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.75))
    ax.set_title("Ghana — share of district population beyond 10 km of a health facility\n"
                 "Euclidean screening metric; top-10 underserved districts labelled",
                 fontsize=11, pad=10)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "underserved_districts.png"), bbox_inches="tight")
    plt.close(fig)
    print("wrote outputs/underserved_districts.png")


if __name__ == "__main__":
    main()
