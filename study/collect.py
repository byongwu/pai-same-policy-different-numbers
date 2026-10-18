# Collect multi-model stack study results from S3 (2026-10-15).
# Usage: python3 collect.py [--since 2026-10-15-0630] [--json out.json]
# Reads vla-sim-results-<stack>-<region>-<acct>/<RUN>/task-N/ for every study bucket,
# reads every run with RUN id >= --since; per (model,suite,cond[,task]) keeps the latest finished cell, and prints model x suite x condition = k/n.
import os
import argparse, json, re, sys, collections
import boto3

ACCT = boto3.client('sts').get_caller_identity()['Account']
def discover():
    # every study bucket in the account: OFT suite stacks, pi, gr00t (all regions)
    out = {'oft': [], 'pi': [], 'gr00t': [], 'cosmos': [], 'fastwam': [], 'lingbot': [], 'dreamzero': []}
    for b in boto3.client('s3').list_buckets()['Buckets']:
        m = re.match(r'vla-sim-results-(openvla-oft(?:-spatial|-object|-goal)?-demo|oft-spatial-[hm]|pi-demo|gr00t-demo|cosmos-demo|cosmos-w(?:-[lsog])?|fastwam-[lsog]|lingbot-t\d|dreamzero-(?:[sogl]|s2a))-([a-z]+-[a-z]+-\d)-' + ACCT + '$', b['Name'])
        if m:
            out['oft' if 'oft' in m.group(1) else m.group(1).split('-')[0]].append((m.group(1), m.group(2)))
    return out
BUCKETS = discover()
ap = argparse.ArgumentParser()
ap.add_argument('--since', default='2026-10-15-0530')

ap.add_argument('--json')
a = ap.parse_args()
s3 = boto3.client('s3')

def ls(b, prefix, delim=None):
    kw = dict(Bucket=b, Prefix=prefix)
    if delim: kw['Delimiter'] = delim
    out, cps = [], []
    for page in s3.get_paginator('list_objects_v2').paginate(**kw):
        out += page.get('Contents', []); cps += [c['Prefix'] for c in page.get('CommonPrefixes', [])]
    return out, cps

def get(b, k):
    try: return s3.get_object(Bucket=b, Key=k)['Body'].read().decode('utf-8', 'replace')
    except Exception: return None

rows = []  # dict(model, suite, cond, k, n, src, status)

def dreamzero_rows(part, region):
    # RLinf eval (out/wam/dz/dz-run.sh): <run>/out/summary-<suite>-<cond>.txt + <run>/out/<suite>-<cond>.log
    b = f'vla-sim-results-{part}-{region}-{ACCT}'
    _, runs = ls(b, '', '/')
    for run in sorted(r.rstrip('/') for r in runs if r[:4].isdigit()):
        objs, _ = ls(b, run + '/out/')
        for o in objs:
            mm = re.search(r'/summary-(\w+)-(S\w+)\.txt$', o['Key'])
            if not mm: continue
            kv = dict(re.findall(r'^(\w+): ?(.*)$', get(b, o['Key']) or '', re.M))
            rate = re.search(r'([\d.]+)$', kv.get('metric', ''))
            n = int(kv['num_trajectories']) if kv.get('num_trajectories', '').isdigit() else None
            if n is None:
                log = get(b, f"{run}/out/{mm.group(1)}-{mm.group(2)}.log") or ''
                t = re.findall(r"eval/num_trajectories.: ?(\d+)", log); n = int(t[-1]) if t else None
            k = round(float(rate.group(1)) * n) if (rate and n) else None
            rows.append(dict(model='dreamzero', suite=kv.get('suite', '?'), cond=mm.group(2), k=k, n=n, src=f'{b}/{run}',
                             status='done' if n else 'failed'))
