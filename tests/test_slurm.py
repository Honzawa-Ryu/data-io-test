from iobench.slurm import dataset_hash, write_pattern


def test_dataset_hash_is_stable():
    assert dataset_hash("ds1") == dataset_hash("ds1")
    assert dataset_hash("ds1") != dataset_hash("ds2")
    assert len(dataset_hash("ds1")) == 16


def test_pattern_a_written(tmp_path):
    written = write_pattern(
        "A", str(tmp_path), src="/nfs/data", ssd_dst="/scratch/x",
        exp_yaml="exp.yaml", dataset_root="ds",
    )
    assert len(written) == 1
    content = (tmp_path / "stageA.sh").read_text()
    assert "rsync -a" in content
    assert "iobench loader" in content


def test_pattern_b_written(tmp_path):
    written = write_pattern(
        "B", str(tmp_path), src="/nfs/data", ssd_dst="/scratch/x",
        exp_yaml="exp.yaml", dataset_root="ds", cpu_partition="cpu", train_node="node01",
    )
    names = {p.split("/")[-1] for p in written}
    assert names == {"stageB_transfer.sh", "stageB_train.sh", "stageB_submit.sh"}
    submit = (tmp_path / "stageB_submit.sh").read_text()
    assert "afterok" in submit
    assert "node01" in submit


def test_pattern_c_written_with_flock_and_lru(tmp_path):
    written = write_pattern(
        "C", str(tmp_path), src="/nfs/data", dataset_hash="abc123",
        cache_root="/scratch/cache", exp_yaml="exp.yaml", dataset_root="ds", cache_cap_gb=100,
    )
    job = (tmp_path / "stageC.sh").read_text()
    assert "flock" in job
    assert ".complete" in job  # 存在チェックスキップ
    assert (tmp_path / "lru_evict.sh").exists()
    lru = (tmp_path / "lru_evict.sh").read_text()
    assert "evict" in lru
