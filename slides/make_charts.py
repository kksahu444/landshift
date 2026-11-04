"""Write the deck's TikZ charts from results/results.json, so every number on a slide comes from the pipeline output.

Usage: python3 slides/make_charts.py
"""
import json
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
    out = []
    order = [(a, b) for a in range(4) for b in range(4) if flow[a][b] > 0]
    for a, b in order:
        h = max(flow[a][b] * s, 0.02) if a != 3 else L[3][0] - L[3][1]
        y0t, y0b = lcur[a], lcur[a] - h
        y1t, y1b = rcur[b], rcur[b] - h
        lcur[a], rcur[b] = y0b, y1b
        x0, x1, xm = bar, W - bar, W / 2
        op = 0.22 if a == b else 0.85
        out.append(f'\\fill[{COL[a]},opacity={op}] ({x0},{y0t:.3f}) .. controls ({xm},{y0t:.3f}) and ({xm},{y1t:.3f}) .. ({x1},{y1t:.3f})'
                   f' -- ({x1},{y1b:.3f}) .. controls ({xm},{y1b:.3f}) and ({xm},{y0b:.3f}) .. ({x0},{y0b:.3f}) -- cycle;')
        if a != b and flow[a][b] > 5:
            ym = (y0t + y0b + y1t + y1b) / 4
            out.append(f'\\node[font=\\scriptsize\\bfseries,text=ink,fill=white,draw=rule,inner sep=1.5pt,rounded corners=2pt] at ({xm},{ym:.3f}) {{{flow[a][b]:.1f} ha}};')
    for i in range(4):
        (lt, lb), (rt, rb) = L[i], Rt[i]
        out.append(f'\\fill[{COL[i]}] (0,{lt:.3f}) rectangle ({bar},{lb:.3f});')
        out.append(f'\\fill[{COL[i]}] ({W - bar},{rt:.3f}) rectangle ({W},{rb:.3f});')
        out.append(f'\\node[anchor=east,font=\\scriptsize,align=right] at (-0.08,{(lt + lb) / 2:.3f}) {{{NAMES[i]}\\\\\\textcolor{{muted}}{{{left[i]:.1f} ha}}}};')
        out.append(f'\\node[anchor=west,font=\\scriptsize,align=left] at ({W + 0.08},{(rt + rb) / 2:.3f}) {{{NAMES[i]}\\\\\\textcolor{{muted}}{{{right[i]:.1f} ha}}}};')
    out.append(f'\\node[font=\\footnotesize\\bfseries,text=green] at ({bar / 2},{H + 0.35}) {{2020}};')
    out.append(f'\\node[font=\\footnotesize\\bfseries,text=green] at ({W - bar / 2},{H + 0.35}) {{2025}};')
    write('sankey', out)


def area_bars():
    sy, bw = 0.0125, 0.62
    out = []
    for t in range(0, 351, 50):
        out.append(f'\\draw[rule] (-0.2,{t * sy:.3f}) -- (10.3,{t * sy:.3f}); \\node[anchor=east,font=\\tiny,text=muted] at (-0.25,{t * sy:.3f}) {{{t}}};')
    for k in range(3):
        x = 0.4 + k * 3.5
        for j, yr in enumerate(['2020', '2025']):
            mp = R[yr]['area_ha'][k]['sum']
            adj = R[yr]['independent_area_weighted']['adjusted_area_ha'][k]
            lo, hi = R[yr]['independent_area_weighted']['adjusted_area_95ci_ha'][k]
            bx = x + j * (bw + 0.5)
            op = '0.45' if yr == '2020' else '1'
            cx = bx + bw / 2
            out.append(f'\\fill[{COL[k]},fill opacity={op}] ({bx:.3f},0) rectangle ({bx + bw:.3f},{mp * sy:.3f});')
            out.append(f'\\node[font=\\tiny\\bfseries,text={"white" if yr == "2025" and k != 2 else "ink"},anchor=north] at ({cx:.3f},{mp * sy - 0.04:.3f}) {{{mp:.0f}}};')
            ex = bx + bw + 0.0
            out.append(f'\\draw[ink,line width=.9pt] ({bx + bw + 0.25:.3f},{lo * sy:.3f}) -- ({bx + bw + 0.25:.3f},{hi * sy:.3f});')
            out.append(f'\\node[diamond,fill=terra,inner sep=1.4pt] at ({bx + bw + 0.25:.3f},{adj * sy:.3f}) {{}};')
            out.append(f'\\node[font=\\tiny,text=muted,anchor=north] at ({cx:.3f},-0.05) {{{yr}}};')
        out.append(f'\\node[font=\\scriptsize\\bfseries,anchor=north] at ({x + bw + 0.25:.3f},-0.35) {{{NAMES[k]}}};')
    out.append('\\draw[ink] (-0.2,0) -- (10.3,0);')
    write('area_bars', out)


