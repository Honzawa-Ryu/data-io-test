"""ステージング運用パターンA/B/CのsbatchスクリプトをPython文字列テンプレートから生成する。

外部テンプレートエンジン(jinja2)には依存せず、str.formatで組み立てる。
- パターンA: ジョブ内ステージング(ジョブ先頭でsrc->SSDへ転送してから学習)
- パターンB: CPUパーティション転送ジョブ + afterok依存 + -w固定の学習ジョブ(2スクリプト)
- パターンC: /scratch/cache/<hash>/ 共有キャッシュ。flock排他・存在チェックスキップ・LRU管理
"""

from __future__ import annotations

_PATTERN_A = """#!/bin/bash
#SBATCH --job-name=iobench_stageA
#SBATCH --exclusive
#SBATCH --output=results/slurm_%j.out
set -euo pipefail
source ~/.bashrc

SRC="{src}"
SSD_DST="{ssd_dst}"
EXP_YAML="{exp_yaml}"
DATASET_ROOT="{dataset_root}"

echo "[pattern A] ジョブ内ステージング開始: $SRC -> $SSD_DST"
mkdir -p "$SSD_DST"
t0=$(date +%s)
rsync -a "$SRC/" "$SSD_DST/"
echo "[pattern A] T_stage=$(($(date +%s)-t0))s"

apptainer exec --nv env.sif bash -c \\
    "uv run iobench loader --config '$EXP_YAML' --dataset-root '$DATASET_ROOT'"
"""

_PATTERN_B_TRANSFER = """#!/bin/bash
#SBATCH --job-name=iobench_stageB_xfer
#SBATCH --partition={cpu_partition}
#SBATCH --output=results/slurm_%j.out
set -euo pipefail
source ~/.bashrc

SRC="{src}"
SSD_DST="{ssd_dst}"
echo "[pattern B/transfer] $SRC -> $SSD_DST on $(hostname)"
mkdir -p "$SSD_DST"
rsync -a "$SRC/" "$SSD_DST/"
echo "[pattern B/transfer] done"
"""

_PATTERN_B_TRAIN = """#!/bin/bash
#SBATCH --job-name=iobench_stageB_train
#SBATCH --exclusive
#SBATCH --output=results/slurm_%j.out
set -euo pipefail
source ~/.bashrc

EXP_YAML="{exp_yaml}"
DATASET_ROOT="{dataset_root}"
echo "[pattern B/train] on $(hostname)(-w固定済み)、転送済みSSDから学習"
apptainer exec --nv env.sif bash -c \\
    "uv run iobench loader --config '$EXP_YAML' --dataset-root '$DATASET_ROOT'"
"""

# パターンB投入手順を示すコメント付きのヘルパスクリプト
_PATTERN_B_SUBMIT = """#!/bin/bash
# パターンB投入: CPUで転送 -> afterok -> -w で同一ノードに学習を固定
set -euo pipefail
TARGET_NODE="{train_node}"
XFER_ID=$(sbatch --parsable -w "$TARGET_NODE" {transfer_script})
echo "transfer job: $XFER_ID"
sbatch --dependency=afterok:$XFER_ID -w "$TARGET_NODE" {train_script}
"""

_PATTERN_C = """#!/bin/bash
#SBATCH --job-name=iobench_stageC
#SBATCH --exclusive
#SBATCH --output=results/slurm_%j.out
set -euo pipefail
source ~/.bashrc

SRC="{src}"
DATASET_HASH="{dataset_hash}"
CACHE_ROOT="{cache_root}"
CACHE_DIR="$CACHE_ROOT/$DATASET_HASH"
LOCK="$CACHE_ROOT/$DATASET_HASH.lock"
EXP_YAML="{exp_yaml}"
DATASET_ROOT="{dataset_root}"
CACHE_CAP_GB="{cache_cap_gb}"

mkdir -p "$CACHE_ROOT"

# flockで排他。先行ジョブがステージング中なら待ち、完了済みならスキップ。
exec {{lock_fd}}>"$LOCK"
flock "${{lock_fd}}"
if [ -f "$CACHE_DIR/.complete" ]; then
    echo "[pattern C] キャッシュヒット、ステージングスキップ: $CACHE_DIR"
else
    echo "[pattern C] キャッシュミス、ステージング: $SRC -> $CACHE_DIR"
    mkdir -p "$CACHE_DIR"
    rsync -a "$SRC/" "$CACHE_DIR/"
    touch "$CACHE_DIR/.complete"
    # LRU容量管理: 上限超過分を最終アクセスの古い順に削除
    bash {lru_script} "$CACHE_ROOT" "$CACHE_CAP_GB" || true
fi
flock -u "${{lock_fd}}"

apptainer exec --nv env.sif bash -c \\
    "uv run iobench loader --config '$EXP_YAML' --dataset-root '$DATASET_ROOT'"
"""

_LRU_SCRIPT = """#!/bin/bash
# 共有キャッシュのLRU容量管理。CACHE_ROOT配下の <hash> ディレクトリを
# 最終アクセス時刻の古い順に、合計が上限以下になるまで削除する。
set -euo pipefail
CACHE_ROOT="${1:?cache_root}"
CAP_GB="${2:?cap_gb}"
CAP_BYTES=$((CAP_GB * 1024 * 1024 * 1024))

total=$(du -sb "$CACHE_ROOT" 2>/dev/null | cut -f1)
[ -z "$total" ] && exit 0
[ "$total" -le "$CAP_BYTES" ] && exit 0

# atime昇順(古い順)にディレクトリを列挙して削除
for d in $(ls -1dtu --time=atime "$CACHE_ROOT"/*/ 2>/dev/null | tac); do
    [ "$total" -le "$CAP_BYTES" ] && break
    sz=$(du -sb "$d" | cut -f1)
    echo "[LRU] evict $d ($sz bytes)"
    rm -rf "$d"
    total=$((total - sz))
done
"""


def render_pattern_a(src: str, ssd_dst: str, exp_yaml: str, dataset_root: str) -> str:
    return _PATTERN_A.format(src=src, ssd_dst=ssd_dst, exp_yaml=exp_yaml, dataset_root=dataset_root)


def render_pattern_b(
    src: str,
    ssd_dst: str,
    exp_yaml: str,
    dataset_root: str,
    cpu_partition: str,
    train_node: str,
) -> dict[str, str]:
    return {
        "transfer": _PATTERN_B_TRANSFER.format(src=src, ssd_dst=ssd_dst, cpu_partition=cpu_partition),
        "train": _PATTERN_B_TRAIN.format(exp_yaml=exp_yaml, dataset_root=dataset_root),
        "submit": _PATTERN_B_SUBMIT.format(
            train_node=train_node,
            transfer_script="stageB_transfer.sh",
            train_script="stageB_train.sh",
        ),
    }


def render_pattern_c(
    src: str,
    dataset_hash: str,
    cache_root: str,
    exp_yaml: str,
    dataset_root: str,
    cache_cap_gb: int = 500,
    lru_script: str = "lru_evict.sh",
) -> dict[str, str]:
    return {
        "job": _PATTERN_C.format(
            src=src,
            dataset_hash=dataset_hash,
            cache_root=cache_root,
            exp_yaml=exp_yaml,
            dataset_root=dataset_root,
            cache_cap_gb=cache_cap_gb,
            lru_script=lru_script,
        ),
        "lru": _LRU_SCRIPT,
    }
