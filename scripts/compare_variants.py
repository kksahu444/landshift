"""Score classification variants on the validation points, odd ids for choosing and even ids held out.

Usage: python scripts/compare_variants.py <cloud-project> [variant ...]
Prints overall accuracy (area-weighted), open-land producer's and built-up user's accuracy per year and half.
"""
import csv
import json
import sys
from pathlib import Path

import ee

ee.Initialize(project=sys.argv[1])
REPO = Path(__file__).parent.parent
ring = json.load(open(REPO / 'data' / 'iitkgp_campus_osm.geojson'))['coordinates'][0]
aoi = ee.Geometry.Polygon([[[round(x, 5), round(y, 5)] for x, y in ring]])
BANDS = ['B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B8A', 'B11', 'B12']
NAMES = ['built-up', 'vegetation', 'open land', 'water']
ORDER = [0, 1, 2, 3]
STRATA = json.load(open(REPO / 'validation' / 'strata_ha.json'))
W_HA = {2020: STRATA['2020'], 2025: STRATA['2025']}

def add_aoi_cloud(img):
    scl = img.select('SCL')
    cloudy = scl.eq(3).Or(scl.eq(8)).Or(scl.eq(9)).Or(scl.eq(10))
    frac = cloudy.reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi, scale=20, maxPixels=1e9).get('SCL')
    return img.set('aoi_cloud_pct', ee.Number(frac).multiply(100))

def prep(img):
    scl = img.select('SCL')
    good = scl.neq(1).And(scl.neq(3)).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
    return ee.Image(img.select(BANDS).resample('bilinear').updateMask(good).divide(10000).copyProperties(img, ['system:time_start']))

def composite(start, end, cloud_max=10):
    col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(aoi).filterDate(start, end)
           .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 40)).map(add_aoi_cloud).filter(ee.Filter.lt('aoi_cloud_pct', cloud_max)))
    comp = col.map(prep).median().clip(aoi)
    return (comp.addBands(comp.normalizedDifference(['B8', 'B4']).rename('NDVI'))
            .addBands(comp.normalizedDifference(['B11', 'B8']).rename('NDBI'))
            .addBands(comp.normalizedDifference(['B3', 'B8']).rename('NDWI')))

def dw_ref(start, end, dw_to, agree=0.6):
    dw = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1').filterBounds(aoi).filterDate(start, end).select('label').map(lambda i: i.remap(list(range(8)), dw_to))
    mode = dw.mode()
    return mode.int().rename('class').updateMask(dw.map(lambda i: i.eq(mode)).mean().gte(agree)).clip(aoi)

def points(year, half=None):
    rows = [r for r in csv.DictReader(open(REPO / 'validation' / 'points.csv')) if r['year'] == str(year) and r['class']]
    if half is not None:
        rows = [r for r in rows if int(r['id'][-3:]) % 2 == half]
    return ee.FeatureCollection([ee.Feature(ee.Geometry.Point([float(r['lon']), float(r['lat'])]),
            {'class': int(r['class']), 'stratum': NAMES.index(r['map_class'])}) for r in rows])

def score(img, year, half=None):
    fs = img.rename('map').sampleRegions(collection=points(year, half), properties=['class', 'stratum'], scale=10).getInfo()['features']
    pts = [(f['properties']['stratum'], f['properties']['class'], f['properties']['map']) for f in fs]
    total = sum(W_HA[year]); w = [a / total for a in W_HA[year]]
    n = [sum(1 for s, _, _ in pts if s == h) for h in ORDER]
    est = lambda f: sum(w[h] * sum(f(r, m) for s, r, m in pts if s == h) / n[h] for h in ORDER)
    oa = est(lambda r, m: r == m)
    pa = [est(lambda r, m: r == m == i) / max(est(lambda r, m: r == i), 1e-9) for i in ORDER]
    ua = [est(lambda r, m: r == m == j) / max(est(lambda r, m: m == j), 1e-9) for j in ORDER]
    return oa, pa, ua

EP = {2020: ('2019-11-01', '2020-03-01'), 2025: ('2024-11-01', '2025-03-01')}
DW_BASE = [3, 1, 2, 1, 2, 1, 0, 2]


DRY = {2020: ('2020-03-01', '2020-06-01'), 2025: ('2025-03-01', '2025-06-01')}

