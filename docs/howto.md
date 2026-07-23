# iobench 使い方ガイド(HowToUse)

Slurmクラスタで **ジョブを投げて実行する** 前提の手順書。各マシンにこのリポをクローンして使う。
設定ファイルの詳細は [config_schema.md](config_schema.md)、設計は [design.md](design.md) を参照。

## 全体の流れ

```
1. クローン & 環境構築(コンテナ or venv)
2. このマシン用に configs/nodes.yaml を用意(または --node-class で明示)
3. sbatch でジョブ投入: probe → storage → datagen(遅い側に生成)
   → staging(計測がてら速い側へ配置) → loader
4. iobench report で集計・グラフ化・損益分岐表
5. iobench clean で後始末
```

datagen を遅い側(HDD/NFS)に行い、staging の転送計測がそのまま loader 用の
SSD側コピー作成を兼ねる、という順序にすることで、1回のデータ準備で
「フォーマット別の転送速度」「両ストレージのloader比較」「損益分岐E」が全部揃う。

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

### 合成データ生成(datagen)— 遅い側(HDD/NFS)に作る

同一内容を4フォーマットで生成できる。`--out` はストレージ上の実パス。
**フォーマットごとに別ディレクトリ**に生成する(datagenは出力先を毎回作り直すため、
同じ `--out` を使い回すと前のフォーマットの出力が消える)。
後段の staging で速い側(SSD)へ運ぶので、**まず遅い側に生成する**。

```bash
# 生ファイル 10万枚 224x224(WSI-AD想定)
sbatch -p x-large-andre01 scripts/run_iobench.sh datagen \
    --format raw --out /workspace/andre01/honzawa/ds_raw \
    --num-images 100000 --height 224 --width 224 --files-per-dir 10000

# WebDataset 512MBシャード
sbatch -p x-large-andre01 scripts/run_iobench.sh datagen \
    --format webdataset --out /workspace/andre01/honzawa/ds_wds \
    --num-images 100000 --height 224 --width 224 --shard-size 536870912

# HDF5 / Zarr(v3+v2参考を同時生成)
#   --format hdf5   --out .../ds.h5    --chunk-size 1048576
#   --format zarr   --out .../ds_zarr  --chunk-size 1048576
```

### ステージング計測(staging)— 計測がてらSSDへ配置する

遅い側→速い側の転送時間(T_stage)を計測しながら、loader計測用のSSD側コピーを作る。
**フォーマット(レイアウト)ごとに実施する** — 小ファイル大量(raw)とtar数本(webdataset)では
転送速度がまったく違うため、これ自体がレイアウト間の転送速度比較になる。
結果は TrialRecord として `results/trials_staging.jsonl` に追記され、
`iobench report` が loader 結果と突合して損益分岐E(breakeven_table.csv)を算出する。

```bash
# 投入直前に手動 drop_caches(cold化。下記「cold/warm 計測についての注意」参照)してから:
sbatch -p x-large-andre01 scripts/run_iobench.sh staging --tool rsync \
    --src /workspace/andre01/honzawa/ds_raw --dst /scratch/honzawa/ds_raw \
    --format raw --cache-state cold

# フォーマットごとに drop → 投入を繰り返す
sbatch -p x-large-andre01 scripts/run_iobench.sh staging --tool rsync \
    --src /workspace/andre01/honzawa/ds_wds --dst /scratch/honzawa/ds_wds \
    --format webdataset --cache-state cold

# 転送ツール比較は --tool cp / tar / parallel_rsync(毎回 dst削除+drop してから)
```

- `--format` は report で loader 結果と突合する結合キー(転送するデータのレイアウトを指定)。
- `--cache-state cold` は「外部でdrop済み」の自己申告(loaderの`external`戦略と同じ信頼モデル)。
  drop せずに測った場合は既定の warm のまま記録する。cold と warm は別jsonlに分けること。
- src/dst の論理ストレージ名(hdd/ssd_scratch等)は nodes.yaml の resolved_paths から
  自動解決される。解決できないパスは `--src-logical`/`--dst-logical` で明示する。
- 転送スループットはデータサイズにほぼ比例するので、マシン×レイアウトごとに1〜3回で足りる
  (loaderのような条件掃引は不要)。

### DataLoader スループット(loader)— 本命

staging で両ストレージにデータが揃った状態で回す。実験マトリクスは YAML で宣言する
([experiment.example.yaml](../configs/experiment.example.yaml) 参照)。
`--dataset-root` は各ストレージ論理パス配下の**相対パス**(例: `ds_wds`)。
絶対パスを渡すと storage 軸が実質無効になる(全条件が同じ実パスを読む)ので渡さないこと。

```bash
sbatch -p x-large-andre01 scripts/run_iobench.sh loader \
    --config configs/experiment.yaml --dataset-root ds_wds
# 12/18/... 試行が results/trials.jsonl に追記される(反復・cache_state・sidecar付き)
```

`experiment.yaml` の `matrix` で format × storage × num_workers × shuffle_mode × decode を直積展開し、各条件を `repetitions` 回実行する。matrix の format はすべて同じ base ディレクトリ
(`ストレージ論理パス/dataset-root`)から読むため、フォーマットごとに `--out` を分けた場合は
**formatごとに config と `--dataset-root` を分けて別ジョブで回す**。

### 運用パターン A/B/C(slurm template)

```bash
# パターンA/B/C の sbatch スクリプトを生成(投入前に中身を確認)
sbatch scripts/run_iobench.sh slurm template --pattern C \
    --src /workspace/andre01/honzawa/ds_wds --exp-yaml configs/experiment.yaml \
    --dataset-root ds_wds --cache-root /scratch/cache
# 生成物: results/slurm_templates/stageC.sh, lru_evict.sh
```

- **A**: ジョブ内ステージング / **B**: CPU転送ジョブ+`afterok`+`-w`固定 / **C**: 共有キャッシュ(flock排他・存在チェックでスキップ・LRU容量管理)

## 4. 集計・グラフ化(report)

`--jsonl` は複数指定でき、loader系とstaging系の結果をまとめて集計・突合する:

```bash
iobench report \
    --jsonl results/trials.jsonl \
    --jsonl results/trials_staging.jsonl \
    --out results/report
```

出力:

- `trials_raw.csv` / `trials_aggregated.csv` — 全試行と条件別集計(中央値/min/max)
- `throughput_comparison.png` / `shardsize_sweep.png` — スループット比較・シャードサイズ掃引
- `breakeven_table.csv` — **損益分岐表**。staging の T_stage と loader の epoch_seconds を
  (node_class × format)で突合し、「Eエポック以上回すならステージングが得」のEを条件ごとに出す。
  同一 node_class × format で、staging_src と staging_dst 両ストレージの loader 計測が
  揃っている場合のみ行が生成される。

cold/warm が混在した比較は report がエラーで止めるため、loader と同様 staging も
cold と warm は別jsonlに分けて、比較したい組だけを `--jsonl` で渡す。

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
