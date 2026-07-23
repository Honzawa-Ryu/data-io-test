"""iobench 統一CLIエントリポイント。

probe/storage/datagen/loader/staging/multi/slurm/report/clean の各サブコマンドを提供する。
"""

from __future__ import annotations

import shutil
from pathlib import Path

import click
import yaml

from iobench.config import NodesConfig


def _load_nodes_config(path: str) -> NodesConfig:
    p = Path(path)
    if not p.exists():
        raise click.ClickException(
            f"ノード構成ファイルが見つかりません: {path}\n"
            "configs/nodes.example.yaml をコピーして環境に合わせて編集してください。"
        )
    data = yaml.safe_load(p.read_text())
    return NodesConfig.model_validate(data)


@click.group()
@click.option(
    "--nodes-config",
    default="configs/nodes.yaml",
    show_default=True,
    help="ノード構成定義YAMLのパス",
)
@click.pass_context
def main(ctx: click.Context, nodes_config: str) -> None:
    """異種Slurmノード向けIO・データ供給性能ベンチマークライブラリ。"""
    ctx.ensure_object(dict)
    ctx.obj["nodes_config"] = nodes_config


@main.command()
@click.option("--node-class", "node_class", default=None, help="構成を明示指定し自動分類をスキップ(X/Y/Z)")
@click.pass_context
def probe(ctx: click.Context, node_class: str | None) -> None:
    """現ノードを分類し、ProbeResultをJSONで表示する。

    hostnameパターンが合わないマシンでは --node-class か環境変数 IOBENCH_NODE_CLASS で明示できる。
    """
    from iobench.probe import ProbeClassificationError, run_probe

    nodes_config = _load_nodes_config(ctx.obj["nodes_config"])
    try:
        result = run_probe(nodes_config, force_node_class=node_class)
    except ProbeClassificationError as e:
        raise click.ClickException(str(e)) from e
    click.echo(result.model_dump_json(indent=2))


@main.command()
@click.option("--target", required=True, help="計測対象のパス")
@click.option("--preset", default=None, help="fioプリセット名(iobench storage --list-presetsで一覧表示)")
@click.option("--list-presets", is_flag=True, default=False, help="利用可能なプリセット一覧を表示して終了")
@click.option("--runtime", default=10, show_default=True, type=int, help="fio実行時間(秒)")
@click.pass_context
def storage(
    ctx: click.Context,
    target: str,
    preset: str | None,
    list_presets: bool,
    runtime: int,
) -> None:
    """fioプリセット(またはNFS小ファイルベンチ)を実行しストレージ素性を計測する。"""
    from iobench.storage import (
        NFS_SMALLFILE_PRESET,
        FioNotFoundError,
        get_preset,
        iter_presets,
        parse_fio_result,
        run_fio,
        run_smallfile_benchmark,
    )

    if list_presets:
        for p in iter_presets():
            click.echo(p["name"])
        click.echo(NFS_SMALLFILE_PRESET["name"])
        return

    if preset is None:
        raise click.UsageError("--preset を指定してください(--list-presets で一覧表示)")

    if preset == NFS_SMALLFILE_PRESET["name"]:
        metrics = run_smallfile_benchmark(
            target,
            file_count=NFS_SMALLFILE_PRESET["file_count"],
            file_size_bytes=NFS_SMALLFILE_PRESET["file_size_bytes"],
        )
    else:
        preset_cfg = get_preset(preset)
        try:
            raw = run_fio(preset_cfg, target, runtime_sec=runtime)
        except FioNotFoundError as e:
            raise click.ClickException(str(e)) from e
        metrics = parse_fio_result(raw)

    click.echo(metrics)