def stack(y, texture, dry, glcm=None):
    s = composite(*EP[y])
    if texture:
        nd = s.select('NDVI')
        s = s.addBands(nd.reduceNeighborhood(ee.Reducer.stdDev(), ee.Kernel.square(1)).rename('NDVI_sd'))
        s = s.addBands(s.select('B8').reduceNeighborhood(ee.Reducer.stdDev(), ee.Kernel.square(1)).rename('B8_sd'))
    if dry:
        d = composite(*DRY[y], cloud_max=20)
        s = s.addBands(d.select(['B4', 'B8', 'B11', 'B12', 'NDVI', 'NDBI', 'NDWI'], ['dB4', 'dB8', 'dB11', 'dB12', 'dNDVI', 'dNDBI', 'dNDWI']))
        s = s.addBands(s.select('NDVI').subtract(s.select('dNDVI')).rename('NDVI_drop'))
    if glcm:
        # GLCM needs integer grey levels: B8 0-0.51 and NDVI -1..1 each quantised to 0-255
        bands, size = glcm
        grey = {'B8': s.select('B8').multiply(500).clamp(0, 255), 'NDVI': s.select('NDVI').add(1).multiply(127.5)}
        for b in bands:
            g = grey[b].toByte().rename(b).glcmTexture(size=size)
            s = s.addBands(g.select([f'{b}_contrast', f'{b}_ent', f'{b}_idm', f'{b}_corr'], [f'{b}_glcm_contrast', f'{b}_glcm_ent', f'{b}_glcm_idm', f'{b}_glcm_corr']))
    return s

def run(name, cp=(300, 700, 150, 40), texture=False, dry=False, dw_to=DW_BASE, glcm=None):
    st, samp = {}, []
    for y in (2020, 2025):
        st[y] = stack(y, texture, dry, glcm)
        samp.append(st[y].addBands(dw_ref(*EP[y], dw_to)).stratifiedSample(numPoints=0, classBand='class', classValues=ORDER,
                    classPoints=list(cp), region=aoi, scale=10, seed=42, geometries=True, tileScale=4).randomColumn('r', 42))
    train = samp[0].merge(samp[1]).filter(ee.Filter.lt('r', 0.7))
    rf = ee.Classifier.smileRandomForest(numberOfTrees=100, seed=42).train(features=train, classProperty='class', inputProperties=st[2020].bandNames())
    out = [name]
    for y in (2020, 2025):
        m = st[y].classify(rf).focalMode(1, 'square', 'pixels')
        for half in (1, 0):
            oa, pa, ua = score(m, y, half)
            out.append(f'{y}h{half} {oa:.2f} openPA {pa[2]:.2f} builtPA {pa[0]:.2f} builtUA {ua[0]:.2f}')
    print(' | '.join(out), flush=True)

SH = [3, 1, 2, 1, 2, 2, 0, 2]
V = {
 'E0 base': {},
 'E1 open450': dict(cp=(300, 700, 450, 40)),
 'E2 texture': dict(texture=True),
 'E3 dry': dict(dry=True),
 'E4 all3': dict(cp=(300, 700, 450, 40), texture=True, dry=True),
 'E5 all3+shrub->open': dict(cp=(300, 700, 450, 40), texture=True, dry=True, dw_to=SH),
 'E6 shrub only': dict(dw_to=SH),
 'E7 open450+shrub': dict(cp=(300, 700, 450, 40), dw_to=SH),
 'E8 open450+dry+shrub': dict(cp=(300, 700, 450, 40), dry=True, dw_to=SH),
 'E9 E5 open600': dict(cp=(300, 700, 600, 40), texture=True, dry=True, dw_to=SH),
 'G1 E5+GLCM B8 3x3': dict(cp=(300, 700, 450, 40), texture=True, dry=True, dw_to=SH, glcm=(('B8',), 1)),
 'G2 E5+GLCM B8 5x5': dict(cp=(300, 700, 450, 40), texture=True, dry=True, dw_to=SH, glcm=(('B8',), 2)),
 'G3 E5+GLCM B8,NDVI 3x3': dict(cp=(300, 700, 450, 40), texture=True, dry=True, dw_to=SH, glcm=(('B8', 'NDVI'), 1)),
}
if __name__ == '__main__':
    for k in sys.argv[2:] or V:
        run(k, **V[k])
