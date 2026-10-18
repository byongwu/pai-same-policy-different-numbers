#!/usr/bin/env bash
# launch_dz.sh <stack-name-lowercase> <region> <subnet> <vpc> "<conds>" [instance-type]
set -uo pipefail
cd "$(dirname "$0")"; S=$1; R=$2; SUB=$3; VPC=$4; C=$5; IT=${6:-g6e.8xlarge}; RUN=$(date -u +%Y-%m-%d-%H%M)
aws cloudformation create-stack --region $R --stack-name $S --template-body file://stack.yaml --capabilities CAPABILITY_IAM \
  --parameters ParameterKey=InstanceType,ParameterValue=$IT ParameterKey=SubnetId,ParameterValue=$SUB ParameterKey=VpcId,ParameterValue=$VPC \
  ParameterKey=Conds,ParameterValue="$C" ParameterKey=RunId,ParameterValue=$RUN >/dev/null || exit 1
B=vla-sim-results-$S-$R-$(aws sts get-caller-identity --query Account --output text)
for i in $(seq 1 60); do aws s3api head-bucket --bucket $B --region $R 2>/dev/null && break; sleep 5; done
aws s3 cp dz-run.sh s3://$B/run/dz-run.sh --region $R --quiet && echo "$(date -u +%FT%TZ) launched $S $R run=$RUN conds=[$C] bucket=$B"
