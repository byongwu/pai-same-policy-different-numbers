# Same Policy, Different Numbers — reproduction package

Code and configuration to re-run the multi-model stack study in
*Same Policy, Different Numbers: Success Rate Is Not Portable Across Evaluation Stacks for Vision-Language-Action Policies*
(AMLC 2026 Workshop on Physical AI & World Models, poster).

The study takes public LIBERO checkpoints of seven policy families, runs each under its
own official evaluation stack (S0), then changes one stack setting at a time and reports
how far the success rate moves. Everything runs on AWS: one CDK stack per model and region,
one GPU instance per stack, results written to an S3 bucket in your account.

| Family | Type | Checkpoint (public) | Harness |
|---|---|---|---|
| OpenVLA-OFT | VLA | `moojink/openvla-7b-oft-finetuned-libero-{spatial,object,goal,10}` | A |
| pi0.5 | VLA | `pi05_libero` (openpi) | A |
| GR00T N1.7 | VLA | `nvidia/GR00T-N1.7-LIBERO` | A |
| Cosmos Policy | WAM | `nvidia/Cosmos-Policy-LIBERO-Predict2-2B` | A |
| FastWAM | WAM | `lerobot/fastwam_libero_uncond_2cam224` | B |
| LingBot-VA | WAM | `lerobot/lingbot_va_libero_long` (LIBERO-10 only) | B |
| DreamZero | WAM | `RLinf/RLinf-DreamZero-WAN2.2-5B-LIBERO-SFT-Step26000@7416908d` | `dreamzero/` |

## Conditions

| Id | What changes | Applies to |
|---|---|---|
| S0 | nothing: the family's official stack | all |
| S1 | MuJoCo version swapped: OpenVLA-OFT 3.3.1 to 3.2.3, pi0.5 3.2.3 to 3.1.6 | OpenVLA-OFT, pi0.5 |
| S2a / S2b | per-episode step cap x0.75 / x1.5 | all |
| S2c | step cap 1000 (the LIBERO environment horizon; 1080 crashes past step 1000) | GR00T (Goal, LIBERO-10) |
| S3a / S3b | actions executed per predicted chunk: half / 1 | all chunked policies |
| S3c / S3d | as S3a / S3b but executing the first actions of the chunk (the official OpenVLA-OFT script executes the last ones) | OpenVLA-OFT, Cosmos Policy |
| S4 | random initial states instead of the fixed public ones | OpenVLA-OFT, pi0.5 |

Each cell = one suite x one condition = 50 episodes (10 tasks x 5 trials).
Our numbers for every cell are in [`results/cells.csv`](results/cells.csv) (149 cells).

## Layout

```
harness/setup.sh            builds the two patched checkouts of aws-samples/sample-vla-simulator-on-aws
harness/patches/A-*.patch   on upstream 07876f0: stack knobs for OpenVLA-OFT, pi0.5, GR00T N1.7, Cosmos Policy
harness/patches/B-*.patch   on upstream 489335a: stack knobs for FastWAM, LingBot-VA
study/mkcfg*.py             write one model yaml per shard (suite x condition list)
study/launch*.sh            deploy shards: copy the shard yaml into the harness, run deploy.py
study/collect.py            read every results bucket in the account -> model x suite x condition = k/n
study/analyze.py            tables and paired comparisons used in the paper
dreamzero/                  CloudFormation stack + run script for DreamZero (RLinf), one self-terminating instance
results/cells.csv           our results
```

Patch A also carries hooks for other targets that were explored but are not part of the study;
only the four families listed above are supported by this package.

## Run it

Requirements: an AWS account with G-instance quota (g6.xlarge / g6.2xlarge; DreamZero g6e.8xlarge),
Python 3.10+, Node 20+, AWS CDK v2, a Hugging Face token stored in SSM at `/vla-simulator/hf-token`
in each region you deploy to (see the upstream README).

```bash
bash harness/setup.sh ./work            # prints two export lines
export HARNESS_A=... HARNESS_B=...      # paste them
export NOTIFY_EMAIL=you@example.com     # SNS mail when a stack finishes

cd study
python3 mkcfg.py && python3 mkcfg_cosmos.py && python3 mkcfg_fastwam.py && python3 mkcfg_lingbot.py
# one shard = model:suite-tag:region, e.g. OpenVLA-OFT LIBERO-Spatial in us-west-2
bash launch.sh oft:libero_spatial:us-west-2
python3 collect.py --json collect.json  # after the SNS mail arrives; needs boto3 and read access to the result buckets
```

`mkcfg*.py` regenerate byte-identical copies of the 53 shard files we ran.
Shards in different regions can run in parallel; `launch.sh` waits until each shard has synthesized
before copying the next yaml, because synth reads `models/*.yaml` from the working copy.

DreamZero: `bash dreamzero/launch_dz.sh <stack-name> <region> <subnet-id> <vpc-id> "spatial:S0:480:16 spatial:S3b:480:4"`
(each condition = `suite:cond:max_episode_steps:actions_per_chunk`). The instance terminates itself;
the results bucket is retained.

## Cost and time (measured in our runs, on-demand)

- One cell (one suite, one condition, 50 episodes): about 10 minutes for OpenVLA-OFT on one g6.xlarge,
  plus one-time setup per stack (image build, checkpoint download). The world action models are slower per episode.
- DreamZero: about 25 minutes per cell on one g6e.8xlarge (1,535 s for LIBERO-Spatial S0), plus setup.
- Check current EC2 prices for your region; stacks keep running only while the evaluation runs
  (`destroy.py` removes a harness stack, `aws cloudformation delete-stack` the DreamZero stack).

## License

MIT No Attribution, same as the upstream harness. Model checkpoints, simulators and benchmarks keep their own licenses.
