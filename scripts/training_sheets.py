"""Labelling sheets for the training locations: a 70 m WorldView chip per location and year, 10 m square marked.

Usage: python scripts/training_sheets.py <tile_cache_dir> <out_dir> [repo_dir]

Imagery is Esri World Imagery Wayback, the same two scenes as the validation points: release 119 (2020-10-14)
shows WorldView-2 of 15 Mar 2020, release 43291 (2026-10-29) shows WorldView-3 of 13 Jan 2024.
Both are shifted against Sentinel-2 (validation/NOTES.md): 2020 by 4.5 m east and 0.8 m south, 2024 by 3.5 m
west, so each chip is centred on the point plus that shift. Sheets hold 12 locations, 2020 left, 2024 right.
"""
import csv
import math
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw

CACHE, OUT = Path(sys.argv[1]), Path(sys.argv[2])
REPO = Path(sys.argv[3] if len(sys.argv) > 3 else '.')
Z = 19
URL = 'https://wayback.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/WMTS/1.0.0/default028mm/MapServer/tile/{rel}/{z}/{y}/{x}'
SCENES = [('2020', 119, (4.5, -0.8)), ('2024', 43291, (-3.5, 0.0))]
WINDOW_M, BOX_M, PER_SHEET, COLS = 70, 10, 12, 3


def global_px(lon, lat):
    n = 256 * 2 ** Z
    return (lon + 180) / 360 * n, (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n


def tile(rel, x, y):
    f = CACHE / f'{rel}_{Z}_{y}_{x}.jpg'
    if not f.exists():
        req = urllib.request.Request(URL.format(rel=rel, z=Z, y=y, x=x), headers={'User-Agent': 'campus-lulc-labelling'})
        f.write_bytes(urllib.request.urlopen(req, timeout=60).read())
    return f


def chip(rel, shift, lon, lat):
    mpp = 156543.03392 * math.cos(math.radians(lat)) / 2 ** Z
    cx, cy = global_px(lon, lat)
    cx, cy = cx + shift[0] / mpp, cy - shift[1] / mpp
    half = WINDOW_M / 2 / mpp
    x0, y0, x1, y1 = cx - half, cy - half, cx + half, cy + half
    tiles = [(tx, ty) for tx in range(int(x0 // 256), int(x1 // 256) + 1) for ty in range(int(y0 // 256), int(y1 // 256) + 1)]
    canvas = Image.new('RGB', ((tiles[-1][0] - tiles[0][0] + 1) * 256, (tiles[-1][1] - tiles[0][1] + 1) * 256))
    for tx, ty in tiles:
        canvas.paste(Image.open(tile(rel, tx, ty)), ((tx - tiles[0][0]) * 256, (ty - tiles[0][1]) * 256))
    ox, oy = tiles[0][0] * 256, tiles[0][1] * 256
    img = canvas.crop((round(x0 - ox), round(y0 - oy), round(x1 - ox), round(y1 - oy)))
    d = ImageDraw.Draw(img)
    s, b = img.size[0] / 2, BOX_M / 2 / mpp
    d.rectangle((s - b, s - b, s + b, s + b), outline=(255, 230, 0), width=2)
    return img


if __name__ == '__main__':
    CACHE.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(REPO / 'training' / 'candidates.csv')))
    jobs = [(r, rel, shift) for r in rows for _, rel, shift in SCENES]
    with ThreadPoolExecutor(8) as pool:
        chips = list(pool.map(lambda j: chip(j[1], j[2], float(j[0]['lon']), float(j[0]['lat'])), jobs))
    w = chips[0].size[0]
    cell_w, cell_h = 2 * w + 30, w + 26
    for k in range(0, len(rows), PER_SHEET):
        batch = rows[k:k + PER_SHEET]
        sheet = Image.new('RGB', (COLS * cell_w, math.ceil(len(batch) / COLS) * cell_h), 'white')
        d = ImageDraw.Draw(sheet)
        for i, r in enumerate(batch):
            x, y = (i % COLS) * cell_w, (i // COLS) * cell_h
            d.text((x + 4, y + 4), f"{r['id']}   2020 | 2024", fill='black')
            for j in range(2):
                sheet.paste(chips[(k + i) * 2 + j], (x + j * (w + 6), y + 20))
        sheet.save(OUT / f"sheet_{k // PER_SHEET + 1:02d}.png")
    print(len(rows), 'locations,', math.ceil(len(rows) / PER_SHEET), 'sheets ->', OUT)
