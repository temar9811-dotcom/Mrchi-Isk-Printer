# FILE: app/utils/formatting.py
# VERSION: 1.1.0


def fmt_num(value: float, decimals: int = 2) -> str:
    v = float(value)
    neg = "-" if v < 0 else ""
    a = abs(v)

    if a >= 1_000_000_000:
        return f"{neg}{a / 1_000_000_000:.{decimals}f}B"
    if a >= 1_000_000:
        return f"{neg}{a / 1_000_000:.{decimals}f}M"
    if a >= 1_000:
        return f"{neg}{a / 1_000:.{decimals}f}t"
    return f"{neg}{a:,.{decimals}f}"


def fmt_age(seconds) -> str:
    """
    Human friendly cache age: 'just now', '5m ago', '3h ago', '2d ago'.
    """
    if seconds is None:
        return "never"
    seconds = int(seconds)
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    return f"{hours // 24}d ago"