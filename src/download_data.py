"""
Download all input datasets for the Ghana health-facility accessibility analysis.

Every source is open data, fetched programmatically. This script is idempotent:
files that already exist are skipped. After downloading it writes
data/provenance.csv recording the exact source, URL and access date.

Sources
-------
1. Health facility locations — HDX dataset "Ghana Healthsites"
   (healthsites.io extract, curated by Open Healthsite Consulting).
2. Population — WorldPop Ghana 2020, 100 m unconstrained (open, no key).
3. Roads — Geofabrik Ghana OSM extract (.osm.pbf); highways extracted locally
   because the Overpass API is unreachable from this build machine.
4. District boundaries — GADM v4.1 Ghana level 2 (261 MMDAs).

Usage:  python src/download_data.py
"""
import csv
import os
import urllib.request
from datetime import date, timezone

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

SOURCES = [
    {
        "name": "Ghana Healthsites (healthsites.io extract)",
        "publisher": "Open Healthsite Consulting via Humanitarian Data Exchange",
        "hdx_dataset": "https://data.humdata.org/dataset/ghana-healthsites",
        "url": "https://data.humdata.org/dataset/364c5aca-7cd7-4248-b394-335113293c7a"
               "/resource/fcac0d0d-4363-4a62-a4d4-cfef2a25b12f/download/ghana.geojson",
        "local": "ghana.geojson",
        "note": "Point locations of health facilities; OSM-derived, curated by healthsites.io",
    },
    {
        "name": "WorldPop Ghana 2020 population, 100 m unconstrained",
        "publisher": "WorldPop, University of Southampton",
        "hdx_dataset": "https://www.worldpop.org/geodata/summary?id=49757",
        "url": "https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/GHA/gha_ppp_2020.tif",
        "local": "gha_ppp_2020.tif",
        "note": "Estimated persons per 100 m grid cell, 2020",
    },
    {
        "name": "GADM v4.1 Ghana level-2 boundaries",
        "publisher": "GADM",
        "hdx_dataset": "https://gadm.org/download_country.html",
        "url": "https://geodata.ucdavis.edu/gadm/gadm4.1/shp/gadm41_GHA_shp.zip",
        "local": "gadm41_GHA_shp.zip",
        "note": "260 districts (MMDAs); used for per-district aggregation",
    },
    {
        "name": "Geofabrik Ghana OSM extract",
        "publisher": "Geofabrik GmbH / OpenStreetMap contributors",
        "hdx_dataset": "https://download.geofabrik.de/africa/ghana.html",
        "url": "https://download.geofabrik.de/africa/ghana-latest.osm.pbf",
        "local": "ghana-latest.osm.pbf",
        "note": "Full OSM extract; highways pulled out locally with pyosmium. "
                "NOT committed to git (116 MB) — see README for the download command.",
    },
]


def fetch(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "samuel-portfolio/1.0 (research)"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(dest, "wb") as fh:
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            fh.write(chunk)


def main():
    os.makedirs(DATA, exist_ok=True)
    today = date.today().isoformat()
    rows = []
    for src in SOURCES:
        dest = os.path.join(DATA, src["local"])
        if os.path.exists(dest) and os.path.getsize(dest) > 0:
            status = "already present — skipped"
        else:
            print(f"downloading {src['local']} ...")
            fetch(src["url"], dest)
            status = "downloaded"
        size_mb = os.path.getsize(dest) / 1e6
        print(f"  {status} ({size_mb:.1f} MB)")
        rows.append({
            "dataset": src["name"],
            "publisher": src["publisher"],
            "source_page": src["hdx_dataset"],
            "download_url": src["url"],
            "local_file": src["local"],
            "access_date_utc": today,
            "notes": src["note"],
        })
    prov = os.path.join(DATA, "provenance.csv")
    with open(prov, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {prov}")


if __name__ == "__main__":
    main()
