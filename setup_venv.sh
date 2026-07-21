#!/bin/bash
#SBATCH --partition=interactive
#SBATCH --output=setup_%j.log

CONTAINER_IMAGE="env.sif"

# uvのキャッシュディレクトリをホスト側に固定（高速化のため）
export UV_CACHE_DIR="$(pwd)/.uv_cache"
mkdir -p "$UV_CACHE_DIR"

echo "=== uv syncing (creating .venv) ==="

# apptainer exec でコンテナ内の uv を呼び出す
apptainer exec --nv "$CONTAINER_IMAGE" \
    bash -c "uv venv .venv --clear && \
             uv sync"

echo "=== Setup Complete ==="
echo "To activate the environment, run: source .venv/bin/activate"
