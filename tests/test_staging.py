import numpy as np

from iobench.staging.breakeven import compute_breakeven
from iobench.staging.transfer import run_transfer


def _make_tree(root, n_files=10, size=1024):
    root.mkdir(parents=True, exist_ok=True)
    for i in range(n_files):
        (root / f"f{i:03d}.bin").write_bytes(np.random.bytes(size))


def test_transfer_cp_copies_all(tmp_path):
    src = tmp_path / "src"
    _make_tree(src, n_files=5)
    result = run_transfer("cp", str(src), str(tmp_path / "dst"))
    assert result.total_bytes > 0
    assert result.elapsed_seconds >= 0
    copied = list((tmp_path / "dst").rglob("*.bin"))
    assert len(copied) == 5


def test_transfer_tar_pipe(tmp_path):
    src = tmp_path / "src"
    _make_tree(src, n_files=5)
    dst = tmp_path / "dst"
    result = run_transfer("tar", str(src), str(dst))
    assert result.tool == "tar"
    assert len(list(dst.rglob("*.bin"))) == 5


def test_breakeven_positive_saving():
    # T_stage=100s, direct=50s/ep, ssd=30s/ep -> saving=20s/ep -> E=ceil(100/20)=5
    r = compute_breakeven(100.0, 50.0, 30.0)
    assert r.per_epoch_saving_seconds == 20.0
    assert r.breakeven_epochs == 5


def test_breakeven_no_saving_returns_none():
    # SSDが直読みより遅い(あり得ないが)場合、ステージングは常に損
    r = compute_breakeven(100.0, 30.0, 50.0)
    assert r.breakeven_epochs is None
