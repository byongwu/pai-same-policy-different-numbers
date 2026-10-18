#!/usr/bin/env bash
# Multi-model stack study launcher (2026-10-15). One shard = one stack; yaml copy is serialized (synth reads it).
set -uo pipefail
H=${HARNESS_A:?set HARNESS_A to the patched vla-simulator checkout (harness/setup.sh)}
S=$(cd "$(dirname "$0")" && pwd)
EMAIL=${NOTIFY_EMAIL:?set NOTIFY_EMAIL (SNS completion mail)}
mkdir -p $S/logs; cd $H
SHARDS="${*:-oft:libero_spatial:us-west-2 pi:libero_spatial:us-east-1 oft:libero_object:us-west-2 pi:libero_object:eu-central-1 oft:libero_goal:us-west-2 pi:libero_goal:ap-northeast-1 oft:libero_10-A:us-west-2 pi:libero_10-A:ap-northeast-2 oft:libero_10-B:us-east-1 pi:libero_10-B:us-west-2}"
for sh in $SHARDS; do
  IFS=: read m tag region <<< "$sh"
  suite=${tag%-*}; suite=${suite#libero_}
  if [ $m = oft ]; then
    cp $S/oft-$tag.yaml models/openvla-oft.yaml
    VLASIM_OFT_STACK_NAME="${OFT_STACK:-}" VLASIM_CDK_OUT_SUFFIX="study-$tag-$region" setsid nohup python3 deploy.py --vla openvla-oft --libero-suite $suite --num-trials 5 --email $EMAIL --region $region > $S/logs/oft-$tag-$region.log 2>&1 < /dev/null &
  elif [ $m = cosmos ]; then
    cp $S/cosmos-$tag.yaml models/cosmos.yaml
    VLASIM_COSMOS_STACK_NAME="${COSMOS_STACK:-}" VLASIM_CDK_OUT_SUFFIX="study-$tag-$region" setsid nohup python3 deploy.py --vla cosmos --email $EMAIL --region $region > $S/logs/cosmos-$tag-$region.log 2>&1 < /dev/null &
  elif [ $m = gr00t ]; then
    cp $S/gr00t-$tag.yaml models/gr00t.yaml
    VLASIM_CDK_OUT_SUFFIX="study-$tag-$region" setsid nohup python3 deploy.py --vla gr00t --email $EMAIL --region $region > $S/logs/gr00t-$tag-$region.log 2>&1 < /dev/null &
  else
    cp $S/pi-$tag.yaml models/pi.yaml
    VLASIM_CDK_OUT_SUFFIX="study-$tag-$region" setsid nohup python3 deploy.py --vla pi --email $EMAIL --region $region > $S/logs/pi-$tag-$region.log 2>&1 < /dev/null &
  fi
  echo "$(date -u +%FT%TZ) launched $m $tag $region pid=$!" | tee -a $S/launches.txt
  # wait until this shard is past synth (it reads models/*.yaml) before the next copy — 75s was a race (2026-10-15 gr00t shards read the next yaml)
  for i in $(seq 1 90); do
    grep -qE "IN_PROGRESS|Done!|failed|Error|error:" $S/logs/$m-$tag-$region.log 2>/dev/null && break; sleep 10
  done
  sleep 5
done
