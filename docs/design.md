# iobench 設計文書 (フェーズ1)

goal.md に基づく設計。**この文書はフェーズ1のレビュー対象であり、人間の承認を得てからフェーズ2(コア実装)へ進む。**

## 1. 決定事項とモジュールの対応

| 意思決定 | 担当モジュール |
|---|---|
| 1. 供給経路(直読み vs SSDステージング)の損益分岐 | `staging`(T_stage計測・E閾値算出)、`loaderbench`(T_epoch計測) |
| 2. フォーマット推奨・シャード/チャンク最適帯 | `datagen`(4形態生成)、`loaderbench`(掃引計測)、`report`(集計) |
| 3. ステージング運用(A/B/C) | `staging` + `slurm`(パターン実装)、`multi`(パターンCの多重負荷免疫確認) |

`probe` / `cache` / `sidecar` / `results` はすべての計測を横断して支える基盤。異種ノードで比較可能性を保証する要。

## 2. モジュール責務・インターフェース

### 2.1 `probe`
- **入力**: なし(実行ノード上で自動収集)+ `configs/*.yaml` の `storages` セクション(論理名→解決ルール)
- **出力**: `ProbeResult`(→ 2.4 節参照)
- **責務**:
  - ホスト名、Slurm変数(`SLURM_JOB_ID`, `SLURM_JOB_PARTITION`, `SLURM_TMPDIR`)取得
  - `/proc/mounts` 解析 → 各マウントの fs種別(nfs/ext4/xfs/tmpfs)
  - `/sys/block/*/queue/rotational` → HDD/SSD判定、`/sys/block/*/device/model` 等でNVMe判定
  - CPU/RAM/GPU情報(`psutil`, `pynvml`)、ユニファイドメモリ判定(GPU可視メモリ==システムRAMかで推定 or 明示config)
  - config内の `node_classes` 定義(hostnameパターン=glob / partition / constraint のマッチャ)に対して現在ノードを分類。判定は**空でない条件すべての一致(AND)**。**0一致または2構成以上一致(曖昧)なら `ProbeClassificationError` で即停止**(黙って計測しない、goal.md 2.2 の要求)。パーティションを複数構成で共有するクラスタでは hostname_pattern が識別子になる
  - 論理ストレージ名(`nfs`, `hdd`, `ssd_scratch`, `tmpfs`)→ 実パスを、マッチしたnode_classの`paths`から解決
- **未確定情報への対応**: node_classマッチャ・実パスは全てconfig(`configs/nodes.yaml`)側のデータであり、probeのコード自体はノード名・パスを一切ハードコードしない。ノード名/パス確定後は config を1枚書けば済む。

### 2.2 `cache`
- **責務**: 試行前のページキャッシュ制御を強制する唯一の入口。`CachePolicy`(config駆動)を受け取り、以下のいずれかを実行:
  - `drop_caches`戦略: 既定は `sudo tee /proc/sys/vm/drop_caches` (値=3)。ユーザ確認により権限はあるが具体運用は未確定のため、**Strategyパターンで差し替え可能**にする(`DropCachesStrategy` 抽象基底 → `SudoTeeStrategy` を既定実装として提供。将来 prolog連携等が決まれば新戦略を追加するだけで済む)
  - 権限/戦略が使えない場合: `cache_state="warm"` を強制記録 + データセットサイズ≥RAM×2の自動検証(不足なら警告 or エラー、config化)
- 実行結果(成功/失敗、採用した戦略名)を `cache_state` と合わせて結果レコードに埋める
- 集計段(`report`)で cold/warm 混在を検出したら **エラー終了**

### 2.3 `sidecar`
- **責務**: 計測開始と同時に `iostat -x 1` / `vmstat 1` / `nvidia-smi dmon`(GPU搭載時)をサブプロセスとして起動し、計測終了で停止・ログ回収
- 各ログ行に試行開始からの経過秒を付与し、`trial_id` に紐付けたファイルとして `results/sidecar/<trial_id>/{iostat,vmstat,dmon}.log` に保存
- ラッパは `with SidecarSession(trial_id) as sc: ...` の形のコンテキストマネージャとして提供し、`storage`/`loaderbench`/`staging` から共通利用する

### 2.4 `results`
- **責務**: 結果スキーマ(pydanticモデル)の定義、JSON Lines追記、集計CSV生成
- スキーマは本設計の核。詳細は3節

