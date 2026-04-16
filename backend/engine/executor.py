"""策略执行器，负责加载和执行用户策略代码"""

from types import ModuleType
from typing import Any


class StrategyExecutor:
    """策略执行器，安全地执行用户代码"""

    def __init__(self, code: str):
        self.code = code
        self._module: ModuleType | None = None
        self._initialize_func = None
        self._handle_bar_func = None

    def load(self):
        """加载策略代码"""
        import types

        # 创建一个新模块来执行策略代码
        self._module = types.ModuleType("strategy_module")
        namespace = self._module.__dict__

        # 执行策略代码
        try:
            exec(self.code, namespace)
        except Exception as e:
            raise ValueError(f"策略代码加载失败: {e}")

        # 查找策略函数
        self._initialize_func = namespace.get("initialize")
        self._handle_bar_func = namespace.get("handle_bar")

        if not self._handle_bar_func:
            raise ValueError("策略必须定义 handle_bar 函数")

    def initialize(self, context) -> None:
        """初始化策略"""
        if self._initialize_func:
            self._initialize_func(context)

    def handle_bar(self, context) -> list:
        """处理单根K线，返回订单列表"""
        if not self._handle_bar_func:
            return []

        # 清空之前的订单
        context.orders = []

        try:
            result = self._handle_bar_func(context)
            # 如果策略返回订单列表，使用返回值；否则使用 context.orders
            if result is not None:
                return result if isinstance(result, list) else []
            return context.orders.copy()
        except Exception as e:
            print(f"策略执行错误: {e}")
            return []
