# iobench 使い方ガイド(HowToUse)

Slurmクラスタで **ジョブを投げて実行する** 前提の手順書。各マシンにこのリポをクローンして使う。
設定ファイルの詳細は [config_schema.md](config_schema.md)、設計は [design.md](design.md) を参照。

## 全体の流れ

```
1. クローン & 環境構築(コンテナ or venv)
2. このマシン用に configs/nodes.yaml を用意(または --node-class で明示)
3. sbatch でジョブ投入: probe → storage → datagen → loader → staging
4. iobench report で集計・グラフ化
5. iobench clean で後始末
```

すべてのサブコマンドは汎用ラッパ [`scripts/run_iobench.sh`](../scripts/run_iobench.sh) で Slurm ジョブとして投げられる。ラッパは実行のたびに `results/<timestamp>_<jobid>/` に **git commit・diff・実行コマンド** を保存し、実験回を追跡できるようにする。

---

## 1. 環境構築

```bash
git clone <repo> && cd data-io-test

# コンテナ(推奨): env.def から env.sif をビルド → uv環境を作る
sbatch make_sif.sh          # env.sif 生成(fio/sysstat/rsync 同梱)
sbatch setup_venv.sh        # コンテナ内で uv sync
```

コンテナを使わない場合:

```bash
uv venv .venv && source .venv/bin/activate && uv sync
```

> **注意**: 依存に `torch==2.10.0+cu128`(PyTorch専用index)を含むため、**`uv sync` を使うこと**(`pyproject.toml` の `[[tool.uv.index]]` を読んで専用indexから取得する)。plain の `pip install -e .` は torch を解決できず失敗する。GPUが無い/CPUだけで動作確認したい場合は `pip install -e . --no-deps` で `iobench` コマンド本体だけ入れ、`pydantic click pyyaml psutil pandas numpy` を別途入れれば probe/storage/datagen/report は動く(loaderのみtorch必須)。

`scripts/run_iobench.sh` は `env.sif` があればコンテナ内で、無ければ `.venv`、無ければ `src` 直実行の順に自動フォールバックする。`iobench` はコンソールスクリプトとして提供されるので、インストール後は `iobench <subcommand>` で直接呼べる。

## 2. このマシンの構成設定

```bash
cp configs/nodes.example.yaml configs/nodes.yaml
# configs/nodes.yaml を編集: このマシンの hostname_pattern と実マウントパスを記入
```

**自動判定を使わない場合**(hostnameパターンを合わせるのが面倒なとき): `nodes.yaml` に構成定義(paths)だけ書き、実行時に構成を明示する。

```bash
# 環境変数で構成を指定(sbatch にそのまま渡る)
IOBENCH_NODE_CLASS=Y sbatch -p x-large-andre01 scripts/run_iobench.sh probe
```

まず probe で正しく認識されるか確認する:

```bash
sbatch -p x-large-andre01 scripts/run_iobench.sh probe
# results/latest/stdout.log に ProbeResult(node_class, resolved_paths)が出る
```

## 3. 計測ジョブの投入

### ストレージ素性(fio)

```bash
sbatch -p x-large-andre01 scripts/run_iobench.sh storage --list-presets
sbatch -p x-large-andre01 scripts/run_iobench.sh storage \
    --target /scratch/honzawa --preset seq_1m_qd32_nj8
# NFS向け小ファイル: --preset nfs_smallfile_stat_read
```

### 合成データ生成(datagen)

同一内容を4フォーマットで生成できる。`--out` はストレージ上の実パス。

```bash
# WebDataset 512MBシャード, 10万枚, 224x224(WSI-AD想定)
sbatch -p x-large-andre01 scripts/run_iobench.sh datagen \
    --format webdataset --out /scratch/honzawa/ds_wds \
    --num-images 100000 --height 224 --width 224 --shard-size 536870912

# 生ファイル / HDF5 / Zarr(v3+v2参考を同時生成)
#   --format raw    --files-per-dir 10000
#   --format hdf5   --chunk-size 1048576
#   --format zarr   --chunk-size 1048576
```

### DataLoader スループット(loader)— 本命

実験マトリクスは YAML で宣言する([experiment.example.yaml](../configs/experiment.example.yaml) 参照)。`--dataset-root` は各ストレージ論理パス配下の相対パス。

```bash
sbatch -p x-large-andre01 scripts/run_iobench.sh loader \
    --config configs/experiment.yaml --dataset-root ds_wds
# 12/18/... 試行が results/trials.jsonl に追記される(反復・cache_state・sidecar付き)
```

`experiment.yaml` の `matrix` で format × storage × num_workers × shuffle_mode × decode を直積展開し、各条件を `repetitions` 回実行する。

