# FastWAM (WAM) shard yamls for the AMLC multi-model stack study (2026-10-15). Official: n_action_steps 10 · episode_length 300 (libero_10 600).
import os
import yaml
H = os.environ['HARNESS_B']
import subprocess
def model_base(m):  # committed models/<m>.yaml of the patched harness (launch*.sh overwrites the working copy)
    return yaml.safe_load(subprocess.check_output(['git', '-C', H, 'show', f'HEAD:models/{m}.yaml']))
def conds(suite):
    L = 600 if suite == 'libero_10' else 300
    return {'S0': [], 'S2a': [f'--env.episode_length={int(L*0.75)}'], 'S2b': [f'--env.episode_length={int(L*1.5)}'],
            'S3a': ['--policy.n_action_steps=5'], 'S3b': ['--policy.n_action_steps=1']}
def cfg(suite, names, tag):
    y = model_base('fastwam')
    if suite == 'libero_10':
        y['model']['env_args'] = [a if not a.startswith('--env.episode_length') else '--env.episode_length=600' for a in y['model']['env_args']]
    y['instance']['creationpolicy_timeout'] = 'PT700M'
    y['tasks'] = [dict(suite=suite, n_episodes=5, seed=1000, condition=c, extra_args=conds(suite)[c],
                       description=f'{suite} {c}') for c in names]
    yaml.safe_dump(y, open(f'fastwam-{tag}.yaml', 'w'), sort_keys=False)
for s in ['libero_spatial', 'libero_object', 'libero_goal', 'libero_10']:
    cfg(s, ['S0', 'S2a', 'S2b', 'S3a', 'S3b'], s)
print('ok')
