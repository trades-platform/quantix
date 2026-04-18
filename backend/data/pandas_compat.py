"""pandas 2.x 兼容性补丁。

AmazingData 内部使用 fillna(method='ffill') 等已废弃的 pandas API，
需要在调用前 monkey-patch，调用后恢复。
"""

import pandas as pd


def patch_fillna():
    """Monkey-patch DataFrame.fillna，返回原始方法用于恢复。"""
    _original = pd.DataFrame.fillna

    def _patched(self, *args, **kwargs):
        if 'method' in kwargs:
            method = kwargs.pop('method')
            if method in ('ffill', 'pad'):
                return self.ffill(**kwargs)
            elif method in ('bfill', 'backfill'):
                return self.bfill(**kwargs)
        return _original(self, *args, **kwargs)

    pd.DataFrame.fillna = _patched
    return _original


def restore_fillna(original):
    """恢复 DataFrame.fillna 为原始方法。"""
    pd.DataFrame.fillna = original
