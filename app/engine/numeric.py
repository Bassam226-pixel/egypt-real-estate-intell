"""Shared NaN/None-safe numeric coercion for values coming back from Dremio."""


def safe_float(val: object, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        v = float(val)
        if v != v:  # NaN
            return default
        return v
    except (ValueError, TypeError):
        return default


def safe_int(val: object, default: int = 0) -> int:
    if val is None:
        return default
    try:
        v = float(val)
        if v != v:  # NaN
            return default
        return int(v)
    except (ValueError, TypeError):
        return default
