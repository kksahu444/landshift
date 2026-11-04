// LULC mapping and change detection, IIT Kharagpur campus, 2020 vs 2025.
// CS60111 GIS term project, Group 8.
// Sentinel-2 L2A dry-season median composites -> Random Forest -> post-classification change.
//
// Paste into code.earthengine.google.com and press Run. Nothing has to be drawn first:
//   - the campus boundary is OSM way 52435606, embedded below
//   - training labels are the 556 points I labelled on WorldView: paste gee/training_points.js
//     (training20, training25) above this file, or the forest has nothing to train on
//   - one Random Forest, 500 trees, is trained on both years and applied to both
// Optional: gee/validation_points.js, pasted above as well, defines
//   built20, veg20, open20, water20, built25, veg25, open25, water25
// and gives the independent accuracy figures (unweighted; scripts/run_pipeline.py has the
// area-weighted ones). Without them only the agreement with Dynamic World is printed.

var aoi = ee.Geometry.Polygon([[
  [87.29372, 22.31302], [87.29374, 22.31260], [87.29375, 22.31245], [87.29377, 22.31198], [87.29389, 22.31166], [87.29399, 22.31146],
  [87.29407, 22.31128], [87.29418, 22.31112], [87.29428, 22.31101], [87.29440, 22.31092], [87.29460, 22.31076], [87.29477, 22.31064],
  [87.29518, 22.31045], [87.29558, 22.31027], [87.29573, 22.31013], [87.29587, 22.30994], [87.29609, 22.30960], [87.29655, 22.30899],
  [87.29672, 22.30882], [87.29687, 22.30868], [87.29700, 22.30859], [87.29714, 22.30853], [87.29728, 22.30848], [87.29757, 22.30840],
  [87.29800, 22.30830], [87.29841, 22.30820], [87.29914, 22.30802], [87.29945, 22.30796], [87.29973, 22.30793], [87.29999, 22.30793],
  [87.30026, 22.30792], [87.30040, 22.30793], [87.30051, 22.30794], [87.30065, 22.30797], [87.30075, 22.30803], [87.30084, 22.30810],
  [87.30094, 22.30820], [87.30142, 22.30875], [87.30198, 22.30936], [87.30205, 22.30941], [87.30208, 22.30943], [87.30211, 22.30945],
  [87.30217, 22.30948], [87.30225, 22.30951], [87.30250, 22.30956], [87.30309, 22.30961], [87.30342, 22.30964], [87.30362, 22.30963],
  [87.30384, 22.30960], [87.30403, 22.30952], [87.30420, 22.30941], [87.30436, 22.30930], [87.30455, 22.30915], [87.30466, 22.30901],
  [87.30472, 22.30891], [87.30477, 22.30882], [87.30489, 22.30868], [87.30498, 22.30861], [87.30502, 22.30859], [87.30566, 22.30803],
  [87.30562, 22.30800], [87.30677, 22.30709], [87.30754, 22.30650], [87.30759, 22.30656], [87.30768, 22.30652], [87.30816, 22.30610],
  [87.30915, 22.30664], [87.30939, 22.30669], [87.30991, 22.30655], [87.31018, 22.30680], [87.31014, 22.30684], [87.31017, 22.30690],
  [87.31025, 22.30701], [87.31034, 22.30699], [87.31043, 22.30707], [87.31113, 22.30713], [87.31133, 22.30709], [87.31136, 22.30697],
  [87.31162, 22.30689], [87.31165, 22.30707], [87.31184, 22.30701], [87.31203, 22.30688], [87.31217, 22.30675], [87.31233, 22.30661],
  [87.31234, 22.30653], [87.31239, 22.30649], [87.31308, 22.30652], [87.31379, 22.30656], [87.31489, 22.30654], [87.31497, 22.30691],
  [87.31500, 22.30705], [87.31504, 22.30714], [87.31547, 22.30703], [87.31597, 22.30706], [87.31635, 22.30708], [87.31638, 22.30704],
  [87.31666, 22.30704], [87.31678, 22.30688], [87.31739, 22.30672], [87.31851, 22.30719], [87.31848, 22.30747], [87.31850, 22.30776],
  [87.31878, 22.30789], [87.31889, 22.30789], [87.31977, 22.30772], [87.32018, 22.30790], [87.32166, 22.30852], [87.32182, 22.30864],
  [87.32188, 22.30894], [87.32200, 22.30910], [87.32212, 22.30946], [87.32299, 22.31001], [87.32350, 22.31000], [87.32364, 22.31003],
  [87.32390, 22.30996], [87.32417, 22.30975], [87.32510, 22.31010], [87.32519, 22.30986], [87.32725, 22.31068], [87.32875, 22.31129],
  [87.32899, 22.31156], [87.32894, 22.31164], [87.32887, 22.31227], [87.32866, 22.31269], [87.32851, 22.31283], [87.32804, 22.31330],
  [87.32744, 22.31375], [87.32591, 22.31480], [87.32572, 22.31502], [87.32518, 22.31536], [87.32475, 22.31556], [87.32466, 22.31570],
  [87.32345, 22.31637], [87.32300, 22.31660], [87.32251, 22.31687], [87.32139, 22.31736], [87.32121, 22.31745], [87.31719, 22.32032],
  [87.31767, 22.32089], [87.31654, 22.32165], [87.31634, 22.32184], [87.31555, 22.32218], [87.31508, 22.32235], [87.31467, 22.32245],
  [87.31388, 22.32255], [87.31295, 22.32264], [87.31097, 22.32283], [87.31079, 22.32283], [87.31078, 22.32272], [87.31059, 22.32275],
  [87.31053, 22.32266], [87.31038, 22.32274], [87.31023, 22.32244], [87.31007, 22.32249], [87.30999, 22.32249], [87.30970, 22.32254],
  [87.30887, 22.32277], [87.30828, 22.32285], [87.30731, 22.32296], [87.30697, 22.32298], [87.30563, 22.32300], [87.30527, 22.32296],
  [87.30523, 22.32292], [87.30398, 22.32276], [87.30393, 22.32278], [87.30351, 22.32269], [87.30222, 22.32244], [87.30135, 22.32228],
  [87.29887, 22.32189], [87.29860, 22.32186], [87.29834, 22.32184], [87.29812, 22.32177], [87.29797, 22.32167], [87.29765, 22.32140],
  [87.29631, 22.31957], [87.29548, 22.31839], [87.29449, 22.31700], [87.29441, 22.31686], [87.29415, 22.31603], [87.29397, 22.31516],
  [87.29383, 22.31451], [87.29377, 22.31404], [87.29373, 22.31371], [87.29372, 22.31302]
]]);

