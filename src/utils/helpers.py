"""
ExaSignal - Funções Auxiliares
"""
from datetime import datetime, timezone


def utc_now() -> datetime:
    """Retorna datetime atual em UTC."""
    return datetime.now(timezone.utc)


def format_usd(amount: float) -> str:
    """Formata valor em USD (ex: $25k, $1.5M)."""
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.1f}M"
    elif amount >= 1_000:
        return f"${amount / 1_000:.0f}k"
    else:
        return f"${amount:.0f}"


def truncate_text(text: str, max_length: int = 100) -> str:
    """Trunca texto com ellipsis se exceder limite."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."
