"""drop_caches実行戦略。運用方法が確定していないため差し替え可能なStrategyパターンにする。"""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod


class DropCachesStrategy(ABC):
    name: str

    @abstractmethod
    def run(self) -> bool:
        """drop_cachesを実行する。成功したらTrue、失敗/権限なしならFalseを返す(例外にしない)。"""


class SudoTeeStrategy(DropCachesStrategy):
    """既定実装: sync; echo 3 | sudo tee /proc/sys/vm/drop_caches"""

    name = "sudo_tee"

    def run(self) -> bool:
        try:
            subprocess.run(["sync"], check=True, timeout=30)
            proc = subprocess.run(
                ["sudo", "tee", "/proc/sys/vm/drop_caches"],
                input="3",
                text=True,
                capture_output=True,
                timeout=30,
            )
            return proc.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False


class NoopStrategy(DropCachesStrategy):
    """drop_caches不可の環境向け。常にFalseを返し、呼び出し側にwarm/サイズ判定を委ねる。"""

    name = "noop"

    def run(self) -> bool:
        return False


class ExternalColdStrategy(DropCachesStrategy):
    """ジョブ投入直前に運用者が手動で(sudoで)drop_cachesする運用向け。

    ライブラリ自身はキャッシュを落とさず、「外部で落とされた」前提で cold を記録する。
    ⚠️ 手動dropはそのジョブの**最初の読み込み**だけをcoldにする。反復2回目以降は
    データがページキャッシュに載るためwarmになる。したがってこの戦略は
    **repetitions=1 で使い、cold試行が欲しい回数だけ別ジョブとして投入**する運用と
    セットで使うこと(投入前に毎回手動drop)。詳細は docs/howto.md 参照。
    """

    name = "external"

    def run(self) -> bool:
        return True


STRATEGY_REGISTRY: dict[str, type[DropCachesStrategy]] = {
    "sudo_tee": SudoTeeStrategy,
    "noop": NoopStrategy,
    "external": ExternalColdStrategy,
}


def get_strategy(name: str) -> DropCachesStrategy:
    try:
        return STRATEGY_REGISTRY[name]()
    except KeyError as e:
        raise ValueError(
            f"未知のdrop_caches戦略: {name!r}。利用可能: {list(STRATEGY_REGISTRY)}"
        ) from e
