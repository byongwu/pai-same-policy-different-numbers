#!/bin/bash
# AMLC study 2026-10-15: DreamZero (RLinf 5B LIBERO SFT) on LIBERO via the RLinf HF/PyTorch eval path.
# Args: <bucket> <run_id> "<suite:cond:max_episode_steps:k> ...". k = actions executed per 16-step chunk (16 = official).
set -uo pipefail
B=$1; RUN=$2; CONDS=$3
RLINF_COMMIT=7e90641c4135229db6d3426950cdb45cee6259a6
CKPT=RLinf/RLinf-DreamZero-WAN2.2-5B-LIBERO-SFT-Step26000; CKPT_REV=7416908d4e12c7a9fb3b7eb4fde7408fd2559e3c
E=${DZ_ENVS:-8}  # one L40S: envs 32 and 16 both OOMed (rollout 26->35 GiB + EGL env contexts), smoke2/4 2026-10-15
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export HOME=/root
mkdir -p /data/out; LOG=/data/out/dz.log
exec > >(tee -a $LOG) 2>&1
log(){ echo "[DZ] $(date -u +%T) $*"; }
up(){ aws s3 cp $LOG s3://$B/$RUN/dz.log --quiet; aws s3 cp /data/out s3://$B/$RUN/out --recursive --exclude '*.mp4' --quiet; aws s3 sync /data/results s3://$B/$RUN/results --exclude '*.mp4' --quiet 2>/dev/null; }
( while true; do sleep 180; up; done ) &
finish(){ log "finish rc=$1"; up; aws s3 sync /data/videos s3://$B/$RUN/videos --quiet 2>/dev/null; sleep 5; shutdown -h now; }
trap 'finish $?' EXIT
log "start run=$RUN conds=[$CONDS] envs=$E instance=$(curl -s -H "X-aws-ec2-metadata-token: $(curl -s -X PUT http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 300')" http://169.254.169.254/latest/meta-data/instance-type)"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
rm -f /etc/apt/apt.conf.d/50command-not-found
export DEBIAN_FRONTEND=noninteractive
for i in 1 2 3; do timeout 600 apt-get update -qq && break; sleep 20; done
timeout 1800 apt-get install -y -qq git git-lfs libegl1 libgl1 libglib2.0-0 libosmesa6 ffmpeg build-essential cmake python3-pip >/dev/null || log "apt install warn"
curl -LsSf https://astral.sh/uv/install.sh | sh; export PATH=/root/.local/bin:$PATH
log "[1/4] RLinf @$RLINF_COMMIT"
cd /opt && git clone -q https://github.com/RLinf/RLinf.git && cd RLinf && git checkout -q $RLINF_COMMIT || exit 11
export UV_HTTP_RETRIES=10   # smoke3 died on a transient DNS failure mid-install
ok=0; for i in 1 2 3; do bash requirements/install.sh embodied --model dreamzero --env libero > /data/out/install.log 2>&1 && { ok=1; break; }; log "install attempt $i failed"; tail -5 /data/out/install.log; sleep 30; done
[ $ok = 1 ] || { tail -40 /data/out/install.log; exit 12; }
source .venv/bin/activate
export DREAMZERO_PATH=/opt/RLinf/.venv/dreamzero
[ -d $DREAMZERO_PATH ] || export DREAMZERO_PATH=$(dirname $(python -c "import groot,os;print(os.path.dirname(groot.__file__))" 2>/dev/null))
log "DREAMZERO_PATH=$DREAMZERO_PATH ($(git -C $DREAMZERO_PATH rev-parse --short HEAD 2>/dev/null))"
# exec-length patch: DZ_EXEC_K>0 keeps only the first k actions of each 16-step chunk (unset = official, full chunk)
python - <<'PY' || exit 13
p='rlinf/models/embodiment/dreamzero/dreamzero_policy.py'; s=open(p).read()
old='''        flat = (
            torch.as_tensor(actions, dtype=torch.float32)'''
new='''        import os as _os
        _k = int(_os.environ.get("DZ_EXEC_K", "0"))
        if _k > 0:
            actions = actions[:, :_k]
        flat = (
            torch.as_tensor(actions, dtype=torch.float32)'''
assert s.count(old) == 1, 'patch anchor'
open(p, 'w').write(s.replace(old, new)); print('patched exec-k')
PY
log "[2/4] checkpoint $CKPT@$CKPT_REV"
# use the venv's pinned huggingface_hub (0.36.x) — upgrading it breaks transformers 4.57 (smoke 1 failed that way)
for i in 1 2 3; do python -c "from huggingface_hub import snapshot_download as d; d('$CKPT', revision='$CKPT_REV', local_dir='/data/dz5b')" > /data/out/dl.log 2>&1 && break; sleep 30; done
[ -f /data/dz5b/model.safetensors.index.json ] || { tail -20 /data/out/dl.log; exit 14; }
python -c "from transformers import AutoTokenizer; AutoTokenizer.from_pretrained('google/umt5-xxl')" > /data/out/tok.log 2>&1 || { tail /data/out/tok.log; exit 15; }
log "[3/4] eval"
cd /opt/RLinf
for c in $CONDS; do
  IFS=: read suite cond T k neps envs <<< "$c"; neps=${neps:-500}; envs=${envs:-$E}
  # eval reset pool is interleaved (task0 trial0, task1 trial0, ...), so the first 50 = 10 tasks x 5 trials
  name=libero_${suite}_dreamzero_eval
  if [ "$suite" != spatial ]; then
    sed -e "s#env/libero_spatial@env.eval#env/libero_${suite}@env.eval#" -e "s#libero_spatial_eval_dreamzero#libero_${suite}_eval_dreamzero#" evaluations/libero/libero_spatial_dreamzero_eval.yaml > evaluations/libero/$name.yaml
  fi
  NEP=$(( (neps + envs - 1) / envs )); STEPS=$(( NEP * T ))
  ARGS=( rollout.model.model_path=/data/dz5b rollout.model.metadata_json_path=/data/dz5b/experiment_cfg/metadata.json runner.ckpt_path=null
         env.eval.total_num_envs=$envs env.eval.max_episode_steps=$T env.eval.max_steps_per_rollout_epoch=$STEPS
         runner.logger.log_path=/data/results/$suite-$cond env.eval.video_cfg.video_base_dir=/data/videos/$suite-$cond )
  if [ "$k" != 16 ]; then export DZ_EXEC_K=$k; ARGS+=( rollout.model.num_action_chunks=$k ); else unset DZ_EXEC_K; fi
  log "cond $suite $cond T=$T k=$k envs=$envs episodes=$neps steps=$STEPS"
  t0=$(date +%s)
  timeout 21600 bash evaluations/run_eval.sh libero $name "${ARGS[@]}" > /data/out/$suite-$cond.log 2>&1; rc=$?
  dt=$(( $(date +%s) - t0 ))
  m=$(grep -oiE "success_once[^0-9]{0,40}[0-9.]+" /data/out/$suite-$cond.log | tail -1)
  ntraj=$(grep -oE "eval/num_trajectories.: ?[0-9]+" /data/out/$suite-$cond.log | tail -1 | grep -oE "[0-9]+$")
  log "done $suite $cond rc=$rc ${dt}s :: ${m:-NO_METRIC}"
  [ -z "$m" ] && tail -30 /data/out/$suite-$cond.log
  printf 'model: dreamzero\ncheckpoint: %s@%s\ncode: RLinf@%s\nsuite: libero_%s\ncondition: %s\nmax_episode_steps: %s\nexec_k: %s\nenvs: %s\nepisodes: %s\nmetric: %s\nnum_trajectories: %s\nrc: %s\nseconds: %s\n' $CKPT ${CKPT_REV:0:8} ${RLINF_COMMIT:0:8} $suite $cond $T $k $envs $neps "${m:-none}" "${ntraj:-none}" $rc $dt > /data/out/summary-$suite-$cond.txt
  up
done
log "[4/4] all done"
