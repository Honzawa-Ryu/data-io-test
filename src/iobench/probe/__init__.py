"""環境自動検出: ホスト/マウント/CPU・RAM・GPU情報の収集とノード構成(X/Y/Z)分類。"""

import os

from iobench.config import NodesConfig
from iobench.probe.classify import ProbeClassificationError, classify_node
from iobench.probe.system import (
    get_cpu_cores,
    get_gpu_info,
    get_hostname,
    get_ram_gb,
    get_slurm_env,
    list_mounts,
)
from iobench.results.schema import ProbeResult

__all__ = ["ProbeClassificationError", "run_probe"]


def run_probe(nodes_config: NodesConfig, force_node_class: str | None = None) -> ProbeResult:
    """現ノードを分類しProbeResultを返す。

    per-machineデプロイでhostnameパターンが合わない場合に備え、node_classを明示指定できる:
    - 引数 force_node_class、または環境変数 IOBENCH_NODE_CLASS で指定
    - 指定があれば自動分類をスキップする(自動判定は必須ではない、というユーザー運用に対応)
    """
    hostname = get_hostname()
    slurm = get_slurm_env()

    override = force_node_class or os.environ.get("IOBENCH_NODE_CLASS")
    if override:
        if override not in nodes_config.node_classes:
            raise ProbeClassificationError(
                f"指定された node_class '{override}' が configs/nodes.yaml に存在しません。"
                f"利用可能: {list(nodes_config.node_classes)}"
            )
        node_class = override
    else:
        node_class = classify_node(
            nodes_config, hostname, slurm["partition"], slurm["constraint"] or ""
        )
    cls_cfg = nodes_config.node_classes[node_class]

    resolved_paths = {k: v for k, v in cls_cfg.paths.items() if v is not None}
    if slurm["tmpdir"]:
        resolved_paths["tmpfs"] = slurm["tmpdir"]

    gpu_present, gpu_model = get_gpu_info()

    return ProbeResult(
        hostname=hostname,
        node_class=node_class,
        slurm_job_id=slurm["job_id"],
        slurm_partition=slurm["partition"],
        slurm_tmpdir=slurm["tmpdir"],
        mounts=list_mounts(),
        cpu_cores=get_cpu_cores(),
        ram_gb=get_ram_gb(),
        gpu_present=gpu_present,
        gpu_model=gpu_model,
        unified_memory=cls_cfg.unified_memory,
        resolved_paths=resolved_paths,
    )