var EPOCHS = [
  {label: 'Epoch1_2020', start: '2019-11-01', end: '2020-03-01', dryStart: '2020-03-01', dryEnd: '2020-06-01'},
  {label: 'Epoch2_2025', start: '2024-11-01', end: '2025-03-01', dryStart: '2025-03-01', dryEnd: '2025-06-01'}
];
var BANDS = ['B2','B3','B4','B5','B6','B7','B8','B8A','B11','B12'];
var CLOUD_AOI_MAX = 10;
// Pre-monsoon haze is worse, and that composite only adds a few bands.
var CLOUD_AOI_MAX_DRY = 20;
var CLASS_NAMES = ee.List(['Built-up', 'Vegetation', 'Open land', 'Water']);
var ORDER = [0, 1, 2, 3];
var TREES = 500;
// The water training points are ponds up to 3 km outside the fence (training/NOTES.md), so the stack the
// training points are read from reaches that far; the maps stay clipped to the campus.
var TRAIN_REGION = aoi.buffer(3500);

// Dynamic World label -> project class. Runs 1-3 trained on these labels; now they are only compared with.
// DW: 0 water, 1 trees, 2 grass, 3 flooded veg, 4 crops, 5 shrub, 6 built, 7 bare
// Grass, crops and shrub go to open land. There is no farmland inside the fence; DW labels
// the lawns and playgrounds as crops, and almost never as grass. DW's shrub on campus is the
// dry grassland with scattered bushes in the east end, which the reference points call open land.
var DW_FROM = [0, 1, 2, 3, 4, 5, 6, 7];
var DW_TO   = [3, 1, 2, 1, 2, 2, 0, 2];
var DW_MIN_AGREEMENT = 0.6;
// The Dynamic World sample runs 1-3 trained on, kept unchanged so the agreement figure stays
// comparable. Close to the campus class shares (about 22 / 70 / 7 / 0.2 %), with a floor for
// water; open land above its share, since at its share the forest rarely predicted it.
var CLASS_POINTS = [300, 700, 450, 40];

