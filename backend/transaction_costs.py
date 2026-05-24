"""
transaction_costs.py
--------------------
Reality-check layer that converts a clean backtest return into a
real-world return by accounting for:

  1. Commissions    – flat fee or % per trade leg
  2. Slippage       – market-impact cost on fills
  3. Bid-ask spread – round-trip cost per trade
  4. Taxes          – short-term / long-term capital-gains treatment

Public API
----------
calculate_commissions(trades, ...)  →  dict
calculate_slippage(trades, ...)     →  dict
calculate_bid_ask_spread(trades, …) →  dict
calculate_taxes(trades, ...)        →  dict
calculate_win_rate(trades)          →  dict
calculate_real_costs(trades, account_size, config)  →  dict   ← main entry-point

Input formats accepted
----------------------
A. Detailed trade list (list[dict] or list of rows from parsed CSV):
   [
     {"date": "2024-01-15", "symbol": "AAPL", "action": "BUY",  "price": 185.50, "shares": 10},
     {"date": "2024-02-20", "symbol": "AAPL", "action": "SELL", "price": 195.20, "shares": 10},
     ...
   ]

B. Summary dict (when only aggregate metrics are available):
   {
     "initial_capital": 100000,
     "final_balance":   147000,
     "num_trades":      156,
     "win_rate":        0.62,
     "start_date":      "2021-01-01",
     "end_date":        "2025-12-31"
   }

Both formats are normalised internally before computation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default cost assumptions (all overridable via CostConfig)
# ---------------------------------------------------------------------------

DEFAULT_COMMISSION_PER_TRADE: float = 0.00   # Commission in USD per trade leg — $0 for commission-free brokers (Robinhood, Webull, etc.)
DEFAULT_SLIPPAGE_PCT: float = 0.008          # 0.8% per fill (round-trip = ×2)
DEFAULT_SPREAD_PCT: float = 0.002            # 0.2% round-trip
DEFAULT_SHORT_TERM_TAX_RATE: float = 0.37   # Federal max short-term CGT
DEFAULT_LONG_TERM_TAX_RATE: float = 0.20    # Federal long-term CGT
SHORT_TERM_HOLD_DAYS: int = 365              # < 1 year → short-term treatment

MIN_CLOSED_TRADES_FOR_CONCLUSIONS: int = 30  # Minimum closed trades for statistically reliable results

def check_trade_count_sufficiency(closed_trade_count: int) -> dict | None:
    if closed_trade_count < MIN_CLOSED_TRADES_FOR_CONCLUSIONS:
        return {
            "type": "insufficient_trade_count",
            "level": "warning",
            "message": (
                f"Only {closed_trade_count} closed trade(s) found. "
                f"At least {MIN_CLOSED_TRADES_FOR_CONCLUSIONS} closed trades are needed to draw reliable conclusions."
            ),
            "count": closed_trade_count,
        }
    return None


# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------

@dataclass
class CostConfig:
    """
    Holds all tunable cost parameters.  Defaults match a commission-free
    retail broker (Robinhood, Webull, etc.) — hidden costs like slippage
    and bid-ask spread still apply.
    """
    # Commissions
    commission_per_trade: float = DEFAULT_COMMISSION_PER_TRADE
    commission_is_pct: bool = False          # True  → treat as % of trade value
                                             # False → treat as flat $ amount

    # Slippage (applied once per trade, representing round-trip impact)
    slippage_pct: float = DEFAULT_SLIPPAGE_PCT

    # Bid-ask spread (round-trip)
    spread_pct: float = DEFAULT_SPREAD_PCT

    # Taxes
    short_term_tax_rate: float = DEFAULT_SHORT_TERM_TAX_RATE
    long_term_tax_rate: float = DEFAULT_LONG_TERM_TAX_RATE
    apply_taxes: bool = True

    # Convenience: override slippage bucket
    slippage_preset: str | None = None  # "low" | "medium" | "high" | None


_SLIPPAGE_PRESETS: dict[str, float] = {
    "low":    0.003,   # 0.3% – large-cap, liquid stocks
    "medium": 0.008,   # 0.8% – typical retail
    "high":   0.020,   # 2.0% – small-cap / illiquid
}

_SPREAD_PRESETS: dict[str, float] = {
    "low":    0.001,
    "medium": 0.002,
    "high":   0.005,
}


# ---------------------------------------------------------------------------
# Internal trade representation
# ---------------------------------------------------------------------------

@dataclass
class NormalisedTrade:
    """Unified representation used by all calculators."""
    action: str            # "BUY" | "SELL"
    price: float
    shares: float
    trade_value: float     # abs(price × shares)
    entry_date: date | None = None
    exit_date: date | None = None
    hold_days: int | None = None
    profit: float | None = None   # gross profit for this round-trip (SELL side)
    symbol: str = ""


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _parse_date(val: Any) -> date | None:
    if val is None:
        return None
    if isinstance(val, (date, datetime)):
        return val if isinstance(val, date) else val.date()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(str(val).strip(), fmt).date()
        except ValueError:
            continue
    return None


def _normalise_detailed(trades: list[dict]) -> list[NormalisedTrade]:
    """Convert a list of raw trade dicts into NormalisedTrade objects."""
    normalised: list[NormalisedTrade] = []
    # Group into round-trips: match each BUY to its next SELL for the same symbol
    open_positions: dict[str, list[NormalisedTrade]] = {}

    for raw in trades:
        action = str(raw.get("action", "")).upper().strip()
        if action not in ("BUY", "SELL"):
            continue

        price  = float(raw.get("price",  0) or 0)
        shares = float(raw.get("shares", 0) or raw.get("quantity", 0) or 0)
        symbol = str(raw.get("symbol", "UNKNOWN")).upper().strip()
        d      = _parse_date(raw.get("date") or raw.get("datetime") or raw.get("timestamp"))
        tv     = abs(price * shares)

        nt = NormalisedTrade(
            action=action,
            price=price,
            shares=shares,
            trade_value=tv,
            entry_date=d if action == "BUY" else None,
            exit_date=d  if action == "SELL" else None,
            symbol=symbol,
        )

        if action == "BUY":
            open_positions.setdefault(symbol, []).append(nt)
            normalised.append(nt)
        elif action == "SELL":
            nt.exit_date = d
            # Try to find matching BUY
            if symbol in open_positions and open_positions[symbol]:
                buy = open_positions[symbol].pop(0)
                nt.entry_date = buy.entry_date
                if nt.entry_date and nt.exit_date:
                    nt.hold_days = (nt.exit_date - nt.entry_date).days
                nt.profit = (nt.price - buy.price) * nt.shares
            normalised.append(nt)

    return normalised


def _normalise_summary(summary: dict) -> list[NormalisedTrade]:
    """
    Convert a summary-only dict into synthetic NormalisedTrade objects so that
    the same cost calculators can operate on them.  We synthesise average-sized
    trades based on the aggregate metrics.
    """
    initial_capital = float(summary.get("initial_capital", 100_000) or 100_000)
    final_balance   = float(summary.get("final_balance",   initial_capital) or initial_capital)
    num_trades      = int(summary.get("num_trades",    0) or 0)
    win_rate        = float(summary.get("win_rate",   0.5) or 0.5)
    start           = _parse_date(summary.get("start_date"))
    end             = _parse_date(summary.get("end_date"))

    if num_trades == 0:
        return []

    gross_profit    = final_balance - initial_capital
    avg_trade_value = initial_capital / max(num_trades / 2, 1)  # rough approximation

    hold_days: int | None = None
    if start and end:
        total_days = (end - start).days
        hold_days  = max(1, total_days // max(num_trades // 2, 1))

    trades: list[NormalisedTrade] = []
    num_wins  = round(num_trades * win_rate)
    num_round = num_trades // 2  # BUY+SELL pairs (simplified)

    for i in range(num_round):
        is_win = i < num_wins // 2
        profit_per_rt = (gross_profit / num_round) if num_round else 0

        nt = NormalisedTrade(
            action="SELL",           # represent each round-trip as one SELL
            price=avg_trade_value / max(10, 1),
            shares=10,
            trade_value=avg_trade_value,
            hold_days=hold_days,
            profit=profit_per_rt if is_win else -abs(profit_per_rt) * 0.4,
            symbol="SYNTHETIC",
        )
        trades.append(nt)

    return trades


def _is_summary(data: Any) -> bool:
    return isinstance(data, dict) and "initial_capital" in data


def _to_normalised(data: Any) -> tuple[list[NormalisedTrade], bool]:
    """
    Returns (normalised_trades, is_summary_mode).
    Accepts list[dict] (detailed) or dict (summary).
    """
    if _is_summary(data):
        return _normalise_summary(data), True
    if isinstance(data, list):
        return _normalise_detailed(data), False
    raise ValueError(
        "trades must be either a list of trade dicts or a summary dict. "
        f"Got: {type(data)}"
    )


# ---------------------------------------------------------------------------
# 1. Commission calculator
# ---------------------------------------------------------------------------

def calculate_commissions(
    trades: Any,
    commission_per_trade: float = DEFAULT_COMMISSION_PER_TRADE,
    commission_is_pct: bool = False,
) -> dict:
    """
    Calculate total commission costs.

    $1 per trade leg (every BUY and SELL separately)
    """
    normalised, is_summary = _to_normalised(trades)

    if not normalised:
        return {
            "total_commission_usd": 0.0,
            "per_trade_avg_usd": 0.0,
            "num_trades": 0,
            "commission_rate": commission_per_trade,
            "is_pct": commission_is_pct,
        }

    total = 0.0
    for nt in normalised:
        if commission_is_pct:
            total += nt.trade_value * commission_per_trade
        else:
            total += commission_per_trade

    num = len(normalised)
    return {
        "total_commission_usd": round(total, 4),
        "per_trade_avg_usd":    round(total / num, 4),
        "num_trades":           num,
        "commission_rate":      commission_per_trade,
        "is_pct":               commission_is_pct,
    }


# ---------------------------------------------------------------------------
# 2. Slippage calculator
# ---------------------------------------------------------------------------

def calculate_slippage(
    trades: Any,
    slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
    preset: str | None = None,
) -> dict:
    """
    Calculate market-impact / slippage costs.

    Difference between the expected fill price (what the backtest assumes) and the actual fill price
    """
    if preset and preset in _SLIPPAGE_PRESETS:
        slippage_pct = _SLIPPAGE_PRESETS[preset]

    # Validate slippage_pct
    if not isinstance(slippage_pct, (int, float)) or slippage_pct < 0 or slippage_pct > 1:
        raise ValueError(f"slippage_pct must be between 0 and 1, got {slippage_pct}")

    normalised, is_summary = _to_normalised(trades)

    def _market_impact_pct(slippage_usd, trade_value):
        if not trade_value or trade_value <= 0:
            return 0.0
        return (slippage_usd / trade_value) * 100

    if not normalised:
        return {
            "total_slippage_usd":  0.0,
            "per_trade_avg_usd":   0.0,
            "num_trades":          0,
            "slippage_pct_used":   slippage_pct,
            "preset":              preset,
            "per_trade_breakdown": [],
        }

    per_trade_breakdown = []
    for nt in normalised:
        tv = nt.trade_value
        slippage_usd = round(tv * slippage_pct, 4) if tv > 0 else 0.0
        mipct = _market_impact_pct(slippage_usd, tv)
        per_trade_breakdown.append({
            "symbol": nt.symbol,
            "action": nt.action,
            "trade_value": round(tv, 4),
            "slippage_usd": slippage_usd,
            "market_impact_pct": round(mipct, 6),
        })

    total = sum(entry["slippage_usd"] for entry in per_trade_breakdown)
    num   = len(normalised)

    return {
        "total_slippage_usd":  round(total, 4),
        "per_trade_avg_usd":   round(total / num, 4) if num else 0.0,
        "num_trades":          num,
        "slippage_pct_used":   slippage_pct,
        "preset":              preset,
        "per_trade_breakdown": per_trade_breakdown,
    }


# ---------------------------------------------------------------------------
# 3. Bid-ask spread calculator
# ---------------------------------------------------------------------------

def calculate_bid_ask_spread(
    trades: Any,
    spread_pct: float = DEFAULT_SPREAD_PCT,
    preset: str | None = None,
) -> dict:
    """
    Calculate round-trip bid-ask spread costs for each trade leg.

    Returns a dict with total and per-trade breakdown. Each entry in per_trade_breakdown includes:
      - symbol
      - action
      - trade_value
      - round_trip_spread_usd (cost for this leg)
      - spread_rate (the spread_pct used)
    """
    if preset and preset in _SPREAD_PRESETS:
        spread_pct = _SPREAD_PRESETS[preset]

    if not isinstance(spread_pct, (int, float)) or spread_pct < 0 or spread_pct > 1:
        raise ValueError(f"spread_pct must be between 0 and 1, got {spread_pct}")

    normalised, is_summary = _to_normalised(trades)

    if not normalised:
        return {
            "total_spread_usd":    0.0,
            "per_trade_avg_usd":   0.0,
            "num_trades":          0,
            "spread_pct_used":     spread_pct,
            "preset":              preset,
            "per_trade_breakdown": [],
        }

    per_trade_breakdown = []
    for nt in normalised:
        tv = nt.trade_value
        round_trip_spread_usd = round(tv * spread_pct, 4) if tv > 0 else 0.0
        per_trade_breakdown.append({
            "symbol":                nt.symbol,
            "action":                nt.action,
            "trade_value":           round(tv, 4),
            "round_trip_spread_usd": round_trip_spread_usd,
            "spread_rate":           spread_pct,
        })

    total = sum(entry["round_trip_spread_usd"] for entry in per_trade_breakdown)
    num   = len(normalised)

    return {
        "total_spread_usd":    round(total, 4),
        "per_trade_avg_usd":   round(total / num, 4),
        "num_trades":          num,
        "spread_pct_used":     spread_pct,
        "preset":              preset,
        "per_trade_breakdown": per_trade_breakdown,
    }


# ---------------------------------------------------------------------------
# 4. Tax calculator
# ---------------------------------------------------------------------------

def calculate_taxes(
    trades: Any,
    short_term_tax_rate: float = DEFAULT_SHORT_TERM_TAX_RATE,
    long_term_tax_rate:  float = DEFAULT_LONG_TERM_TAX_RATE,
    apply_taxes: bool = True,
    offset_losses: bool = True,
) -> dict:
    """
    Estimate capital-gains tax liability on trades.

    Trades held <= 365 days are taxed at the short-term rate;
    trades held > 365 days at the long-term rate (IRS: more than 1 year).
    If hold duration is unknown (e.g. summary input), short-term rate is used.

    By default, losses offset gains within each category (short/long term).
    Set offset_losses=False to use conservative approach (no offsetting).
    """
    if not apply_taxes:
        return {
            "total_tax_usd":            0.0,
            "short_term_tax_usd":       0.0,
            "long_term_tax_usd":        0.0,
            "short_term_gains_usd":     0.0,
            "long_term_gains_usd":      0.0,
            "total_gains_usd":          0.0,
            "total_losses_usd":         0.0,
            "num_profitable_trades":    0,
            "num_losing_trades":        0,
            "effective_tax_rate":       0.0,
            "short_term_tax_rate_used": short_term_tax_rate,
            "long_term_tax_rate_used":  long_term_tax_rate,
        }

    from datetime import timedelta
    normalised, is_summary = _to_normalised(trades)

    short_term_net = 0.0
    long_term_net = 0.0
    short_gains = 0.0
    long_gains = 0.0
    short_losses = 0.0
    long_losses = 0.0
    n_win = 0
    n_loss = 0
    n_short = 0
    n_long = 0

    for nt in normalised:
        if nt.profit is None or nt.hold_days is None or nt.hold_days < 0:
            continue
        hold = nt.hold_days
        if hold > 365:
            n_long += 1
            if nt.profit > 0:
                long_gains += nt.profit
                long_term_net += nt.profit
                n_win += 1
            else:
                long_losses += abs(nt.profit)
                long_term_net += nt.profit
                n_loss += 1
        else:
            n_short += 1
            if nt.profit > 0:
                short_gains += nt.profit
                short_term_net += nt.profit
                n_win += 1
            else:
                short_losses += abs(nt.profit)
                short_term_net += nt.profit
                n_loss += 1

    if offset_losses:
        short_taxable = max(short_term_net, 0.0)
        long_taxable = max(long_term_net, 0.0)
    else:
        short_taxable = short_gains
        long_taxable = long_gains

    short_tax = short_taxable * short_term_tax_rate
    long_tax = long_taxable * long_term_tax_rate
    total_tax = short_tax + long_tax
    total_gains = short_gains + long_gains
    total_losses = short_losses + long_losses
    effective_rate = (total_tax / (short_taxable + long_taxable)) if (short_taxable + long_taxable) > 0 else 0.0

    return {
        "total_tax_usd":            round(total_tax,     4),
        "short_term_tax_usd":       round(short_tax,     4),
        "long_term_tax_usd":        round(long_tax,      4),
        "short_term_gains_usd":     round(short_gains,   4),
        "long_term_gains_usd":      round(long_gains,    4),
        "total_gains_usd":          round(total_gains,   4),
        "total_losses_usd":         round(total_losses,  4),
        "num_profitable_trades":    n_win,
        "num_losing_trades":        n_loss,
        "effective_tax_rate":       round(effective_rate, 6),
        "short_term_tax_rate_used": short_term_tax_rate,
        "long_term_tax_rate_used":  long_term_tax_rate,
        "offset_losses":            offset_losses,
    }


# ---------------------------------------------------------------------------
# 5. Win-rate calculator
# ---------------------------------------------------------------------------

def calculate_win_rate(trades: Any) -> dict:
    """
    Calculate the percentage of closed trades that were profitable.

    A closed trade is a round-trip (matched BUY + SELL) with a numeric profit value.
    Trades with exactly zero profit or non-numeric profit are counted as losses.
    """
    normalised, _ = _to_normalised(trades)

    # Only SELL-side legs with a numeric profit value represent closed round-trips
    def _is_numeric(val):
        return isinstance(val, (int, float))

    closed = [nt for nt in normalised if nt.action == "SELL" and _is_numeric(nt.profit)]
    num_closed = len(closed)

    if num_closed == 0:
        return {
            "win_rate_pct":       0.0,
            "win_rate":           0.0,
            "num_closed_trades":  0,
            "num_winning_trades": 0,
            "num_losing_trades":  0,
            "low_sample_warning": True,
            "low_sample_warning_description": (
                "No closed trades were found, so a win rate cannot be calculated. "
                "Upload a trade history that includes both entries and exits."
            ),
            "closed_trade_count": 0,
        }

    num_wins   = sum(1 for nt in closed if nt.profit > 0)
    num_losses = num_closed - num_wins
    _low_sample = num_closed < MIN_CLOSED_TRADES_FOR_CONCLUSIONS

    return {
        "win_rate_pct":       round(num_wins / num_closed * 100, 4),
        "win_rate":           round(num_wins / num_closed, 6),
        "num_closed_trades":  num_closed,
        "num_winning_trades": num_wins,
        "num_losing_trades":  num_losses,
        "low_sample_warning": _low_sample,
        "low_sample_warning_description": (
            (
                f"Only {num_closed} closed trades were found — fewer than the "
                f"{MIN_CLOSED_TRADES_FOR_CONCLUSIONS} needed for a reliable win rate. "
                "A short lucky or unlucky streak could make this number look very different "
                "from your long-run performance. Add more trade history for a stable read."
            ) if _low_sample else (
                f"{num_closed} closed trades — enough for a reliable win rate figure."
            )
        ),
        "closed_trade_count": num_closed,
    }


# ---------------------------------------------------------------------------
# 6. Plain-English cost summary helper
# ---------------------------------------------------------------------------

def _plain_english_summary(
    gross_profit_usd: float,
    after_costs_and_tax_profit_usd: float,
    total_all_costs_usd: float,
    gross_return_pct: float,
    after_costs_and_tax_pct: float,
) -> str:
    """Turn the cost numbers into a single sentence a non-expert can understand."""
    gross = gross_profit_usd
    net   = after_costs_and_tax_profit_usd
    costs = total_all_costs_usd

    if gross == 0.0:
        return "You broke even before costs. Costs and taxes reduced your return."

    if gross < 0:
        return (
            f"You lost ${abs(gross):.2f} before costs. "
            f"Costs and taxes added ${costs:.2f} more, for a total loss of ${abs(net):.2f}."
        )

    if net <= 0:
        return (
            f"You made ${gross:.2f} on paper ({gross_return_pct:.1f}%), but costs and taxes "
            f"of ${costs:.2f} wiped out the profit, leaving a net loss of ${abs(net):.2f}."
        )

    fraction_kept = net / gross
    if fraction_kept >= 0.90:
        kept_phrase = "nearly all"
    elif fraction_kept >= 0.65:
        kept_phrase = "most"
    elif fraction_kept >= 0.45:
        kept_phrase = "about half"
    elif fraction_kept >= 0.25:
        kept_phrase = "less than half"
    else:
        kept_phrase = "only a small portion"

    return (
        f"You made ${gross:.2f} before costs ({gross_return_pct:.1f}%). "
        f"Costs and taxes took ${costs:.2f}, so you kept {kept_phrase} — "
        f"${net:.2f} ({after_costs_and_tax_pct:.1f}% net return)."
    )


# ---------------------------------------------------------------------------
# 6. Main entry-point: calculate_real_costs
# ---------------------------------------------------------------------------

def calculate_real_costs(
    trades: Any,
    account_size: float,
    config: CostConfig | None = None,
    offset_losses: bool = True,
) -> dict:
    """
    Master function — run all four cost components and return a unified
    breakdown + adjusted-return figures.
    """
    if config is None:
        config = CostConfig()

    # Apply slippage preset if provided
    slippage_pct = config.slippage_pct
    if config.slippage_preset and config.slippage_preset in _SLIPPAGE_PRESETS:
        slippage_pct = _SLIPPAGE_PRESETS[config.slippage_preset]

    # Determine gross return from input
    gross_return_pct: float = 0.0
    gross_profit_usd: float = 0.0

    if _is_summary(trades):
        initial = float(trades.get("initial_capital", account_size) or account_size)
        final   = float(trades.get("final_balance",   account_size) or account_size)
        gross_profit_usd = final - initial
        gross_return_pct = (gross_profit_usd / initial * 100) if initial else 0.0
    else:
        # Derive gross profit from sell-side trades
        normalised, _ = _to_normalised(trades)
        gross_profit_usd = sum(
            nt.profit for nt in normalised if nt.profit is not None
        )
        gross_return_pct = (gross_profit_usd / account_size * 100) if account_size else 0.0

    # Run individual calculators
    win_rate = calculate_win_rate(trades)
    comm   = calculate_commissions(
        trades,
        commission_per_trade=config.commission_per_trade,
        commission_is_pct=config.commission_is_pct,
    )
    slip   = calculate_slippage(
        trades,
        slippage_pct=slippage_pct,
        preset=config.slippage_preset,
    )
    spread = calculate_bid_ask_spread(
        trades,
        spread_pct=config.spread_pct,
    )
    taxes  = calculate_taxes(
        trades,
        short_term_tax_rate=config.short_term_tax_rate,
        long_term_tax_rate=config.long_term_tax_rate,
        apply_taxes=config.apply_taxes,
        offset_losses=offset_losses,
    )

    # Aggregate
    total_trading_costs_usd = (
        comm["total_commission_usd"]
        + slip["total_slippage_usd"]
        + spread["total_spread_usd"]
    )
    total_tax_usd       = taxes["total_tax_usd"]
    total_all_costs_usd = total_trading_costs_usd + total_tax_usd

    total_cost_pct          = (total_trading_costs_usd / account_size * 100) if account_size else 0.0
    total_all_costs_pct     = (total_all_costs_usd      / account_size * 100) if account_size else 0.0

    after_costs_profit_usd          = gross_profit_usd - total_trading_costs_usd
    after_costs_and_tax_profit_usd  = gross_profit_usd - total_all_costs_usd

    after_costs_pct          = gross_return_pct - total_cost_pct
    after_costs_and_tax_pct  = gross_return_pct - total_all_costs_pct

    # Build warnings
    warnings: list[str] = []
    if gross_return_pct == 0:
        warnings.append("Gross return is 0% — verify that trades or summary data are correctly formatted.")
    if total_trading_costs_usd > abs(gross_profit_usd) * 0.5:
        warnings.append("Trading costs exceed 50% of gross profit — trade frequency may be too high.")
    if after_costs_and_tax_pct < 0 < gross_return_pct:
        warnings.append("Strategy is profitable gross but unprofitable after all costs and taxes.")
    normalised_check, is_summary_mode = _to_normalised(trades)
    if len(normalised_check) < 30:
        warnings.append(
            f"Only {len(normalised_check)} trade legs detected. "
            "Statistical significance requires 30+ trades."
        )

    return {
        "input_summary": {
            "num_trades":      len(normalised_check),
            "is_summary_mode": is_summary_mode,
            "is_summary_mode_description": (
                "Analysis ran in summary mode — your input contained only aggregate "
                "totals (e.g. final balance, overall win rate) rather than individual "
                "trade records. Cost estimates are therefore approximations. "
                "Upload a detailed trade list for trade-by-trade precision."
            ) if is_summary_mode else (
                "Analysis ran on individual trade records, so cost figures are "
                "calculated precisely for each entry and exit."
            ),
            "account_size":    account_size,
        },
        "commissions":   comm,
        "slippage":      slip,
        "bid_ask_spread": spread,
        "taxes":         taxes,
        "win_rate":      win_rate,
        "cost_summary": {
            "gross_return_pct":        round(gross_return_pct,         4),
            "after_costs_return_pct":  round(after_costs_pct,          4),
            "after_tax_return_pct":    round(after_costs_and_tax_pct,  4),
            "total_trading_costs_usd": round(total_trading_costs_usd,  4),
            "total_trading_costs_pct": round(total_cost_pct,           4),
            "total_tax_usd":           round(total_tax_usd,             4),
            "total_all_costs_usd":     round(total_all_costs_usd,       4),
            "total_all_costs_pct":     round(total_all_costs_pct,       4),
            "plain_english_summary":   _plain_english_summary(
                gross_profit_usd,
                after_costs_and_tax_profit_usd,
                total_all_costs_usd,
                gross_return_pct,
                after_costs_and_tax_pct,
            ),
            "breakdown_pct": {
                "commissions":   round(comm["total_commission_usd"]   / account_size * 100, 4) if account_size else 0,
                "slippage":      round(slip["total_slippage_usd"]     / account_size * 100, 4) if account_size else 0,
                "bid_ask_spread":round(spread["total_spread_usd"]     / account_size * 100, 4) if account_size else 0,
                "taxes":         round(total_tax_usd                   / account_size * 100, 4) if account_size else 0,
            },
        },
        "adjusted_returns": {
            "gross_return_pct":                round(gross_return_pct,              4),
            "after_costs_pct":                 round(after_costs_pct,               4),
            "after_costs_and_tax_pct":         round(after_costs_and_tax_pct,       4),
            "gross_profit_usd":                round(gross_profit_usd,              4),
            "after_costs_profit_usd":          round(after_costs_profit_usd,        4),
            "after_costs_and_tax_profit_usd":  round(after_costs_and_tax_profit_usd,4),
        },
        "metadata": {
            "config_used": {
                "commission_per_trade":  config.commission_per_trade,
                "commission_is_pct":     config.commission_is_pct,
                "slippage_pct":          slippage_pct,
                "slippage_preset":       config.slippage_preset,
                "spread_pct":            config.spread_pct,
                "short_term_tax_rate":   config.short_term_tax_rate,
                "long_term_tax_rate":    config.long_term_tax_rate,
                "apply_taxes":           config.apply_taxes,
            },
            "warnings": warnings,
        },
    }