### 2.5 `storage`
- fioラッパ。プリセット: シーケンシャル/ランダム × ブロックサイズ{4K,128K,1M,16M} × iodepth{1,32} × numjobs{1,8}。NFS向け小ファイルstat/readプリセット(`smallfile`連携 or 自前実装、要調査)同梱
- fio実行結果(JSON出力モード)をパースし `results` スキーマの `metrics` に正規化

### 2.6 `datagen`
- 合成画像データセットを4形態(生ファイル/WebDataset/HDF5/Zarr)で同一内容生成。シード固定
- **Zarrの扱い**: `--format zarr` は1回の呼び出しで **Zarr v3(sharded、主系列)と Zarr v2(参考コピー)を同一seed・同一チャンクサイズで同時生成** する(goal.md 2.5「Zarr v3 sharded(同チャンク掃引)+ 参考用 Zarr v2」に対応)。出力は `<out>/v3.zarr` と `<out>/v2_reference.zarr`。`loaderbench` 側の `Condition.format` は `zarr_v3` / `zarr_v2` でどちらを読んだかを区別する(結果スキーマのFormatNameは4値: raw/webdataset/hdf5/zarr_v3/zarr_v2)
- 生成物のファイル数・総サイズ・生成時間を記録するメタデータJSONを併せて出力

### 2.7 `loaderbench`(実装確定)
- PyTorch `DataLoader` で1エポック読み切り計測。変数: フォーマット、ストレージ、`num_workers{0,4,8,16}`、シャッフル{なし/シャード内/完全ランダム}、デコード{あり/なし}
- フォーマット別Dataset: `RawFileDataset`(map-style)、`WebDatasetShards`(iterable、worker間でシャード分割・shard shuffle対応)、`Hdf5Dataset`(worker毎に遅延オープンでfork安全)、`ZarrDataset`
- `decode=False` はバイト列長のみ読む(ストレージ帯域の上限。デコードCPUコストを除外)
- shuffle_mode の realized behavior(goal.md「なし/シャード内/完全ランダム」を全フォーマットで区別):
  - `none`: 逐次
  - `shard`(シャード内): map系=ブロック内シャッフル(`OrderSampler`、局所性を保つ)、webdataset=シャード順シャッフル+シャッフルバッファ
  - `full`(完全ランダム): map系=全体置換。**webdatasetはtar逐次構造のため実現不能→条件展開時にスキップ**(崩れた比較を記録しない)
- **`gpu_idle_ratio` は proxy**: 前バッチ処理終了〜次バッチ取得までの待ち時間積算をelapsedで正規化(`--to-gpu` 時のみ)。実際のモデルforwardを伴わないため絶対値は高めに出る。**系列間の相対比較専用**で、report/レポートで解釈する際はこの点を明記する(H6のCPUデコード支配の解釈時に誤読しないこと)。dmon併用で実使用率も参照
- `runner.py` が実験YAMLを展開(`iter_conditions`)→ 反復 → `cache.determine_cache_state` → `SidecarSession` → `TrialRecord` 追記 まで統合。フォーマット `zarr_v3`/`zarr_v2` は datagen 出力の `v3.zarr`/`v2_reference.zarr` に解決される

### 2.8 `staging`(実装確定)
- 転送計測 [`transfer.py`]: `{cp, rsync, tarパイプ, シャード単位並列rsync}` × bwlimit有無。`TransferResult`(total_bytes / elapsed / MB/s)を返す
- 損益分岐 [`breakeven.py`]: `E = ceil(T_stage / (T_epoch_direct − T_epoch_SSD))` を算出。saving≤0(SSDが直読み以上に遅い)なら「常に損」として `breakeven_epochs=None`

### 2.9 `slurm`(実装確定)
- sbatchスクリプト生成 [`templates.py` + `write_pattern`]・投入(`slurm submit` は `sbatch --parsable` ラッパ)・依存関係管理。テンプレートはjinja2非依存の `str.format`
- パターンA(ジョブ内ステージング)/B(CPU転送ジョブ+`--dependency=afterok`+`-w`固定の2スクリプト+投入ヘルパ)/C(`<cache_root>/<dataset_hash>/`共有キャッシュ、`flock`排他、`.complete`存在チェックによるスキップ、`lru_evict.sh`によるatimeベースLRU容量管理)を実装。パターンCの「2本目でスキップ」はローカルで実証済み

