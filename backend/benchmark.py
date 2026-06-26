"""
Fetches historical returns for a given ticker over the date range of uploaded trades.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta

import yfinance as yf

logger = logging.getLogger(__name__)

# Simple in-process cache: (ticker, start_str, end_str) -> result dict or None
_cache: dict[tuple[str, str, str], dict | None] = {}

# Minimum number of trading day rows required for a meaningful return
MIN_TRADING_DAYS = 2


def fetch_benchmark(trades: list[dict], ticker: str) -> dict | None:
    """Return return data for the given ticker covering the date range of the given trades.

    Extracts the earliest and latest trade dates, fetches adjusted close prices
    via yfinance, and returns a summary dict for benchmarking.
    Returns None if trades are empty, data is unavailable, or the period is too short.
    """
    if not trades:
        return None

    if not ticker or not ticker.strip():
        logger.warning("fetch_benchmark called with empty ticker")
        return None

    dates = []
    for trade in trades:
        d = trade.get("date")
        if d:
            try:
                dates.append(datetime.strptime(d, "%Y-%m-%d"))
            except ValueError:
                pass

    if not dates:
        return None

    start = min(dates)
    end = max(dates)

    cache_key = (ticker, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    if cache_key in _cache:
        return _cache[cache_key]

    # yfinance end parameter is exclusive, so add one day to include the last trade date
    fetch_end = end + timedelta(days=1)

    try:
        data = yf.download(ticker, start=start, end=fetch_end, auto_adjust=True, progress=False)
        # yfinance 1.x returns MultiIndex columns (field, ticker) for all downloads
        if hasattr(data.columns, "levels"):
            data.columns = data.columns.get_level_values(0)
        data.columns = data.columns.str.lower()
    except Exception as exc:
        logger.warning("%s benchmark fetch failed: %s", ticker, exc)
        _cache[cache_key] = None
        return None

    if data.empty:
        logger.warning("%s benchmark: no data available for %s to %s", ticker, start.date(), end.date())
        _cache[cache_key] = None
        return None

    data = data.sort_index()

    if len(data) < MIN_TRADING_DAYS:
        logger.warning(
            "%s benchmark: only %d trading day(s) of data for %s to %s — period too short",
            ticker, len(data), start.date(), end.date(),
        )
        _cache[cache_key] = None
        return None

    start_price = float(data["close"].iloc[0])
    end_price = float(data["close"].iloc[-1])

    if start_price == 0:
        logger.warning("%s benchmark: start price is zero, cannot compute return", ticker)
        _cache[cache_key] = None
        return None

    total_return_pct = round((end_price - start_price) / start_price * 100, 4)

    # Actual trading day dates yfinance used (may differ from trade dates if
    # the trade date fell on a weekend or holiday)
    actual_start_date = data.index[0].strftime("%Y-%m-%d")
    actual_end_date = data.index[-1].strftime("%Y-%m-%d")

    result = {
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
        "actual_start_date": actual_start_date,
        "actual_end_date": actual_end_date,
        "start_price": round(start_price, 4),
        "end_price": round(end_price, 4),
        "total_return_pct": total_return_pct,
    }
    _cache[cache_key] = result
    return result


def compare_user_return_to_benchmarks(
    trades: list[dict],
    after_cost_return_pct: float,
    tickers: list[str] | None = None,
) -> dict:
    """Compare the user's after-cost return against one or more benchmark tickers.

    For each ticker, fetches the benchmark return over the same date range as
    the trades, then computes the difference (alpha). Returns a summary dict
    with per-ticker results and an overall best/worst comparison.

    Returns an empty comparisons list if trades are empty or no benchmark data
    is available for any ticker.
    """
    if not isinstance(after_cost_return_pct, (int, float)) or math.isnan(after_cost_return_pct):
        raise ValueError(
            f"after_cost_return_pct must be a valid number, got {after_cost_return_pct!r}"
        )

    if tickers is None:
        tickers = ["SPY", "QQQ"]

    comparisons = []
    for ticker in tickers:
        benchmark = fetch_benchmark(trades, ticker)
        if benchmark is None:
            comparisons.append({
                "ticker": ticker,
                "benchmark_return_pct": None,
                "alpha_pct": None,
                "available": False,
            })
            continue

        benchmark_return = benchmark["total_return_pct"]
        alpha = round(after_cost_return_pct - benchmark_return, 4)
        comparisons.append({
            "ticker": ticker,
            "benchmark_return_pct": benchmark_return,
            "alpha_pct": alpha,
            "outperformed": alpha > 0,  # ties (alpha == 0) do not count as outperforming
            "available": True,
        })

    available = [c for c in comparisons if c["available"]]

    result = {
        "after_cost_return_pct": round(after_cost_return_pct, 4),
        "comparisons": comparisons,
        "best_alpha_ticker": max(available, key=lambda c: c["alpha_pct"])["ticker"] if available else None,
        "any_benchmark_available": len(available) > 0,
    }
    result["verdict"] = generate_verdict(result)
    return result


def generate_verdict(comparison_result: dict) -> str:
    """Return a plain-English summary of how the user's strategy compared to benchmarks."""
    if not comparison_result["any_benchmark_available"]:
        return "No benchmark data available to compare your results."

    available = [c for c in comparison_result["comparisons"] if c["available"]]
    outperformed = [c for c in available if c["outperformed"]]

    user_return = comparison_result["after_cost_return_pct"]

    if len(outperformed) == len(available):
        # Show the benchmark the user barely beat for context
        nearest = min(available, key=lambda c: c["alpha_pct"])
        return (
            f"Your strategy beat every benchmark — you made {user_return:.1f}%"
            f" vs {nearest['ticker']}'s {nearest['benchmark_return_pct']:.1f}%."
        )

    # Worst = largest gap where user trailed
    worst = min(available, key=lambda c: c["alpha_pct"])

    if not outperformed:
        # Underperformed every benchmark
        return (
            f"Buying and holding {worst['ticker']} would have made you"
            f" {abs(worst['alpha_pct']):.1f}% more with less effort."
        )

    # Mixed: beat some, trailed others — name only the worst underperformer so
    # the quoted percentage always matches the named ticker
    winner_names = ", ".join(c["ticker"] for c in outperformed)
    return (
        f"Your strategy beat {winner_names} but buying and holding {worst['ticker']}"
        f" would have made you {abs(worst['alpha_pct']):.1f}% more with less effort."
    )
