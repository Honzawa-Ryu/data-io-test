"""副計測(iostat/vmstat/nvidia-smi dmon)の起動・回収。試行IDに紐付けて保存する。

design.md 2.3 の設計コミットメント: 各ログ行に試行開始からの経過秒を付与する。
iostat/vmstatの出力タイミングはプロセス起動オーバーヘッドに左右されるため、
生の出力をそのまま保存すると後で metrics のタイムライン(first-batch latency等)と
突き合わせる際にズレる。そこで各行を読み取り時刻の経過秒でスタンプして書き出す。

対象コマンドがシステムに無い場合は、その旨をログファイルに記して黙って落とさず継続する
(sidecarが無いことは計測の失敗理由にしない。ただし結果には記録が残るので追跡できる)。
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
from pathlib import Path
from types import TracebackType


class SidecarSession:
    def __init__(
        self,
        trial_id: str,
        out_dir: str = "results/sidecar",
        gpu_present: bool = False,
    ) -> None:
        self.trial_id = trial_id
        self.dir = Path(out_dir) / trial_id
        self.gpu_present = gpu_present
        self._procs: dict[str, subprocess.Popen] = {}
        self._threads: list[threading.Thread] = []
        self._t0 = 0.0

    def __enter__(self) -> "SidecarSession":
        self.dir.mkdir(parents=True, exist_ok=True)
        self._t0 = time.perf_counter()
        self._start("iostat", ["iostat", "-x", "1"])
        self._start("vmstat", ["vmstat", "1"])
        if self.gpu_present:
            self._start("dmon", ["nvidia-smi", "dmon"])
        return self

    def _stamp_lines(self, proc: subprocess.Popen, log_path: Path) -> None:
        """subprocess の各stdout行に試行開始からの経過秒を前置してファイルへ書く。"""
        with open(log_path, "w") as f:
            f.write("# columns: <elapsed_seconds>\\t<original line>\n")
            assert proc.stdout is not None
            for raw in proc.stdout:
                elapsed = time.perf_counter() - self._t0
                f.write(f"{elapsed:.3f}\t{raw.rstrip(chr(10))}\n")
                f.flush()

    def _start(self, name: str, cmd: list[str]) -> None:
        log_path = self.dir / f"{name}.log"
        if shutil.which(cmd[0]) is None:
            log_path.write_text(f"# コマンド '{cmd[0]}' が見つからないため副計測をスキップしました\n")
            return
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        self._procs[name] = proc
        t = threading.Thread(target=self._stamp_lines, args=(proc, log_path), daemon=True)
        t.start()
        self._threads.append(t)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool:
        for proc in self._procs.values():
            proc.terminate()
        for proc in self._procs.values():
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        # stdoutが閉じればreaderスレッドは自然終了する
        for t in self._threads:
            t.join(timeout=5)
        return False

    @property
    def ref(self) -> str:
        return str(self.dir)
