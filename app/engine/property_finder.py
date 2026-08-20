import numpy as np

from app.engine.data_provider import DremioDataProvider
from app.engine.numeric import safe_float as _safe_float, safe_int as _safe_int
from app.engine.schemas import (
    PropertyListing,
    PropertyFinderFilters,
    PropertyFinderResult,
)


def _build_listings(df: "pd.DataFrame") -> list[PropertyListing]:
    import pandas as pd
    listings = []
    for _, row in df.iterrows():
        listings.append(PropertyListing(
            district=str(row.get("district") or ""),
            property_type=str(row.get("property_type") or ""),
            area_sqm=_safe_float(row.get("area_sqm")),
            price_egp=_safe_float(row.get("price_egp")),
            price_per_sqm=_safe_float(row.get("price_per_sqm")),
            bedrooms=_safe_int(row.get("bedrooms")),
            bathrooms=_safe_int(row.get("bathrooms")),
            link=str(row.get("link") or ""),
        ))
    return listings


class PropertyFinder:
    def __init__(self, data_provider: DremioDataProvider) -> None:
        self._dp = data_provider

    def get_filter_options(self) -> dict:
        return self._dp.get_re_filter_options()

    def search(
        self,
        budget: float,
        district: str | None = None,
        property_type: str | None = None,
        bedrooms: str | None = None,
        min_area: float | None = None,
        max_area: float | None = None,
    ) -> PropertyFinderResult:
        df = self._dp.search_re_listings(
            budget=budget,
            district=district,
            property_type=property_type,
            bedrooms=bedrooms,
            min_area=min_area,
            max_area=max_area,
        )

        if not df.empty:
            return PropertyFinderResult(
                budget=budget,
                district=district,
                filters=PropertyFinderFilters(
                    property_type=property_type,
                    bedrooms=bedrooms,
                    min_area=min_area,
                    max_area=max_area,
                ),
                total_matches=len(df),
                listings=_build_listings(df),
                relaxed=False,
            )

        relaxed = self._dp.search_re_listings(budget=budget)
        return PropertyFinderResult(
            budget=budget,
            district=None,
            filters=PropertyFinderFilters(
                property_type=None,
                bedrooms=None,
                min_area=None,
                max_area=None,
            ),
            total_matches=len(relaxed),
            listings=_build_listings(relaxed),
            relaxed=True,
        )
