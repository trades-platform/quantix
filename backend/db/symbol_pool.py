"""标的池读写与解析工具"""

from collections.abc import Iterable

from sqlalchemy.orm import Session

from backend.models import SymbolPool

POOL_PREFIX = "@"


def normalize_pool_name(name: str) -> str:
    value = name.strip()
    if value.startswith(POOL_PREFIX):
        value = value[1:]
    value = value.lower()
    if not value:
        raise ValueError("标的池名称不能为空")
    if not all(ch.isalnum() or ch in {"_", "-"} for ch in value):
        raise ValueError("标的池名称仅支持字母、数字、下划线和中划线")
    return value


def normalize_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if not value:
        raise ValueError("标的代码不能为空")
    if value.startswith(POOL_PREFIX):
        raise ValueError("标的池成员不能引用其他标的池")
    return value


def split_symbol_tokens(raw_targets: str | Iterable[str]) -> list[str]:
    if isinstance(raw_targets, str):
        parts = [raw_targets]
    else:
        parts = list(raw_targets)

    tokens: list[str] = []
    for part in parts:
        for token in part.replace("\n", ",").split(","):
            value = token.strip()
            if value:
                tokens.append(value)
    return tokens


def normalize_symbols(symbols: str | Iterable[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for token in split_symbol_tokens(symbols):
        value = normalize_symbol(token)
        if value not in seen:
            seen.add(value)
            normalized.append(value)
    if not normalized:
        raise ValueError("至少需要一个标的代码")
    return normalized


def normalize_target_tokens(raw_targets: str | Iterable[str]) -> list[str]:
    tokens = split_symbol_tokens(raw_targets)
    if not tokens:
        raise ValueError("至少提供一个标的或标的池")

    normalized: list[str] = []
    for token in tokens:
        if token.startswith(POOL_PREFIX):
            normalized.append(f"{POOL_PREFIX}{normalize_pool_name(token)}")
        else:
            normalized.append(normalize_symbol(token))
    return normalized


def get_display_target(raw_targets: str | Iterable[str]) -> str:
    tokens = normalize_target_tokens(raw_targets)
    if len(tokens) == 1:
        return tokens[0]
    return ",".join(tokens)


def list_symbol_pools(db: Session) -> list[SymbolPool]:
    return db.query(SymbolPool).order_by(SymbolPool.name).all()


def get_symbol_pool_by_name(db: Session, name: str) -> SymbolPool | None:
    normalized_name = normalize_pool_name(name)
    return db.query(SymbolPool).filter(SymbolPool.name == normalized_name).first()


def create_symbol_pool(db: Session, name: str, symbols: str | Iterable[str], description: str = "") -> SymbolPool:
    normalized_name = normalize_pool_name(name)
    if get_symbol_pool_by_name(db, normalized_name):
        raise ValueError(f"标的池已存在: {normalized_name}")

    pool = SymbolPool(name=normalized_name, description=(description or "").strip())
    pool.symbols = normalize_symbols(symbols)
    db.add(pool)
    db.commit()
    db.refresh(pool)
    return pool


def update_symbol_pool(
    db: Session,
    pool: SymbolPool,
    *,
    name: str | None = None,
    symbols: str | Iterable[str] | None = None,
    description: str | None = None,
) -> SymbolPool:
    if name is not None:
        normalized_name = normalize_pool_name(name)
        conflict = db.query(SymbolPool).filter(SymbolPool.name == normalized_name, SymbolPool.id != pool.id).first()
        if conflict:
            raise ValueError(f"标的池已存在: {normalized_name}")
        pool.name = normalized_name

    if description is not None:
        pool.description = description.strip()

    if symbols is not None:
        pool.symbols = normalize_symbols(symbols)

    db.commit()
    db.refresh(pool)
    return pool


def delete_symbol_pool(db: Session, pool: SymbolPool) -> None:
    db.delete(pool)
    db.commit()


def resolve_symbol_targets(db: Session, raw_targets: str | Iterable[str]) -> list[str]:
    tokens = normalize_target_tokens(raw_targets)

    resolved: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token.startswith(POOL_PREFIX):
            pool_name = normalize_pool_name(token)
            pool = get_symbol_pool_by_name(db, pool_name)
            if not pool:
                raise LookupError(f"标的池不存在: {pool_name}")
            for symbol in pool.symbols:
                if symbol not in seen:
                    seen.add(symbol)
                    resolved.append(symbol)
        else:
            if token not in seen:
                seen.add(token)
                resolved.append(token)

    if not resolved:
        raise ValueError("未解析到任何标的代码")
    return resolved
