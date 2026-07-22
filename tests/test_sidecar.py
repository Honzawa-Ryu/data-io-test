import re

from iobench.sidecar import SidecarSession


def test_missing_command_is_skipped_gracefully(tmp_path, monkeypatch):
    # shutil.which を常にNoneにして、コマンド不在時の分岐を検証する
    import iobench.sidecar as sc

    monkeypatch.setattr(sc.shutil, "which", lambda _: None)
    with SidecarSession("trial_missing", out_dir=str(tmp_path)) as s:
        pass
    log = (tmp_path / "trial_missing" / "iostat.log").read_text()
    assert "見つからない" in log
    # 例外を出さずにセッションが完了すること
    assert s.ref.endswith("trial_missing")


def test_real_command_lines_are_stamped_with_elapsed_seconds(tmp_path, monkeypatch):
    # iostat/vmstatの代わりに、確実に存在する `seq` を1行ずつ出すコマンドで代用する。
    import iobench.sidecar as sc

    monkeypatch.setattr(sc.shutil, "which", lambda name: "/usr/bin/env")

    real_start = SidecarSession._start

    def fake_start(self, name, cmd):
        # iostatのときだけ短い出力を出すコマンドに差し替える
        if name == "iostat":
            return real_start(self, name, ["seq", "1", "3"])
        # vmstat/dmonは起動しない
        return None

    monkeypatch.setattr(SidecarSession, "_start", fake_start)

    with SidecarSession("trial_stamp", out_dir=str(tmp_path)) as s:
        import time

        time.sleep(0.2)

    lines = (tmp_path / "trial_stamp" / "iostat.log").read_text().splitlines()
    data_lines = [ln for ln in lines if not ln.startswith("#")]
    assert len(data_lines) >= 1
    # 各データ行が "<経過秒>\t<元の行>" 形式であること
    for ln in data_lines:
        m = re.match(r"^\d+\.\d+\t", ln)
        assert m is not None, f"経過秒スタンプがない: {ln!r}"
