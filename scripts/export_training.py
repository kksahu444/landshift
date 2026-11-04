"""Training points from training/points.csv -> GEE point layers.

Usage: python scripts/export_training.py [repo_dir]
Writes gee/training_points.js (training20, training25, paste above gee/lulc_pipeline.js). One collection per year,
in CSV order, built the same way as own_points() in scripts/run_pipeline.py, so both pipelines train the same forest.
"""
import csv
import sys
from collections import Counter
from pathlib import Path

REPO = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
rows = list(csv.DictReader(open(REPO / 'training' / 'points.csv')))
CLASSES = ['built-up', 'vegetation', 'open land', 'water']

lines = [
    '// Training points for gee/lulc_pipeline.js (CS60111 GIS, Group 8). The pipeline needs them: paste this whole file',
    '// above it in one Code Editor script. Labelled by eye on the same WorldView scenes as the validation points',
    '// (15 Mar 2020 for 2020, 13 Jan 2024 for 2025); every point is at least 30 m from every validation point.',
    '// 260 campus locations plus 30 ponds within 3 km outside the fence. Notes: training/NOTES.md.',
    '// Generated from training/points.csv by scripts/export_training.py; edit the CSV, not this file.',
    '',
]
for year in ('2020', '2025'):
    pts = [r for r in rows if r['year'] == year]
    n = Counter(r['label'] for r in pts)
    feats = ',\n'.join(f"  ee.Feature(ee.Geometry.Point([{r['lon']}, {r['lat']}]), {{'class': {r['class']}, id: '{r['id']}'}})"
                       for r in pts)
    lines.append(f'// {year}: {len(pts)} points, ' + ', '.join(f'{c} {n[c]}' for c in CLASSES))
    lines.append(f'var training{year[2:]} = ee.FeatureCollection([\n{feats}\n]);')
    lines.append('')
(REPO / 'gee' / 'training_points.js').write_text('\n'.join(lines), encoding='utf-8')
print('wrote gee/training_points.js:', {y: sum(r['year'] == y for r in rows) for y in ('2020', '2025')})
