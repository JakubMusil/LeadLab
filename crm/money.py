"""
Exchange Rate Engine – core money utilities for LeadLab.

Public API:
    get_rate(firm, from_currency, to_currency, date) -> Decimal | None
    to_canonical(amount, from_currency, firm, date) -> Decimal | None

SUPPORTED_CURRENCIES mirrors the frontend constant so both sides stay in sync.
"""
from __future__ import annotations

import datetime
import logging
from decimal import Decimal
from typing import Optional

from django.db.models import Q

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported currencies (same list as frontend-spa/src/composables/useMoney.ts)
# ---------------------------------------------------------------------------

SUPPORTED_CURRENCIES: list[str] = [
    "CZK", "EUR", "USD", "GBP", "PLN", "HUF", "CHF",
    "NOK", "SEK", "DKK", "RON", "BGN", "UAH", "RSD",
]

# Fallback window: how many days back we look for a system rate when the
# exact date is unavailable (e.g. weekends, ECB not yet published).
_ECB_FALLBACK_DAYS = 7


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_system_rate(
    from_currency: str,
    to_currency: str,
    target_date: datetime.date,
) -> Optional[Decimal]:
    """
    Look up a rate from SystemExchangeRate (ECB data).

    ECB publishes EUR-based rates.  We support three cases:
      1. Direct: from_currency == 'EUR'  → rate = EUR/to_currency
      2. Inverse: to_currency == 'EUR'   → rate = 1 / (EUR/from_currency)
      3. Cross via EUR pivot             → rate = (EUR/to_currency) / (EUR/from_currency)

    Returns None if the required rates are not available.
    """
    from firms.models import SystemExchangeRate  # avoid circular import

    cutoff = target_date - datetime.timedelta(days=_ECB_FALLBACK_DAYS)

    def _fetch(base: str, quote: str) -> Optional[Decimal]:
        qs = (
            SystemExchangeRate.objects
            .filter(
                base_currency=base,
                quote_currency=quote,
                date__lte=target_date,
                date__gte=cutoff,
            )
            .order_by("-date")
        )
        obj = qs.first()
        return obj.rate if obj else None

    if from_currency == to_currency:
        return Decimal("1")

    # Case 1: EUR → X
    if from_currency == "EUR":
        return _fetch("EUR", to_currency)

    # Case 2: X → EUR
    if to_currency == "EUR":
        eur_from = _fetch("EUR", from_currency)
        if eur_from is None or eur_from == 0:
            return None
        return (Decimal("1") / eur_from).quantize(Decimal("0.00000001"))

    # Case 3: cross via EUR
    eur_from = _fetch("EUR", from_currency)
    eur_to = _fetch("EUR", to_currency)
    if eur_from is None or eur_to is None or eur_from == 0:
        return None
    return (eur_to / eur_from).quantize(Decimal("0.00000001"))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_rate(
    firm,
    from_currency: str,
    to_currency: str,
    date: Optional[datetime.date] = None,
) -> Optional[Decimal]:
    """
    Return the exchange rate from_currency → to_currency for the given date.

    Priority:
      1. FirmExchangeRate with source='manual' for this firm (highest priority,
         regardless of exchange_rate_mode).
      2. If exchange_rate_mode == 'auto': SystemExchangeRate from ECB.
      3. If no rate found: return None (caller handles gracefully).
    """
    from firms.models import FirmExchangeRate  # avoid circular import

    if from_currency == to_currency:
        return Decimal("1")

    target_date = date or datetime.date.today()

    # 1. Firm-level manual override (always wins)
    firm_rate = (
        FirmExchangeRate.objects
        .filter(
            firm=firm,
            from_currency=from_currency,
            to_currency=to_currency,
            valid_from__lte=target_date,
        )
        .filter(Q(valid_to__isnull=True) | Q(valid_to__gte=target_date))
        .order_by("-valid_from")
        .first()
    )
    if firm_rate:
        return firm_rate.rate

    # 2. Auto ECB
    if firm.exchange_rate_mode == "auto":
        sys_rate = _get_system_rate(from_currency, to_currency, target_date)
        if sys_rate is not None:
            return sys_rate

    return None


def to_canonical(
    amount: Decimal,
    from_currency: str,
    firm,
    date: Optional[datetime.date] = None,
) -> tuple[Optional[Decimal], Optional[Decimal]]:
    """
    Convert *amount* (in *from_currency*) to firm.default_currency.

    Returns:
        (canonical_amount, rate_used)
        Both are None if the rate is unavailable.
    """
    if from_currency == firm.default_currency:
        return amount, Decimal("1")

    rate = get_rate(firm, from_currency, firm.default_currency, date)
    if rate is None:
        return None, None

    canonical = (amount * rate).quantize(Decimal("0.01"))
    return canonical, rate
