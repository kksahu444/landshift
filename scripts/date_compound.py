"""Date the south-east compound: one winter composite per year, each classified by the shipped forest.

Usage: python scripts/date_compound.py <cloud-project>
Writes results/compound_dating.json and results/compound_<year>.png (true colour, site outline in yellow).
"""
import json
import sys
import urllib.request

import ee

from run_pipeline import NAMES, ROOT, aoi, area_table, composite, train_forest

OUT = ROOT / 'results'
YEARS = range(2020, 2026)

stacks, report = {}, {'2020': {}, '2025': {}}
s1, s2, _, _, rf = train_forest(report)
stacks[2020], stacks[2025] = s1, s2
for y in range(2021, 2025):
    report[str(y)] = {}
    stacks[y] = composite({'start': f'{y - 1}-11-01', 'end': f'{y}-03-01', 'dry_start': f'{y}-03-01', 'dry_end': f'{y}-06-01'},
                          report[str(y)])
maps = {y: stacks[y].classify(rf).focalMode(1, 'square', 'pixels').rename('class') for y in YEARS}

# Same 30 m change filter as run_pipeline, so the site pixels are the open -> built-up pixels on the change map.
raw = maps[2020].neq(maps[2025])
changed = raw.focalMin(1, 'square', 'pixels').focalMax(1, 'square', 'pixels').And(raw)
open_to_built = maps[2020].eq(2).And(maps[2025].eq(0)).And(changed)

# The compound is the largest cluster of open -> built-up pixels once 30 m gaps (roads, courtyards) are bridged.
blobs = open_to_built.focalMax(3, 'square', 'pixels').selfMask().reduceToVectors(
    geometry=aoi, scale=10, geometryType='polygon', eightConnected=True, maxPixels=1e9)
site = ee.Feature(blobs.map(lambda f: f.set('ha', f.geometry().area(1).divide(1e4))).sort('ha', False).first()).geometry()


def ha(img, geom=aoi):
    return ee.Number(ee.Image.pixelArea().divide(1e4).updateMask(img).reduceRegion(
        reducer=ee.Reducer.sum(), geometry=geom, scale=10, maxPixels=1e9).get('area'))


campus_open_to_built = ha(open_to_built).getInfo()
by_year = {}
for y in YEARS:
    by_year[str(y)] = {NAMES[k].lower(): round(ha(open_to_built.And(maps[y].eq(k)), site).getInfo(), 2) for k in range(4)}

out = {
    'open_to_built_campus_ha': round(campus_open_to_built, 2),
    'site_ha': round(site.area(1).divide(1e4).getInfo(), 2),
    'site_centroid': [round(c, 4) for c in site.centroid(1).coordinates().getInfo()],
    'site_open_to_built_ha': round(ha(open_to_built, site).getInfo(), 2),
    'scenes_winter_dry': {str(y): [len(report[str(y)]['scenes']), len(report[str(y)]['scenes_dry'])] for y in YEARS},
    'compound_pixels_by_year_ha': by_year,
    'campus_area_ha_2022': {str(g['class']): round(g['sum'], 2) for g in area_table(maps[2022], 'class')},
}
json.dump(out, open(OUT / 'compound_dating.json', 'w'), indent=1)
print(json.dumps(out, indent=1))

box = site.bounds(1).buffer(120, 1).bounds(1)
edge = ee.Image().byte().paint(ee.FeatureCollection([ee.Feature(site)]), 1, 2).visualize(palette=['ffd400'])
for y in YEARS:
    tc = stacks[y].visualize(bands=['B4', 'B3', 'B2'], min=0.02, max=0.25).blend(edge)
    url = tc.getThumbURL({'region': box, 'dimensions': 400, 'format': 'png'})
    urllib.request.urlretrieve(url, OUT / f'compound_{y}.png')