@main.command()
@click.option(
    "--format",
    "fmt",
    required=True,
    type=click.Choice(["raw", "webdataset", "hdf5", "zarr"]),
)
@click.option("--out", required=True, help="出力先パス")
@click.option("--num-images", required=True, type=int, help="生成する画像枚数")
@click.option("--height", default=512, show_default=True, type=int)
@click.option("--width", default=512, show_default=True, type=int)
@click.option("--files-per-dir", default=1000, show_default=True, type=int, help="raw用: ディレクトリあたりファイル数")
@click.option("--shard-size", "shard_size_bytes", default=512 * 1024 * 1024, show_default=True, type=int, help="webdataset用シャードサイズ(bytes)")
@click.option("--chunk-size", "chunk_size_bytes", default=1024 * 1024, show_default=True, type=int, help="hdf5/zarr用チャンクサイズ(bytes)")
@click.option("--skip-v2", is_flag=True, default=False, help="zarr用: 参考用Zarr v2の生成を省略する")
@click.option("--seed", default=0, show_default=True, type=int)
@click.pass_context
def datagen(
    ctx: click.Context,
    fmt: str,
    out: str,
    num_images: int,
    height: int,
    width: int,
    files_per_dir: int,
    shard_size_bytes: int,
    chunk_size_bytes: int,
    skip_v2: bool,
    seed: int,
) -> None:
    """合成画像データセットを指定フォーマットで生成する。

    --format zarr は goal.md 2.5 の「Zarr v3 sharded + 参考用Zarr v2」を同一seedで
    同時生成する(v3が主系列、v2は比較用参考コピー)。--skip-v2 でv2生成を省略できる。
    """
    from iobench.datagen import generate_hdf5, generate_raw, generate_webdataset, generate_zarr_pair

    if fmt == "raw":
        meta = generate_raw(out, num_images, files_per_dir=files_per_dir, height=height, width=width, seed=seed)
    elif fmt == "webdataset":
        meta = generate_webdataset(out, num_images, shard_size_bytes=shard_size_bytes, height=height, width=width, seed=seed)
    elif fmt == "hdf5":
        meta = generate_hdf5(out, num_images, chunk_size_bytes=chunk_size_bytes, height=height, width=width, seed=seed)
    else:
        meta = generate_zarr_pair(
            out, num_images, chunk_size_bytes=chunk_size_bytes, height=height, width=width, seed=seed, skip_v2=skip_v2
        )

    click.echo(meta)


@main.command()
@click.option("--config", "config_path", required=True, help="実験定義YAMLのパス")
@click.option("--dataset-root", required=True, help="ストレージ論理パス配下のデータセット相対パス(datagen --outと対応)")
@click.option("--batch-size", default=32, show_default=True, type=int)
@click.option("--to-gpu", is_flag=True, default=False, help="バッチをGPUへ転送しGPU idle率も計測する")
@click.option("--node-class", "node_class", default=None, help="構成を明示指定し自動分類をスキップ(X/Y/Z)")
@click.pass_context
def loader(
    ctx: click.Context,
    config_path: str,
    dataset_root: str,
    batch_size: int,
    to_gpu: bool,
    node_class: str | None,
) -> None:
    """PyTorch DataLoaderで1エポック読み切り計測を、実験マトリクス×反復で実行する。"""
    import yaml

    from iobench.config import ExperimentConfig
    from iobench.loaderbench.runner import run_experiment

    nodes_config = _load_nodes_config(ctx.obj["nodes_config"])
    exp_data = yaml.safe_load(Path(config_path).read_text())
    cfg = ExperimentConfig.model_validate(exp_data)

    records = run_experiment(
        cfg, nodes_config, dataset_root, batch_size=batch_size, to_gpu=to_gpu,
        force_node_class=node_class,
    )
    click.echo(f"{len(records)}試行を記録しました -> {cfg.output.jsonl}")


@main.command()
@click.option(
    "--tool",
    required=True,
    type=click.Choice(["cp", "rsync", "tar", "parallel_rsync"]),
)
@click.option("--src", required=True, help="転送元パス")
@click.option("--dst", required=True, help="転送先パス(SSD scratch等)")
@click.option("--bwlimit", default=None, help="転送帯域制限(rsync系のみ、例: 100m)")
@click.option(
    "--format",
    "fmt",
    required=True,
    type=click.Choice(["raw", "webdataset", "hdf5", "zarr_v3", "zarr_v2"]),
    help="転送するデータのレイアウト(reportでloader結果と突合する結合キー)",
)
@click.option(
    "--jsonl",
    "jsonl_path",
    default="results/trials_staging.jsonl",
    show_default=True,
    help="結果を追記するJSON Linesパス",
)
@click.option(
    "--cache-state",
    type=click.Choice(["cold", "warm"]),
    default="warm",
    show_default=True,
    help="投入直前に外部でdrop_caches済みならcold(external運用)。それ以外はwarm",
)
@click.option("--purpose", type=click.Choice(["dev", "campaign"]), default="dev", show_default=True)
@click.option("--src-logical", default=None, help="srcの論理ストレージ名(自動解決できないとき明示)")
@click.option("--dst-logical", default=None, help="dstの論理ストレージ名(自動解決できないとき明示)")
@click.option("--node-class", "node_class", default=None, help="構成を明示指定し自動分類をスキップ")
@click.pass_context
def staging(
    ctx: click.Context,
    tool: str,
    src: str,
    dst: str,
    bwlimit: str | None,
    fmt: str,
    jsonl_path: str,
    cache_state: str,
    purpose: str,
    src_logical: str | None,
    dst_logical: str | None,
    node_class: str | None,
) -> None:
    """ソース→SSDの転送を計測し(T_stage)、結果をJSONLへ記録する。

    損益分岐Eは iobench report が同じjsonl群のloader結果と突合して算出する。
    """
    from iobench.gitinfo import get_git_hash
    from iobench.probe import ProbeClassificationError, run_probe
    from iobench.results.writer import append_record
    from iobench.staging import build_staging_record, run_transfer

    nodes_config = _load_nodes_config(ctx.obj["nodes_config"])
    try:
        probe_result = run_probe(nodes_config, force_node_class=node_class)
    except ProbeClassificationError as e:
        raise click.ClickException(str(e)) from e

    result = run_transfer(tool, src, dst, bwlimit=bwlimit)
    click.echo(
        f"tool={result.tool} bytes={result.total_bytes} "
        f"T_stage={result.elapsed_seconds:.3f}s throughput={result.throughput_mb_s:.2f}MB/s"
    )

    try:
        record = build_staging_record(
            result,
            probe_result,
            fmt=fmt,
            cache_state=cache_state,
            purpose=purpose,
            library_version=get_git_hash(),
            src_logical=src_logical,
            dst_logical=dst_logical,
        )
    except ValueError as e:
        raise click.ClickException(str(e)) from e
    append_record(record, jsonl_path)
    click.echo(f"1試行を記録しました -> {jsonl_path}")


