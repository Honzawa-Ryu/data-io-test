from pathlib import Path

import yaml

from iobench.config import ExperimentConfig, NodesConfig

CONFIGS_DIR = Path(__file__).resolve().parents[1] / "configs"


def test_nodes_example_parses():
    data = yaml.safe_load((CONFIGS_DIR / "nodes.example.yaml").read_text())
    cfg = NodesConfig.model_validate(data)
    assert set(cfg.node_classes) == {"X", "Y", "Z"}
    # Xは hostname_pattern で識別、nfs論理パスを持つ
    assert cfg.node_classes["X"].match.hostname_pattern == "*creator*"
    assert "nfs" in cfg.node_classes["X"].paths
    assert cfg.node_classes["Z"].unified_memory is True


def test_experiment_example_parses():
    data = yaml.safe_load((CONFIGS_DIR / "experiment.example.yaml").read_text())
    cfg = ExperimentConfig.model_validate(data)
    assert cfg.purpose == "dev"
    assert cfg.repetitions == 3
    assert "raw" in cfg.matrix.format
