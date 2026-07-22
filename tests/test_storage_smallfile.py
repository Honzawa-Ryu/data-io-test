from iobench.storage.smallfile import run_smallfile_benchmark


def test_smallfile_benchmark_returns_positive_rates(tmp_path):
    metrics = run_smallfile_benchmark(str(tmp_path), file_count=50, file_size_bytes=256)
    assert metrics["write_ops_s"] > 0
    assert metrics["meta_ops_s"] > 0
    assert metrics["read_ops_s"] > 0
    # 後始末されクリーンな状態に戻ること
    assert list(tmp_path.iterdir()) == []
