"""
Extract major highways from the Geofabrik Ghana OSM extract.

The Overpass API is unreachable from this build machine, so highways are
pulled from the local .osm.pbf with pyosmium instead. Keeps motorway / trunk /
primary / secondary / tertiary ways and writes data/highways.geojson (WGS84).

The 116 MB PBF itself is NOT committed to git — see README for the download
command and .gitignore.

Usage:  python src/extract_roads.py
"""
import os

import osmium
import geopandas as gpd
from shapely.geometry import LineString

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")

KEEP = {"motorway", "trunk", "primary", "secondary", "tertiary"}


class HighwayHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.coords = {}
        self.lines = []

    def node(self, n):
        if n.location.valid():
            self.coords[n.id] = (n.location.lon, n.location.lat)

    def way(self, w):
        hw = w.tags.get("highway")
        if hw not in KEEP:
            return
        pts = [self.coords[nd.ref] for nd in w.nodes if nd.ref in self.coords]
        if len(pts) >= 2:
            self.lines.append({"highway": hw, "name": w.tags.get("name", ""),
                               "geometry": LineString(pts)})


def main():
    pbf = os.path.join(DATA, "ghana-latest.osm.pbf")
    if not os.path.exists(pbf):
        raise SystemExit(f"missing {pbf} — run src/download_data.py first")
    print("parsing PBF (this takes a few minutes) ...")
    h = HighwayHandler()
    h.apply_file(pbf, locations=True)
    gdf = gpd.GeoDataFrame(h.lines, crs="EPSG:4326")
    dest = os.path.join(DATA, "highways.geojson")
    gdf.to_file(dest, driver="GeoJSON")
    print(f"highway segments: {len(gdf)} -> {dest}")
    print(gdf["highway"].value_counts().to_string())
    # total length in km (rough, EPSG:32630)
    km = gdf.to_crs("EPSG:32630").geometry.length.sum() / 1000
    print(f"total major-road length: {km:,.0f} km")


if __name__ == "__main__":
    main()