function addAoiCloud(img) {
  var scl = img.select('SCL');
  var cloudy = scl.eq(3).or(scl.eq(8)).or(scl.eq(9)).or(scl.eq(10));
  var frac = cloudy.reduceRegion({reducer: ee.Reducer.mean(), geometry: aoi, scale: 20, maxPixels: 1e9}).get('SCL');
  return img.set('aoi_cloud_pct', ee.Number(frac).multiply(100));
}

function prep(img) {
  var scl = img.select('SCL');
  var good = scl.neq(1).and(scl.neq(3)).and(scl.neq(8)).and(scl.neq(9)).and(scl.neq(10));
  return ee.Image(img.select(BANDS).resample('bilinear').updateMask(good).divide(10000)
                     .copyProperties(img, ['system:time_start']));
}

function seasonal(label, start, end, cloudMax, region) {
  var col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterBounds(aoi).filterDate(start, end)
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 40))
    .map(addAoiCloud)
    .filter(ee.Filter.lt('aoi_cloud_pct', cloudMax));
  // The training stack uses the same scenes (cloud is still judged over the campus), so only the map stack prints them.
  if (!region) {
    print(label + ': scenes used', col.size());
    print(label + ': scene table', ee.FeatureCollection(col.map(function (i) {
      return ee.Feature(null, {date: i.date().format('YYYY-MM-dd'), tile: i.get('MGRS_TILE'),
        tile_cloud_pct: i.get('CLOUDY_PIXEL_PERCENTAGE'), aoi_cloud_pct: i.get('aoi_cloud_pct')});
    })));
  }
  var comp = col.map(prep).median().clip(region || aoi);
  return comp
    .addBands(comp.normalizedDifference(['B8','B4']).rename('NDVI'))
    .addBands(comp.normalizedDifference(['B11','B8']).rename('NDBI'))
    .addBands(comp.normalizedDifference(['B3','B8']).rename('NDWI'));
}

// Winter composite plus two things that separate lawns from canopy: 3x3 texture (canopy is
// rough, lawns are smooth) and the March-May composite, when grass dries out and trees stay green.
// region defaults to the campus; the training stack passes TRAIN_REGION.
function composite(ep, region) {
  var comp = seasonal(ep.label, ep.start, ep.end, CLOUD_AOI_MAX, region);
  var dry = seasonal(ep.label + ' pre-monsoon', ep.dryStart, ep.dryEnd, CLOUD_AOI_MAX_DRY, region)
    .select(['B4','B8','B11','B12','NDVI','NDBI','NDWI'], ['dB4','dB8','dB11','dB12','dNDVI','dNDBI','dNDWI']);
  var sd = ee.Reducer.stdDev();
  return comp
    .addBands(comp.select('NDVI').reduceNeighborhood(sd, ee.Kernel.square(1)).rename('NDVI_sd'))
    .addBands(comp.select('B8').reduceNeighborhood(sd, ee.Kernel.square(1)).rename('B8_sd'))
    .addBands(dry)
    .addBands(comp.select('NDVI').subtract(dry.select('dNDVI')).rename('NDVI_drop'));
}

