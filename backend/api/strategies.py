"""策略管理 API"""

import json
from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.db import SessionLocal
from backend.models import Strategy

router = APIRouter(prefix="/strategies", tags=["strategies"])


class StrategyCreate(BaseModel):
    name: str
    description: str = ""
    code: str


class StrategyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    code: str | None = None


class StrategyResponse(BaseModel):
    id: int
    name: str
    description: str
    code: str
    created_at: datetime
    updated_at: datetime


@router.get("", response_model=List[StrategyResponse])
def list_strategies():
    """获取策略列表"""
    with SessionLocal() as db:
        strategies = db.query(Strategy).order_by(Strategy.id.desc()).all()
        return strategies


@router.post("", response_model=StrategyResponse, status_code=status.HTTP_201_CREATED)
def create_strategy(strategy: StrategyCreate):
    """创建策略"""
    with SessionLocal() as db:
        db_strategy = Strategy(
            name=strategy.name,
            description=strategy.description,
            code=strategy.code,
        )
        db.add(db_strategy)
        db.commit()
        db.refresh(db_strategy)
        return db_strategy


@router.get("/{strategy_id}", response_model=StrategyResponse)
def get_strategy(strategy_id: int):
    """获取策略详情"""
    with SessionLocal() as db:
        strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")
        return strategy


@router.put("/{strategy_id}", response_model=StrategyResponse)
def update_strategy(strategy_id: int, strategy: StrategyUpdate):
    """更新策略"""
    with SessionLocal() as db:
        db_strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        if not db_strategy:
            raise HTTPException(status_code=404, detail="策略不存在")

        if strategy.name is not None:
            db_strategy.name = strategy.name
        if strategy.description is not None:
            db_strategy.description = strategy.description
        if strategy.code is not None:
            db_strategy.code = strategy.code

        db_strategy.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(db_strategy)
        return db_strategy


@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_strategy(strategy_id: int):
    """删除策略"""
    with SessionLocal() as db:
        strategy = db.query(Strategy).filter(Strategy.id == strategy_id).first()
        if not strategy:
            raise HTTPException(status_code=404, detail="策略不存在")

        db.delete(strategy)
        db.commit()
        return None
