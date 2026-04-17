"""登录配置加载"""

import json
from pathlib import Path

CONFIG_PATH = Path.home() / ".quantix" / "config.json"


def load_config() -> dict:
    """加载配置文件"""
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"配置文件不存在: {CONFIG_PATH}\n"
            f"请创建配置文件，内容如下:\n"
            f'{{"tgw": {{"username": "xxx", "password": "xxx", "host": "xxx", "port": xxx}}}}'
        )

    with open(CONFIG_PATH) as f:
        return json.load(f)


def get_tgw_credentials() -> dict:
    """获取 TGW 登录凭证"""
    config = load_config()
    tgw = config.get("tgw")
    if not tgw:
        raise ValueError("配置文件中缺少 'tgw' 字段")

    required = ["username", "password", "host", "port"]
    missing = [k for k in required if not tgw.get(k)]
    if missing:
        raise ValueError(f"配置文件中缺少必要字段: {missing}")

    return tgw