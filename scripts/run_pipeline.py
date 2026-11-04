"""Python mirror of gee/lulc_pipeline.js. Writes every Console number to results.json, plus map PNGs.

Usage: python scripts/run_pipeline.py <cloud-project> [out_dir]
"""
import csv
import json
import sys
import urllib.request
from pathlib import Path

import ee

ee.Initialize(project=sys.argv[1])

ROOT = Path(__file__).parent.parent
ring = json.load(open(ROOT / 'data' / 'iitkgp_campus_osm.geojson'))['coordinates'][0]
aoi = ee.Geometry.Polygon([[[round(x, 5), round(y, 5)] for x, y in ring]])

EPOCHS = [
    {'label': 'Epoch1_2020', 'start': '2019-11-01', 'end': '2020-03-01', 'dry_start': '2020-03-01', 'dry_end': '2020-06-01'},
    {'label': 'Epoch2_2025', 'start': '2024-11-01', 'end': '2025-03-01', 'dry_start': '2025-03-01', 'dry_end': '2025-06-01'},
]
BANDS = ['B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B8A', 'B11', 'B12']
CLOUD_AOI_MAX = 10
CLOUD_AOI_MAX_DRY = 20
NAMES = ['Built-up', 'Vegetation', 'Open land', 'Water']
NAMES_LOWER = [n.lower() for n in NAMES]
ORDER = [0, 1, 2, 3]
DW_FROM = [0, 1, 2, 3, 4, 5, 6, 7]
DW_TO = [3, 1, 2, 1, 2, 2, 0, 2]
DW_MIN_AGREEMENT = 0.6
CLASS_POINTS = [300, 700, 450, 40]
TREES = 500
# The water training points are ponds up to 3 km outside the fence (training/NOTES.md), so the stack the
# training points are read from reaches that far; the maps stay clipped to the campus.
TRAIN_REGION = aoi.buffer(3500)


def add_aoi_cloud(img):
    scl = img.select('SCL')
    cloudy = scl.eq(3).Or(scl.eq(8)).Or(scl.eq(9)).Or(scl.eq(10))
    frac = cloudy.reduceRegion(reducer=ee.Reducer.mean(), geometry=aoi, scale=20, maxPixels=1e9).get('SCL')
    return img.set('aoi_cloud_pct', ee.Number(frac).multiply(100))


def prep(img):
    scl = img.select('SCL')
    good = scl.neq(1).And(scl.neq(3)).And(scl.neq(8)).And(scl.neq(9)).And(scl.neq(10))
    return ee.Image(img.select(BANDS).resample('bilinear').updateMask(good).divide(10000)
                    .copyProperties(img, ['system:time_start']))


def seasonal(start, end, cloud_max, scenes_out, region=aoi):
    col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
           .filterBounds(aoi).filterDate(start, end)
           .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 40))
           .map(add_aoi_cloud)
           .filter(ee.Filter.lt('aoi_cloud_pct', cloud_max)))
    scenes = ee.FeatureCollection(col.map(lambda i: ee.Feature(None, {
        'date': i.date().format('YYYY-MM-dd'), 'tile': i.get('MGRS_TILE'),
        'tile_cloud_pct': i.get('CLOUDY_PIXEL_PERCENTAGE'), 'aoi_cloud_pct': i.get('aoi_cloud_pct')})))
    scenes_out.extend(f['properties'] for f in scenes.getInfo()['features'])
    comp = col.map(prep).median().clip(region)
    return (comp.addBands(comp.normalizedDifference(['B8', 'B4']).rename('NDVI'))
                .addBands(comp.normalizedDifference(['B11', 'B8']).rename('NDBI'))
                .addBands(comp.normalizedDifference(['B3', 'B8']).rename('NDWI')))


def composite(ep, report, region=aoi):
    comp = seasonal(ep['start'], ep['end'], CLOUD_AOI_MAX, report.setdefault('scenes', []), region)
    dry = seasonal(ep['dry_start'], ep['dry_end'], CLOUD_AOI_MAX_DRY, report.setdefault('scenes_dry', []), region).select(
        ['B4', 'B8', 'B11', 'B12', 'NDVI', 'NDBI', 'NDWI'], ['dB4', 'dB8', 'dB11', 'dB12', 'dNDVI', 'dNDBI', 'dNDWI'])
    sd = ee.Reducer.stdDev()
    return (comp.addBands(comp.select('NDVI').reduceNeighborhood(sd, ee.Kernel.square(1)).rename('NDVI_sd'))
                .addBands(comp.select('B8').reduceNeighborhood(sd, ee.Kernel.square(1)).rename('B8_sd'))
                .addBands(dry)
                .addBands(comp.select('NDVI').subtract(dry.select('dNDVI')).rename('NDVI_drop')))


