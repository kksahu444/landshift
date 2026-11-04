"""Write the deck's TikZ charts from results/results.json, so every number on a slide comes from the pipeline output.

Usage: python3 slides/make_charts.py
"""
import json
import struct
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
R = json.load(open(HERE.parent / 'results' / 'results.json'))
OUT = HERE / 'charts'
OUT.mkdir(exist_ok=True)

NAMES = ['Built-up', 'Vegetation', 'Open land', 'Water']
COL = ['cbuilt', 'cveg', 'copen', 'cwater']
trans = {t['code']: t['sum'] for t in R['transitions_ha']}
flow = [[trans.get(10 * a + b, 0.0) for b in range(4)] for a in range(4)]


def sankey():
    H, W, bar, gap, hmin = 5.6, 7.2, 0.32, 0.22, 0.10
    total = sum(map(sum, flow))
    s = (H - 3 * gap) / total
    left = [sum(flow[a]) for a in range(4)]
    right = [sum(flow[a][b] for a in range(4)) for b in range(4)]

    def stack(areas):
        y, spans = H, []
        for v in areas:
            h = max(v * s, hmin)
            spans.append([y, y - h])
            y -= h + gap
        return spans

    L, Rt = stack(left), stack(right)
    lcur = [sp[0] for sp in L]
    rcur = [sp[0] for sp in Rt]
    out, labels = [], []
    order = [(a, b) for a in range(4) for b in range(4) if flow[a][b] > 0]
    for a, b in order:
        # water's bar is stretched to hmin, so its flows split that bar by area instead of using the ha scale
        h = (L[a][0] - L[a][1]) * flow[a][b] / left[a]
        if a != b:
            h = max(h, 0.02)
        y0t, y0b = lcur[a], lcur[a] - h
        y1t, y1b = rcur[b], rcur[b] - h
        lcur[a], rcur[b] = y0b, y1b
        x0, x1, xm = bar, W - bar, W / 2
        op = 0.22 if a == b else 0.85
        out.append(f'\\fill[{COL[a]},opacity={op}] ({x0},{y0t:.3f}) .. controls ({xm},{y0t:.3f}) and ({xm},{y1t:.3f}) .. ({x1},{y1t:.3f})'
                   f' -- ({x1},{y1b:.3f}) .. controls ({xm},{y1b:.3f}) and ({xm},{y0b:.3f}) .. ({x0},{y0b:.3f}) -- cycle;')
        if a != b and flow[a][b] > 5:
            ym = (y0t + y0b + y1t + y1b) / 4
            labels.append(f'\\node[font=\\scriptsize\\bfseries,text=ink,fill=white,draw=rule,inner sep=1.5pt,rounded corners=2pt] at ({xm},{ym:.3f}) {{{flow[a][b]:.1f} ha}};')
    out += labels
    for i in range(4):
        (lt, lb), (rt, rb) = L[i], Rt[i]
        out.append(f'\\fill[{COL[i]}] (0,{lt:.3f}) rectangle ({bar},{lb:.3f});')
        out.append(f'\\fill[{COL[i]}] ({W - bar},{rt:.3f}) rectangle ({W},{rb:.3f});')
        out.append(f'\\node[anchor=east,font=\\scriptsize,align=right,inner sep=0] at (-0.12,{(lt + lb) / 2:.3f}) {{{NAMES[i]}\\\\\\textcolor{{muted}}{{{left[i]:.1f} ha}}}};')
        out.append(f'\\node[anchor=west,font=\\scriptsize,align=left,inner sep=0] at ({W + 0.12},{(rt + rb) / 2:.3f}) {{{NAMES[i]}\\\\\\textcolor{{muted}}{{{right[i]:.1f} ha}}}};')
    out.append(f'\\node[font=\\footnotesize\\bfseries,text=iris] at ({bar / 2},{H + 0.35}) {{2020}};')
    out.append(f'\\node[font=\\footnotesize\\bfseries,text=iris] at ({W - bar / 2},{H + 0.35}) {{2025}};')
    write('sankey', out)


