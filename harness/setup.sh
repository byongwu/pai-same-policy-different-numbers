#!/usr/bin/env bash
# Build the two patched harness checkouts used in the study.
#   A = OpenVLA-OFT, pi0.5, GR00T N1.7, Cosmos Policy  (upstream @07876f0 + patches/A-vla-stack-knobs.patch)
#   B = FastWAM, LingBot-VA                             (upstream @489335a + patches/B-wam-stack-knobs.patch)
# DreamZero does not use the harness (see ../dreamzero).
# Usage: bash harness/setup.sh [<work dir>]   then export the two paths it prints.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
W=${1:-$PWD/work}
UP=https://github.com/aws-samples/sample-vla-simulator-on-aws.git
mkdir -p "$W"
build() {  # <dir> <commit> <patch>
  rm -rf "$W/$1"; git clone -q "$UP" "$W/$1"
  git -C "$W/$1" checkout -q -b study "$2"
  git -C "$W/$1" -c user.name=study -c user.email=study@example.com am -q "$HERE/patches/$3"
}
build vla-simulator-A 07876f0 A-vla-stack-knobs.patch
build vla-simulator-B 489335a B-wam-stack-knobs.patch
for d in A B; do (cd "$W/vla-simulator-$d" && pip install -q -r requirements.txt && (cd cdk && npm ci --silent)); done
echo "export HARNESS_A=$W/vla-simulator-A"
echo "export HARNESS_B=$W/vla-simulator-B"
