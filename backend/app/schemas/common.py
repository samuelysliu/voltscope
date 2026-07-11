from pydantic import BaseModel, Field


class PageParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class Page(BaseModel):
    items: list
    total: int
    page: int
    page_size: int


class HealthStatus(BaseModel):
    status: str


class MetricsStatus(BaseModel):
    service: str
    status: str
    database: str
    redis: str
