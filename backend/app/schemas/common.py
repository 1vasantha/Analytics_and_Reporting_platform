# Common Pydantic schemas used across endpoints.

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

# Base for schemas mapped from SQLAlchemy ORM objects.
class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

# Timestamp
class TimestampedModel(ORMModel):
    id: UUID
    created_at: datetime
    updated_at: datetime

# Pagination 
class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1, le=10_000)
    page_size: int = Field(default=20, ge=1, le=200)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size

# Page Items
class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int

    @classmethod
    def create(cls, items: list[T], total: int, params: PaginationParams) -> "Page[T]":
        pages = max(1, (total + params.page_size - 1) // params.page_size)
        return cls(
            items=items,
            total=total,
            page=params.page,
            page_size=params.page_size,
            pages=pages,
        )

# Health Check Model
class HealthCheck(BaseModel):
    status: str
    version: str
    database: bool
    redis: bool

# Error Response model
class ErrorResponse(BaseModel):
    error_code: str
    message: str
    details: dict | None = None
