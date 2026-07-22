import pytest

from iobench.config import NodeClassConfig, NodeClassMatch, NodesConfig
from iobench.probe import ProbeClassificationError, run_probe


def _cfg() -> NodesConfig:
    return NodesConfig(
        node_classes={
            "X": NodeClassConfig(match=NodeClassMatch(hostname_pattern="*creator*"), paths={"nfs": "/n"}),
            "Y": NodeClassConfig(match=NodeClassMatch(hostname_pattern="*andre01*"), paths={"hdd": "/h"}),
        }
    )


def test_force_node_class_bypasses_classification():
    # hostnameが何であれ、明示指定した構成になる
    result = run_probe(_cfg(), force_node_class="X")
    assert result.node_class == "X"
    assert "nfs" in result.resolved_paths


def test_force_node_class_env_var(monkeypatch):
    monkeypatch.setenv("IOBENCH_NODE_CLASS", "Y")
    result = run_probe(_cfg())
    assert result.node_class == "Y"


def test_force_invalid_node_class_raises():
    with pytest.raises(ProbeClassificationError):
        run_probe(_cfg(), force_node_class="Q")