def area_bars():
    # From-to totals, so the bars agree with the net change quoted on the slides. The 2025 map on its own
    # also counts the one-pixel ring around roofs that the 30 m filter drops (9.4 ha of built-up).
    totals = {'2020': [sum(flow[k]) for k in range(4)], '2025': [sum(flow[a][k] for a in range(4)) for k in range(4)]}
    sy, bw = 0.0125, 0.62
    out = []
    for t in range(0, 351, 50):
        out.append(f'\\draw[rule] (-0.2,{t * sy:.3f}) -- (10.3,{t * sy:.3f}); \\node[anchor=east,font=\\tiny,text=muted] at (-0.25,{t * sy:.3f}) {{{t}}};')
    for k in range(3):
        x = 0.4 + k * 3.5
        for j, yr in enumerate(['2020', '2025']):
            mp = totals[yr][k]
            adj = R[yr]['independent_area_weighted']['adjusted_area_ha'][k]
            lo, hi = R[yr]['independent_area_weighted']['adjusted_area_95ci_ha'][k]
            bx = x + j * (bw + 0.5)
            op = '0.45' if yr == '2020' else '1'
            cx = bx + bw / 2
            out.append(f'\\fill[{COL[k]},fill opacity={op}] ({bx:.3f},0) rectangle ({bx + bw:.3f},{mp * sy:.3f});')
            out.append(f'\\node[font=\\tiny\\bfseries,text={"white" if yr == "2025" and k != 2 else "ink"},anchor=north] at ({cx:.3f},{mp * sy - 0.04:.3f}) {{{mp:.0f}}};')
            out.append(f'\\draw[ink,line width=.9pt] ({bx + bw + 0.25:.3f},{lo * sy:.3f}) -- ({bx + bw + 0.25:.3f},{hi * sy:.3f});')
            out.append(f'\\node[diamond,fill=saffron,inner sep=1.4pt] at ({bx + bw + 0.25:.3f},{adj * sy:.3f}) {{}};')
            out.append(f'\\node[font=\\tiny,text=muted,anchor=north] at ({cx:.3f},-0.05) {{{yr}}};')
        out.append(f'\\node[font=\\scriptsize\\bfseries,anchor=north] at ({x + bw + 0.25:.3f},-0.35) {{{NAMES[k]}}};')
    out.append('\\draw[ink] (-0.2,0) -- (10.3,0);')
    write('area_bars', out)


def gain_loss():
    minus = lambda v: f'{v:+.1f}'.replace('-', '$-$')
    rows = []
    for i in range(3):
        gain = sum(flow[a][i] for a in range(4) if a != i)
        loss = sum(flow[i][b] for b in range(4) if b != i)
        rows.append(f'\\sw{{{COL[i]}}}\\,{NAMES[i]} & {gain:.1f} & {loss:.1f} & \\textbf{{{minus(gain - loss)}}} & {2 * min(gain, loss):.1f} \\\\')
    write('gain_loss', ['\\begin{tabular}{@{}lrrrr@{}}', '\\toprule', 'ha & gained & lost & net & swap \\\\', '\\midrule', *rows, '\\bottomrule', '\\end{tabular}'])


def importance():
    label = lambda k: (k[1:] + ' pre-mon.' if k.startswith('d') else k).replace('_sd', ' texture').replace('_drop', ' drop')
    group = lambda k: 'saffron' if k.startswith('d') or k == 'NDVI_drop' else ('iris' if k.endswith('_sd') else 'muted')
    top = sorted(R['importance'].items(), key=lambda kv: -kv[1])[:10]
    # Gini importance sums over trees, so it grows with the forest; bars are scaled to the top feature
    sx, rh = 4.13 / top[0][1], 0.36
    out = []
    for i, (k, v) in enumerate(top):
        y = -i * rh
        out.append(f'\\fill[{group(k)}] (0,{y - 0.13:.3f}) rectangle ({v * sx:.3f},{y + 0.13:.3f});')
        out.append(f'\\node[anchor=east,font=\\scriptsize] at (-0.08,{y:.3f}) {{{label(k)}}};')
        out.append(f'\\node[anchor=west,font=\\tiny,text=muted] at ({v * sx + 0.05:.3f},{y:.3f}) {{{v:.0f}}};')
    write('importance', out)
    added = sum(1 for k, _ in top if k.startswith('d') or k.endswith('_sd') or k == 'NDVI_drop')
    return added


