from app.engine.schemas import RiskLevel, Duration


def get_risk_params(risk_level: RiskLevel) -> dict:
    params = {
        RiskLevel.LOW: {
            "target_vol": 0.10,
            "max_single_asset_weight": 0.40,
            "min_stocks_weight": 0.0,
            "max_stocks_weight": 0.30,
            "preference": "capital_preservation",
        },
        RiskLevel.MEDIUM: {
            "target_vol": 0.18,
            "max_single_asset_weight": 0.50,
            "min_stocks_weight": 0.10,
            "max_stocks_weight": 0.50,
            "preference": "balanced_growth",
        },
        RiskLevel.HIGH: {
            "target_vol": 0.28,
            "max_single_asset_weight": 0.60,
            "min_stocks_weight": 0.20,
            "max_stocks_weight": 0.70,
            "preference": "max_return",
        },
    }
    return params[risk_level]


def get_duration_params(duration: Duration) -> dict:
    params = {
        Duration.SHORT: {
            "max_re_weight": 0.15,
            "min_liquidity_score": 0.7,
            "label": "short_term",
        },
        Duration.MEDIUM: {
            "max_re_weight": 0.40,
            "min_liquidity_score": 0.3,
            "label": "medium_term",
        },
        Duration.LONG: {
            "max_re_weight": 0.60,
            "min_liquidity_score": 0.0,
            "label": "long_term",
        },
    }
    return params[duration]