def dw_reference(ep):
    dw = (ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1')
          .filterBounds(aoi).filterDate(ep['start'], ep['end']).select('label')
          .map(lambda i: i.remap(DW_FROM, DW_TO)))
    mode = dw.mode()
    agreement = dw.map(lambda i: i.eq(mode)).mean()
    return mode.int().rename('class').updateMask(agreement.gte(DW_MIN_AGREEMENT)).clip(aoi)


def accuracy(cm):
    return ee.Dictionary({
        'matrix': cm.array(), 'overall': cm.accuracy(), 'kappa': cm.kappa(),
        'producers': cm.producersAccuracy(), 'users': cm.consumersAccuracy()}).getInfo()


def labelled_samples(ep, year, report):
    stack = composite(ep, report)
    samples = stack.addBands(dw_reference(ep)).stratifiedSample(
        numPoints=0, classBand='class', classValues=ORDER, classPoints=CLASS_POINTS,
        region=aoi, scale=10, seed=42, geometries=True, tileScale=4
    ).randomColumn('r', 42).map(lambda f: f.set('year', year))
    report['samples_per_class'] = samples.aggregate_histogram('class').getInfo()
    return stack, samples


def own_points(year):
    rows = [r for r in csv.DictReader(open(ROOT / 'training' / 'points.csv')) if r['year'] == str(year)]
    return ee.FeatureCollection([ee.Feature(ee.Geometry.Point([float(r['lon']), float(r['lat'])]), {'class': int(r['class'])})
                                 for r in rows])


def hand_points(year):
    rows = [r for r in csv.DictReader(open(ROOT / 'validation' / 'points.csv'))
            if r['year'] == str(year) and r['class']]
    return ee.FeatureCollection([ee.Feature(ee.Geometry.Point([float(r['lon']), float(r['lat'])]),
                                            {'class': int(r['class']), 'stratum': NAMES_LOWER.index(r['map_class'])})
                                 for r in rows])


def area_weighted(points, area_ha):
    """Stratified estimators (Olofsson et al. 2014; Stehman 2014 for strata that differ from the map).

    points: (stratum, reference, map) per point. The strata are the classes of the earlier map the sample
    was drawn from (validation/strata_ha.json), so stratum and map class are kept apart.
    """
    total = sum(area_ha)
    w = [a / total for a in area_ha]
    n = [sum(1 for s, _, _ in points if s == h) for h in ORDER]

    def mean(h, f):
        return sum(f(r, m) for s, r, m in points if s == h) / n[h]

    def estimate(f):
        return sum(w[h] * mean(h, f) for h in ORDER)

    def ratio(num, den):
        d = estimate(den)
        return estimate(num) / d if d else None

    def ci(f, scale=1):
        se = sum(w[h] ** 2 * mean(h, f) * (1 - mean(h, f)) / (n[h] - 1) for h in ORDER) ** 0.5
        return [scale * (estimate(f) - 1.96 * se), scale * (estimate(f) + 1.96 * se)]

    return {'points_per_stratum': n,
            'matrix': [[sum(1 for _, r, m in points if r == i and m == j) for j in ORDER] for i in ORDER],
            'overall': estimate(lambda r, m: r == m), 'overall_95ci': ci(lambda r, m: r == m),
            'users': [ratio(lambda r, m: r == m == j, lambda r, m: m == j) for j in ORDER],
            'producers': [ratio(lambda r, m: r == m == i, lambda r, m: r == i) for i in ORDER],
            'adjusted_area_ha': [total * estimate(lambda r, m: r == i) for i in ORDER],
            'adjusted_area_95ci_ha': [ci(lambda r, m: r == i, total) for i in ORDER]}


def area_table(img, field):
    groups = ee.List(ee.Image.pixelArea().divide(10000).addBands(img).reduceRegion(
        reducer=ee.Reducer.sum().group(groupField=1, groupName=field),
        geometry=aoi, scale=10, maxPixels=1e9).get('groups'))
    return groups.getInfo()


def thumb(img, vis, name, out):
    url = img.getThumbURL({**vis, 'region': aoi, 'dimensions': 1400, 'format': 'png'})
    urllib.request.urlretrieve(url, out / f'{name}.png')


def train_forest(results):
    """The shipped forest, trained on my WorldView-labelled points of both epochs. scripts/date_compound.py reuses it.

    The Dynamic World samples that used to train it are kept only for the agreement check (`holdout`), on the same
    30 % split as before.
    """
    s1, samp1 = labelled_samples(EPOCHS[0], 2020, results['2020'])
    s2, samp2 = labelled_samples(EPOCHS[1], 2025, results['2025'])
    holdout = samp1.merge(samp2).filter(ee.Filter.gte('r', 0.7))
    train = ee.FeatureCollection([composite(ep, {}, TRAIN_REGION).sampleRegions(
        collection=own_points(y), properties=['class'], scale=10, tileScale=4) for ep, y in zip(EPOCHS, (2020, 2025))]).flatten()
    rf = ee.Classifier.smileRandomForest(numberOfTrees=TREES, seed=42).train(
        features=train, classProperty='class', inputProperties=s1.bandNames())
    return s1, s2, train, holdout, rf


