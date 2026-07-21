# template-paper
論文公開用テンプレート

`template-dev`を基礎とし, 論文の結果の**再現性**を担保することを最優先としたテンプレート。第三者がリポジトリの指示に従うだけで論文の図や数値を再現できる状態を目指す。  
Slurmでの利用が可能なように環境構築、実行のスクリプトを含む。


## 特徴

  - **再現手順のスクリプト化**: `scripts/`に番号付きの実行スクリプトを配置し、再現手順を明確化する。
  - **データの流れを分離**: `data` (入力データ), `results/` (生成物) を分離し, データの流れを追跡しやすくする。
  - **再現ガイド中心の`README.md`**: `README.md`は, 論文の読者が結果を再現するためのガイドとしての役割を最優先する。

## ディレクトリ構成

```
.
├── data/                  
├── notebooks/
│   └── make_figures.ipynb # 論文の図を生成する最終版ノートブック
├── results/
│   ├── figures/      # 生成された図
│   └── models/       # 訓練済みモデル
├── scripts/
│   ├── 01_preprocess.py  # 再現手順1: 前処理
│   └── 02_train.py       # 再現手順2: モデル訓練, 等
├── src/
│   └── my_project/
│       ├── init.py
│       └── core.py
├── .gitignore
├── LICENSE
├── env.def          # 基本的な環境情報をまとめたもの
├── make_sif.sh      # Apptainer構築のシェルスクリプト
├── pyproject.toml
├── setup_venv.sh    # 環境構築のシェルスクリプト
├── run.sh           # 実行用シェルスクリプト
└── README.md
```

## 利用手順

### 1\. リポジトリの作成

GitHub上で "Use this template" ボタンを押し, 新規リポジトリを作成する。

### 2\. 環境のセットアップ

ローカルにクローン後, 以下のコマンドを実行する。

```bash
# clone
git clone -b {branch名} {repository URL}
cd {repository名}
```
基本インストール (開発環境が整っているコンテナではこれでOK)。

```bash
# 編集可能モードでインストールすることでsrc以下の編集が即座に反映される
pip install -e "."
```

開発用ツールも含めたフルインストールの場合は以下 (詳細はtoml参照)
```bash
pip install -e ".[dev]"
```

### 3\. プロジェクト名の設定

1.  `pyproject.toml` 内の `name` を変更する。
2.  `src/my_project` ディレクトリ名を `pyproject.toml` の `name` と一致させる。

## 再現ワークフロー

1.  データ準備: 論文で用いる生データを```data```に配置する。必要であれば, ダウンロード方法を```README.md```に記述する。
2.  コード実装: モデル定義やデータ処理など, プロジェクトの中核となるロジックを```src/```以下に記述する。
3.  再現スクリプト作成: 論文の結果を再現するための一連の処理を, ```scripts/```に番号付きのスクリプトとして作成する (01_preprocess.py -> 02_train.py ...)。各スクリプトは ```data```からデータを読み込み, ```results/```に成果物を出力するように記述する。
4.  図の作成: ```notebooks/```で, ```results/```に保存された実験結果を読み込み, 論文に掲載する図を作成・保存する。3の過程で出力されるならその旨を記し, 全てのFigureの出所がここからわかるようにする。
5.  README.mdの編集: 下記の英語テンプレートを編集し, 第三者が迷わずに結果を再現できるよう, 具体的な手順を記述する。


***
***
***
# ▼ テンプレート利用時は上記を全て削除し, 以下をプロジェクトに合わせて編集する ▼
***

# Official Code for "[Paper Title Here]"
This is the official repository for our paper:

> **[Full Paper Title Here]**<br>
> [Author 1], [Author 2], and [Author 3]<br>
> *[Journal or Conference Name]*, 2025.<br>
> [[Link to Paper]](https://example.com) | [[arXiv]](https://arxiv.org/abs/xxxx.xxxxx)

## Abstract
a brief abstract of the paper.  

## Installation
You can install this package from PyPI.  

```bash
pip install {project_name}
```

Alternatively, install the latest version directly from the GitHub repository:

```bash
pip install git+[repository URL]
```

## Directory Structure
```
.
├── notebooks/            # example notebooks
│   └── usage_example.ipynb
├── src/
│   └── my_project/       # source codes
│       ├── init.py
│       ├── cli.py        # CLI entry point
│       └── core.py
├── tests/                # test codes
│   └── test_module.py
├── .gitignore
├── LICENSE               
├── pyproject.toml        
└── README.md             
```

## Requirements
All dependencies are listed in the pyproject.toml file.  


## Installation for Reproducing the Results
Clone this repository and install the required packages in editable mode. We recommend using a virtual environment.  

```bash
# Clone the repository
git clone {repository_URL}
cd {repository_name}

# Install dependencies
pip install -e .

```

## How to Cite
If you find this work useful for your research, please consider citing our paper:  

```
@article{YourLastName2025,
  title   = {{Paper Title Here}},
  author  = {Author 1 and Author 2 and Author 3},
  journal = {Journal or Conference Name},
  year    = {2025},
}
```
    
## License
This project is licensed under the MIT License.  
See the LICENSE file for details.  

## Authors
- [YOUR NAME](LINK OF YOUR GITHUB PAGE)  
    - main contributor  
- [Tadahaya Mizuno](https://github.com/tadahayamiz)  
    - correspondence  

## Contact
- [your_name] - [your_address]

- [Tadahaya Mizuno] - tadahaya[at]gmail.com (lead contact)
