from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from sqlmodel import SQLModel, Field


class CurrencyRate(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    char_code: str = Field(index=True)
    name: str
    value: float
    date: datetime = Field(default_factory=datetime.now)


class CurrencyRateCreate(BaseModel):
    char_code: str
    name: str
    value: float


class CurrencyRateUpdate(BaseModel):
    char_code: Optional[str] = None
    name: Optional[str] = None
    value: Optional[float] = None


class CurrencyRateResponse(CurrencyRateCreate):
    id: int
    date: datetime