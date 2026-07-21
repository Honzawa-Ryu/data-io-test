#!/bin/bash
#SBATCH --job-name=Hello_test
#SBATCH --partition=batch
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem=16G
#SBATCH --output=/dev/null
#SBATCH --error=/dev/null

# 環境変数として.bashrcを宣言
source ~/.bashrc
CONTAINER_IMAGE="env.sif"

# sifがあるかどうかを確認、なければエラーを出す
if [ ! -f $CONTAINER_IMAGE ]; then
    echo ".sif file does not exist."
    exit 1
fi

# ログなどの出力設定
TIMESTAMP=$(date +%y%m%d_%H%M)
OUT_DIR="results/${TIMESTAMP}_${SLURM_JOB_ID}"

# 結果出力用のディレクトリを作成
mkdir -p "$OUT_DIR"

# 標準出力、エラー出力のファイル
exec > >(tee -a "${OUT_DIR}/stdout.log")
exec 2> >(tee -a "${OUT_DIR}/stderr.log" >&2)

# 実行スクリプト、実行した際のgitコミット、そこからの差分を記録
cp "$0" "$OUT_DIR/job_script.sh"
git rev-parse HEAD > "$OUT_DIR/git_commit.txt"
git diff > "$OUT_DIR/git_diff.patch"

# 最新の結果を表示するlatest下のリンク作成
ln -snf "$(realpath $OUT_DIR)" results/latest

# コード実行
apptainer exec --nv $CONTAINER_IMAGE bash -c "uv run python scripts/00_test.py"