@main.command()
@click.option("--baseline-jsonl", required=True, help="単独実行の結果JSONL")
@click.option("--multi-jsonl", required=True, help="N本同時実行の結果JSONL")
@click.pass_context
def multi(ctx: click.Context, baseline_jsonl: str, multi_jsonl: str) -> None:
    """単独実行とN本同時実行の結果を突合し、多重負荷劣化率を集計する。

    ジョブ投入は `sbatch scripts/run_loader.sh` をN本同一ノードへ流すか
    `iobench slurm` のパターン生成物を使う。本コマンドは結果集計を担う。
    """
    from iobench.multi import compute_degradation
    from iobench.results.writer import load_records

    baseline = load_records(baseline_jsonl)
    multi_recs = load_records(multi_jsonl)
    for d in compute_degradation(baseline, multi_recs):
        click.echo(
            f"{d.condition_key} concurrency={d.concurrency} "
            f"baseline={d.baseline_samples_s:.0f}sps multi={d.multi_samples_s_mean:.0f}sps "
            f"degradation_ratio={d.degradation_ratio:.3f}"
        )


@main.group()
def slurm() -> None:
    """sbatchテンプレート生成・投入(ステージング運用パターンA/B/C)。"""


@slurm.command("template")
@click.option("--pattern", required=True, type=click.Choice(["A", "B", "C"]))
@click.option("--out-dir", default="results/slurm_templates", show_default=True)
@click.option("--src", required=True, help="ステージング元パス(NFS/HDD)")
@click.option("--exp-yaml", required=True, help="学習に使う実験定義YAML")
@click.option("--dataset-root", required=True, help="dataset_root(datagen --outと対応)")
@click.option("--ssd-dst", default="$SLURM_TMPDIR/iobench_stage", show_default=True, help="A/B用: SSD転送先")
@click.option("--cpu-partition", default="cpu", show_default=True, help="B用: 転送ジョブのパーティション")
@click.option("--train-node", default="NODE", show_default=True, help="B用: -w固定する学習ノード名")
@click.option("--cache-root", default="/scratch/cache", show_default=True, help="C用: 共有キャッシュのルート")
@click.option("--dataset-ref", default="dataset", show_default=True, help="C用: dataset_hash生成の種")
@click.option("--cache-cap-gb", default=500, show_default=True, type=int, help="C用: LRU容量上限GB")
def slurm_template(
    pattern: str,
    out_dir: str,
    src: str,
    exp_yaml: str,
    dataset_root: str,
    ssd_dst: str,
    cpu_partition: str,
    train_node: str,
    cache_root: str,
    dataset_ref: str,
    cache_cap_gb: int,
) -> None:
    """指定パターンのsbatchスクリプト群を生成しファイルに書き出す。"""
    from iobench.slurm import dataset_hash, write_pattern

    if pattern == "A":
        written = write_pattern("A", out_dir, src=src, ssd_dst=ssd_dst, exp_yaml=exp_yaml, dataset_root=dataset_root)
    elif pattern == "B":
        written = write_pattern(
            "B", out_dir, src=src, ssd_dst=ssd_dst, exp_yaml=exp_yaml, dataset_root=dataset_root,
            cpu_partition=cpu_partition, train_node=train_node,
        )
    else:
        written = write_pattern(
            "C", out_dir, src=src, dataset_hash=dataset_hash(dataset_ref), cache_root=cache_root,
            exp_yaml=exp_yaml, dataset_root=dataset_root, cache_cap_gb=cache_cap_gb,
        )

    for p in written:
        click.echo(f"[generated] {p}")
    click.echo("投入前に生成物を確認し、必要ならノード名/パスを編集してください。")