def confusion(yr):
    m = R[yr]['independent_area_weighted']['matrix']
    c, out = 0.7, []
    short = ['Built', 'Veg', 'Open', 'Water']
    for i in range(4):
        rs = sum(m[i])
        for j in range(4):
            p = m[i][j] / rs
            tone = 'iris' if i == j else 'saffron'
            out.append(f'\\fill[{tone}!{int(8 + 85 * p)}!bg] ({j * c:.3f},{-i * c:.3f}) rectangle ({(j + 1) * c - 0.04:.3f},{-(i + 1) * c + 0.04:.3f});')
            txt = 'white' if p > 0.5 else 'ink'
            out.append(f'\\node[font=\\scriptsize,text={txt}] at ({(j + 0.48) * c:.3f},{-(i + 0.48) * c:.3f}) {{{m[i][j]}}};')
        out.append(f'\\node[anchor=east,font=\\tiny] at (-0.05,{-(i + 0.48) * c:.3f}) {{{short[i]}}};')
        out.append(f'\\node[anchor=south,font=\\tiny] at ({(i + 0.48) * c:.3f},0.02) {{{short[i]}}};')
    oa = R[yr]['independent_area_weighted']['overall']
    lo, hi = R[yr]['independent_area_weighted']['overall_95ci']
    out.append(f'\\node[font=\\footnotesize\\bfseries,anchor=south] at ({2 * c:.3f},0.42) {{{yr}: OA {oa:.2f} ({lo:.2f} to {hi:.2f})}};')
    out.append(f'\\node[font=\\tiny,text=muted,rotate=90] at (-0.95,{-2 * c:.3f}) {{reference (WorldView)}};')
    out.append(f'\\node[font=\\tiny,text=muted] at ({2 * c:.3f},{-4 * c - 0.2:.3f}) {{map}};')
    write(f'confusion_{yr}', out)


def timeline():
    W, out = 11.0, []
    days = lambda d, y0: (d - date(y0, 11, 1)).days
    span = days(date(2020, 5, 31), 2019)
    sx = W / span
    xm = days(date(2020, 3, 1), 2019) * sx
    out.append(f'\\fill[haze] (0,-0.25) rectangle ({xm:.3f},1.45); \\fill[saffron!12!bg] ({xm:.3f},-0.25) rectangle ({W},1.45);')
    out.append(f'\\node[font=\\tiny\\bfseries,text=iris,anchor=north west] at (0.05,1.45) {{WINTER, Nov-Feb}};')
    out.append(f'\\node[font=\\tiny\\bfseries,text=saffron,anchor=north west] at ({xm + 0.05:.3f},1.45) {{PRE-MONSOON, Mar-May}};')
    for i, (yr, y0) in enumerate([('2020', 2019), ('2025', 2024)]):
        y = 0.75 - i * 0.6
        out.append(f'\\node[anchor=east,font=\\scriptsize\\bfseries] at (-0.1,{y}) {{{y0}-{str(y0 + 1)[2:]}}};')
        out.append(f'\\draw[rule] (0,{y}) -- ({W},{y});')
        for key, col in [('scenes', 'iris'), ('scenes_dry', 'saffron')]:
            for sc in R[yr][key]:
                x = days(date.fromisoformat(sc['date']), y0) * sx
                out.append(f'\\fill[{col}] ({x:.3f},{y}) circle (2.4pt);')
    for mo, lab in [(11, 'Nov'), (12, 'Dec'), (1, 'Jan'), (2, 'Feb'), (3, 'Mar'), (4, 'Apr'), (5, 'May')]:
        x = days(date(2019 if mo > 6 else 2020, mo, 1), 2019) * sx
        out.append(f'\\node[font=\\tiny,text=muted,anchor=north] at ({x + 0.5:.3f},-0.25) {{{lab}}};')
    write('timeline', out)


def write(name, lines):
    (OUT / f'{name}.tex').write_text('\n'.join(lines) + '\n')


sankey()
area_bars()
gain_loss()
print('feature-set additions in top 10 importance:', importance())
confusion('2020')
confusion('2025')
timeline()


