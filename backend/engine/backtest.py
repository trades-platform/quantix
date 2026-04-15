"""回测引擎核心模块"""

import pandas as pd


class BacktestEngine:
    """回测引擎"""

    def run(self, strategy, data: pd.DataFrame) -> dict:
        raise NotImplementedError
