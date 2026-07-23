import pytest

from iobench.config import NodeClassConfig, NodesConfig
from iobench.probe.classify import ProbeClassificationError, classify_node


def _nodes_config() -> NodesConfig:
    return NodesConfig(
        node_classes={
            "creator": NodeClassConfig(hostname_pattern="*creator*", paths={"nfs": "/mnt/nfs"}),
            "andre01": NodeClassConfig(hostname_pattern="*andre01*", paths={"hdd": "/mnt/hdd"}),
            "grace02": NodeClassConfig(
                hostname_pattern="*grace02*", paths={"unified": "/workspace"}, unified_memory=True
            ),
        }
    )


def test_classify_by_glob_hostname():
    cfg = _nodes_config()
    assert classify_node(cfg, "gpu-creator-01") == "creator"
    assert classify_node(cfg, "node-andre01") == "andre01"
    assert classify_node(cfg, "node-grace02") == "grace02"


def test_no_match_raises():
    cfg = _nodes_config()
    with pytest.raises(ProbeClassificationError):
        classify_node(cfg, "unknown-host")


def test_class_without_pattern_never_matches():
    # hostname_pattern未設定のクラスは分類候補にならない(全ホストに一致したりしない)
    cfg = NodesConfig(
        node_classes={
            "no_pattern": NodeClassConfig(paths={}),
            "andre01": NodeClassConfig(hostname_pattern="*andre01*", paths={}),
        }
    )
    assert classify_node(cfg, "x-andre01") == "andre01"
    with pytest.raises(ProbeClassificationError):
        classify_node(cfg, "other-host")


def test_ambiguous_raises():
    # 2クラスのパターンが同一ホストに一致する曖昧なケース
    cfg = NodesConfig(
        node_classes={
            "a": NodeClassConfig(hostname_pattern="*node*", paths={}),
            "b": NodeClassConfig(hostname_pattern="*node*", paths={}),
        }
    )
    with pytest.raises(ProbeClassificationError):
        classify_node(cfg, "my-node-1")