@slurm.command("submit")
@click.argument("script_path")
@click.option("--dependency", default=None, help="afterok:JOBID 等のsbatch依存指定")
@click.option("-w", "node", default=None, help="ノード固定(-w)")
def slurm_submit(script_path: str, dependency: str | None, node: str | None) -> None:
    """生成済みsbatchスクリプトを投入する(sbatch --parsable のラッパ)。"""
    import subprocess

    if not Path(script_path).exists():
        raise click.ClickException(f"スクリプトが見つかりません: {script_path}")

    cmd = ["sbatch", "--parsable"]
    if dependency:
        cmd += ["--dependency", dependency]
    if node:
        cmd += ["-w", node]
    cmd.append(script_path)

    if shutil.which("sbatch") is None:
        raise click.ClickException(
            f"sbatch が見つかりません(Slurm環境で実行してください)。生成コマンド: {' '.join(cmd)}"
        )
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    click.echo(result.stdout.strip())


@main.command()
@click.option(
    "--jsonl",
    "jsonl_paths",
    required=True,
    multiple=True,
    help="結果JSON Linesのパス(複数指定可: loader系とstaging系をまとめて突合する)",
)
@click.option("--out", "out_dir", required=True, help="集計出力先ディレクトリ")
@click.option("--no-plots", is_flag=True, default=False, help="グラフ生成をスキップしCSVのみ出力")
@click.pass_context
def report(ctx: click.Context, jsonl_paths: tuple[str, ...], out_dir: str, no_plots: bool) -> None:
    """結果JSONL/CSVから集計表(中央値/min/max)・グラフ・損益分岐表を生成する。

    グラフ: スループット比較、シャード/チャンクサイズ掃引カーブ、(データがあれば)多重負荷劣化。
    staging試行とloader試行が両方あれば breakeven_table.csv(損益分岐エポック数E)も出力する。
    """
    from iobench.results import aggregate, check_cache_state_consistency, load_records, to_rows
    from iobench.results.report import build_breakeven_rows

    records = []
    for p in jsonl_paths:
        records.extend(load_records(p))
    check_cache_state_consistency(records)
    rows = to_rows(records)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    import pandas as pd

    pd.DataFrame(rows).to_csv(out / "trials_raw.csv", index=False)
    agg = aggregate(rows)
    agg.to_csv(out / "trials_aggregated.csv", index=False)

    breakeven_rows = build_breakeven_rows(records)
    generated = []
    if not no_plots:
        from iobench.results.plots import generate_all_plots

        generated = generate_all_plots(agg, str(out), breakeven_rows=breakeven_rows)
    elif breakeven_rows:
        from iobench.results.plots import write_breakeven_table

        table = write_breakeven_table(breakeven_rows, out)
        if table is not None:
            generated = [table]

    click.echo(
        f"raw={len(rows)}行, aggregated={len(agg)}グループ, breakeven={len(breakeven_rows)}行 -> {out}"
    )
    for p in generated:
        click.echo(f"[plot] {p}")


@main.command()
@click.option("--target", "targets", multiple=True, required=True, help="削除対象パス(複数指定可)")
@click.option("--yes", is_flag=True, default=False, help="確認なしで削除する")
@click.option("--dry-run", is_flag=True, default=False, help="削除対象を表示のみ")
@click.pass_context
def clean(ctx: click.Context, targets: tuple[str, ...], yes: bool, dry_run: bool) -> None:
    """指定したベンチデータ・キャッシュのパスを削除する(消し忘れ防止用)。"""
    paths = [Path(t) for t in targets]
    existing = [p for p in paths if p.exists()]

    if not existing:
        click.echo("削除対象は見つかりませんでした。")
        return

    for p in existing:
        click.echo(f"[target] {p}")

    if dry_run:
        click.echo("--dry-run のため削除は実行していません。")
        return

    if not yes:
        click.confirm(f"{len(existing)}件を削除しますか?", abort=True)

    for p in existing:
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        click.echo(f"[deleted] {p}")


if __name__ == "__main__":
    main()