if __name__ == '__main__':
    OUT = Path(sys.argv[2] if len(sys.argv) > 2 else 'results')
    OUT.mkdir(parents=True, exist_ok=True)
    results = {'campus_ha': aoi.area(1).divide(10000).getInfo(), '2020': {}, '2025': {}}
    s1, s2, train, holdout, rf = train_forest(results)
    results['train'], results['holdout'] = train.size().getInfo(), holdout.size().getInfo()
    explained = rf.explain().getInfo()
    results['importance'] = explained['importance']
    results['oob_error'] = explained['outOfBagErrorEstimate']
    results['train_per_class'] = train.aggregate_histogram('class').getInfo()
    tested = holdout.classify(rf)
    for year in (2020, 2025):
        results[str(year)]['dw_holdout_accuracy'] = accuracy(
            tested.filter(ee.Filter.eq('year', year)).errorMatrix('class', 'classification', ORDER))
    results['dw_holdout_accuracy_pooled'] = accuracy(tested.errorMatrix('class', 'classification', ORDER))
    # 3x3 majority filter removes isolated pixels before anything is measured.
    m1 = s1.classify(rf).focalMode(1, 'square', 'pixels').rename('class')
    m2 = s2.classify(rf).focalMode(1, 'square', 'pixels').rename('class')

    results['2020']['area_ha'] = area_table(m1, 'class')
    results['2025']['area_ha'] = area_table(m2, 'class')
    # Independent points. Same matrix the Code Editor prints (unfiltered classification), then the
    # filtered map that the areas come from, weighted by stratum area: the sample is stratified by
    # map class and water, 0.2 % of the campus, has a third of the points.
    STRATA_HA = json.load(open(ROOT / 'validation' / 'strata_ha.json'))
    for stack, final, year in ((s1, m1, 2020), (s2, m2, 2025)):
        pts = hand_points(year)
        results[str(year)]['independent_accuracy'] = accuracy(
            stack.sampleRegions(collection=pts, properties=['class'], scale=10, tileScale=4)
            .classify(rf).errorMatrix('class', 'classification', ORDER))
        on_map = final.rename('map').sampleRegions(collection=pts, properties=['class', 'stratum'], scale=10, tileScale=4)
        sampled = [(f['properties']['stratum'], f['properties']['class'], f['properties']['map'])
                   for f in on_map.getInfo()['features']]
        results[str(year)]['independent_area_weighted'] = area_weighted(sampled, STRATA_HA[str(year)])
    # Change has to survive a 1-pixel erosion. Strips under 30 m wide are roof edges
    # shifting between the two composites, not change.
    raw_change = m1.neq(m2)
    changed = raw_change.focalMin(1, 'square', 'pixels').focalMax(1, 'square', 'pixels').And(raw_change)
    code = m1.multiply(10).add(m1.where(changed, m2)).rename('code')
    results['transitions_ha'] = area_table(code, 'code')
    results['changed_ha'] = area_table(changed.rename('changed'), 'changed')
    results['changed_ha_before_mmu'] = area_table(raw_change.rename('changed'), 'changed')
    json.dump(results, open(OUT / 'results.json', 'w'), indent=1)

    pal = ['d73027', '1a9850', 'e6d98a', '2c7fb8']
    outline = ee.Image().byte().paint(ee.FeatureCollection([ee.Feature(aoi)]), 1, 2).visualize(palette=['000000'])
    for stack, year in ((s1, 2020), (s2, 2025)):
        tc = stack.visualize(bands=['B4', 'B3', 'B2'], min=0.02, max=0.25)
        thumb(tc.blend(outline), {}, f'true_colour_{year}', OUT)
    lulc_vis = dict(min=0, max=3, palette=pal)
    thumb(m1.visualize(**lulc_vis).blend(outline), {}, 'lulc_2020', OUT)
    thumb(m2.visualize(**lulc_vis).blend(outline), {}, 'lulc_2025', OUT)
    base = s2.visualize(bands=['B4', 'B3', 'B2'], min=0.02, max=0.25).multiply(0.5).uint8()
    thumb(base.blend(changed.selfMask().visualize(palette=['ff00ff'])).blend(outline), {}, 'change_2020_2025', OUT)
    print('wrote', OUT.resolve())