def gain_loss():
    sx, rowh = 0.06, 0.95
    out = []
    for i in range(3):
        gain = sum(flow[a][i] for a in range(4) if a != i)
        loss = sum(flow[i][b] for b in range(4) if b != i)
        net, swap = gain - loss, 2 * min(gain, loss)
        y = -i * rowh
        out.append(f'\\fill[{COL[i]},fill opacity=.4] ({-loss * sx:.3f},{y - 0.28:.3f}) rectangle (0,{y + 0.28:.3f});')
        out.append(f'\\fill[{COL[i]}] (0,{y - 0.28:.3f}) rectangle ({gain * sx:.3f},{y + 0.28:.3f});')
        out.append(f'\\node[font=\\scriptsize,anchor=east] at ({-loss * sx - 0.08:.3f},{y:.3f}) {{$-${loss:.1f}}};')
        out.append(f'\\node[font=\\scriptsize,anchor=west] at ({gain * sx + 0.08:.3f},{y:.3f}) {{+{gain:.1f}}};')
        out.append(f'\\node[font=\\scriptsize\\bfseries,anchor=east] at (-4.3,{y:.3f}) {{{NAMES[i]}}};')
        out.append(f'\\node[font=\\scriptsize,anchor=west,text=terra] at (4.0,{y:.3f}) {{net {net:+.1f}}};')
        out.append(f'\\node[font=\\scriptsize,anchor=west,text=green] at (5.3,{y:.3f}) {{swap {swap:.1f}}};')
    out.append(f'\\draw[ink,line width=.8pt] (0,0.5) -- (0,{-2 * rowh - 0.5:.3f});')
    out.append('\\node[font=\\tiny,text=muted] at (-2,0.62) {loss (ha)}; \\node[font=\\tiny,text=muted] at (2,0.62) {gain (ha)};')
    write('gain_loss', out)


def importance():
    label = lambda k: (k[1:] + ' pre-mon.' if k.startswith('d') else k).replace('_sd', ' texture').replace('_drop', ' drop')
    group = lambda k: 'terra' if k.startswith('d') or k == 'NDVI_drop' else ('green' if k.endswith('_sd') else 'muted')
    top = sorted(R['importance'].items(), key=lambda kv: -kv[1])[:10]
    sx, rh = 0.026, 0.36
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
            tone = 'green' if i == j else 'terra'
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


def dumbbell():
    sx, rh, out = 6.0, 0.42, []
    for t in [0, 0.25, 0.5, 0.75, 1.0]:
        out.append(f'\\draw[rule] ({t * sx},0.3) -- ({t * sx},{-5 * rh - 0.25:.3f}); \\node[font=\\tiny,text=muted] at ({t * sx},0.45) {{{t:.2f}}};')
    row = 0
    for k in range(3):
        for kind, key in [("user's", 'users'), ("producer's", 'producers')]:
            a = R['2020']['independent_area_weighted'][key][k]
            b = R['2025']['independent_area_weighted'][key][k]
            y = -row * rh
            out.append(f'\\node[anchor=east,font=\\scriptsize] at (-0.1,{y:.3f}) {{{NAMES[k]}, {kind}}};')
            out.append(f'\\draw[{COL[k]},line width=2.2pt] ({a * sx:.3f},{y:.3f}) -- ({b * sx:.3f},{y:.3f});')
            out.append(f'\\fill[white,draw=ink,line width=.7pt] ({a * sx:.3f},{y:.3f}) circle (2.6pt);')
            out.append(f'\\fill[ink] ({b * sx:.3f},{y:.3f}) circle (2.6pt);')
            row += 1
    write('dumbbell', out)


