from datetime import date

import numpy as np
import pandas as pd

from app.engine.data_provider import DremioDataProvider
from app.engine.optimizer import (
    ASSET_NAMES,
    mean_variance_optimize,
    risk_parity_weights,
    compute_portfolio_stats,
)
from app.engine.risk_profiler import get_risk_params, get_duration_params
from app.engine.schemas import (
    UserProfile,
    AssetAllocation,
    DrillDown,
    RecommendationResult,
)


def best_specific_pick(result: RecommendationResult) -> dict | None:
    """Single best pick within the top asset's drilldown, for the UI verdict."""
    if not result.allocations:
        return None
    for dd in result.drilldowns:
        if dd.asset_class == result.top_asset_class and dd.picks:
            return dd.picks[0]
    return None


def _safe_float(val: object) -> float:
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


class Recommender:
    def __init__(self, data_provider: DremioDataProvider) -> None:
        self._dp = data_provider

    def recommend(self, profile: UserProfile) -> RecommendationResult:
        asset_scores = self._dp.get_asset_scores()
        if asset_scores.empty:
            return self._empty_result(profile, "No Gold layer data available in Dremio.")

        expected_returns: dict[str, float] = {}
        volatilities: dict[str, float] = {}
        for _, row in asset_scores.iterrows():
            ac = str(row.get("asset_class", "")).lower()
            expected_returns[ac] = _safe_float(row.get("roi_proxy"))
            volatilities[ac] = _safe_float(row.get("vol_proxy"))

        risk_p = get_risk_params(profile.risk_level)
        dur_p = get_duration_params(profile.duration)

        weights = mean_variance_optimize(
            expected_returns=expected_returns,
            volatilities=volatilities,
            target_vol=risk_p["target_vol"],
            max_weight=risk_p["max_single_asset_weight"],
            stock_weight_bounds=(risk_p["min_stocks_weight"], risk_p["max_stocks_weight"]),
            max_re_weight=dur_p["max_re_weight"],
        )

        if weights is None:
            weights = risk_parity_weights(volatilities, dur_p["max_re_weight"])

        stats = compute_portfolio_stats(weights, expected_returns, volatilities)

        as_of = asset_scores["as_of_date"].iloc[0] if "as_of_date" in asset_scores.columns else str(date.today())
        if hasattr(as_of, "strftime"):
            as_of = as_of.strftime("%Y-%m-%d")
        as_of = str(as_of)

        allocations = []
        drilldowns = []
        top_idx = int(np.argmax(weights))
        top_asset = ASSET_NAMES[top_idx]
        rc_pcts = stats["risk_contributions"]

        for i, ac in enumerate(ASSET_NAMES):
            alloc = AssetAllocation(
                asset_class=ac,
                weight_pct=float(weights[i]) * 100,
                expected_return=expected_returns.get(ac, 0.0),
                volatility=volatilities.get(ac, 0.0),
                risk_contribution_pct=rc_pcts[i] * 100,
                is_top_pick=(ac == top_asset),
            )
            allocations.append(alloc)

            dd = self._drill_down(ac, float(weights[i]), profile)
            if dd is not None:
                drilldowns.append(dd)

        rationale = self._build_rationale(
            top_asset, allocations, risk_p["preference"], dur_p["label"]
        )

        return RecommendationResult(
            allocations=allocations,
            drilldowns=drilldowns,
            portfolio_expected_return=stats["return"],
            portfolio_volatility=stats["volatility"],
            portfolio_sharpe_ratio=stats["sharpe_ratio"],
            top_asset_class=top_asset,
            rationale=rationale,
            risk_level=profile.risk_level.value,
            duration=profile.duration.value,
            as_of_date=as_of,
            amount=profile.amount,
        )

    def _drill_down(
        self, asset_class: str, weight: float, profile: UserProfile
    ) -> DrillDown | None:
        if weight < 0.01:
            return None

        if asset_class == "stocks":
            return self._drill_stocks(profile, weight)
        elif asset_class == "gold":
            return self._drill_metal("gold")
        elif asset_class == "silver":
            return self._drill_metal("silver")
        elif asset_class == "real_estate":
            return self._drill_real_estate(profile, weight)
        return None

    def _drill_stocks(self, profile: UserProfile, weight: float) -> DrillDown:
        scores = self._dp.get_stock_scores()
        if scores.empty:
            return DrillDown("stocks", [], "No stock score data available.")

        is_high_risk = profile.risk_level.value == "high"
        if "ticker" not in scores.columns:
            return DrillDown("stocks", [], "Stock scores missing ticker column.")

        score_cols = {
            "roe_score": ("norm_roe", 0.3 if not is_high_risk else 0.25),
            "div_score": ("div_yield_score", 0.20 if not is_high_risk else 0.10),
            "liq_score": ("liquidity_score", 0.15),
            "mom_score": ("momentum_3m", 0.10 if not is_high_risk else 0.30),
            "vol_score": ("vol_score", 0.25 if not is_high_risk else 0.20),
        }
        composite = pd.Series(0.0, index=scores.index)
        for alias, (col, w) in score_cols.items():
            if col in scores.columns:
                col_clean = scores[col].fillna(0)
                col_min, col_max = col_clean.min(), col_clean.max()
                if col_max > col_min:
                    normalized = (col_clean - col_min) / (col_max - col_min)
                else:
                    normalized = col_clean * 0.0
                composite += normalized * w

        scores = scores.assign(_composite=composite).sort_values("_composite", ascending=False)
        top3 = scores.head(3)
        stock_budget = profile.amount * weight
        alloc_per_ticker = stock_budget / max(len(top3), 1)

        picks = []
        for _, row in top3.iterrows():
            picks.append({
                "ticker": str(row.get("ticker", "")),
                "allocation_egp": round(alloc_per_ticker, 0),
                "composite_score": round(float(row.get("_composite", 0)), 3),
                "roe": round(float(row.get("roe_proxy", 0)), 4),
                "dividend_yield": round(float(row.get("dividend_yield", 0)), 4),
                "momentum_3m": round(float(row.get("momentum_3m", 0)), 4),
                "vol_90d": round(float(row.get("vol_90d", 0)), 4),
            })

        return DrillDown("stocks", picks, f"Invest EGP {stock_budget:,.0f} in stocks — split equally across top 3 picks")

    def _drill_metal(self, metal: str) -> DrillDown:
        roi = self._dp.get_gold_metal_roi()
        if roi.empty:
            return DrillDown(metal, [], f"No {metal} ROI data available.")
        row = roi[roi["metal"].str.lower() == metal]
        if row.empty:
            row = roi[roi["metal"].str.lower() == ("gold" if metal == "silver" else "silver")]
        if row.empty:
            return DrillDown(metal, [], f"No {metal} data.")

        r = row.iloc[0]
        picks = [{
            "metal": str(r.get("metal", metal)),
            "roi_1yr_egp": round(float(r.get("roi_1yr_egp", 0)) * 100, 2),
            "roi_3yr_egp": round(float(r.get("roi_3yr_egp", 0)) * 100, 2),
            "roi_5yr_egp": round(float(r.get("roi_5yr_egp", 0)) * 100, 2),
            "latest_price_egp": round(float(r.get("latest_price_egp", 0)), 2),
        }]
        rationale = f"{metal.title()} ROI: 1yr={picks[0]['roi_1yr_egp']}%, 3yr={picks[0]['roi_3yr_egp']}%"
        return DrillDown(metal, picks, rationale)

    def _drill_real_estate(self, profile: UserProfile, weight: float) -> DrillDown:
        re_budget = profile.amount * weight
        df = self._dp.search_re_listings(budget=re_budget)
        if df.empty:
            df = self._dp.search_re_listings(budget=profile.amount)
            if df.empty:
                return DrillDown("real_estate", [], f"No listings within EGP {re_budget:,.0f}.")

        picks = []
        for _, row in df.head(10).iterrows():
            picks.append({
                "district": str(row.get("district") or ""),
                "property_type": str(row.get("property_type") or ""),
                "area_sqm": float(row.get("area_sqm") or 0),
                "price_egp": round(float(row.get("price_egp") or 0), 0),
                "price_per_sqm": round(float(row.get("price_per_sqm") or 0), 0),
                "bedrooms": int(float(row.get("bedrooms") or 0)),
                "link": str(row.get("link") or ""),
            })

        return DrillDown("real_estate", picks, f"Actual listings within EGP {re_budget:,.0f} budget (re_budget from {weight*100:.0f}% allocation)")

    def _build_rationale(
        self,
        top_asset: str,
        allocations: list[AssetAllocation],
        preference: str,
        duration_label: str,
    ) -> str:
        top_alloc = next(a for a in allocations if a.asset_class == top_asset)
        parts = [
            f"Recommended portfolio is {preference.replace('_', ' ')} oriented "
            f"with a {duration_label.replace('_', ' ')} horizon.",
            f"Top pick: {top_asset.title()} ({top_alloc.weight_pct:.0f}% allocation) — "
            f"expected return {top_alloc.expected_return*100:.1f}%, "
            f"volatility {top_alloc.volatility*100:.1f}%.",
        ]
        if top_asset == "stocks":
            parts.append("Stocks offer the highest return potential with corresponding risk.")
        elif top_asset in ("gold", "silver"):
            parts.append(f"{top_asset.title()} serves as a safe-haven and inflation hedge.")
        elif top_asset == "real_estate":
            parts.append("Real estate provides stable rental yield and tangible asset exposure.")

        non_zero = [a for a in allocations if a.weight_pct > 1]
        if len(non_zero) > 1:
            others = ", ".join(f"{a.asset_class.title()} ({a.weight_pct:.0f}%)" for a in non_zero if not a.is_top_pick)
            parts.append(f"Diversified across: {others}.")

        return " ".join(parts)

    def _empty_result(self, profile: UserProfile, reason: str) -> RecommendationResult:
        return RecommendationResult(
            allocations=[],
            drilldowns=[],
            portfolio_expected_return=0.0,
            portfolio_volatility=0.0,
            portfolio_sharpe_ratio=0.0,
            top_asset_class="none",
            rationale=reason,
            risk_level=profile.risk_level.value,
            duration=profile.duration.value,
            as_of_date=str(date.today()),
            amount=profile.amount,
        )
