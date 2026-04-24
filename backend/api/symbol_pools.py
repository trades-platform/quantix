"""标的池 API"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, field_validator, model_validator

from backend.db import (
    SessionLocal,
    create_symbol_pool,
    delete_symbol_pool,
    get_symbol_pool_by_name,
    list_symbol_pools,
    update_symbol_pool,
)
from backend.db.symbol_pool import normalize_pool_name, normalize_symbols
from backend.models import SymbolPool

router = APIRouter(prefix="/symbol-pools", tags=["symbol-pools"])


class SymbolPoolCreate(BaseModel):
    name: str
    description: str = ""
    symbols: list[str]

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return normalize_pool_name(value)

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, value: list[str]) -> list[str]:
        return normalize_symbols(value)


class SymbolPoolUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    symbols: list[str] | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_pool_name(value)

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return normalize_symbols(value)

    @model_validator(mode="after")
    def validate_payload(self) -> "SymbolPoolUpdate":
        if self.name is None and self.description is None and self.symbols is None:
            raise ValueError("至少提供一个要更新的字段")
        return self


class SymbolPoolResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    symbols: list[str]
    created_at: datetime
    updated_at: datetime | None = None

    @classmethod
    def from_orm(cls, pool: SymbolPool) -> "SymbolPoolResponse":
        return cls(
            id=pool.id,
            name=pool.name,
            description=pool.description,
            symbols=pool.symbols,
            created_at=pool.created_at,
            updated_at=pool.updated_at,
        )


@router.get("", response_model=list[SymbolPoolResponse])
def get_symbol_pools():
    with SessionLocal() as db:
        pools = list_symbol_pools(db)
        return [SymbolPoolResponse.from_orm(pool) for pool in pools]


@router.post("", response_model=SymbolPoolResponse, status_code=status.HTTP_201_CREATED)
def create_symbol_pool_api(req: SymbolPoolCreate):
    with SessionLocal() as db:
        try:
            pool = create_symbol_pool(db, req.name, req.symbols, req.description)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return SymbolPoolResponse.from_orm(pool)


@router.get("/{pool_name}", response_model=SymbolPoolResponse)
def get_symbol_pool(pool_name: str):
    with SessionLocal() as db:
        pool = get_symbol_pool_by_name(db, pool_name)
        if not pool:
            raise HTTPException(status_code=404, detail="标的池不存在")
        return SymbolPoolResponse.from_orm(pool)


@router.put("/{pool_name}", response_model=SymbolPoolResponse)
def update_symbol_pool_api(pool_name: str, req: SymbolPoolUpdate):
    with SessionLocal() as db:
        pool = get_symbol_pool_by_name(db, pool_name)
        if not pool:
            raise HTTPException(status_code=404, detail="标的池不存在")

        try:
            pool = update_symbol_pool(
                db,
                pool,
                name=req.name,
                description=req.description,
                symbols=req.symbols,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        return SymbolPoolResponse.from_orm(pool)


@router.delete("/{pool_name}", status_code=status.HTTP_204_NO_CONTENT)
def delete_symbol_pool_api(pool_name: str):
    with SessionLocal() as db:
        pool = get_symbol_pool_by_name(db, pool_name)
        if not pool:
            raise HTTPException(status_code=404, detail="标的池不存在")
        delete_symbol_pool(db, pool)
        return None
