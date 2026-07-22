import pytest

from iobench.storage.fio_runner import parse_fio_result
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
