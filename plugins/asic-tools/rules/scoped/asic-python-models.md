---
paths:
  - "**/*.py"
  - "**/*.pyi"
---
## Data models — Pydantic v2 only

Use Pydantic v2 idioms exclusively: `@field_validator`, `model_config = ConfigDict(...)`.
Never v1 `@validator` / `class Config`. Validate at the boundary; strict where it matters.

```python
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductBase(BaseModel):
    """Base product model with common fields."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    price: Decimal = Field(..., gt=0, decimal_places=2)
    category: str
    tags: list[str] = []

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: Decimal) -> Decimal:
        if v > Decimal("1000000"):
            raise ValueError("Price cannot exceed 1,000,000")
        return v


class ProductCreate(ProductBase):
    """Model for creating new products."""


class ProductUpdate(BaseModel):
    """Model for updates — all fields optional."""

    name: str | None = Field(None, min_length=1, max_length=255)
    price: Decimal | None = Field(None, gt=0, decimal_places=2)


class Product(ProductBase):
    """Complete product model with database fields."""

    product_id: int
    created_at: datetime
    updated_at: datetime
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)
```

## Configuration

Settings via pydantic-settings, accessed through a cached singleton — never instantiate
`Settings` directly in application code:

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation."""

    app_name: str = "MyApp"
    debug: bool = False
    database_url: str
    redis_url: str = "redis://localhost:6379"
    max_connections: int = 100

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings instance."""
    return Settings()
```
