# Cosmos Policy (WAM) shard yamls for the multi-model stack study (2026-10-15).
# usage: python3 mkcfg_cosmos.py  -> cosmos-<tag>.yaml ; official replan = chunk = 16
import os
import sys, yaml
H = os.environ['HARNESS_A']
import subprocess
def model_base(m):  # committed models/<m>.yaml of the patched harness (launch*.sh overwrites the working copy)
    return yaml.safe_load(subprocess.check_output(['git', '-C', H, 'show', f'HEAD:models/{m}.yaml']))
TRIALS = 5
R = 16
C = {'S0': {}, 'S2a': {'step_scale': 0.75}, 'S2b': {'step_scale': 1.5},
     'S3a': {'replan': R // 2}, 'S3b': {'replan': 1}, 'S4': {'random_init': True},
     'S3c': {'replan': R // 2, 'replan_head': True}, 'S3d': {'replan': 1, 'replan_head': True}}
def cfg(cells, tag, tok='official', trials=TRIALS):
    y = model_base('cosmos')
    y['model']['tokenizer_source'] = tok
    y['tasks'] = [dict(suite=s, num_trials_per_task=trials, condition=c, description=f'{s} {c}', **C[c]) for s, c in cells]
    yaml.safe_dump(y, open(f'cosmos-{tag}.yaml', 'w'), sort_keys=False)
cfg([('libero_spatial', 'S0')], 'smoke', tok='wan_public', trials=1)
for tok in ['official', 'wan_public']:
    t = '' if tok == 'official' else '-W'
    for s in ['libero_spatial', 'libero_object', 'libero_goal', 'libero_10']:
        cfg([(s, c) for c in ['S0', 'S2a', 'S2b', 'S3c', 'S3d']], s + t, tok=tok)
print('ok')
