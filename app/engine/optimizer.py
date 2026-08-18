import numpy as np
from scipy.optimize import minimize

from app.config import RISK_FREE_RATE

DEFAULT_CORRELATIONS: dict[tuple[str, str], float] = {
    ("stocks", "stocks"): 1.0,
    ("stocks", "gold"): -0.15,
    ("stocks", "silver"): -0.10,
    ("stocks", "real_estate"): 0.30,
    ("gold", "gold"): 1.0,
    ("gold", "silver"): 0.70,
    ("gold", "real_estate"): 0.05,
    ("gold", "stocks"): -0.15,
    ("silver", "silver"): 1.0,
    ("silver", "gold"): 0.70,
    ("silver", "real_estate"): 0.05,
    ("silver", "stocks"): -0.10,
    ("real_estate", "real_estate"): 1.0,
    ("real_estate", "gold"): 0.05,
    ("real_estate", "silver"): 0.05,
    ("real_estate", "stocks"): 0.30,
}

ASSET_NAMES = ["stocks", "gold", "silver", "real_estate"]


def _correlation(a: str, b: str) -> float:
    return DEFAULT_CORRELATIONS.get((a, b), 0.0)


def build_covariance_matrix(
    expected_returns: dict[str, float],
    volatilities: dict[str, float],
) -> np.ndarray:
    n = len(ASSET_NAMES)
    sigma = np.array([volatilities.get(a, 0.0) for a in ASSET_NAMES])
    cov = np.zeros((n, n))
    for i, a in enumerate(ASSET_NAMES):
        for j, b in enumerate(ASSET_NAMES):
            cov[i, j] = sigma[i] * sigma[j] * _correlation(a, b)
    return cov


def _neg_sharpe(
    weights: np.ndarray,
    returns: np.ndarray,
    cov: np.ndarray,
    rf: float,
) -> float:
    port_return = float(np.dot(weights, returns))
    port_vol = float(np.sqrt(np.dot(weights, np.dot(cov, weights))))
    if port_vol < 1e-12:
        return 0.0
    return -(port_return - rf) / port_vol


def _portfolio_vol(weights: np.ndarray, cov: np.ndarray) -> float:
    return float(np.sqrt(np.dot(weights, np.dot(cov, weights))))


def mean_variance_optimize(
    expected_returns: dict[str, float],
    volatilities: dict[str, float],
    target_vol: float | None = None,
    max_weight: float = 0.6,
    min_weight: float = 0.0,
    stock_weight_bounds: tuple[float, float] = (0.0, 0.6),
    max_re_weight: float = 0.6,
) -> np.ndarray | None:
    n = len(ASSET_NAMES)
    returns_arr = np.array([expected_returns.get(a, 0.0) for a in ASSET_NAMES])
    cov = build_covariance_matrix(expected_returns, volatilities)
    rf = RISK_FREE_RATE

    bounds = []
    for a in ASSET_NAMES:
        lo, hi = min_weight, max_weight
        if a == "real_estate":
            hi = min(hi, max_re_weight)
        if a == "stocks":
            lo = max(lo, stock_weight_bounds[0])
            hi = min(hi, stock_weight_bounds[1])
        bounds.append((lo, hi))

    constraints: list[dict] = [{"type": "eq", "fun": lambda w: float(np.sum(w)) - 1.0}]
    if target_vol is not None:
        constraints.append({
            "type": "ineq",
            "fun": lambda w: target_vol - _portfolio_vol(w, cov),
        })

    initial_guesses = [
        np.array([1.0 / n] * n),
    ]
    best_idx = int(np.argmax(returns_arr))
    w = np.full(n, (1.0 - bounds[best_idx][1]) / (n - 1))
    w[best_idx] = bounds[best_idx][1]
    initial_guesses.append(w)

    best_result = None
    best_sharpe = -np.inf

    for guess in initial_guesses:
        result = minimize(
            _neg_sharpe,
            guess,
            args=(returns_arr, cov, rf),
            method="SLSQP",
            bounds=bounds,
            constraints=constraints,
            options={"maxiter": 1000, "ftol": 1e-9},
        )
        if result.success:
            sharpe = -float(result.fun)
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_result = result

    if best_result is None:
        return None
    return best_result.x


def risk_parity_weights(
    volatilities: dict[str, float],
    max_re_weight: float = 0.6,
) -> np.ndarray:
    vol_arr = np.array([volatilities.get(a, 1.0) for a in ASSET_NAMES])
    inv_vol = 1.0 / np.maximum(vol_arr, 1e-6)
    w = inv_vol / inv_vol.sum()
    re_idx = ASSET_NAMES.index("real_estate")
    if w[re_idx] > max_re_weight:
        excess = w[re_idx] - max_re_weight
        w[re_idx] = max_re_weight
        remaining = w.sum() - max_re_weight
        if remaining > 0:
            w = w / remaining * (1.0 - max_re_weight)
            w[re_idx] = max_re_weight
    return w


def compute_portfolio_stats(
    weights: np.ndarray,
    expected_returns: dict[str, float],
    volatilities: dict[str, float],
) -> dict:
    returns_arr = np.array([expected_returns.get(a, 0.0) for a in ASSET_NAMES])
    cov = build_covariance_matrix(expected_returns, volatilities)
    port_return = float(np.dot(weights, returns_arr))
    port_vol = _portfolio_vol(weights, cov)
    sharpe = (port_return - RISK_FREE_RATE) / port_vol if port_vol > 1e-12 else 0.0

    risk_contributions = []
    for i, a in enumerate(ASSET_NAMES):
        rc = weights[i] * float(np.dot(cov[i], weights)) / (port_vol + 1e-12)
        risk_contributions.append(rc)

    return {
        "return": port_return,
        "volatility": port_vol,
        "sharpe_ratio": sharpe,
        "risk_contributions": risk_contributions,
    }
