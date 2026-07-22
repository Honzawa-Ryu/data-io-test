#!/bin/bash
#SBATCH --job-name=iobench_loader
#SBATCH --exclusive
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null
#
# iobench loader をSlurmジョブとして投入するテンプレート。
# 使い方: sbatch scripts/run_loader.sh <experiment.yaml> <dataset_root>
# 例:     sbatch scripts/run_loader.sh configs/experiment.yaml ds_synth
#
# ノード構成(X/Y/Z)は probe が自動分類するため、同一スクリプトを
# どのパーティション/ノードに投げても比較可能な結果が出る(goal.md 最重要設計原則)。

set -euo pipefail

source ~/.bashrc
CONTAINER_IMAGE="env.sif"
EXP_YAML="${1:?experiment.yaml を第1引数で指定してください}"
DATASET_ROOT="${2:?dataset_root を第2引数で指定してください}"
NODES_CONFIG="${NODES_CONFIG:-configs/nodes.yaml}"

if [ ! -f "$CONTAINER_IMAGE" ]; then
    echo ".sif file does not exist." >&2
    exit 1
fi

# 実験回の記録ディレクトリ(goal.md 2.1「実験回の記録を残せるように」)
TIMESTAMP=$(date +%y%m%d_%H%M)
OUT_DIR="results/${TIMESTAMP}_${SLURM_JOB_ID:-manual}"
mkdir -p "$OUT_DIR"

exec > >(tee -a "${OUT_DIR}/stdout.log")
exec 2> >(tee -a "${OUT_DIR}/stderr.log" >&2)

# 再現性のための記録: 実行スクリプト・gitコミット・差分・使った設定
cp "$0" "$OUT_DIR/job_script.sh"
cp "$EXP_YAML" "$OUT_DIR/experiment.yaml"
git rev-parse HEAD > "$OUT_DIR/git_commit.txt" 2>/dev/null || echo "no-git" > "$OUT_DIR/git_commit.txt"
git diff > "$OUT_DIR/git_diff.patch" 2>/dev/null || true

ln -snf "$(realpath "$OUT_DIR")" results/latest

apptainer exec --nv "$CONTAINER_IMAGE" bash -c \
    "uv run iobench --nodes-config '$NODES_CONFIG' loader --config '$EXP_YAML' --dataset-root '$DATASET_ROOT'"
