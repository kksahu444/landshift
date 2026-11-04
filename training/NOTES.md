# Hand-labelled training points

Training labels I drew myself, to replace Dynamic World as the label source. The validation points in
`validation/points.csv` are never used for training; every training point is at least 30 m from all of them.

- `candidates.csv`: the 290 locations, from `scripts/sample_training_points.py` (seed 20261104).
- `points.csv`: one row per location and year that got a label, 556 in all.

## Points per class

| Year | Built-up | Vegetation | Open land | Water | Total |
|---|---|---|---|---|---|
| 2020 | 51 | 120 | 87 | 28 | 286 |
| 2025 | 36 | 154 | 56 | 24 | 270 |

Confidence high / medium / low: 104 / 261 / 191. Left out: 20 location-years where the square was split between two
classes (pond bunds, roof edges, roofs that lean over the square in the 2024 image) and 4 2025 labels inside the
south-east compound (87.318-87.322 E, 22.310-22.314 N), for the same reason as the validation points there.

## Where the locations come from

- 260 campus locations: simple random sample inside the fence, at least 40 m apart, 20 m inside the fence and 30 m
  from every validation point of either year.
- 30 pond locations within 3 km outside the fence (Dynamic World water in at least 60 % of scenes in both epochs).
  The campus ponds are already covered by validation points at 12 m spacing, so a campus water sample would sit on
  top of them.

## Imagery and rules

The same two WorldView scenes and the same offsets as the validation points (`validation/NOTES.md`): 15 Mar 2020
for 2020, 13 Jan 2024 for 2025. `scripts/training_sheets.py` cuts a 70 m chip per location and year with the 10 m
square marked, 12 locations per sheet. The labelling rules are the ones in `validation/NOTES.md`, unchanged.

Footprints of tall buildings are judged from the 2020 image, since the 2024 one is off-nadir.

## Calibration

Before labelling I relabelled 24 validation points (12 per year, every class) blind, from chips cut by the same script,
and compared with the reference labels: 22 of 24 agree. Both that differ are low-confidence reference points: open
ground beside the edge of a structure (reference open land, mine built-up) and a paved strip next to a lawn
(reference built-up, mine open land).

## Result

These points are the label source from run 4 on (`scripts/run_pipeline.py`, `gee/training_points.js`). Area-weighted
OA against the validation points went from 0.67 to 0.74 (2020) and from 0.77 to 0.80 (2025); the test against
radar, embeddings and texture on Dynamic World labels is in the README under "Run 4". One thing they lack: no shaded
ground is labelled, and in 2025 the map calls 22 validation points water that are building shade, dark roofs or
canopy on pond banks.
