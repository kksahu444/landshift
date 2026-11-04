"""Draw locations for hand-labelled training points, kept apart from the validation points.

Usage: python scripts/sample_training_points.py <cloud-project> [repo_dir]

Campus: a simple random sample, at least 40 m apart, 20 m inside the fence, and at least 30 m from every
validation point of either year, so no test point sits next to a training point.
Water: the campus ponds are already covered by validation points at 12 m spacing, so water training points
come from ponds within 3 km outside the fence (Dynamic World water in 60 % of scenes in both epochs), at least 40 m apart.
Each location is labelled twice, on the 2020 and the 2024 WorldView image (scripts/training_sheets.py).
Writes training/candidates.csv.
"""
import csv
import json
import math
import random
import sys
from pathlib import Path

import ee

ee.Initialize(project=sys.argv[1])
REPO = Path(sys.argv[2] if len(sys.argv) > 2 else '.')
SEED = 20261104
N_CAMPUS, N_WATER = 260, 30
M_LAT = 110_757.0
M_LON = 111_320.0 * math.cos(math.radians(22.3145)) * 1.0033

ring = [(round(x, 5), round(y, 5)) for x, y in
        json.load(open(REPO / 'data' / 'iitkgp_campus_osm.geojson'))['coordinates'][0]]
LON0, LON1 = min(p[0] for p in ring), max(p[0] for p in ring)
LAT0, LAT1 = min(p[1] for p in ring), max(p[1] for p in ring)
edges = list(zip(ring, ring[1:] + ring[:1]))
aoi = ee.Geometry.Polygon([ring])


def inside(lon, lat):
    hit = False
    for (x1, y1), (x2, y2) in edges:
        if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def to_fence_m(lon, lat):
    px, py, best = lon * M_LON, lat * M_LAT, 1e18
    for (x1, y1), (x2, y2) in edges:
        ax, ay, dx, dy = x1 * M_LON, y1 * M_LAT, (x2 - x1) * M_LON, (y2 - y1) * M_LAT
        t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
        best = min(best, math.hypot(px - ax - t * dx, py - ay - t * dy))
    return best


def dist_m(p, q):
    return math.hypot((p[0] - q[0]) * M_LON, (p[1] - q[1]) * M_LAT)


validation = [(float(r['lon']), float(r['lat'])) for r in csv.DictReader(open(REPO / 'validation' / 'points.csv'))]
rng = random.Random(SEED)
campus = []
while len(campus) < N_CAMPUS:
    p = (rng.uniform(LON0, LON1), rng.uniform(LAT0, LAT1))
    if (inside(*p) and to_fence_m(*p) >= 20 and all(dist_m(p, q) >= 40 for q in campus)
            and all(dist_m(p, q) >= 30 for q in validation)):
        campus.append(p)

ring_zone = aoi.buffer(3000).difference(aoi.buffer(100))
dw_water = ee.Image.constant(1)
for start, end in (('2019-11-01', '2020-06-01'), ('2024-11-01', '2025-06-01')):
    dw = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1').filterBounds(ring_zone).filterDate(start, end).select('label')
    dw_water = dw_water.And(dw.map(lambda i: i.eq(0)).mean().gte(0.6))
pool = dw_water.selfMask().rename('w').stratifiedSample(numPoints=600, classBand='w', region=ring_zone, scale=10,
                                                        seed=SEED, geometries=True)
pool = [f['geometry']['coordinates'] for f in pool.getInfo()['features']]
rng.shuffle(pool)
water = []
for p in pool:
    if len(water) < N_WATER and all(dist_m(p, q) >= 40 for q in water):
        water.append(tuple(p))

rows = [{'id': f'T{k:03d}', 'lon': f'{lon:.6f}', 'lat': f'{lat:.6f}', 'source': 'campus random'}
        for k, (lon, lat) in enumerate(campus, 1)]
rows += [{'id': f'T{k:03d}', 'lon': f'{lon:.6f}', 'lat': f'{lat:.6f}', 'source': 'pond outside fence'}
         for k, (lon, lat) in enumerate(water, len(campus) + 1)]
out = REPO / 'training' / 'candidates.csv'
out.parent.mkdir(exist_ok=True)
with open(out, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print(len(campus), 'campus and', len(water), 'pond locations ->', out)
