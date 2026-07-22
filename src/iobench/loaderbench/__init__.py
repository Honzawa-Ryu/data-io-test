"""PyTorch DataLoaderによる実効スループット・GPU待ち時間・first-batch latency計測。"""

from iobench.loaderbench.bench import LoaderResult, run_loader_epoch

__all__ = ["LoaderResult", "run_loader_epoch"]