### 2.10 `multi`(実装確定)
- 単独実行の結果JSONLとN本同時実行の結果JSONLを条件キー(format/storage/workers/shuffle/decode/node_class)で突合し、`degradation_ratio = multi平均スループット / baselineスループット` を算出。ジョブ投入自体は `sbatch scripts/run_loader.sh` をN本同一ノードへ流すか slurm パターン生成物を使う

### 2.11 `cli.py`
- 詳細は4節

## 3. 結果スキーマ(`results`)

1試行 = 1レコード。JSON Lines(生データ)+ 集計CSV(`report`が生成)。

```python
class ProbeResult(BaseModel):
    hostname: str
    node_class: Literal["X", "Y", "Z"]
    slurm_job_id: str | None
    slurm_partition: str | None
    slurm_tmpdir: str | None
    mounts: list[MountInfo]          # path, fs_type, device, rotational, is_nvme
    cpu_cores: int
    ram_gb: float
    gpu_present: bool
    gpu_model: str | None
    unified_memory: bool
    resolved_paths: dict[str, str]   # 論理名 -> 実パス

class Condition(BaseModel):
    format: Literal["raw", "webdataset", "hdf5", "zarr_v3", "zarr_v2"]
    storage_logical: str             # "nfs" | "hdd" | "ssd_scratch" | "tmpfs"
    shard_or_chunk_size_bytes: int | None
    num_workers: int
    shuffle_mode: Literal["none", "shard", "full"]
    decode: bool

class Metrics(BaseModel):
    throughput_samples_s: float | None
    throughput_mb_s: float | None
    gpu_idle_ratio: float | None
    t_stage_seconds: float | None
    first_batch_latency_s: float | None
    degradation_ratio: float | None
    meta_ops_s: float | None

class TrialRecord(BaseModel):
    trial_id: str            # uuid4
    timestamp: datetime
    probe: ProbeResult
    condition: Condition
    metrics: Metrics
    cache_state: Literal["cold", "warm"]
    repetition_index: int
    repetition_total: int
    library_version: str     # git hash
    purpose: Literal["dev", "campaign"]
    sidecar_ref: str | None  # results/sidecar/<trial_id>/ へのパス
    subcommand: str          # "storage" | "loader" | "staging" | ...
    notes: str | None = None
```

JSON Lines例:

```json
{"trial_id": "b1e2...", "timestamp": "2026-07-22T10:00:00+09:00", "probe": {"hostname": "nodeX01", "node_class": "X", "slurm_job_id": "123456", "slurm_partition": "gpu", "slurm_tmpdir": "/tmp/123456", "mounts": [{"path": "/mnt/nfs", "fs_type": "nfs4", "device": null, "rotational": null, "is_nvme": false}], "cpu_cores": 32, "ram_gb": 256.0, "gpu_present": true, "gpu_model": "A100", "unified_memory": false, "resolved_paths": {"nfs": "/mnt/nfs/data", "ssd_scratch": "/scratch/ssd"}}, "condition": {"format": "webdataset", "storage_logical": "ssd_scratch", "shard_or_chunk_size_bytes": 536870912, "num_workers": 8, "shuffle_mode": "shard", "decode": true}, "metrics": {"throughput_samples_s": 4200.5, "throughput_mb_s": 980.2, "gpu_idle_ratio": 0.03, "t_stage_seconds": null, "first_batch_latency_s": 1.2, "degradation_ratio": null, "meta_ops_s": null}, "cache_state": "cold", "repetition_index": 0, "repetition_total": 3, "library_version": "a1b2c3d", "purpose": "dev", "sidecar_ref": "results/sidecar/b1e2.../", "subcommand": "loader", "notes": null}
```

## 4. 設定ファイル(実験マトリクス + ノード定義)YAMLスキーマ

2ファイルに分離する: `configs/nodes.yaml`(クラスタのノード分類・パス解決。サイト固有・変更頻度低)と実験定義YAML(計測マトリクス。実験ごとに作成)。

### 4.1 `configs/nodes.yaml`(例。ノード名/パス未確定分は placeholder)