for model, lst in BUCKETS.items():
    for part, region in lst:
        if model == 'dreamzero':
            dreamzero_rows(part, region); continue
        b = f'vla-sim-results-{part}-{region}-{ACCT}'
        try: _, runs = ls(b, '', '/')
        except Exception as e: print(f'# skip {b}: {e.__class__.__name__}', file=sys.stderr); continue
        runs = [r.rstrip('/') for r in sorted(runs) if r.rstrip('/') >= a.since]
        for run in runs:
            _, tasks = ls(b, run + '/', '/')
            for t in sorted(tasks, key=lambda x: int(re.search(r'task-(\d+)', x).group(1)) if re.search(r'task-(\d+)', x) else 0):
                summ = get(b, t + 'summary.txt')
                if summ is None:
                    rows.append(dict(model=model, suite='?', cond='?', k=None, n=None, src=f'{b}/{t}', status='running')); continue
                kv = dict(re.findall(r'^(\w+): ?(.*)$', summ, re.M))
                if model == 'gr00t':
                    env = kv.get('env_name', '')
                    cond = re.search(r'condition: (\S+)', summ); cond = cond.group(1) if cond else '?'
                    k, n = int(kv.get('n_success', 0)), int(kv.get('n_episodes', 0))
                    rows.append(dict(model=model, suite=f'{part}@{region}', task=env, cond=cond, k=k, n=n, src=f'{b}/{t}',
                                     status='done' if kv.get('success_rate', 'unknown') != 'unknown' else 'crashed'))
                    continue
                if model in ('fastwam', 'cosmos', 'lingbot'):
                    suite, cond = kv.get('suite', '?'), kv.get('condition', '?')
                    k = int(kv['n_success']) if kv.get('n_success', '').isdigit() else None
                    n = int(kv['n_episodes']) if kv.get('n_episodes', '').isdigit() else None
                    rows.append(dict(model=model, suite=suite, cond=cond, k=k, n=n, src=f'{b}/{t}', status='done' if n else 'failed',
                                     **({'task': part} if model == 'lingbot' else {})))  # lingbot: one shard per libero_10 task
                    continue
                desc = kv.get('description', '? ?').split()
                suite, cond = (desc + ['?', '?'])[:2]
                k = n = None
                if model == 'pi':
                    log = get(b, t + 'compose.log') or ''
                    m = re.findall(r'Total success rate: ([\d.]+)', log); e = re.findall(r'Total episodes: (\d+)', log)
                    if m and e: n = int(e[-1]); k = round(float(m[-1]) * n)
                else:
                    objs, _ = ls(b, t + 'videos/')
                    succ = [o for o in objs if 'success=True' in o['Key']]; fail = [o for o in objs if 'success=False' in o['Key']]
                    # videos/ holds .mp4 and .txt per episode; count one extension
                    ext = '.mp4' if any(o['Key'].endswith('.mp4') for o in objs) else '.txt'
                    k = sum(o['Key'].endswith(ext) for o in succ); n = k + sum(o['Key'].endswith(ext) for o in fail)
                rows.append(dict(model=model, suite=suite, cond=cond, k=k, n=n, src=f'{b}/{t}',
                                 status='done' if n else 'failed'))

# gr00t: map bucket->suite via the env names and aggregate tasks per (suite, cond)
TM = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'libero_task_map.json')))
inv = {f'libero_sim/{t}': s for s, ts in TM.items() for t in ts}
for r in rows:
    if r['model'] == 'gr00t' and r.get('task'):
        r['suite'] = inv.get(r['task'], '?')
# dedupe: later runs (src sorted by RUN id) supersede earlier ones; a finished cell beats a failed one
best = collections.OrderedDict()
def runid(r): return r['src'].split('/')[1] if '/' in r['src'] else ''
for r in sorted(rows, key=runid):
    key = (r['model'], r['suite'], r['cond'], r.get('task'))
    if r['status'] == 'done' or key not in best or best[key]['status'] != 'done':
        best[key] = r
rows = list(best.values())
agg = collections.OrderedDict()
for r in rows:
    key = (r['model'], r['suite'], r['cond'])
    g = agg.setdefault(key, dict(k=0, n=0, cells=0, bad=[]))
    if r['status'] == 'done' and r['n']:
        g['k'] += r['k']; g['n'] += r['n']; g['cells'] += 1
    else:
        g['bad'].append(f"{r['status']}:{r['src']}")

print(f"{'model':6} {'suite':15} {'cond':5} {'k/n':>8} {'rate':>6}  notes")
for (m, s, c), g in sorted(agg.items()):
    rate = f"{g['k']/g['n']:.2f}" if g['n'] else '-'
    note = (f"{len(g['bad'])} not-done" if g['bad'] else '') + (f" ({g['cells']} gr00t tasks)" if m == 'gr00t' else '')
    print(f"{m:6} {s:15} {c:5} {g['k']:>3}/{g['n']:<4} {rate:>6}  {note}")
for (m, s, c), g in agg.items():
    for x in g['bad']: print(f'# {m} {s} {c} {x}', file=sys.stderr)
if a.json:
    json.dump(dict(rows=rows, agg={'|'.join(k): v for k, v in agg.items()}), open(a.json, 'w'), indent=1)
