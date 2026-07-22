"""損益分岐エポック数の算出: T_stage < E × (T_epoch_direct − T_epoch_SSD)。"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class BreakevenResult:
    t_stage_seconds: float
    t_epoch_direct_seconds: float
    t_epoch_ssd_seconds: float
    per_epoch_saving_seconds: float
    breakeven_epochs: float | None  # ステージングが得になる最小エポック数。Noneなら常に損


def compute_breakeven(
    t_stage_seconds: float,
    t_epoch_direct_seconds: float,
    t_epoch_ssd_seconds: float,
) -> BreakevenResult:
    """E本以上回すならステージングした方が総時間が短くなる、その閾値Eを返す。

    直読み総時間: E * T_epoch_direct
    ステージング総時間: T_stage + E * T_epoch_ssd
    ステージングが得: T_stage + E*T_epoch_ssd < E*T_epoch_direct
      => E > T_stage / (T_epoch_direct - T_epoch_ssd)
    SSDの方が遅い/同等(saving<=0)ならステージングは常に損なのでNone。
    """
    saving = t_epoch_direct_seconds - t_epoch_ssd_seconds
    if saving <= 0:
        breakeven = None
    else:
        breakeven = math.ceil(t_stage_seconds / saving)

    return BreakevenResult(
        t_stage_seconds=t_stage_seconds,
        t_epoch_direct_seconds=t_epoch_direct_seconds,
        t_epoch_ssd_seconds=t_epoch_ssd_seconds,
        per_epoch_saving_seconds=saving,
        breakeven_epochs=breakeven,
    )
