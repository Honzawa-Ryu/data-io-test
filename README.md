# iobench

異種構成のSlurm計算ノード(NFS+SSD構成 / HDD+SSD構成 / GB10ユニファイドメモリ構成)にまたがって、**統一的な方法でIO・データ供給性能を計測するベンチマークライブラリ**。

**使い方(Slurmジョブ投入の手順)は [docs/howto.md](docs/howto.md) を参照。** 詳細な設計は [docs/design.md](docs/design.md)、設定ファイルの書き方は [docs/config_schema.md](docs/config_schema.md)、開発の背景・要件は [goal.md](goal.md) を参照。

## ディレクトリ構成

```
.
├── configs/                     # ノード構成・実験定義YAMLのサンプル
│   ├── nodes.example.yaml       # クラスタのノード分類・パス解決(サイト固有)
│   └── experiment.example.yaml  # 実験マトリクス定義
├── docs/
│   └── design.md                # モジュール構成/結果スキーマ/CLI設計文書
├── src/iobench/
│   ├── probe/        # 環境自動検出・ノード構成(X/Y/Z)分類
│   ├── storage/      # fioラッパによるストレージ素性計測
│   ├── datagen/      # 合成データセット生成(raw/webdataset/hdf5/zarr)
│   ├── loaderbench/  # PyTorch DataLoader実効スループット計測(phase3)
│   ├── staging/      # 転送・ステージング計測(phase4)
│   ├── sidecar/      # iostat/vmstat/dmonの起動・回収
│   ├── cache/        # ページキャッシュ制御(drop_caches)
│   ├── results/      # 結果スキーマ、JSONL/CSV書き出し、集計
│   ├── slurm/        # sbatchテンプレート生成・投入(phase4)
│   ├── config.py     # nodes.yaml / 実験定義YAMLのスキーマ
│   └── cli.py         # `iobench` CLIエントリポイント
├── tests/            # 各モジュールの単体テスト
├── env.def           # Apptainerコンテナ定義
├── setup_venv.sh     # uv環境構築スクリプト
├── run.sh            # sbatch実行テンプレート
└── pyproject.toml
```

## セットアップ

```bash
# コンテナビルド + uv環境構築(Slurm interactive パーティション上で)
sbatch make_sif.sh
sbatch setup_venv.sh
source .venv/bin/activate
```

コンテナを使わない場合:

```bash
uv venv .venv && source .venv/bin/activate
uv sync
```

## クイックスタート

```bash
# 1. クラスタ固有のノード構成ファイルを作成する
cp configs/nodes.example.yaml configs/nodes.yaml
# configs/nodes.yaml を編集: ノード名/パーティション名/constraint、実マウントパスを記入

# 2. 現ノードの分類・環境情報を確認する
iobench --nodes-config configs/nodes.yaml probe

# 3. ストレージ素性を計測する
iobench storage --list-presets
iobench storage --target /scratch/ssd --preset seq_1m_qd1_nj1

# 4. 合成データセットを生成する
iobench datagen --format webdataset --out data/synth_dev --num-images 1000 --shard-size 536870912

# 5. 結果を集計する
iobench report --jsonl results/trials.jsonl --out results/report
```

## ノード追加手順

新しい計算ノード(構成)を追加する場合:

1. `configs/nodes.yaml` の `node_classes` に新しいキー(またはX/Y/Zいずれかへの追加match条件)を書く
2. `match` にホスト名パターン/パーティション名/constraint等の条件を書く(空でない条件は **すべて一致(AND)** したときに分類される)
3. `paths` に論理ストレージ名(`nfs`/`hdd`/`ssd_scratch`/`tmpfs`/`unified`)→実マウントパスを記入
4. `iobench probe` を新ノード上で実行し、意図した構成に分類されることを確認する(分類できない場合はエラーで停止するので、その場合はmatch条件を見直す)

## 開発状況

- フェーズ1(設計)〜フェーズ4(staging/multi/slurm)まで実装済み。全サブコマンドが機能する
  - `probe` / `storage` / `datagen` / `loader` / `staging` / `multi` / `slurm template|submit` / `report` / `clean`
- 合成データによるローカル検証は完了(全42単体テスト通過、パターンCのキャッシュスキップも実証済み)
- **未完了**: 実クラスタ上での検証(フェーズ3の構成Xスモークラン、フェーズ4の異種ノード受け入れ試験)は `configs/nodes.yaml` の実ノード情報が揃い次第実施する
- フェーズ5(計測キャンペーン)・フェーズ6(レポート)は未着手
- 詳細な進捗と各フェーズのレビューポイントは [goal.md](goal.md) の「開発フェーズ」節を参照

## ライセンス

[LICENSE](LICENSE) を参照。
