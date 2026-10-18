# Build per-shard model yamls for the multi-model stack study (2026-10-15).
import os
import copy, sys, yaml
H = os.environ['HARNESS_A']
import subprocess
def model_base(m):  # committed models/<m>.yaml of the patched harness (launch*.sh overwrites the working copy)
    return yaml.safe_load(subprocess.check_output(['git', '-C', H, 'show', f'HEAD:models/{m}.yaml']))
TRIALS = 5
OFFICIAL_REPLAN = {'openvla-oft': 8, 'pi': 5}
def conds(model):
    r = OFFICIAL_REPLAN[model]
    return {'S0': {}, 'S2a': {'step_scale': 0.75}, 'S2b': {'step_scale': 1.5},
            'S3a': {'replan': max(1, r // 2)}, 'S3b': {'replan': 1}, 'S4': {'random_init': True},
            # S3c/S3d = same replan as S3a/S3b but executing the chunk HEAD (OFT upstream executes the tail)
            'S3c': {'replan': max(1, r // 2), 'replan_head': True}, 'S3d': {'replan': 1, 'replan_head': True},
            'S1': {}}
def oft(suite, names, tag, mujoco=None):
    y = model_base('openvla-oft')
    if mujoco: y['model']['sim_protect_pins'] = f'mujoco=={mujoco}'
    key = suite.replace('libero_', '')
    base = y['tasks'][key][0]
    y['tasks'][key] = [dict(base, num_trials_per_task=TRIALS, condition=c,
                            description=f'{suite} {c}', **conds('openvla-oft')[c]) for c in names]
    y['instance']['creationpolicy_timeout'] = {k: 'PT700M' for k in ['spatial', 'object', 'goal', '10']}
    yaml.safe_dump(y, open(f'oft-{tag}.yaml', 'w'), sort_keys=False)
def pi(suite, names, tag, mujoco=None):
    y = model_base('pi')
    if mujoco: y['model']['mujoco_pin'] = f'mujoco=={mujoco}'
    y['tasks'] = [dict(suite=suite, num_episodes=TRIALS, condition=c, description=f'{suite} {c}',
                       **conds('pi')[c]) for c in names]
    y['instance']['creationpolicy_timeout'] = 'PT700M'
    yaml.safe_dump(y, open(f'pi-{tag}.yaml', 'w'), sort_keys=False)
ALL = ['S0', 'S2a', 'S2b', 'S3a', 'S3b', 'S4']
for s in ['libero_spatial', 'libero_object', 'libero_goal']:
    oft(s, ALL, s); pi(s, ALL, s)
oft('libero_10', ['S0', 'S2a', 'S3a'], 'libero_10-A'); oft('libero_10', ['S2b', 'S3b', 'S4'], 'libero_10-B')
pi('libero_10', ['S0', 'S2a', 'S3a'], 'libero_10-A'); pi('libero_10', ['S2b', 'S3b', 'S4'], 'libero_10-B')
print('ok')

# ---- GR00T N1.7 (official LIBERO protocol: random reset, 720-step cap, n_action_steps 8)
def gr00t(suite, names, tag, tasks):
    y = model_base('gr00t')
    y['model']['hf_subfolder'] = suite
    y['instance']['creationpolicy_timeout'] = 'PT700M'
    y['instance']['preferred'] = ['g6.2xlarge', 'g5.2xlarge', 'g6e.xlarge', 'g6.12xlarge']  # xlarge 16GB OOM
    C = {'S0': {}, 'S2a': {'max_episode_steps': 540}, 'S2b': {'max_episode_steps': 1080},
         'S3a': {'replan': 4}, 'S3b': {'replan': 1}}
    out = []
    for c in names:
        for t in tasks:
            d = dict(env_name=f'libero_sim/{t}', embodiment='LIBERO_PANDA', n_episodes=TRIALS, n_envs=1,
                     max_episode_steps=720, video_fps=30, video_crf=18, steps_per_render=1, condition=c)
            d.update(C[c]); out.append(d)
    y['tasks'] = out
    yaml.safe_dump(y, open(f'gr00t-{tag}.yaml', 'w'), sort_keys=False)
import json
TM = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'libero_task_map.json')))
for s in ['libero_spatial', 'libero_object', 'libero_goal', 'libero_10']:
    gr00t(s, ['S0', 'S2a', 'S2b', 'S3a', 'S3b'], s, TM[s])
print('gr00t ok')

# ---- wave 2 (07:50Z): OFT replan-head (S3c/S3d) + OFT S1 (MuJoCo 3.2.3 = pi's official pin)
for s_ in ['libero_spatial', 'libero_object', 'libero_goal', 'libero_10']:
    oft(s_, ['S3c', 'S3d'], s_ + '-H')
    oft(s_, ['S1'], s_ + '-M', mujoco='3.2.3')
    pi(s_, ['S1'], s_ + '-M', mujoco='3.3.1')  # pi official pin 3.2.3 -> OFT's 3.3.1
print('wave2 ok')

# ---- wave 3 (08:45Z): pi combined shards (tasks may mix suites) + rerun of GPU-less conditions
def pi_multi(cells, tag, mujoco=None):
    y = model_base('pi')
    if mujoco: y['model']['mujoco_pin'] = f'mujoco=={mujoco}'
    y['tasks'] = [dict(suite=s_, num_episodes=TRIALS, condition=c, description=f'{s_} {c}', **conds('pi')[c]) for s_, c in cells]
    y['instance']['creationpolicy_timeout'] = 'PT700M'
    yaml.safe_dump(y, open(f'pi-{tag}.yaml', 'w'), sort_keys=False)
pi_multi([('libero_goal', 'S2a'), ('libero_goal', 'S2b'), ('libero_10', 'S0'), ('libero_10', 'S2a')], 'libero_R')
# pi LIBERO runtime is Python 3.8 -> mujoco>=3.2.4 needs py>=3.9 (3.3.1 fails uv resolve). Max for pi = its own 3.2.3; S1 goes DOWN to 3.1.6.
pi_multi([(s_, 'S1') for s_ in ['libero_spatial', 'libero_object', 'libero_goal', 'libero_10']], 'libero_M', mujoco='3.1.6')
print('wave3 ok')

# ---- wave 4 (08:55Z): GR00T S2c = cap 1000 (= robosuite/LIBERO env horizon). S2b=1080 crashes
# ("executing action in terminated episode") on any episode that runs past 1000 steps.
def gr00t_c(suite, tasks):
    y = yaml.safe_load(open(f'gr00t-{suite}.yaml'))
    y['tasks'] = [dict(t, max_episode_steps=1000, condition='S2c') for t in y['tasks'] if t['condition'] == 'S0']
    yaml.safe_dump(y, open(f'gr00t-{suite}-C.yaml', 'w'), sort_keys=False)
for s_ in ['libero_10', 'libero_goal']:
    gr00t_c(s_, TM[s_])
print('wave4 ok')
