# Analysis of the multi-model stack study (2026-10-15).
# Usage: python3 collect.py --json collect.json && python3 analyze.py
# Writes analysis/heatmap.png (+ .pdf) and analysis/cells.csv. Crashed/not-run cells are hatched, never 0.
import csv, json, math, os, collections
os.environ.setdefault('MPLCONFIGDIR', '/tmp/mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

D = json.load(open('collect.json'))
os.makedirs('analysis', exist_ok=True)
MODELS = [('oft', 'OpenVLA-OFT'), ('pi', 'pi0.5'), ('gr00t', 'GR00T N1.7')]
SUITES = ['libero_spatial', 'libero_object', 'libero_goal', 'libero_10']
CONDS = ['S0', 'S1', 'S2a', 'S2b', 'S2c', 'S3a', 'S3b', 'S3c', 'S3d', 'S4']
CLABEL = {'S0': 'official', 'S1': 'MuJoCo\nswap', 'S2a': 'cap\nx0.75', 'S2b': 'cap\nx1.5', 'S2c': 'cap\n1000',
          'S3a': 'chunk/2\n(script)', 'S3b': 'chunk 1\n(script)', 'S3c': 'chunk/2\n(head)', 'S3d': 'chunk 1\n(head)',
          'S4': 'init\nswap'}

cells = {}
for key, g in D['agg'].items():
    m, s, c = key.split('|')
    cells[(m, s, c)] = g

def wilson(k, n, z=1.96):
    if not n: return (None, None)
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)

with open('analysis/cells.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['model', 'suite', 'cond', 'k', 'n', 'rate', 'ci_lo', 'ci_hi', 'not_done'])
    for m, _ in MODELS:
        for s in SUITES:
            for c in CONDS:
                g = cells.get((m, s, c))
                if not g: continue
                lo, hi = wilson(g['k'], g['n'])
                w.writerow([m, s, c, g['k'], g['n'], f"{g['k']/g['n']:.3f}" if g['n'] else '',
                            f'{lo:.3f}' if lo is not None else '', f'{hi:.3f}' if hi is not None else '', len(g['bad'])])

rows = [(m, ml, s) for m, ml in MODELS for s in SUITES]
fig, ax = plt.subplots(figsize=(11, 6.2))
cmap = plt.get_cmap('RdYlGn')
for i, (m, ml, s) in enumerate(rows):
    for j, c in enumerate(CONDS):
        g = cells.get((m, s, c))
        if not g or not g['n']:
            na = 'n/a' if (m != 'oft' and c in ('S3c', 'S3d')) or (c == 'S2c' and (m != 'gr00t' or s in ('libero_spatial', 'libero_object'))) or (m == 'gr00t' and c in ('S1', 'S4')) else 'pending'
            ax.add_patch(plt.Rectangle((j, i), 1, 1, facecolor='#eeeeee', edgecolor='white', hatch='//' if na == 'pending' else None))
            ax.text(j + .5, i + .5, '' if na == 'n/a' else 'running', ha='center', va='center', fontsize=6, color='#888')
            continue
        r = g['k'] / g['n']
        ax.add_patch(plt.Rectangle((j, i), 1, 1, facecolor=cmap(r), edgecolor='white'))
        txt = f"{g['k']}/{g['n']}"
        if g['bad']: txt += f"\n+{len(g['bad'])} crash"
        ax.text(j + .5, i + .5, txt, ha='center', va='center', fontsize=7, color='black' if 0.25 < r < 0.85 else ('white' if r <= .25 else 'black'))
ax.set_xlim(0, len(CONDS)); ax.set_ylim(len(rows), 0)
ax.set_xticks([j + .5 for j in range(len(CONDS))]); ax.set_xticklabels([CLABEL[c] for c in CONDS], fontsize=7)
ax.set_yticks([i + .5 for i in range(len(rows))])
ax.set_yticklabels([f"{ml}  {s.replace('libero_', '')}" for _, ml, s in rows], fontsize=8)
for k in (4, 8): ax.axhline(k, color='black', lw=1.2)
ax.set_title('Success k/n per stack condition (n = 10 tasks x 5 episodes; grey = not applicable, hatched = still running)', fontsize=9)
plt.tight_layout()
plt.savefig('analysis/heatmap.png', dpi=200); plt.savefig('analysis/heatmap.pdf')
print('wrote analysis/heatmap.png, analysis/cells.csv')
