"""Shared data models used across the pipeline."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class Platform(str, Enum):
    AMAZON = "amazon"
    RAKUTEN = "rakuten"


class ArticleType(str, Enum):
    COMPARISON = "comparison"
    SPEC_ANALYSIS = "spec_analysis"
    PRICE_WATCH = "price_watch"


# ---------------------------------------------------------------------------
# Keyword / Trend
# ---------------------------------------------------------------------------
class TrendKeyword(BaseModel):
    """A trending keyword discovered from Google Trends or seasonal calendar."""

    keyword: str
    category: str = ""
    search_volume: int = 0
    trend_score: float = 0.0
    source: str = "google_trends"
    discovered_at: datetime = Field(default_factory=datetime.now)


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------
class ProductSpec(BaseModel):
    """A single key-value specification extracted from a product."""

    name: str
    value: str
    unit: str = ""


class ProductPrice(BaseModel):
    """Price snapshot for a product on a specific platform."""

    platform: Platform
    price: int
    currency: str = "JPY"
    url: str = ""
    affiliate_url: str = ""
    recorded_at: datetime = Field(default_factory=datetime.now)


class Product(BaseModel):
    """Product information aggregated from affiliate APIs."""

    id: str
    title: str
    platform: Platform
    asin: str = ""
    jan_code: str = ""
    category: str = ""
    brand: str = ""
    image_url: str = ""
    description: str = ""
    prices: list[ProductPrice] = Field(default_factory=list)
    specs: list[ProductSpec] = Field(default_factory=list)
    review_count: int = 0
    review_rating: float = 0.0
    affiliate_url: str = ""


class PriceHistoryEntry(BaseModel):
    """A single price observation for tracking over time."""

    date: date
    platform: Platform
    price: int


class PriceHistory(BaseModel):
    """Historical price data for a product across platforms."""

    product_id: str
    product_title: str
    entries: list[PriceHistoryEntry] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------
class ScoreBreakdown(BaseModel):
    """Individual score component with transparent weighting."""

    dimension: str
    raw_value: float
    normalized: float = Field(ge=0.0, le=1.0)
    weight: float
    weighted_score: float


class ProductScore(BaseModel):
    """Composite score for a product with full breakdown."""

    product_id: str
    total_score: float
    rank: int = 0
    breakdown: list[ScoreBreakdown] = Field(default_factory=list)


class ComparisonAxis(BaseModel):
    """One axis of a product comparison matrix."""

    axis_name: str
    unit: str = ""
    values: dict[str, str] = Field(default_factory=dict)
    best_product_id: str = ""


class ComparisonResult(BaseModel):
    """Full comparison result for a set of products."""

    keyword: str
    products: list[Product]
    axes: list[ComparisonAxis] = Field(default_factory=list)
    scores: list[ProductScore] = Field(default_factory=list)
    price_histories: list[PriceHistory] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Article
# ---------------------------------------------------------------------------
class ArticleMeta(BaseModel):
    """Frontmatter metadata for a generated article."""

    title: str
    slug: str
    description: str
    article_type: ArticleType
    keyword: str
    category: str = ""
    products: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class Article(BaseModel):
    """A complete generated article with metadata and content."""

    meta: ArticleMeta
    content: str
    comparison_table_md: str = ""
    score_table_md: str = ""
    price_chart_data: list[dict] = Field(default_factory=list)
