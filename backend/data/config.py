"""登录配置加载"""

import json
from pathlib import Path

GLOBAL_CONFIG_PATH = Path.home() / ".quantix" / "config.json"
LOCAL_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config.json"


def _find_config() -> Path:
    """查找配置文件，优先使用项目本地配置，其次使用全局配置"""
    if LOCAL_CONFIG_PATH.exists():
        return LOCAL_CONFIG_PATH
    if GLOBAL_CONFIG_PATH.exists():
        return GLOBAL_CONFIG_PATH
    raise FileNotFoundError(
        f"配置文件不存在，已搜索:\n"
        f"  1. {LOCAL_CONFIG_PATH}\n"
        f"  2. {GLOBAL_CONFIG_PATH}\n"
        f"请创建配置文件，内容如下:\n"
        f'{{"tgw": {{"username": "xxx", "password": "xxx", "host": "xxx", "port": xxx}}}}'
    )


def load_config() -> dict:
    """加载配置文件"""
    config_path = _find_config()
    with open(config_path) as f:
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