### ステージング(staging)と運用パターン A/B/C

```bash
# 転送計測(T_stage)
sbatch scripts/run_iobench.sh staging --tool rsync \
    --src /workspace/andre01/honzawa/ds --dst /scratch/honzawa/ds

# パターンA/B/C の sbatch スクリプトを生成(投入前に中身を確認)
sbatch scripts/run_iobench.sh slurm template --pattern C \
    --src /workspace/andre01/honzawa/ds --exp-yaml configs/experiment.yaml \
    --dataset-root ds --cache-root /scratch/cache
# 生成物: results/slurm_templates/stageC.sh, lru_evict.sh
```

- **A**: ジョブ内ステージング / **B**: CPU転送ジョブ+`afterok`+`-w`固定 / **C**: 共有キャッシュ(flock排他・存在チェックでスキップ・LRU容量管理)

## 4. 集計・グラフ化(report)

```bash
iobench report --jsonl results/trials.jsonl --out results/report
# trials_raw.csv, trials_aggregated.csv(中央値/min/max), *.png(スループット比較・シャードサイズ掃引)
```

多重負荷の劣化率は、単独実行と同時実行の結果JSONLを突合する(**多重負荷試験の実施は事前に運用者へ確認すること**):

```bash
iobench multi --baseline-jsonl results/baseline.jsonl --multi-jsonl results/multi.jsonl
```

## 5. 後始末(clean)

```bash
iobench clean --dry-run --target /scratch/honzawa/ds_wds   # 対象確認
iobench clean --yes     --target /scratch/honzawa/ds_wds   # 削除実行
```

---

## cold / warm 計測についての注意(重要)

ライブラリは各試行前に `cache_policy` に従ってページキャッシュを扱い、結果に `cache_state`(cold/warm)を必ず記録する。cold/warm が混在した比較は `iobench report` がエラーで止める。

`cache_policy.drop_caches_strategy` は3種類:

| strategy | 挙動 | 使う場面 |
|---|---|---|
| `sudo_tee` | 各試行前に `sync; echo 3 | sudo tee /proc/sys/vm/drop_caches`。成功でcold | passwordless sudo が使えるノード |
| `noop` | 何もしない。データセット≥RAM×2ならcold、未満はwarm強制 | 権限が無く、大容量データでcoldを測る |
| `external` | ライブラリはdropせず、外部で落とされた前提でcold記録 | **投入直前に運用者が手動でsudo drop する運用**(下記) |

### 運用: ジョブ投入直前に手動で drop_caches する(このクラスタの方針)

passwordless sudo を常設しない方針のため、**運用者がジョブ投入の直前に対象ノードへ入り、sudo でキャッシュを落としてから投入する**。ライブラリ側は `drop_caches_strategy: external` にして cold として記録する。

```bash
# 1. 対象ノードに入って手動でキャッシュを落とす
ssh andre01
sync; echo 3 | sudo tee /proc/sys/vm/drop_caches
exit

# 2. すぐにジョブを投入(experiment.yaml は cache_policy.drop_caches_strategy: external)
sbatch -p x-large-andre01 scripts/run_iobench.sh loader \
    --config configs/experiment_cold.yaml --dataset-root ds_wds
```

**⚠️ 重要な制約**: 手動 drop は **そのジョブの最初の読み込み(最初の1試行)だけ** を cold にする。同じデータを2回目に読むとページキャッシュに載って warm になる。したがって `external` 戦略は次のルールで使う:

- **`repetitions: 1` にする**(experiment.yaml)。`repetitions>1` だと2試行目以降が実際はwarmなのにcold記録されてしまう(ライブラリは警告を出す)。
- cold試行を N 回取りたいなら、**「手動drop → 1試行ジョブ投入」を N 回繰り返す**。各ジョブが独立して最初の読みだけを測る。
- 複数条件(format×storage等)を1ジョブで回すと、条件をまたいで別データを読むので各条件の初回はcold。ただし同一条件を反復するとwarm化する点は同じ。

### 参考: 権限があるノード / 自動化する場合

- passwordless sudo が使えるなら `sudo_tee` で各試行前に自動 drop(反復もすべてcold)。
- Slurm prolog に drop_caches を仕込めるなら、それを呼ぶ戦略を `cache/strategies.py` に追加して `drop_caches_strategy` に指定する。
- 例: andre01(RAM 251GB)で drop 不可かつ `noop` の場合、cold相当と判定されるには約 **500GB 以上**(RAM×2)のデータセットが要る。

## dev / campaign の区別

実験定義YAMLの `purpose` で区別する。ライブラリ開発中の動作確認は `purpose: dev`、本計測は `purpose: campaign`。`report` はこのタグを結果に残すので、dev の数値が本計測に混入しない。
