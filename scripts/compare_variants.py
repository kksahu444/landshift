"""Score classification variants on the validation points, odd ids for choosing and even ids held out.

Usage: python scripts/compare_variants.py <cloud-project> [variant ...]
       python scripts/compare_variants.py --score [baseline]
The first form classifies with each variant and writes the map class at every validation point to
results/variants/<variant>.json. The second needs no Earth Engine: it prints area-weighted OA per year and half
from those files, and the paired difference to the baseline with a bootstrap 95 % interval.
"""
import csv
import json
import random
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
NAMES = ['built-up', 'vegetation', 'open land', 'water']
ORDER = [0, 1, 2, 3]
STRATA = json.load(open(REPO / 'validation' / 'strata_ha.json'))
W_HA = {2020: STRATA['2020'], 2025: STRATA['2025']}
POINTS = [r for r in csv.DictReader(open(REPO / 'validation' / 'points.csv')) if r['class']]
PRED_DIR = REPO / 'results' / 'variants'
EP = {2020: ('2019-11-01', '2020-03-01'), 2025: ('2024-11-01', '2025-03-01')}
DRY = {2020: ('2020-03-01', '2020-06-01'), 2025: ('2025-03-01', '2025-06-01')}
DW_BASE = [3, 1, 2, 1, 2, 1, 0, 2]
SH = [3, 1, 2, 1, 2, 2, 0, 2]
# ESRI 10 m land cover codes 1 water, 2 trees, 4 flooded vegetation, 5 crops, 7 built, 8 bare, 11 rangeland
ESRI_FROM, ESRI_TO = [1, 2, 4, 5, 7, 8, 11], [3, 1, 1, 2, 0, 2, 2]


def half_of(pid):
    return int(pid[-3:]) % 2


def score(pts, year):
    """pts: (stratum, reference, map). Area-weighted OA, PA and UA (Olofsson et al. 2014; Stehman 2014)."""
    total = sum(W_HA[year])
    w = [a / total for a in W_HA[year]]
    n = [sum(1 for s, _, _ in pts if s == h) for h in ORDER]
    est = lambda f: sum(w[h] * sum(f(r, m) for s, r, m in pts if s == h) / n[h] for h in ORDER if n[h])
    oa = est(lambda r, m: r == m)
    pa = [est(lambda r, m: r == m == i) / max(est(lambda r, m: r == i), 1e-9) for i in ORDER]
    ua = [est(lambda r, m: r == m == j) / max(est(lambda r, m: m == j), 1e-9) for j in ORDER]
    return oa, pa, ua


def point_table(year, half=None):
    rows = [r for r in POINTS if r['year'] == str(year) and (half is None or half_of(r['id']) == half)]
    return [(r['id'], NAMES.index(r['map_class']), int(r['class'])) for r in rows]


def load_pred(name):
    return json.load(open(PRED_DIR / f'{slug(name)}.json'))['map']


def slug(name):
    return name.split()[0]


def oa_of(pred, year, half):
    return score([(s, r, pred[pid]) for pid, s, r in point_table(year, half) if pid in pred], year)[0]


def paired(pred, base, half, reps=4000, seed=1):
    """Mean over both years of OA(variant) - OA(baseline) on the same points, resampled within strata."""
    rng = random.Random(seed)
    tables = {y: point_table(y, half) for y in (2020, 2025)}
    diffs = []
    for _ in range(reps):
        d = 0
        for y, tab in tables.items():
            by_s = {h: [t for t in tab if t[1] == h] for h in ORDER}
            boot = [rng.choice(by_s[h]) for h in ORDER for _ in by_s[h]]
            d += (score([(s, r, pred[pid]) for pid, s, r in boot], y)[0]
                  - score([(s, r, base[pid]) for pid, s, r in boot], y)[0]) / 2
        diffs.append(d)
    diffs.sort()
    point = sum((oa_of(pred, y, half) - oa_of(base, y, half)) / 2 for y in (2020, 2025))
    return point, diffs[int(.025 * reps)], diffs[int(.975 * reps)]


