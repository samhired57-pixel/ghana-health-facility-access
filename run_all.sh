#!/usr/bin/env bash
# End-to-end pipeline for the Ghana health-facility accessibility analysis.
# Run from the repo root:  bash run_all.sh
set -euo pipefail
PY=~/workspace/venvs/samuel-projects/bin/python

echo "=== 1/6 download data ==="
$PY src/download_data.py

echo "=== 2/6 prepare facilities ==="
$PY src/prepare_facilities.py

echo "=== 3/6 coverage (all facilities) ==="
$PY src/coverage.py

echo "=== 4/6 coverage (clinical only, sensitivity) ==="
$PY src/coverage.py data/facilities_clinical.geojson clinical

echo "=== 5/6 district aggregation ==="
$PY src/districts.py
$PY src/districts.py clinical

echo "=== 6/6 maps + metrics ==="
$PY src/maps.py
$PY src/make_metrics.py

echo "DONE — see outputs/"