def timeline():
    W, out = 11.0, []
    days = lambda d, y0: (d - date(y0, 11, 1)).days
    span = days(date(2020, 5, 31), 2019)
    sx = W / span
    xm = days(date(2020, 3, 1), 2019) * sx
    out.append(f'\\fill[mint] (0,-0.25) rectangle ({xm:.3f},1.45); \\fill[terra!12!bg] ({xm:.3f},-0.25) rectangle ({W},1.45);')
    out.append(f'\\node[font=\\tiny\\bfseries,text=green,anchor=north west] at (0.05,1.45) {{WINTER, Nov-Feb}};')
    out.append(f'\\node[font=\\tiny\\bfseries,text=terra,anchor=north west] at ({xm + 0.05:.3f},1.45) {{PRE-MONSOON, Mar-May}};')
    for i, (yr, y0) in enumerate([('2020', 2019), ('2025', 2024)]):
        y = 0.75 - i * 0.6
        out.append(f'\\node[anchor=east,font=\\scriptsize\\bfseries] at (-0.1,{y}) {{{y0}-{str(y0 + 1)[2:]}}};')
        out.append(f'\\draw[rule] (0,{y}) -- ({W},{y});')
        for key, col in [('scenes', 'green'), ('scenes_dry', 'terra')]:
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
dumbbell()
timeline()


def significance():
    """Net change 2020->2025 per class, error-adjusted, 95% CI from the two independent point samples."""
    a, b = R['2020']['independent_area_weighted'], R['2025']['independent_area_weighted']
    m20 = {d['class']: d['sum'] for d in R['2020']['area_ha']}
    m25 = {d['class']: d['sum'] for d in R['2025']['area_ha']}
    names = ['Built-up', 'Vegetation', 'Open land', 'Water']
    sx = .024
    out = []
    for t in (-100, -50, 0, 50, 100, 150):
        out.append(f'\\draw[{"ink,thick" if t == 0 else "rule"}] ({t * sx:.2f},.3) -- ({t * sx:.2f},-2.2);')
        out.append(f'\\node[font=\\tiny,text=muted] at ({t * sx:.2f},-2.42) {{{t:+d}}};'.replace('+0', '0'))
    for i in range(4):
        y = -.62 * i
        h1 = (a['adjusted_area_95ci_ha'][i][1] - a['adjusted_area_95ci_ha'][i][0]) / 2
        h2 = (b['adjusted_area_95ci_ha'][i][1] - b['adjusted_area_95ci_ha'][i][0]) / 2
        d = b['adjusted_area_ha'][i] - a['adjusted_area_ha'][i]
        h = (h1 ** 2 + h2 ** 2) ** .5
        real = d - h > 0 or d + h < 0
        mapd = m25[i] - m20[i]
        out.append(f'\\node[anchor=east,font=\\scriptsize\\bfseries] at (-3.15,{y}) {{{names[i]}}};')
        out.append(f'\\draw[line width=2.2pt,{COL[i]}!{90 if real else 45}] ({(d - h) * sx:.2f},{y}) -- ({(d + h) * sx:.2f},{y});')
        out.append(f'\\fill[ink] ({d * sx:.2f},{y}) circle (2.6pt);')
        out.append(f'\\draw[ink,fill=white] ({mapd * sx:.2f},{y + .22}) +(0,.09) -- +(.09,0) -- +(0,-.09) -- +(-.09,0) -- cycle;')
        verdict = 'REAL CHANGE' if real else 'within error'
        out.append(f'\\node[anchor=west,font=\\tiny,text={"terra" if real else "muted"}] at (4.3,{y}) {{{d:+.0f} $\\pm$ {h:.0f} ha \\; {verdict}}};')
    out.append(f'\\node[font=\\tiny,text=muted] at (0,-2.75) {{net change 2020 $\\rightarrow$ 2025 (ha)}};')
    return out


write('significance', significance())