def report(baseline):
    """Prints the table and writes it to results/variant_scores.json, which slides/make_charts.py draws from."""
    base = load_pred(baseline)
    print(f'{"variant":34s} {"odd 2020":>8s} {"2025":>6s} {"mean":>6s} {"even 2020":>9s} {"2025":>6s} {"mean":>6s}'
          f'   odd diff [95% CI]        even diff [95% CI]')
    table = {}
    for f in sorted(PRED_DIR.glob('*.json')):
        doc = json.load(open(f))
        pred = doc['map']
        row = table[f.stem] = {'name': doc['name']}
        cells = []
        for half, tag in ((1, 'odd'), (0, 'even')):
            a, b = oa_of(pred, 2020, half), oa_of(pred, 2025, half)
            cells += [a, b, (a + b) / 2]
            row[f'{tag}_oa'] = [a, b]
        line = f'{doc["name"][:34]:34s} ' + ' '.join(f'{c:6.3f}' for c in cells)
        if f.stem != slug(baseline):
            for half, tag in ((1, 'odd'), (0, 'even')):
                d, lo, hi = row[f'{tag}_diff'] = paired(pred, base, half, reps=1000)
                line += f'   {d:+.3f} [{lo:+.3f}, {hi:+.3f}]'
        print(line, flush=True)
    json.dump({'baseline': baseline, 'variants': table}, open(REPO / 'results' / 'variant_scores.json', 'w'), indent=1)


if __name__ == '__main__' and sys.argv[1] == '--score':
    report(sys.argv[2] if len(sys.argv) > 2 else 'E5')
    sys.exit()

import ee

ee.Initialize(project=sys.argv[1])
ring = json.load(open(REPO / 'data' / 'iitkgp_campus_osm.geojson'))['coordinates'][0]
aoi = ee.Geometry.Polygon([[[round(x, 5), round(y, 5)] for x, y in ring]])
BANDS = ['B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B8A', 'B11', 'B12']


def add_aoi_cloud(img):
    scl = img.select('SCL')
    cloudy = scl.eq(3).Or(scl.eq(8)).Or(scl.eq(9)).Or(scl.eq(10))
    frac = cloudy.reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi, scale=20, maxPixels=1e9).get('SCL')
    return img.set('aoi_cloud_pct', ee.Number(frac).multiply(100))

def prep(img):
    scl = img.select('SCL')
    good = scl.neq(1).And(scl.neq(3)).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
    return ee.Image(img.select(BANDS).resample('bilinear').updateMask(good).divide(10000).copyProperties(img, ['system:time_start']))

def composite(start, end, cloud_max=10, region=None):
    col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(aoi).filterDate(start, end)
           .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 40)).map(add_aoi_cloud).filter(ee.Filter.lt('aoi_cloud_pct', cloud_max)))
    comp = col.map(prep).median().clip(region or aoi)
    return (comp.addBands(comp.normalizedDifference(['B8', 'B4']).rename('NDVI'))
            .addBands(comp.normalizedDifference(['B11', 'B8']).rename('NDBI'))
            .addBands(comp.normalizedDifference(['B3', 'B8']).rename('NDWI')))

def dw_ref(start, end, dw_to, agree=0.6):
    dw = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1').filterBounds(aoi).filterDate(start, end).select('label').map(lambda i: i.remap(list(range(8)), dw_to))
    mode = dw.mode()
    return mode.int().rename('class').updateMask(dw.map(lambda i: i.eq(mode)).mean().gte(agree)).clip(aoi)

def esri(y):
    return (ee.ImageCollection('projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS').filterBounds(aoi)
            .filterDate(f'{y}-01-01', f'{y + 1}-01-01').mosaic().remap(ESRI_FROM, ESRI_TO).rename('esri'))

