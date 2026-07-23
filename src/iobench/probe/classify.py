"""ノードをconfigの node_classes に対して分類する。一致しない/曖昧な場合は必ず例外で止める。"""

from __future__ import annotations

import fnmatch

from iobench.config import NodeClassConfig, NodesConfig


class ProbeClassificationError(RuntimeError):
    """このノードを構成X/Y/Zのいずれにも一意に分類できなかった。黙って計測を続行してはならない。"""


def classify_node(nodes_config: NodesConfig, hostname: str) -> str:
    """ホスト名パターン(glob)を評価し、一致する構成クラス名を返す。"""
    matched = [
        name
        for name, cfg in nodes_config.node_classes.items()
        if cfg.hostname_pattern and fnmatch.fnmatch(hostname, cfg.hostname_pattern)
    ]

    if not matched:
        raise ProbeClassificationError(
            f"ノードを構成に分類できません(hostname={hostname!r})。"
            f"configs/nodes.yaml の hostname_pattern を確認してください。"
        )

    if len(matched) > 1:
        raise ProbeClassificationError(
            f"ノードが複数の構成 {matched} に一致し曖昧です(hostname={hostname!r})。"
            f"hostname_pattern の重複を解消してください。"
        )

    return matched[0]
