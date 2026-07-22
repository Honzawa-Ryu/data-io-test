# 設定ファイルスキーマ説明

iobench は2種類のYAMLで駆動する。スキーマの実体は [src/iobench/config.py](../src/iobench/config.py) の pydantic モデル。ここではフィールドの意味と記入方法を説明する。

## 1. `configs/nodes.yaml`(クラスタのノード分類・パス解決)

サイト固有・変更頻度が低い。1度書けば、以降どのノードで実行しても probe が自動でこのノードの構成を判定し、論理ストレージ名→実パスを解決する。サンプル: [configs/nodes.example.yaml](../configs/nodes.example.yaml)

```yaml
node_classes:            # 構成X/Y/Zの定義(キーは "X" | "Y" | "Z")
  X:
    match:               # このノードがXかを判定する条件(空でないものすべてが一致=AND)
      partition: [gpu-x]        # SLURM_JOB_PARTITION がこの一覧に含まれれば一致
      hostname_pattern: "*creator*"  # ホスト名がこの glob にマッチすれば一致
      constraint: [nfs_ssd]     # SLURM_JOB_CONSTRAINT にこの語が含まれれば一致
    paths:               # 論理ストレージ名 -> 実マウントパス
      nfs: /mnt/nfs/data
      ssd_scratch: /scratch/ssd
      tmpfs: null              # null可。$SLURM_TMPDIR があれば probe が tmpfs として自動追加
    unified_memory: false  # 構成Z(GB10)は true。結果レコードの unified_memory に反映
```

| フィールド | 型 | 説明 |
|---|---|---|
| `node_classes` | map | キーは `X`/`Y`/`Z`。各構成の定義 |
| `.match.partition` | list[str] | 一致するパーティション名の一覧 |
| `.match.hostname_pattern` | str\|null | ホスト名のglobパターン(fnmatch)。例: `"*andre01*"` |
| `.match.constraint` | list[str] | 一致するconstraint語の一覧 |
| `.paths` | map[str, str\|null] | 論理名(`nfs`/`hdd`/`ssd_scratch`/`tmpfs`/`unified`)→実パス |
| `.unified_memory` | bool | ユニファイドメモリ構成か |

**分類ルール**: `match` に書いた**空でない条件がすべて一致(AND)**したとき、その構成に分類される。**0個一致**または**2個以上一致(曖昧)**の場合は `ProbeClassificationError` で停止する(goal.md「黙って計測しない」)。

**自動判定のスキップ(明示指定)**: リポを各マシンにクローンして使う運用で、hostnameパターンを合わせるのが面倒な場合は、構成を直接指定して自動分類をスキップできる:
- CLI: `iobench probe --node-class Y` / `iobench loader --node-class Y ...`
- 環境変数: `IOBENCH_NODE_CLASS=Y iobench ...`
指定した構成が `nodes.yaml` に定義されていればその `paths` が使われる(hostname/partition/constraintは判定に使われない)。

- `hostname_pattern` は **glob**(fnmatch)。例: `"*andre01*"` は `andre01` も `x-andre01` もマッチ。
- X/Y/Zが**同じパーティションを共有する**クラスタでは、`partition` は構成を区別できない。この場合 `partition` を書くと Slurmジョブ外(partition未設定)で一致せず分類できなくなるため、識別に使わないなら書かない(空にする)。区別は `hostname_pattern` に担わせる。
- 1つも条件を書かないクラスは分類根拠が無いためマッチしない。

## 2. 実験定義YAML(loader/staging/multi向けの計測マトリクス)

実験ごとに作成する。サンプル: [configs/experiment.example.yaml](../configs/experiment.example.yaml)

```yaml
purpose: dev             # dev | campaign。dev=動作確認、campaign=本計測。結果レコードに記録される
repetitions: 3           # 1条件あたりの反復回数(中央値/min/maxはこれらから算出)

cache_policy:
  mode: cold             # cold | warm | auto
  drop_caches_strategy: sudo_tee  # sudo_tee | noop。cacheモジュールのStrategy名

matrix:                  # 直積で条件を展開する
  format: [raw, webdataset]           # raw|webdataset|hdf5|zarr_v3|zarr_v2
  storage: [nfs, ssd_scratch]         # nfs|hdd|ssd_scratch|tmpfs|unified(nodes.yamlのpaths論理名)
  num_workers: [0, 8]
  shuffle_mode: [shard, full]         # none|shard|full
  decode: [true]

dataset:
  ref: synth_dev_v1                   # datagenで生成したデータセットの識別名(記録用)
  shard_size_bytes: 536870912         # webdataset用。省略可
  chunk_size_bytes: null              # hdf5/zarr用。省略可

output:
  jsonl: results/trials.jsonl         # 結果の追記先
  purpose_tag: dev
```

### `cache_policy.mode` の挙動

| mode | drop_caches成功時 | drop_caches失敗/権限なし時 |
|---|---|---|
| `cold` | `cache_state=cold` | データセット≥RAM×2なら`cold`、さもなくば`warm`に強制記録 |
| `warm` | (drop_cachesを試みず) | `cache_state=warm` |
| `auto` | `cold` | `warm` |

集計段(`iobench report`)で同一条件下の cold/warm 混在を検出すると `MixedCacheStateError` で停止する。

### `matrix` の展開

`format × storage × num_workers × shuffle_mode × decode` の直積が全条件になり、各条件を `repetitions` 回実行する。`storage` の論理名は実行ノードの `nodes.yaml` の `paths` に存在しなければ実行時エラーになる(存在しないストレージを黙って計測しない)。