// Modal project class over the same window, kept only where at least
// DW_MIN_AGREEMENT of the DW scenes agree with the mode. Remapping before the mode
// means grass/crops/bare flicker does not count as disagreement.
function dwReference(ep) {
  var dw = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1')
    .filterBounds(aoi).filterDate(ep.start, ep.end).select('label')
    .map(function (i) { return i.remap(DW_FROM, DW_TO); });
  var mode = dw.mode();
  var agreement = dw.map(function (i) { return i.eq(mode); }).mean();
  return mode.int().rename('class').updateMask(agreement.gte(DW_MIN_AGREEMENT)).clip(aoi);
}

function printAccuracy(title, cm) {
  print(title + ': confusion matrix (rows reference, cols predicted; 0 built, 1 veg, 2 open, 3 water)', cm);
  print(title + ': overall accuracy', cm.accuracy());
  print(title + ': kappa', cm.kappa());
  print(title + ': producer accuracy', cm.producersAccuracy());
  print(title + ': user accuracy', cm.consumersAccuracy());
}

function handLabelled(fcs) {
  return fcs.map(function (fc, v) {
    return ee.FeatureCollection(fc).map(function (f) { return f.set('class', v); });
  }).reduce(function (a, b) { return a.merge(b); });
}

function labelledSamples(ep, year) {
  var stack = composite(ep);
  var samples = stack.addBands(dwReference(ep)).stratifiedSample({
    numPoints: 0, classBand: 'class', classValues: ORDER, classPoints: CLASS_POINTS,
    region: aoi, scale: 10, seed: 42, geometries: true, tileScale: 4
  }).randomColumn('r', 42).map(function (f) { return f.set('year', year); });
  print(ep.label + ': DW samples per class', samples.aggregate_histogram('class'));
  return {stack: stack, samples: samples};
}

function assess(e, year, hand) {
  printAccuracy(year + ' [agreement with Dynamic World, not accuracy]',
    tested.filter(ee.Filter.eq('year', year)).errorMatrix('class', 'classification', ORDER));
  if (hand) {
    var pts = e.stack.sampleRegions({collection: handLabelled(hand), properties: ['class'], scale: 10, tileScale: 4});
    print(year + ': hand-labelled points per class', pts.aggregate_histogram('class'));
    printAccuracy(year + ' [hand-labelled, independent]',
      pts.classify(rf).errorMatrix('class', 'classification', ORDER));
  }
}

function areaTable(img, field) {
  var groups = ee.List(ee.Image.pixelArea().divide(10000).addBands(img).reduceRegion({
    reducer: ee.Reducer.sum().group({groupField: 1, groupName: field}),
    geometry: aoi, scale: 10, maxPixels: 1e9
  }).get('groups'));
  return ee.FeatureCollection(groups.map(function (g) {
    return ee.Feature(null, ee.Dictionary(g).rename(['sum'], ['area_ha']));
  }));
}

function named(fc) {
  return fc.map(function (f) { return f.set('name', CLASS_NAMES.get(ee.Number(f.get('class')).int())); });
}

var hand20 = typeof built20 === 'undefined' ? null : [built20, veg20, open20, water20];
var hand25 = typeof built25 === 'undefined' ? null : [built25, veg25, open25, water25];
var e1 = labelledSamples(EPOCHS[0], 2020);
var e2 = labelledSamples(EPOCHS[1], 2025);

// One forest for both years, so a pixel changes class only when its spectra change,
// not because two separately trained models disagree. The Dynamic World samples that used to
// train it are kept only for the agreement check, on the same 30 % split as before.
var holdout = e1.samples.merge(e2.samples).filter(ee.Filter.gte('r', 0.7));
var train = ee.FeatureCollection([
  composite(EPOCHS[0], TRAIN_REGION).sampleRegions({collection: training20, properties: ['class'], scale: 10, tileScale: 4}),
  composite(EPOCHS[1], TRAIN_REGION).sampleRegions({collection: training25, properties: ['class'], scale: 10, tileScale: 4})
]).flatten();
print('training points / DW holdout', train.size(), holdout.size());
print('training points per class', train.aggregate_histogram('class'));
var rf = ee.Classifier.smileRandomForest({numberOfTrees: TREES, seed: 42}).train({
  features: train, classProperty: 'class', inputProperties: e1.stack.bandNames()});