def significance():
    """Net change 2020->2025 per class, error-adjusted, 95% CI from the two independent point samples."""
    a, b = R['2020']['independent_area_weighted'], R['2025']['independent_area_weighted']
    names = ['Built-up', 'Vegetation', 'Open land', 'Water']
    sx = .024
    out = []
    for t in (-100, -50, 0, 50, 100, 150):
        out.append(f'\\draw[{"ink,thick" if t == 0 else "rule"}] ({t * sx:.2f},.3) -- ({t * sx:.2f},-2.2);')
        out.append(f'\\node[font=\\tiny,text=muted] at ({t * sx:.2f},-2.42) {{{t:+d}}};'.replace('+0', '0').replace('{-', '{$-$'))
    for i in range(4):
        y = -.62 * i
        h1 = (a['adjusted_area_95ci_ha'][i][1] - a['adjusted_area_95ci_ha'][i][0]) / 2
        h2 = (b['adjusted_area_95ci_ha'][i][1] - b['adjusted_area_95ci_ha'][i][0]) / 2
        d = b['adjusted_area_ha'][i] - a['adjusted_area_ha'][i]
        h = (h1 ** 2 + h2 ** 2) ** .5
        real = d - h > 0 or d + h < 0
        mapd = sum(flow[a][i] for a in range(4)) - sum(flow[i])
        out.append(f'\\node[anchor=east,font=\\scriptsize\\bfseries] at (-3.15,{y}) {{{names[i]}}};')
        out.append(f'\\draw[line width=2.2pt,{COL[i]}!{90 if real else 45}] ({(d - h) * sx:.2f},{y}) -- ({(d + h) * sx:.2f},{y});')
        out.append(f'\\fill[ink] ({d * sx:.2f},{y}) circle (2.6pt);')
        out.append(f'\\draw[ink,fill=white] ({mapd * sx:.2f},{y + .22}) +(0,.09) -- +(.09,0) -- +(0,-.09) -- +(-.09,0) -- cycle;')
        verdict = 'REAL CHANGE' if real else 'within error'
        gain = f'{d:+.0f}'.replace('-', '$-$')
        out.append(f'\\node[anchor=west,font=\\tiny,text={"saffron" if real else "muted"}] at (4.3,{y}) {{{gain} $\\pm$ {h:.0f} ha \\; {verdict}}};')
    out.append(f'\\node[font=\\tiny,text=muted] at (0,-2.75) {{net change 2020 $\\rightarrow$ 2025 (ha)}};')
    return out


write('significance', significance())


def compound():
    """Yearly crops of the south-east compound with the share of its open-to-built pixels mapped as each class."""
    C = json.load(open(HERE.parent / 'results' / 'compound_dating.json'))
    years = C['compound_pixels_by_year_ha']
    total = C['site_open_to_built_ha']
    # crops share one size; the bar sits under the year labels whatever the site's aspect
    w_px, h_px = struct.unpack('>II', open(HERE / 'img' / 'compound_2020.png', 'rb').read()[16:24])
    y_bar = -2.7 * h_px / w_px - 0.6
    out = []
    for i, (yr, ha) in enumerate(sorted(years.items())):
        x = 2.95 * i
        y0 = int(yr) - 1
        out.append(f'\\node[anchor=north west,inner sep=0] (c{i}) at ({x:.2f},0) {{\\includegraphics[width=2.7cm]{{img/compound_{yr}.png}}}};')
        out.append(f'\\node[anchor=north west,font=\\scriptsize\\bfseries,inner sep=0] at ([yshift=-1.5mm]c{i}.south west) {{{y0}-{yr[2:]}}};')
        left = x
        for k in (0, 1, 2):
            w = 2.7 * ha[NAMES[k].lower()] / total
            if w > 0.005:
                out.append(f'\\fill[{COL[k]}] ({left:.3f},{y_bar:.2f}) rectangle ({left + w:.3f},{y_bar - 0.22:.2f});')
            left += w
        pct = 100 * ha['built-up'] / total
        out.append(f'\\node[anchor=north east,font=\\scriptsize\\bfseries,text=saffron,inner sep=0] at ([yshift=-1.5mm]c{i}.south east) {{{pct:.0f}\\% built}};')
    return out


write('compound', compound())


VS = json.load(open(HERE.parent / 'results' / 'variant_scores.json'))['variants']