```yaml
node_classes:
  X:
    match:
      partition: ["gpu-x"]          # いずれか一致
      hostname_pattern: "nodeX.*"
      constraint: ["nfs_ssd"]
    paths:
      nfs: /mnt/nfs/data            # TODO: 実パス確定待ち
      ssd_scratch: /scratch/ssd
      tmpfs: null
  Y:
    match:
      partition: ["cpu-y"]
      hostname_pattern: "nodeY.*"
      constraint: ["hdd_ssd"]
    paths:
      hdd: /mnt/hdd
      ssd_scratch: /scratch/ssd
  Z:
    match:
      partition: ["gb10"]
      hostname_pattern: "nodeZ.*"
      constraint: ["unified_mem"]
    paths:
      unified: /workspace
```

### 4.2 実験定義YAML(例)

```yaml
purpose: dev                       # dev | campaign
repetitions: 3
cache_policy:
  mode: cold                       # cold | warm | auto
  drop_caches_strategy: sudo_tee   # config駆動でStrategy差し替え

matrix:
  format: [raw, webdataset]
  storage: [nfs, ssd_scratch]
  num_workers: [0, 8]
  shuffle_mode: [shard, full]
  decode: [true]

dataset:
  ref: synth_v1                    # datagenで生成したデータセットの識別名
  shard_size_bytes: 536870912      # webdataset用。フォーマット別に分岐可

output:
  jsonl: results/trials.jsonl
  purpose_tag: dev
```

CLIはこのYAMLを展開し、逐次実行 or Slurmジョブ投入する。即席のコマンドライン実行(YAMLなし)も可能だが、使用条件は必ず結果レコードに記録する(goal.md 2.3.5 の要求)。

## 5. CLI設計(`iobench <subcommand>`)

| サブコマンド | 主な引数 | 内容 |
|---|---|---|
| `iobench probe` | `[--nodes-config PATH]` | 現ノードを分類しProbeResultをJSON表示 |
| `iobench storage` | `--target PATH` `--preset NAME` `[--list-presets]` `[--runtime SEC]` | fioプリセット実行(NFS小ファイルプリセット含む) |
| `iobench datagen` | `--format {raw,webdataset,hdf5,zarr_v3,zarr_v2}` `--out PATH` `--num-images N` `[--height/--width]` `[--files-per-dir\|--shard-size\|--chunk-size]` `--seed` | 合成データ生成(実装確定、design当初の`--size`から`--num-images`に変更) |
| `iobench loader` | `--config exp.yaml` or 個別フラグ | DataLoader計測 |
| `iobench staging` | `--tool {cp,rsync,tar,parallel_rsync}` `--bwlimit` | 転送計測+E閾値算出 |
| `iobench multi` | `--n {2,4,8}` `--base-config PATH` | 多重負荷オーケストレーション |
| `iobench slurm` | `submit --pattern {A,B,C}` `template --pattern {A,B,C}` | sbatch生成・投入 |
| `iobench report` | `--jsonl PATH` `--out DIR` | 集計表・グラフ生成 |
| `iobench clean` | `[--yes]` `[--dry-run]` | ベンチデータ・キャッシュ削除 |

全サブコマンドは共通で `--nodes-config`(既定 `configs/nodes.yaml`)を受け付け、実行前に `probe` を内部で走らせ分類失敗ならエラー終了する。

## 6. 未確定事項(引き続き人間確認待ち。設計はconfig差し替えのみで対応可能な形にしてあるため実装をブロックしない)

- 構成X/Y/Zの実ノード名・パーティション名・constraint → `configs/nodes.yaml` の `match` を書き換えるだけ
- 各ストレージの実マウントパス・空き容量 → `configs/nodes.yaml` の `paths` を書き換えるだけ
- drop_cachesの具体運用方法 → `DropCachesStrategy` 実装追加で対応。当面は `sudo_tee` を既定実装として進める
- 実ワークロード想定(画像サイズ・総量・モデル種別・エポック数・同時ジョブ数) → `datagen`/実験YAMLのパラメータであり、決まればYAMLの値を変えるだけ。当面はWSI-AD相当(既存プロジェクトの想定)を仮パラメータとして進めてよいか確認中

## 7. フェーズ1完了条件

- [x] モジュール構成の確定(本文書2節)
- [x] 結果スキーマの確定(本文書3節)
- [x] 設定YAMLスキーマの確定(本文書4節)
- [x] CLIインタフェースの確定(本文書5節)
- [ ] **人間によるレビュー承認**(→ 承認後フェーズ2: probe/cache/sidecar/results/storage/datagenの実装に着手)