def radar(y):
    """Sentinel-1 VV and VH, median over Nov-May (about 45 scenes, so speckle averages out)."""
    col = (ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(aoi).filterDate(EP[y][0], DRY[y][1])
           .filter(ee.Filter.eq('instrumentMode', 'IW'))
           .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH')).select(['VV', 'VH']))
    med = col.median()
    return (med.addBands(med.select('VV').subtract(med.select('VH')).rename('VVmVH'))
               .addBands(col.select('VV').reduce(ee.Reducer.stdDev()).rename('VV_tsd')))

def embedding(y, years):
    col = ee.ImageCollection('GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL').filterBounds(aoi)
    imgs = [col.filterDate(f'{y + k}-01-01', f'{y + k + 1}-01-01').mosaic() for k in years]
    return imgs[0] if len(imgs) == 1 else ee.ImageCollection(imgs).mean()

def buildings(y):
    """Open Buildings 2.5D temporal, averaged from 0.5 m to the 10 m grid. Its last year is 2023."""
    col = ee.ImageCollection('GOOGLE/Research/open-buildings-temporal/v1').filterBounds(aoi)
    yy = min(y, 2023)
    img = col.filterDate(f'{yy}-01-01', f'{yy + 1}-01-01').mosaic().select(['building_presence', 'building_height'])
    return (img.setDefaultProjection(col.first().projection())
               .reduceResolution(ee.Reducer.mean(), maxPixels=1024).reproject(crs='EPSG:32645', scale=10))

def stack(y, texture, dry, glcm=None, s1=False, emb=None, obt=False, only_emb=False, region=None):
    s = composite(*EP[y], region=region)
    if texture:
        nd = s.select('NDVI')
        s = s.addBands(nd.reduceNeighborhood(ee.Reducer.stdDev(), ee.Kernel.square(1)).rename('NDVI_sd'))
        s = s.addBands(s.select('B8').reduceNeighborhood(ee.Reducer.stdDev(), ee.Kernel.square(1)).rename('B8_sd'))
    if dry:
        d = composite(*DRY[y], cloud_max=20, region=region)
        s = s.addBands(d.select(['B4', 'B8', 'B11', 'B12', 'NDVI', 'NDBI', 'NDWI'], ['dB4', 'dB8', 'dB11', 'dB12', 'dNDVI', 'dNDBI', 'dNDWI']))
        s = s.addBands(s.select('NDVI').subtract(s.select('dNDVI')).rename('NDVI_drop'))
    if glcm:
        # GLCM needs integer grey levels: B8 0-0.51 and NDVI -1..1 each quantised to 0-255
        bands, size = glcm
        grey = {'B8': s.select('B8').multiply(500).clamp(0, 255), 'NDVI': s.select('NDVI').add(1).multiply(127.5)}
        for b in bands:
            g = grey[b].toByte().rename(b).glcmTexture(size=size)
            s = s.addBands(g.select([f'{b}_contrast', f'{b}_ent', f'{b}_idm', f'{b}_corr'], [f'{b}_glcm_contrast', f'{b}_glcm_ent', f'{b}_glcm_idm', f'{b}_glcm_corr']))
    if s1:
        s = s.addBands(radar(y))
    if emb:
        e = embedding(y, emb)
        s = e.clip(region or aoi) if only_emb else s.addBands(e)
    if obt:
        s = s.addBands(buildings(y))
    return s

def classifier(clf):
    kind, n = clf[:2]
    if kind == 'gtb':
        return ee.Classifier.smileGradientTreeBoost(numberOfTrees=n, shrinkage=0.05, samplingRate=0.7, seed=42)
    if kind == 'knn':
        return ee.Classifier.smileKNN(k=n)
    if kind == 'svm':
        return ee.Classifier.libsvm(kernelType='RBF', gamma=n, cost=10)
    return ee.Classifier.smileRandomForest(numberOfTrees=n, seed=clf[2] if len(clf) > 2 else 42)

def labels(y, dw_to, cons):
    ref = dw_ref(*EP[y], dw_to)
    if cons == 'esri':
        ref = ref.updateMask(ref.eq(esri(y)))
    return ref

def hand_points(half):
    rows = [r for r in POINTS if half_of(r['id']) == half]
    return {y: ee.FeatureCollection([ee.Feature(ee.Geometry.Point([float(r['lon']), float(r['lat'])]), {'class': int(r['class'])})
                                     for r in rows if r['year'] == str(y)]) for y in (2020, 2025)}

def own_points(conf):
    rows = [r for r in csv.DictReader(open(REPO / 'training' / 'points.csv')) if r['confidence'] in conf]
    return {y: ee.FeatureCollection([ee.Feature(ee.Geometry.Point([float(r['lon']), float(r['lat'])]), {'class': int(r['class'])})
                                     for r in rows if r['year'] == str(y)]) for y in (2020, 2025)}

def run(name, cp=(300, 700, 150, 40), texture=False, dry=False, dw_to=DW_BASE, glcm=None, s1=False, emb=None,
        obt=False, only_emb=False, clf=('rf', 100), cons=None, hand=0, hand_only=False, own=0, own_only=False,
        own_conf=('high', 'medium', 'low')):
    st, samp = {}, []
    # own-label pond points lie up to 3 km outside the fence, so those runs keep the stack unclipped that far
    region = aoi.buffer(3500) if own else None
    for y in (2020, 2025):
        st[y] = stack(y, texture, dry, glcm, s1, emb, obt, only_emb, region)
        samp.append(st[y].addBands(labels(y, dw_to, cons)).stratifiedSample(numPoints=0, classBand='class', classValues=ORDER,
                    classPoints=list(cp), region=aoi, scale=10, seed=42, geometries=True, tileScale=4).randomColumn('r', 42))
    train = samp[0].merge(samp[1]).filter(ee.Filter.lt('r', 0.7))
    if own:
        mine = own_points(own_conf)
        fc = ee.FeatureCollection([st[y].sampleRegions(collection=mine[y], properties=['class'], scale=10, tileScale=4)
                                   for y in (2020, 2025)]).flatten()
        train = fc if own_only else train.merge(ee.FeatureCollection([fc] * own).flatten())
    pts = {y: ee.FeatureCollection([ee.Feature(ee.Geometry.Point([float(r['lon']), float(r['lat'])]), {'id': r['id']})
                                    for r in POINTS if r['year'] == str(y)]) for y in (2020, 2025)}
    out = {}
    # hand > 0: two forests, each also trained on one half of the hand-labelled points (repeated `hand` times)
    # and used only on the other half, so no point is ever scored by a forest that saw it.
    folds = [(None, train)] if not hand else []
    for h in ([1, 0] if hand else []):
        extra = hand_points(1 - h)
        fc = ee.FeatureCollection([st[y].sampleRegions(collection=extra[y], properties=['class'], scale=10, tileScale=4)
                                   for y in (2020, 2025)]).flatten()
        reps = ee.FeatureCollection([fc] * hand).flatten()
        folds.append((h, reps if hand_only else train.merge(reps)))
    for h, tr in folds:
        rf = classifier(clf).train(features=tr, classProperty='class', inputProperties=st[2020].bandNames())
        for y in (2020, 2025):
            m = st[y].classify(rf).focalMode(1, 'square', 'pixels')
            fs = m.rename('map').sampleRegions(collection=pts[y], properties=['id'], scale=10, tileScale=4).getInfo()['features']
            out.update({f['properties']['id']: f['properties']['map'] for f in fs
                        if h is None or half_of(f['properties']['id']) == h})
    PRED_DIR.mkdir(parents=True, exist_ok=True)
    json.dump({'name': name, 'map': out}, open(PRED_DIR / f'{slug(name)}.json', 'w'))
    print(name, ' '.join(f'{y}h{h} {oa_of(out, y, h):.3f}' for y in (2020, 2025) for h in (1, 0)), flush=True)

E5 = dict(cp=(300, 700, 450, 40), texture=True, dry=True, dw_to=SH)
V = {
 'E0 base': {},
 'E1 open450': dict(cp=(300, 700, 450, 40)),
 'E2 texture': dict(texture=True),
 'E3 dry': dict(dry=True),
 'E4 all3': dict(cp=(300, 700, 450, 40), texture=True, dry=True),
 'E5 all3+shrub->open': E5,
 'E6 shrub only': dict(dw_to=SH),
 'E7 open450+shrub': dict(cp=(300, 700, 450, 40), dw_to=SH),
 'E8 open450+dry+shrub': dict(cp=(300, 700, 450, 40), dry=True, dw_to=SH),
 'E9 E5 open600': dict(cp=(300, 700, 600, 40), texture=True, dry=True, dw_to=SH),
 'G1 E5+GLCM B8 3x3': dict(E5, glcm=(('B8',), 1)),
 'G2 E5+GLCM B8 5x5': dict(E5, glcm=(('B8',), 2)),
 'G3 E5+GLCM B8,NDVI 3x3': dict(E5, glcm=(('B8', 'NDVI'), 1)),
 'R1 E5+Sentinel-1': dict(E5, s1=True),
 'A1 E5+AlphaEarth same year': dict(E5, emb=[0]),
 'A2 E5+AlphaEarth two-year mean': dict(E5, emb=[-1, 0]),
 'A3 AlphaEarth only, two-year mean': dict(E5, emb=[-1, 0], only_emb=True),
 'A4 E5+AlphaEarth+Sentinel-1': dict(E5, emb=[-1, 0], s1=True),
 'B1 E5+Open Buildings': dict(E5, obt=True),
 'L1 E5, labels DW=ESRI only': dict(E5, cons='esri'),
 'C1 E5, 300 trees': dict(E5, clf=('rf', 300)),
 'C2 E5, gradient boosting': dict(E5, clf=('gtb', 200)),
 'H1 E5+hand points x10 (cross-fit)': dict(E5, hand=10),
 'H2 E5+hand x3': dict(E5, hand=3),
 'H3 E5+hand x30': dict(E5, hand=30),
 'H4 E5 features, hand points only': dict(E5, hand=1, hand_only=True),
 'H5 E5+AlphaEarth, hand x10': dict(E5, emb=[-1, 0], hand=10),
 'H6 AlphaEarth only, hand points only': dict(E5, emb=[-1, 0], only_emb=True, hand=1, hand_only=True),
 'H7 E5+AlphaEarth, hand points only': dict(E5, emb=[-1, 0], hand=1, hand_only=True),
 'H8 E5+Sentinel-1, hand x10': dict(E5, s1=True, hand=10),
 'O1 E5 features, own labels only': dict(E5, own=1, own_only=True),
 'O2 AlphaEarth only, own labels only': dict(E5, emb=[-1, 0], only_emb=True, own=1, own_only=True),
 'O3 E5+AlphaEarth, own labels only': dict(E5, emb=[-1, 0], own=1, own_only=True),
 'O4 E5+AlphaEarth+Sentinel-1, own only': dict(E5, emb=[-1, 0], s1=True, own=1, own_only=True),
 'O5 E5, DW+own x10': dict(E5, own=10),
 'O6 E5+AlphaEarth, DW+own x10': dict(E5, emb=[-1, 0], own=10),
 'O7 E5+AlphaEarth, own high+med only': dict(E5, emb=[-1, 0], own=1, own_only=True, own_conf=('high', 'medium')),
 'O8 AlphaEarth only, own, kNN k=5': dict(E5, emb=[-1, 0], only_emb=True, own=1, own_only=True, clf=('knn', 5)),
 'O9 E5+AlphaEarth, own, 300 trees': dict(E5, emb=[-1, 0], own=1, own_only=True, clf=('rf', 300)),
 'P1 O1+Sentinel-1': dict(E5, s1=True, own=1, own_only=True),
 'P2 O1, 300 trees': dict(E5, own=1, own_only=True, clf=('rf', 300)),
 'P3 O1, high+med only': dict(E5, own=1, own_only=True, own_conf=('high', 'medium')),
 'P4 winter bands only, own labels': dict(own=1, own_only=True),
 'P5 O1, gradient boosting': dict(E5, own=1, own_only=True, clf=('gtb', 200)),
 'P6 O1+GLCM B8 3x3': dict(E5, glcm=(('B8',), 1), own=1, own_only=True),
 'E5t500 E5, 500 trees': dict(E5, clf=('rf', 500)),
 'O1t500 O1, 500 trees (shipped)': dict(E5, own=1, own_only=True, clf=('rf', 500)),
}
# seed 42 was the luckiest of six for O1 on the odd half, so both label sources are rerun with five other forest seeds
for s in (1, 7, 13, 99, 2026):
    V[f'E5s{s} E5, forest seed {s}'] = dict(E5, clf=('rf', 100, s))
    V[f'O1s{s} O1, forest seed {s}'] = dict(E5, own=1, own_only=True, clf=('rf', 100, s))
if __name__ == '__main__':
    for k in [n for n in V if not sys.argv[2:] or slug(n) in sys.argv[2:]]:
        run(k, **V[k])
