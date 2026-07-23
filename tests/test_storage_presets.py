import pytest

from iobench.storage.fio_runner import (
    FioNotFoundError,
    build_fio_command,
    parse_fio_result,
    run_fio,
)
from iobench.storage.presets import get_preset, iter_presets


def test_preset_count_matches_matrix():
    # 2パターン × 4ブロックサイズ × 2iodepth × 2numjobs = 32
    assert len(list(iter_presets())) == 32


def test_get_preset_roundtrip():
    p = get_preset("seq_1m_qd32_nj8")
    assert p["rw"] == "read"
    assert p["bs"] == "1m"
    assert p["iodepth"] == 32
    assert p["numjobs"] == 8


def test_get_unknown_preset_raises():
    with pytest.raises(ValueError):
        get_preset("does_not_exist")


def test_parse_fio_result_sums_read_write():
    raw = {
        "jobs": [
            {
                "read": {"bw": 1024, "iops": 100.0},
                "write": {"bw": 0, "iops": 0.0},
            }
        ]
    }
    parsed = parse_fio_result(raw)
    assert parsed["throughput_mb_s"] == pytest.approx(1.0)
    assert parsed["iops"] == pytest.approx(100.0)


def test_build_fio_command_has_expected_args():
    preset = get_preset("rand_128k_qd32_nj8")
    cmd = build_fio_command(preset, "/scratch/x", runtime_sec=15, size="2G")
    assert cmd[0] == "fio"
    assert "--rw=randread" in cmd
    assert "--bs=128k" in cmd
    assert "--iodepth=32" in cmd
    assert "--numjobs=8" in cmd
    assert "--ioengine=libaio" in cmd
    assert "--direct=1" in cmd
    assert "--runtime=15" in cmd
    assert "--size=2G" in cmd
    assert "--output-format=json" in cmd
    # filename が target_dir 配下を指す
    assert any(a.startswith("--filename=/scratch/x/") for a in cmd)


def test_run_fio_without_fio_raises_helpful_error(monkeypatch, tmp_path):
    import iobench.storage.fio_runner as fr

    monkeypatch.setattr(fr.shutil, "which", lambda _: None)
    with pytest.raises(FioNotFoundError):
        run_fio(get_preset("seq_4k_qd1_nj1"), str(tmp_path))
