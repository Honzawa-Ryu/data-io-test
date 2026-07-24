import numpy as np
import pytest

from iobench.results.schema import ProbeResult
from iobench.staging.breakeven import compute_breakeven
from iobench.staging.record import build_staging_record, resolve_storage_logical
from iobench.staging.transfer import TransferResult, run_transfer


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


def test_transfer_rsync_single_file(tmp_path):
    src = tmp_path / "ds.h5"
    src.write_bytes(np.random.bytes(2048))
    dst = tmp_path / "out" / "ds.h5"
    result = run_transfer("rsync", str(src), str(dst))
    assert dst.read_bytes() == src.read_bytes()
    assert result.total_bytes == 2048


def test_transfer_cp_single_file(tmp_path):
    src = tmp_path / "ds.h5"
    src.write_bytes(np.random.bytes(1024))
    dst = tmp_path / "out" / "ds.h5"
    run_transfer("cp", str(src), str(dst))
    assert dst.read_bytes() == src.read_bytes()


def test_transfer_cp_dir_copies_contents_not_nested(tmp_path):
    src = tmp_path / "src"
    _make_tree(src, n_files=3)
    dst = tmp_path / "dst"
    run_transfer("cp", str(src), str(dst))
    assert len(list(dst.glob("*.bin"))) == 3  # dst直下(src名で入れ子にならない)


def test_transfer_tar_rejects_single_file(tmp_path):
    src = tmp_path / "ds.h5"
    src.write_bytes(b"x" * 128)
    with pytest.raises(ValueError, match="ディレクトリ転送専用"):
        run_transfer("tar", str(src), str(tmp_path / "out"))


def test_run_transfer_missing_src_raises(tmp_path):
    with pytest.raises(FileNotFoundError, match="転送元が存在しません"):
        run_transfer("rsync", str(tmp_path / "no_such_dir"), str(tmp_path / "dst"))


def test_run_surfaces_stderr_on_failure():
    from iobench.staging.transfer import _run

    with pytest.raises(RuntimeError, match="boom"):
        _run(["bash", "-c", "echo boom >&2; exit 3"])


def test_breakeven_positive_saving():
    # T_stage=100s, direct=50s/ep, ssd=30s/ep -> saving=20s/ep -> E=ceil(100/20)=5
    r = compute_breakeven(100.0, 50.0, 30.0)
    assert r.per_epoch_saving_seconds == 20.0
    assert r.breakeven_epochs == 5


def test_breakeven_no_saving_returns_none():
    # SSDが直読みより遅い(あり得ないが)場合、ステージングは常に損
    r = compute_breakeven(100.0, 30.0, 50.0)
    assert r.breakeven_epochs is None


def _probe(resolved_paths: dict[str, str]) -> ProbeResult:
    return ProbeResult(
        hostname="andre01",
        node_class="andre01",
        cpu_cores=32,
        ram_gb=251.0,
        gpu_present=False,
        resolved_paths=resolved_paths,
    )


def _transfer_result(src: str, dst: str) -> TransferResult:
    return TransferResult(
        tool="rsync",
        src=src,
        dst=dst,
        total_bytes=3_000_000_000,
        elapsed_seconds=9.3,
        throughput_mb_s=326.0,
        bwlimit=None,
    )


def test_resolve_storage_logical_longest_match(tmp_path):
    paths = {"hdd": str(tmp_path / "ws"), "ssd_scratch": str(tmp_path / "ws" / "scratch")}
    assert resolve_storage_logical(str(tmp_path / "ws" / "ds"), paths) == "hdd"
    assert resolve_storage_logical(str(tmp_path / "ws" / "scratch" / "ds"), paths) == "ssd_scratch"
    assert resolve_storage_logical(str(tmp_path / "elsewhere"), paths) is None


def test_build_staging_record_resolves_and_fills(tmp_path):
    hdd = tmp_path / "hdd"
    ssd = tmp_path / "ssd"
    probe = _probe({"hdd": str(hdd), "ssd_scratch": str(ssd)})
    result = _transfer_result(str(hdd / "ds_raw"), str(ssd / "ds_raw"))

    record = build_staging_record(
        result, probe, fmt="raw", cache_state="cold", purpose="dev", library_version="abc123"
    )
    assert record.subcommand == "staging"
    assert record.condition.staging_tool == "rsync"
    assert record.condition.staging_src == "hdd"
    assert record.condition.staging_dst == "ssd_scratch"
    assert record.condition.storage_logical == "ssd_scratch"
    assert record.metrics.t_stage_seconds == 9.3
    assert record.metrics.staged_bytes == 3_000_000_000
    assert record.cache_state == "cold"


def test_build_staging_record_unresolvable_raises(tmp_path):
    probe = _probe({"hdd": str(tmp_path / "hdd")})
    result = _transfer_result(str(tmp_path / "unknown" / "ds"), str(tmp_path / "hdd" / "ds"))
    with pytest.raises(ValueError, match="src"):
        build_staging_record(
            result, probe, fmt="raw", cache_state="warm", purpose="dev", library_version="abc123"
        )


def test_build_staging_record_explicit_logical_overrides(tmp_path):
    probe = _probe({})
    result = _transfer_result(str(tmp_path / "a"), str(tmp_path / "b"))
    record = build_staging_record(
        result,
        probe,
        fmt="webdataset",
        cache_state="warm",
        purpose="dev",
        library_version="abc123",
        src_logical="nfs",
        dst_logical="ssd_scratch",
    )
    assert record.condition.staging_src == "nfs"
    assert record.condition.staging_dst == "ssd_scratch"
