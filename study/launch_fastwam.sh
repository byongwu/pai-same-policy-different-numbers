#!/usr/bin/env bash
# FastWAM study launcher (2026-10-15) — vla-sim main copy (out/wam/vlasim-main). One shard = one region (stack FastWAM-Demo).
set -uo pipefail
H=${HARNESS_B:?set HARNESS_B to the patched vla-simulator checkout for FastWAM/LingBot-VA (harness/setup.sh)}
S=$(cd "$(dirname "$0")" && pwd)
EMAIL=${NOTIFY_EMAIL:?set NOTIFY_EMAIL (SNS completion mail)}
mkdir -p $S/logs; cd $H
for sh in "$@"; do
  IFS=: read tag region stack <<< "$sh"
  cp $S/fastwam-$tag.yaml models/fastwam.yaml
  VLASIM_FASTWAM_STACK_NAME="${stack:-}" VLASIM_CDK_OUT_SUFFIX="study-$tag-$region" setsid nohup python3 deploy.py --vla fastwam --email $EMAIL --region $region > $S/logs/fastwam-$tag-$region.log 2>&1 < /dev/null &
  echo "$(date -u +%FT%TZ) launched fastwam $tag $region pid=$!" | tee -a $S/launches.txt
  for i in $(seq 1 90); do grep -qE "IN_PROGRESS|deploying\.\.\.|Done!|failed|Error|error:" $S/logs/fastwam-$tag-$region.log 2>/dev/null && break; sleep 10; done
  sleep 5
done