print('RF variable importance', ee.Dictionary(rf.explain().get('importance')));
var tested = holdout.classify(rf);
assess(e1, 2020, hand20);
assess(e2, 2025, hand25);

// 3x3 majority filter removes isolated pixels before anything is measured.
var map20 = e1.stack.classify(rf).focalMode(1, 'square', 'pixels').rename('class');
var map25 = e2.stack.classify(rf).focalMode(1, 'square', 'pixels').rename('class');

print('Campus area (ha)', aoi.area(1).divide(10000));
var area20 = named(areaTable(map20, 'class'));
var area25 = named(areaTable(map25, 'class'));
print('Area by class 2020 (ha)', area20);
print('Area by class 2025 (ha)', area25);

// Change has to survive a 1-pixel erosion. Strips under 30 m wide are roof edges
// shifting between the two composites, not change.
var rawChange = map20.neq(map25);
var changed = rawChange.focalMin(1, 'square', 'pixels').focalMax(1, 'square', 'pixels')
  .and(rawChange).rename('changed');
// code = 10 * class2020 + class2025, so 12 is vegetation -> open land
var code = map20.multiply(10).add(map20.where(changed, map25)).rename('code');
var transitions = areaTable(code, 'code').map(function (f) {
  var c = ee.Number(f.get('code')).int();
  return f.set('from', CLASS_NAMES.get(c.divide(10).floor().int()), 'to', CLASS_NAMES.get(c.mod(10)));
});
print('From-to change (ha)', transitions);
print('Changed (1) vs unchanged (0), ha', areaTable(changed, 'changed'));
print('Changed before the 30 m filter, ha', areaTable(rawChange.rename('changed'), 'changed'));

var pal = ['d73027', '1a9850', 'e6d98a', '2c7fb8'];
var outline = ee.Image().byte().paint(ee.FeatureCollection([ee.Feature(aoi)]), 1, 2);
Map.centerObject(aoi, 15);
Map.addLayer(e1.stack, {bands: ['B4','B3','B2'], min: 0.02, max: 0.25}, 'True colour 2020', false);
Map.addLayer(e2.stack, {bands: ['B4','B3','B2'], min: 0.02, max: 0.25}, 'True colour 2025', false);
Map.addLayer(map20, {min: 0, max: 3, palette: pal}, 'LULC 2020');
Map.addLayer(map25, {min: 0, max: 3, palette: pal}, 'LULC 2025');
Map.addLayer(changed.selfMask(), {palette: ['ff00ff']}, 'Changed pixels');
Map.addLayer(outline, {palette: ['000000']}, 'Campus boundary (OSM)');

// Exports land in Drive/GEE_LULC. Start them from the Tasks tab.
function exportImage(img, name) {
  Export.image.toDrive({image: img, description: name, folder: 'GEE_LULC',
    fileNamePrefix: name, region: aoi, scale: 10, crs: 'EPSG:32645', maxPixels: 1e9});
}
function exportTable(fc, name) {
  Export.table.toDrive({collection: fc, description: name, folder: 'GEE_LULC', fileFormat: 'CSV'});
}
exportImage(e1.stack.select(BANDS).toFloat(), 'S2_composite_2020');
exportImage(e2.stack.select(BANDS).toFloat(), 'S2_composite_2025');
exportImage(map20.toByte(), 'LULC_2020');
exportImage(map25.toByte(), 'LULC_2025');
exportImage(code.toByte(), 'LULC_transition_code');
exportTable(area20, 'area_2020');
exportTable(area25, 'area_2025');
exportTable(transitions, 'transitions_2020_2025');
