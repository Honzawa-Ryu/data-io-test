"""ノードをconfigの node_classes に対して分類する。一致しない/曖昧な場合は必ず例外で止める。"""

from __future__ import annotations

import fnmatch

from iobench.config import NodeClassConfig, NodesConfig


class ProbeClassificationError(RuntimeError):
    """このノードを構成X/Y/Zのいずれにも一意に分類できなかった。黙って計測を続行してはならない。"""


def _class_matches(cls_cfg: NodeClassConfig, hostname: str, partition: str | None, constraint_str: str) -> bool:
    """指定された(空でない)条件が **すべて** 一致したときだけTrue(AND)。

    パーティションが複数構成で共有される実クラスタでは、OR判定だとパーティション一致だけで
    全構成にマッチし常に「曖昧」になる。そのため hostname_pattern 等で構成を絞り込めるよう
    AND判定にする。条件が1つも指定されていないクラスはマッチしない(分類根拠がないため)。
    hostname_pattern は glob(fnmatch)で評価する(例: "*-creator")。
    """
    m = cls_cfg.match
    constraints = {c for c in constraint_str.split(",") if c}

    specified = 0
    if m.partition:
        specified += 1
        if not (partition and partition in m.partition):
            return False
    if m.hostname_pattern:
        specified += 1
        if not fnmatch.fnmatch(hostname, m.hostname_pattern):
            return False
    if m.constraint:
        specified += 1
        if not (constraints & set(m.constraint)):
            return False

    return specified > 0


def classify_node(
    nodes_config: NodesConfig,
    hostname: str,
    partition: str | None,
    constraint_str: str,
) -> str:
    matched = [
        name
        for name, cfg in nodes_config.node_classes.items()
        if _class_matches(cfg, hostname, partition, constraint_str)
    ]
    if len(matched) == 0:
        raise ProbeClassificationError(
            f"ノードを構成に分類できません(hostname={hostname!r}, partition={partition!r}, "
            f"constraint={constraint_str!r})。configs/nodes.yaml の match 条件を確認してください。"
        )
    if len(matched) > 1:
        raise ProbeClassificationError(
            f"ノードが複数の構成 {matched} に一致し曖昧です(hostname={hostname!r}, "
            f"partition={partition!r}, constraint={constraint_str!r})。match条件の重複を解消してください。"
        )
    return matched[0]
