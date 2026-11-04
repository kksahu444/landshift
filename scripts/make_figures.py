"""README and slide figures from results/.

Usage: python scripts/make_figures.py . docs/img [--bare]
--bare drops the figure title and footer, for slides that carry their own.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

REPO, OUT = Path(sys.argv[1]), Path(sys.argv[2])
BARE = '--bare' in sys.argv
OUT.mkdir(parents=True, exist_ok=True)
RES = REPO / 'results'
r = json.load(open(RES / 'results.json'))

plt.rcParams.update({'font.family': ['Avenir', 'Avenir Next', 'DejaVu Sans'], 'font.size': 12, 'axes.titlesize': 14,
                     'axes.spines.top': False, 'axes.spines.right': False})
NAMES = ['Built-up', 'Vegetation', 'Open land', 'Water']
COLS = ['#d73027', '#1a9850', '#e6d98a', '#2c7fb8']
INK, MUTED = '#1f2a30', '#5b6770'
FOOT = 'CS60111 GIS  |  Group 8  |  github.com/ashuwhy/landshift'
SCENES = {y: len(r[y]['scenes']) for y in ('2020', '2025')}


def finish(fig, name, title):
    if not BARE:
        fig.suptitle(title, x=0.02, ha='left', fontsize=19, fontweight='heavy', color=INK)
        fig.text(0.02, 0.015, FOOT, fontsize=10, color=MUTED)
    fig.savefig(OUT / name, dpi=150, facecolor='white')
    plt.close(fig)


def pair(stem, title, sub, legend=False):
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.6 if not legend else 5.2))
    for ax, year, label in zip(axes, ('2020', '2025'), sub):
        ax.imshow(plt.imread(RES / f'{stem}_{year}.png'))
        ax.set_title(label, color=INK)
        ax.axis('off')
    if legend:
        fig.legend(handles=[Patch(color=c, label=n) for c, n in zip(COLS, NAMES)],
                   loc='lower center', ncol=4, frameon=False, bbox_to_anchor=(0.5, 0.04))
    fig.subplots_adjust(left=0.01, right=0.99, top=0.84, bottom=0.14 if legend else 0.08, wspace=0.03)
    return fig


fig = pair('true_colour', '', [f'Nov 2019 - Feb 2020 ({SCENES["2020"]} scenes)',
                               f'Nov 2024 - Feb 2025 ({SCENES["2025"]} scenes)'])
finish(fig, '01_sentinel2_composites.png', 'Sentinel-2 winter median composites, IIT Kharagpur campus')

fig = pair('lulc', '', ['2020', '2025'], legend=True)
finish(fig, '02_lulc_maps.png', 'Land use / land cover, Random Forest on Sentinel-2')

area = {y: {g['class']: g['sum'] for g in r[y]['area_ha']} for y in ('2020', '2025')}
fig, ax = plt.subplots(figsize=(9, 5))
x = range(4)
b20 = ax.bar([i - 0.2 for i in x], [area['2020'][i] for i in x], 0.38, color=COLS, alpha=0.55, label='2020')
b25 = ax.bar([i + 0.2 for i in x], [area['2025'][i] for i in x], 0.38, color=COLS, edgecolor=INK, label='2025')
for bars in (b20, b25):
    ax.bar_label(bars, fmt='%.1f', padding=3, fontsize=10, color=INK)
ax.set_xticks(list(x), NAMES)
ax.set_ylabel('hectares')
ax.legend(handles=[Patch(facecolor='#999999', alpha=0.55, label='2020'),
                   Patch(facecolor='#999999', edgecolor=INK, label='2025')], frameon=False)
ax.set_ylim(0, 390)
fig.subplots_adjust(left=0.1, right=0.98, top=0.85, bottom=0.14)
finish(fig, '03_area_by_class.png', f'Area by class, campus {r["campus_ha"]:.1f} ha')

trans = {t['code']: t['sum'] for t in r['transitions_ha']}
pairs = sorted(((trans[c], NAMES[c // 10], NAMES[c % 10]) for c in trans if c // 10 != c % 10 and trans[c] > 0.5),
               reverse=True)
changed = next(g['sum'] for g in r['changed_ha'] if g['changed'] == 1)
before = next(g['sum'] for g in r['changed_ha_before_mmu'] if g['changed'] == 1)
fig = plt.figure(figsize=(15, 5.6))
ax = fig.add_axes([0.01, 0.08, 0.56, 0.76])
ax.imshow(plt.imread(RES / 'change_2020_2025.png'))
ax.set_title('Magenta: changed patches at least 30 m wide, over the 2025 image', fontsize=11, color=MUTED)
ax.axis('off')
bx = fig.add_axes([0.72, 0.14, 0.26, 0.66])
labels = [f'{a} → {b}' for _, a, b in pairs][::-1]
vals = [v for v, _, _ in pairs][::-1]
bars = bx.barh(labels, vals, color=[COLS[NAMES.index(b)] for _, _, b in pairs][::-1], edgecolor=INK, linewidth=0.5)
bx.bar_label(bars, fmt='%.1f ha', padding=4, fontsize=10)
bx.set_xlim(0, max(vals) * 1.3)
bx.set_xlabel('hectares')
bx.set_title(f'{changed:.1f} ha changed ({changed / r["campus_ha"] * 100:.1f} % of campus)\n'
             f'{before:.1f} ha before the 30 m filter', fontsize=12, color=INK, loc='left')
finish(fig, '04_change_2020_2025.png', 'Change 2020 to 2025')

fig, axes = plt.subplots(2, 2, figsize=(12, 11))
short = ['Built', 'Veg', 'Open', 'Water']
for row, (key, ylabel) in enumerate((('independent_area_weighted', 'hand-labelled reference'),
                                      ('dw_holdout_accuracy', 'Dynamic World reference'))):
    for ax, year in zip(axes[row], ('2020', '2025')):
        acc = r[year][key]
        m = acc['matrix']
        top = max(map(max, m))
        ax.imshow(m, cmap='Greens')
        for i in range(4):
            for j in range(4):
                ax.text(j, i, m[i][j], ha='center', va='center', fontsize=12,
                        color='white' if m[i][j] > top * 0.6 else INK)
        ax.set_xticks(range(4), short)
        ax.set_yticks(range(4), short)
        ax.set_xlabel('map')
        ax.set_ylabel(ylabel)
        if row == 0:
            lo, hi = acc['overall_95ci']
            ax.set_title(f'{year}: {sum(map(sum, m))} points\nOA {acc["overall"]:.2f} (95 % CI {lo:.2f}-{hi:.2f}), area-weighted',
                         color=INK, fontsize=13)
        else:
            ax.set_title(f'{year}: agreement with Dynamic World\nOA {acc["overall"]:.2f}, kappa {acc["kappa"]:.2f}', color=INK, fontsize=13)
        ax.spines[:].set_visible(False)
fig.subplots_adjust(left=0.1, right=0.97, top=0.9, bottom=0.12, wspace=0.3, hspace=0.6)
notes = ('Independent: stratified random points labelled on WorldView imagery (Krishnkant Sahu). '
         'Point counts; OA weighted by map-class area.',
         f'Dynamic World pixels ({r["holdout"]} over both years, never used for training): agreement with another map, '
         'not accuracy.')
for row, note in enumerate(notes):
    fig.text(0.5, axes[row][0].get_position().y0 - 0.075, note, ha='center', fontsize=10.5, color=MUTED)
finish(fig, '05_accuracy.png', 'Classification accuracy')
print(sorted(p.name for p in OUT.iterdir()))