def label_test():
    """Paired OA gain over run 3 on each half of the points (scripts/compare_variants.py --score E5), mean of both years."""
    rows = [(None, 'DYNAMIC WORLD LABELS', 'muted'), ('R1', '+ Sentinel-1 radar'),
            ('A2', '+ AlphaEarth embeddings'), ('B1', '+ Open Buildings 2.5D'), ('G1', '+ GLCM texture'),
            ('E5t500', '500 trees instead of 100'), ('L1', 'only pixels ESRI agrees on'),
            (None, 'OUR WORLDVIEW LABELS', 'saffron'), ('O1t500', 'run 4: same 23 features'),
            ('P1', '+ Sentinel-1 radar'), ('P6', '+ GLCM texture'), ('O3', '+ AlphaEarth embeddings')]
    lim, w, rh = 0.15, 3.0, 0.335
    panels = {'odd': 3.85, 'even': 7.15}
    sx, bottom = w / (2 * lim), -(len(rows) - 0.5) * rh
    ship = [k for k, *_ in rows].index('O1t500')
    out = [f'\\fill[saffron!12] (-0.15,{-(ship - 0.5) * rh:.2f}) rectangle ({panels["even"] + w + 0.85:.2f},{-(ship + 0.5) * rh:.2f});']
    for half, x0 in panels.items():
        cx = x0 + w / 2
        for t in (-0.1, -0.05, 0, 0.05, 0.1):
            out.append(f'\\draw[{"ink,thick" if t == 0 else "rule"}] ({cx + t * sx:.2f},0.25) -- ({cx + t * sx:.2f},{bottom:.2f});')
        for t in (-0.1, 0, 0.1):
            tick = f'{t:+.2f}'.replace('+0.00', '0').replace('-', '$-$')
            out.append(f'\\node[font=\\tiny,text=muted] at ({cx + t * sx:.2f},{bottom - 0.2:.2f}) {{{tick}}};')
        title = 'CHOSEN ON: ODD IDS' if half == 'odd' else 'HELD OUT: EVEN IDS'
        out.append(f'\\node[font=\\tiny\\bfseries,text=iris] at ({cx:.2f},0.45) {{{title}}};')
    col = 'muted'
    for i, (key, text, *c) in enumerate(rows):
        y = -i * rh
        if key is None:
            col = c[0]
            out.append(f'\\node[anchor=west,font=\\tiny\\bfseries,text={col},inner sep=0] at (-0.1,{y:.2f}) {{{text}}};')
            continue
        bold = '\\bfseries' if key == 'O1t500' else ''
        out.append(f'\\node[anchor=east,font=\\scriptsize{bold}] at (3.7,{y:.2f}) {{{text}}};')
        for half, x0 in panels.items():
            d, lo, hi = VS[key][f'{half}_diff']
            cx = x0 + w / 2
            out.append(f'\\draw[{col},line width=1.5pt] ({cx + max(lo, -lim) * sx:.3f},{y:.2f}) -- ({cx + min(hi, lim) * sx:.3f},{y:.2f});')
            out.append(f'\\fill[{"ink" if key == "O1t500" else col}] ({cx + d * sx:.3f},{y:.2f}) circle ({3 if key == "O1t500" else 2.3}pt);')
        gain = f"{VS[key]['even_diff'][0]:+.3f}".replace('-', '$-$')
        out.append(f'\\node[anchor=west,font=\\tiny{bold},text={col}] at ({panels["even"] + w + 0.05:.2f},{y:.2f}) {{{gain}}};')
    return out


def label_seeds():
    """Mean OA of both years for seven forests per label source on each half: seeds 42, 1, 7, 13, 99, 2026 and 500 trees."""
    keys = lambda g: [g] + [f'{g}s{s}' for s in (1, 7, 13, 99, 2026)] + [f'{g}t500']
    lo, sy = 0.64, 14
    out = []
    for t in (0.65, 0.70, 0.75, 0.80, 0.85):
        out.append(f'\\draw[rule] (0,{(t - lo) * sy:.2f}) -- (4.9,{(t - lo) * sy:.2f});')
        out.append(f'\\node[anchor=east,font=\\tiny,text=muted] at (-0.05,{(t - lo) * sy:.2f}) {{{t:.2f}}};')
    spread = {}
    for j, half in enumerate(('odd', 'even')):
        for k, (g, col, name) in enumerate((('E5', 'muted', 'DW'), ('O1', 'saffron', 'own'))):
            x = 1.0 + 2.4 * j + 1.0 * k
            vals = [sum(VS[v][f'{half}_oa']) / 2 for v in keys(g)]
            spread[half, name] = (min(vals), sum(vals) / len(vals), max(vals))
            for i, v in enumerate(vals):
                out.append(f'\\fill[{col},opacity=.85] ({x + (i - 3) * 0.1:.2f},{(v - lo) * sy:.3f}) circle (2.2pt);')
            m = (sum(vals) / len(vals) - lo) * sy
            out.append(f'\\draw[ink,line width=1pt] ({x - 0.42:.2f},{m:.3f}) -- ({x + 0.42:.2f},{m:.3f});')
            out.append(f'\\node[font=\\tiny\\bfseries,text={col}] at ({x:.2f},-0.22) {{{name}}};')
        out.append(f'\\node[font=\\tiny\\bfseries,text=iris] at ({1.5 + 2.4 * j:.2f},-0.52) {{{"CHOSEN ON" if half == "odd" else "HELD OUT"}}};')
    return out, spread


write('label_test', label_test())
seeds, spread = label_seeds()
write('label_seeds', seeds)
for k, (a, m, b) in spread.items():
    print('seven forests', *k, f'min {a:.3f} mean {m:.3f} max {b:.3f}')
