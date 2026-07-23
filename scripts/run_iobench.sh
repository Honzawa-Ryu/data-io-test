#!/bin/bash
#SBATCH --job-name=iobench
#SBATCH --exclusive
#SBATCH --output=results/iobench_%j.out
#SBATCH --error=results/iobench_%j.err
#
# 任意の iobench サブコマンドを Slurm ジョブとして実行する汎用ラッパ。
# 実験回の記録(git commit/diff・使ったコマンド)を results/<timestamp>_<jobid>/ に残す。
#
# 使い方:
#   sbatch [-p <partition>] [-w <node>] scripts/run_iobench.sh <iobench 引数...>
# 例:
#   sbatch -p x-large-andre01 scripts/run_iobench.sh probe
#   sbatch -p x-large-andre01 scripts/run_iobench.sh storage --target /scratch/honzawa --preset seq_1m_qd32_nj8
#   sbatch -p x-large-andre01 scripts/run_iobench.sh datagen --format webdataset --out /scratch/honzawa/ds --num-images 100000 --shard-size 536870912
#   sbatch -p x-large-andre01 scripts/run_iobench.sh loader --config configs/experiment.yaml --dataset-root ds
#
# 構成の自動判定が効かないマシンでは、環境変数で明示できる:
#   IOBENCH_NODE_CLASS=Y sbatch ... scripts/run_iobench.sh loader ...

set -uo pipefail
source ~/.bashrc 2>/dev/null || true

CONTAINER_IMAGE="${CONTAINER_IMAGE:-env.sif}"
NODES_CONFIG="${NODES_CONFIG:-configs/nodes.yaml}"

# 実験回の記録ディレクトリ
TIMESTAMP=$(date +%y%m%d_%H%M)
OUT_DIR="results/${TIMESTAMP}_${SLURM_JOB_ID:-manual}"
mkdir -p "$OUT_DIR"

exec > >(tee -a "${OUT_DIR}/stdout.log")
exec 2> >(tee -a "${OUT_DIR}/stderr.log" >&2)

echo "=== iobench on $(hostname) (partition=${SLURM_JOB_PARTITION:-?}) ==="
echo "=== args: $* ==="

# 再現性のための記録
cp "$0" "$OUT_DIR/job_script.sh"
echo "iobench $*" > "$OUT_DIR/command.txt"
git rev-parse HEAD > "$OUT_DIR/git_commit.txt" 2>/dev/null || echo "no-git" > "$OUT_DIR/git_commit.txt"
git diff > "$OUT_DIR/git_diff.patch" 2>/dev/null || true
ln -snf "$(realpath "$OUT_DIR")" results/latest

# コンテナ優先
if [ -f "$CONTAINER_IMAGE" ]; then
    apptainer exec --nv "$CONTAINER_IMAGE" bash -c \
        "uv run iobench --nodes-config '$NODES_CONFIG' $*"
else
    echo "No container image found at $CONTAINER_IMAGE."
fi
