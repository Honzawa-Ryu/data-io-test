import pytest

from iobench.config import NodeClassConfig, NodeClassMatch, NodesConfig
from iobench.probe.classify import ProbeClassificationError, classify_node


def _nodes_config() -> NodesConfig:
    return NodesConfig(
        node_classes={
            "X": NodeClassConfig(
                match=NodeClassMatch(partition=["gpu-x"], hostname_pattern="*creator*"),
                paths={"nfs": "/mnt/nfs"},
            ),
            "Y": NodeClassConfig(
                match=NodeClassMatch(partition=["cpu-y"], hostname_pattern="*andre01*"),
                paths={"hdd": "/mnt/hdd"},
            ),
            "Z": NodeClassConfig(
                match=NodeClassMatch(constraint=["gb10"]),
                paths={"unified": "/workspace"},
                unified_memory=True,
            ),
        }
    )


def _shared_partition_config() -> NodesConfig:
    """実クラスタ想定: X/Y/Zがパーティションを共有し、hostnameだけが識別子。"""
    parts = ["x-large", "large", "medium", "small"]
    return NodesConfig(
        node_classes={
            "X": NodeClassConfig(match=NodeClassMatch(partition=parts, hostname_pattern="*creator*"), paths={"nfs": "/n"}),
            "Y": NodeClassConfig(match=NodeClassMatch(partition=parts, hostname_pattern="*andre01*"), paths={"hdd": "/h"}),
            "Z": NodeClassConfig(match=NodeClassMatch(partition=parts, hostname_pattern="*grace02*", constraint=["gb10"]), paths={"unified": "/w"}),
        }
    )


def test_classify_by_glob_hostname_and_partition():
    cfg = _nodes_config()
    assert classify_node(cfg, "gpu-creator-01", "gpu-x", "") == "X"


def test_classify_requires_all_specified_conditions():
    # partitionが一致してもhostnameが一致しなければ、そのクラスにはならない(AND)
    cfg = _nodes_config()
    with pytest.raises(ProbeClassificationError):
        classify_node(cfg, "unrelated-host", "gpu-x", "")


def test_classify_by_constraint_only():
    cfg = _nodes_config()
    assert classify_node(cfg, "unrelated-host", None, "gb10,other") == "Z"


def test_shared_partition_discriminated_by_hostname():
    # 全構成が同じパーティションを持つ実クラスタ構成でも、hostnameで一意に分類できる
    cfg = _shared_partition_config()
    assert classify_node(cfg, "node-andre01", "large", "") == "Y"
    assert classify_node(cfg, "node-creator", "large", "") == "X"
    assert classify_node(cfg, "node-grace02", "large", "gb10") == "Z"


def test_no_match_raises():
    cfg = _nodes_config()
    with pytest.raises(ProbeClassificationError):
        classify_node(cfg, "unknown-host", "other-partition", "")


def test_ambiguous_raises():
    # 2つのクラスが全条件一致する曖昧なケース
    parts = ["p"]
    cfg = NodesConfig(
        node_classes={
            "X": NodeClassConfig(match=NodeClassMatch(partition=parts, hostname_pattern="*node*"), paths={}),
            "Y": NodeClassConfig(match=NodeClassMatch(partition=parts, hostname_pattern="*node*"), paths={}),
        }
    )
    with pytest.raises(ProbeClassificationError):
        classify_node(cfg, "my-node-1", "p", "")
