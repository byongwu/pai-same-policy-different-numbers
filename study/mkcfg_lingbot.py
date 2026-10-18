# LingBot-VA (WAM) shard yamls for the AMLC multi-model stack study (2026-10-15). One shard = one libero_10 task.
# Official eval: libero_10 · episode_length None -> LeRobot suite max 520. S3 (head execution) N/A: n_action_steps is
# derived (frame_chunk_size x action_per_frame) and executed actions are fed back into the KV cache.
import os
import yaml
H = os.environ['HARNESS_B']
import subprocess
def model_base(m):  # committed models/<m>.yaml of the patched harness (launch*.sh overwrites the working copy)
    return yaml.safe_load(subprocess.check_output(['git', '-C', H, 'show', f'HEAD:models/{m}.yaml']))
L = 520
CONDS = {'S0': [], 'S2a': [f'--env.episode_length={int(L*0.75)}'], 'S2b': [f'--env.episode_length={int(L*1.5)}']}
for t in range(10):
    y = model_base('lingbot-va')
    y['instance']['creationpolicy_timeout'] = 'PT700M'
    y['tasks'] = [dict(suite='libero_10', task_ids=[t], n_episodes=5, seed=1000, condition=c, extra_args=a,
                       description=f'libero_10 {c} task{t}') for c, a in CONDS.items()]
    yaml.safe_dump(y, open(f'lingbot-t{t}.yaml', 'w'), sort_keys=False)
print('ok')
