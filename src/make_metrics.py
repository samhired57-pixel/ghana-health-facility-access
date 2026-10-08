"""
Compile outputs/metrics.json — every headline number in one machine-readable file.

Reads outputs/coverage_summary.json and outputs/district_summary.csv and writes
a single metrics.json with national coverage stats plus the top/bottom
districts. All values are computed, never hand-entered.

Usage:  python src/make_metrics.py
"""
import json
import os

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, "outputs")


def main():
    with open(os.path.join(OUT, "coverage_summary.json")) as fh:
        cov = json.load(fh)
    with open(os.path.join(OUT, "coverage_summary_clinical.json")) as fh:
        cov_clinical = json.load(fh)
    df = pd.read_csv(os.path.join(OUT, "district_summary.csv"))
    top = df.head(10)[["district", "region", "population_2020", "n_facilities",
                       "facilities_per_10k", "pct_beyond_10km"]]
    bottom = df.tail(5)[["district", "region", "population_2020", "n_facilities",
                         "facilities_per_10k", "pct_beyond_10km"]]
    metrics = {
        "national_all_facilities": cov,
        "national_clinical_only": cov_clinical,
        "n_districts": len(df),
        "most_underserved_districts": top.to_dict(orient="records"),
        "best_served_districts": bottom.to_dict(orient="records"),
        "method": ("Euclidean distance from each WorldPop 100 m cell to the nearest "
                   "healthsites.io facility point; population-weighted. Screening metric, "
                   "not a travel-time model. 'clinical_only' excludes pharmacies."),
    }
    # Ship the cleaned facility points with the outputs.
    import shutil
    shutil.copy(os.path.join(BASE, "data", "facilities.geojson"),
                os.path.join(OUT, "facilities.geojson"))
    dest = os.path.join(OUT, "metrics.json")
    with open(dest, "w") as fh:
        json.dump(metrics, fh, indent=2)
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
