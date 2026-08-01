from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Duration(Enum):
    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


@dataclass
class UserProfile:
    amount: float
    risk_level: RiskLevel
    duration: Duration


@dataclass
class AssetAllocation:
    asset_class: str
    weight_pct: float
    expected_return: float
    volatility: float
    risk_contribution_pct: float
    is_top_pick: bool = False


@dataclass
class DrillDown:
    asset_class: str
    picks: list[dict[str, Any]]
    rationale: str


@dataclass
class RecommendationResult:
    allocations: list[AssetAllocation]
    drilldowns: list[DrillDown]
    portfolio_expected_return: float
    portfolio_volatility: float
    portfolio_sharpe_ratio: float
    top_asset_class: str
    rationale: str
    risk_level: str
    duration: str
    as_of_date: str
    amount: float


@dataclass
class PropertyListing:
    district: str
    property_type: str
    area_sqm: float
    price_egp: float
    price_per_sqm: float
    bedrooms: int
    bathrooms: int
    link: str


@dataclass
class PropertyFinderFilters:
    property_type: str | None
    bedrooms: str | None
    min_area: float | None
    max_area: float | None


@dataclass
class PropertyFinderResult:
    budget: float
    district: str | None
    filters: PropertyFinderFilters
    total_matches: int
    listings: list[PropertyListing]
    relaxed: bool = False
