"""
csv_analyzer.py
---------------
Parses, validates, and normalises uploaded trade history CSV files before
handing the cleaned trade data off to the analysis modules.
"""

from __future__ import annotations

import csv
import io
import logging
import math
import re
import statistics
from datetime import datetime
from typing import Any, Sequence

from transaction_costs import calculate_commissions, calculate_slippage, calculate_bid_ask_spread, DEFAULT_COMMISSION_PER_TRADE, DEFAULT_SLIPPAGE_PCT, DEFAULT_SPREAD_PCT, MIN_CLOSED_TRADES_FOR_CONCLUSIONS, check_trade_count_sufficiency
from statistical_tests import run_significance_tests
from benchmark import fetch_benchmark

SPY_TICKER = "SPY"
QQQ_TICKER = "QQQ"

def _normalize_action(action):
    """Normalize trade action to uppercase, handling None and whitespace."""
    return (str(action).strip().upper() if action is not None else "")


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants and Exceptions
# ---------------------------------------------------------------------------

FREE_TIER_TRADE_LIMIT = 100

class FreeTierLimitExceeded(ValueError):
    """Raised when the free tier trade limit is exceeded."""
    pass

REQUIRED_DETAILED_COLUMNS: frozenset[str] = frozenset(
    {"date", "symbol", "action", "price", "shares"}
)

REQUIRED_SUMMARY_KEYS: frozenset[str] = frozenset(
    {"initial_capital", "final_balance", "num_trades", "win_rate", "start_date", "end_date"}
)

# Binary file magic bytes that should never appear in a CSV
_BINARY_MAGIC: tuple[bytes, ...] = (
    b"MZ",           # Windows PE/EXE
    b"\x7fELF",      # Linux ELF
    b"#!",           # Shell/script shebang
    b"%PDF",         # PDF
    b"PK\x03\x04",   # ZIP / XLSX / DOCX
    b"\x89PNG",      # PNG image
    b"\x1f\x8b",     # GZIP archive
)

# Characters that trigger formula execution in spreadsheet tools (CSV injection)
_FORMULA_CHARS: frozenset[str] = frozenset({"=", "+", "@"})
# First characters that mark a cell as unsafe (formula chars + negative sign)
_UNSAFE_FIRST_CHARS: frozenset[str] = _FORMULA_CHARS | frozenset({"-"})

# Valid ticker: uppercase letters, digits, dots, hyphens; 1-20 chars total
_SYMBOL_RE = re.compile(r"^[A-Z0-9]([A-Z0-9.\-]{0,19})?$")

FORMAT_DESCRIPTIONS: dict[str, str] = {
    "detailed": (
        "Your file contains individual trade records (buy/sell entries). "
        "All cost and statistical calculations use your exact trade history."
    ),
    "summary": (
        "Your file contains summary totals only (e.g. overall win rate, final balance). "
        "Cost estimates will be approximations because individual trade records are not available."
    ),
}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _is_numeric_cell(value: str) -> bool:
    """Return True if value is a plain number (int, float, or scientific notation)."""
    try:
        float(value)
        return True
    except ValueError:
        return False


def _require_field(value: str | None, row_num: int, name: str) -> str:
    if value is None or not str(value).strip():
        raise ValueError(f"Row {row_num}: {name} is blank")
    return str(value).strip()


def _parse_positive_float(value: str | None, field: str, row_num: int) -> float:
    """Parse a string as a positive finite float, raising ValueError with a clear message."""
    value = _require_field(value, row_num, field)
    try:
        result = float(value)
    except ValueError:
        raise ValueError(f"Row {row_num}: {field} '{value}' is not a number")
    if math.isnan(result) or math.isinf(result) or result <= 0:
        raise ValueError(f"Row {row_num}: {field} must be positive, got '{value}'")
    return result


def _parse_iso_date(value: str | None, field: str, row_num: int) -> datetime:
    """Parse a strict YYYY-MM-DD date string, raising ValueError with a clear message."""
    value = _require_field(value, row_num, field)
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Row {row_num}: invalid {field} '{value}', expected YYYY-MM-DD")
    if parsed.strftime("%Y-%m-%d") != value:
        raise ValueError(f"Row {row_num}: invalid {field} '{value}', expected YYYY-MM-DD")
    return parsed


def _assert_content_safe(csv_data: str) -> None:
    """Raise ValueError if csv_data looks like a binary file or contains formula injection."""
    # Strip BOM at string level before encoding so it cannot hide binary signatures.
    # Use latin-1 (not utf-8) so each character maps to exactly one byte, preserving
    # extended-ASCII magic bytes like 0x89 (PNG) and 0x8b (GZIP) that would become
    # two-byte sequences in utf-8.
    check_str = csv_data[1:] if csv_data.startswith("\ufeff") else csv_data
    check_raw = check_str.encode("latin-1", errors="replace")

    for magic in _BINARY_MAGIC:
        if check_raw.startswith(magic):
            raise ValueError("CSV content appears to be a binary file, not a CSV")

    raw = csv_data.encode("utf-8", errors="replace")
    if b"\x00" in raw:
        raise ValueError("CSV content contains null bytes")

    # Check every cell for formula injection.
    # Numeric cells (including negative numbers and scientific notation) are safe.
    normalized = csv_data.replace("\r\n", "\n").replace("\r", "\n")
    reader = csv.reader(io.StringIO(normalized))
    for row in reader:
        for cell in row:
            stripped = cell.strip()
            if not stripped or _is_numeric_cell(stripped):
                continue
            if stripped[0] in _UNSAFE_FIRST_CHARS:
                raise ValueError(
                    "Your file contains a cell that cannot be processed safely "
                    "(e.g. a value starting with =, +, @, or -). "
                    "Please export a plain CSV from your trading platform."
                )


def _convert_semicolon_to_comma(csv_data: str) -> str:
    """Re-serialize a semicolon-delimited CSV as comma-delimited, preserving quoted fields."""
    out = io.StringIO()
    writer = csv.writer(out)
    for row in csv.reader(io.StringIO(csv_data), delimiter=";"):
        writer.writerow(row)
    return out.getvalue()


def _strip_row(row: dict) -> dict:
    # csv.DictReader can produce None for columns beyond the header width; skip those
    return {k: (v.strip() if isinstance(v, str) else v) for k, v in row.items()}


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def sanitize_csv(csv_data: str) -> str:
    """Strip BOM, normalise line endings, and convert semicolon delimiters to commas."""
    _assert_content_safe(csv_data)
    # Remove exactly one UTF-8 BOM if present
    if csv_data.startswith("\ufeff"):
        csv_data = csv_data[1:]
    # Normalise line endings to \n
    csv_data = csv_data.replace("\r\n", "\n").replace("\r", "\n")
    # Detect delimiter and convert semicolon-delimited files to comma-delimited
    first_non_empty = next((l for l in csv_data.split("\n") if l.strip()), "")
    try:
        dialect = csv.Sniffer().sniff(first_non_empty, delimiters=",;")
        logger.debug("CSV delimiter detected: %r", dialect.delimiter)
        if dialect.delimiter == ";":
            csv_data = _convert_semicolon_to_comma(csv_data)
    except csv.Error:
        # Sniffer can't decide (e.g. single-column file) — fall back to heuristic
        if ";" in first_non_empty and "," not in first_non_empty:
            csv_data = _convert_semicolon_to_comma(csv_data)
    return csv_data


# ---------------------------------------------------------------------------
# Broker format normalisation
# ---------------------------------------------------------------------------

# Headers present in a Robinhood CSV export (lowercase)
_ROBINHOOD_HEADERS: frozenset[str] = frozenset({
    "activity date", "process date", "settle date",
    "instrument", "description", "trans code", "quantity", "price", "amount",
})

# Trans Code values that represent actual trades (not dividends, transfers, etc.)
_ROBINHOOD_TRADE_CODES: frozenset[str] = frozenset({"BUY", "SELL"})


def _detect_broker_format(csv_data: str) -> str | None:
    """Return a broker name string if a known brokerage export is detected, else None."""
    reader = csv.reader(io.StringIO(csv_data))
    try:
        header_row = next(reader)
    except StopIteration:
        return None
    headers = frozenset(col.strip().lower() for col in header_row if col.strip())
    if _ROBINHOOD_HEADERS <= headers:
        return "robinhood"
    return None


def _normalize_robinhood(csv_data: str) -> str:
    """Convert a Robinhood CSV export to the standard detailed format.

    Filters to Buy/Sell rows only, remaps columns, converts dates from
    M/D/YYYY to YYYY-MM-DD, and strips currency symbols from prices.
    """
    reader = csv.DictReader(io.StringIO(csv_data))
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["date", "symbol", "action", "price", "shares"])
    for row in reader:
        trans_code = (row.get("Trans Code") or "").strip()
        if trans_code.upper() not in _ROBINHOOD_TRADE_CODES:
            continue
        raw_date = (row.get("Activity Date") or "").strip()
        try:
            date_val = datetime.strptime(raw_date, "%m/%d/%Y").strftime("%Y-%m-%d")
        except ValueError:
            continue
        symbol = (row.get("Instrument") or "").strip()
        action = trans_code.upper()
        # Strip leading "$" and commas (e.g. "$1,234.56" -> "1234.56")
        raw_price = (row.get("Price") or "").strip().lstrip("$").replace(",", "")
        shares = (row.get("Quantity") or "").strip()
        writer.writerow([date_val, symbol, action, raw_price, shares])
    return out.getvalue()


def normalize_broker_format(csv_data: str) -> str:
    """Detect and convert known broker export formats to the standard detailed format.

    Returns the data unchanged if no known broker format is detected.
    Currently supports: Robinhood.
    """
    broker = _detect_broker_format(csv_data)
    if broker == "robinhood":
        logger.info("Detected Robinhood export; normalizing to standard format")
        return _normalize_robinhood(csv_data)
    return csv_data


def detect_format(csv_data: str) -> str:
    """Return 'detailed' or 'summary' based on the CSV header columns.

    Expects data that has already been through sanitize_csv().
    Raises ValueError if the header matches neither known format.
    'detailed' is checked first; a file satisfying both formats is treated as 'detailed'.
    """
    reader = csv.reader(io.StringIO(csv_data))
    try:
        header_row = next(reader)
    except StopIteration:
        raise ValueError("CSV is empty or has no header row")

    actual_cols: frozenset[str] = frozenset(col.strip().lower() for col in header_row if col.strip())

    if not actual_cols:
        raise ValueError("CSV is empty or has no header row")

    if REQUIRED_DETAILED_COLUMNS <= actual_cols:
        return "detailed"

    if REQUIRED_SUMMARY_KEYS <= actual_cols:
        return "summary"

    missing_detailed = REQUIRED_DETAILED_COLUMNS - actual_cols
    missing_summary = REQUIRED_SUMMARY_KEYS - actual_cols
    if len(missing_detailed) <= len(missing_summary):
        raise ValueError(
            f"Your CSV looks like a trade-by-trade upload but is missing these columns: {sorted(missing_detailed)}. "
            "Please check your file headers."
        )
    raise ValueError(
        f"Your CSV looks like a summary upload but is missing these columns: {sorted(missing_summary)}. "
        "Please check your file headers."
    )


def parse_detailed(csv_data: str, is_free_tier: bool = True) -> list[dict]:
    """Parse a detailed trade-list CSV into a list of typed trade dicts.
    If is_free_tier is True, enforce the free tier trade limit.
    """
    reader = csv.DictReader(io.StringIO(csv_data))

    if reader.fieldnames is None:
        raise ValueError("CSV is empty or has no header row")

    # Build normalized (lowercase, stripped) -> original fieldname mapping
    norm_to_original: dict[str, str] = {f.strip().lower(): f for f in reader.fieldnames}

    missing = REQUIRED_DETAILED_COLUMNS - norm_to_original.keys()
    if missing:
        raise ValueError(f"Your CSV is missing required columns: {sorted(missing)}. Please check your file headers.")

    # Access each required column by its original (un-normalized) fieldname
    col = {norm: norm_to_original[norm] for norm in REQUIRED_DETAILED_COLUMNS}

    trades: list[dict] = []
    for row_num, raw_row in enumerate(reader, start=2):
        # Skip entirely blank rows before checking the limit
        if all(v is None or v.strip() == "" for v in raw_row.values()):
            continue

        # Enforce limit on non-blank rows only
        if is_free_tier and len(trades) >= FREE_TIER_TRADE_LIMIT:
            raise FreeTierLimitExceeded(
                f"Trade count exceeds the free tier limit of {FREE_TIER_TRADE_LIMIT}"
            )

        raw_row = _strip_row(raw_row)

        date_val = _require_field(raw_row[col["date"]], row_num, "date")
        _parse_iso_date(date_val, "date", row_num)  # validation only; date stored as string

        symbol_val = _require_field(raw_row[col["symbol"]], row_num, "symbol").upper()
        # Disallow all-digit, trailing dot/hyphen, or any space
        if (
            not _SYMBOL_RE.match(symbol_val)
            or symbol_val.isdigit()
            or symbol_val.endswith(('.', '-'))
            or ' ' in symbol_val
        ):
            raise ValueError(f"Row {row_num}: symbol '{symbol_val}' contains invalid characters")

        action_val = _require_field(raw_row[col["action"]], row_num, "action").upper()
        if action_val not in {"BUY", "SELL"}:
            raise ValueError(f"Row {row_num}: action '{action_val}' is not BUY or SELL")

        price_val = _parse_positive_float(raw_row[col["price"]], "price", row_num)
        shares_val = _parse_positive_float(raw_row[col["shares"]], "shares", row_num)

        trades.append({
            "date": date_val,
            "symbol": symbol_val,
            "action": action_val,
            "price": price_val,
            "shares": shares_val,
        })

    return trades


def parse_summary(csv_data: str) -> dict:
    """
    Parse a summary-format CSV into a single dict of aggregate metrics.

    Expected columns (case/padding ignored):
        - initial_capital (float > 0)
        - final_balance (float > 0)
        - num_trades (int > 0, accepts e.g. "42" or "42.0")
        - win_rate (float in [0, 1])
        - start_date (YYYY-MM-DD string)
        - end_date (YYYY-MM-DD string)
    Extra columns are ignored. Missing/typoed columns raise ValueError.
    """
    reader = csv.DictReader(io.StringIO(csv_data))

    if reader.fieldnames is None:
        raise ValueError("CSV is empty or has no header row")

    # Normalize headers and check for required columns
    norm_to_original: dict[str, str] = {f.strip().lower(): f for f in reader.fieldnames}
    actual_cols = set(norm_to_original.keys())
    missing = REQUIRED_SUMMARY_KEYS - actual_cols
    extra = actual_cols - REQUIRED_SUMMARY_KEYS
    if missing:
        raise ValueError(f"Your CSV is missing required fields: {sorted(missing)}. Please check your column names.")

    # Map normalized required keys to original header
    col = {norm: norm_to_original[norm] for norm in REQUIRED_SUMMARY_KEYS}

    data_row: dict | None = None
    for raw_row in reader:
        if all(v is None or v.strip() == "" for v in raw_row.values()):
            continue
        if data_row is not None:
            raise ValueError("Summary CSV must contain exactly one data row")
        data_row = _strip_row(raw_row)

    if data_row is None:
        raise ValueError("CSV has no data rows")

    initial_capital = _parse_positive_float(
        data_row[col["initial_capital"]], "initial_capital", 2
    )
    final_balance = _parse_positive_float(
        data_row[col["final_balance"]], "final_balance", 2
    )

    # Accept num_trades as "42" or "42.0" (but not "42.5")
    num_trades_str = data_row[col["num_trades"]]
    try:
        num_trades_f = float(num_trades_str)
    except ValueError:
        raise ValueError(f"Row 2: num_trades '{num_trades_str}' is not a number")
    if (
        math.isnan(num_trades_f)
        or math.isinf(num_trades_f)
        or num_trades_f <= 0
        or num_trades_f % 1 != 0
    ):
        raise ValueError(f"Row 2: num_trades must be a positive integer, got '{num_trades_str}'")
    num_trades = int(num_trades_f)

    win_rate_str = data_row[col["win_rate"]]
    try:
        win_rate = float(win_rate_str)
    except ValueError:
        raise ValueError(f"Row 2: win_rate '{win_rate_str}' is not a number")
    # expects a decimal fraction, e.g. 0.65 not 65
    if math.isnan(win_rate) or math.isinf(win_rate) or win_rate < 0.0 or win_rate > 1.0:
        raise ValueError(f"Row 2: win_rate must be between 0 and 1, got '{win_rate_str}'")

    start_date_str = data_row[col["start_date"]]
    parsed_start = _parse_iso_date(start_date_str, "start_date", 2)

    end_date_str = data_row[col["end_date"]]
    parsed_end = _parse_iso_date(end_date_str, "end_date", 2)

    if parsed_start > parsed_end:
        raise ValueError(
            f"Row 2: start_date '{start_date_str}' must not be after end_date '{end_date_str}'"
        )

    # Extra columns are ignored, but could be logged if needed
    return {
        "initial_capital": initial_capital,
        "final_balance": final_balance,
        "num_trades": num_trades,
        "win_rate": win_rate,
        "start_date": start_date_str,
        "end_date": end_date_str,
    }


def validate_trades(trades: list[dict]) -> list[dict]:
    """Check trades for pairing errors and duplicates; return a list of warning dicts.

    Warnings (not exceptions) are returned so callers can still show results while
    surfacing data quality issues to the user.
    """
    warnings: list[dict] = []

    # Detect duplicate rows: same date + symbol + action (normalized)
    seen: dict[tuple, int] = {}
    for trade in trades:
        action = _normalize_action(trade.get("action"))
        symbol = str(trade.get("symbol") or "").strip().upper()
        date = str(trade.get("date") or "").strip()
        key = (date, symbol, action)
        seen[key] = seen.get(key, 0) + 1

    for key, count in seen.items():
        if count > 1:
            date, symbol, action = key
            warnings.append({
                "type": "duplicate",
                "level": "warning",
                "message": (
                    f"Duplicate trade: {action} {symbol} on {date} appears {count} times"
                ),
            })

    # Check BUY/SELL pairing per symbol using a simple FIFO stack
    open_buys: dict[str, list[dict]] = {}
    for trade in trades:
        action = _normalize_action(trade.get("action"))
        symbol = str(trade.get("symbol") or "").strip().upper()
        if action == "BUY":
            open_buys.setdefault(symbol, []).append(trade)
        elif action == "SELL":
            if not open_buys.get(symbol):
                date = trade.get("date") or "unknown date"
                warnings.append({
                    "type": "unmatched_sell",
                    "level": "warning",
                    "message": f"SELL for {symbol} on {date} has no preceding BUY",
                })
            else:
                open_buys[symbol].pop(0)

    for symbol, buys in open_buys.items():
        for buy in buys:
            date = buy.get("date") or "unknown date"
            warnings.append({
                "type": "unclosed_position",
                "level": "info",
                "message": f"Open position: {symbol} BUY on {date} (no matching SELL yet)",
            })

    # Check for zero or negative price or share count, or missing/invalid values
    def _is_invalid_value(val):
        try:
            return float(val) <= 0
        except (TypeError, ValueError):
            return True

    for idx, trade in enumerate(trades):
        symbol = str(trade.get("symbol") or "").strip().upper()
        date = trade.get("date") or "unknown date"
        price = trade.get("price")
        shares = trade.get("shares")

        if _is_invalid_value(price):
            warnings.append({
                "type": "invalid_price",
                "level": "warning",
                "message": f"Row {idx+1}: Trade {symbol} on {date} has invalid price: {price}",
            })
        if _is_invalid_value(shares):
            warnings.append({
                "type": "invalid_shares",
                "level": "warning",
                "message": f"Row {idx+1}: Trade {symbol} on {date} has invalid share count: {shares}",
            })

    return warnings


def calculate_pnl(trades: list[dict]) -> dict:
    """Compute per-trade P&L, equity curve, and total return from a trade list.

    Pairs BUY->SELL trades per symbol using FIFO matching. Unpaired trades are skipped.
    Returns a dict with keys: trade_pnl, equity_curve, total_pnl, total_return_pct.
    """
    # FIFO buy queues per symbol: stores (date, price, shares) for each open BUY
    open_buys: dict[str, list[dict]] = {}
    trade_pnl: list[dict] = []
    cumulative_pnl = 0.0

    for trade in trades:
        symbol = trade.get("symbol")
        action = _normalize_action(trade.get("action"))
        if action == "BUY":
            open_buys.setdefault(symbol, []).append(trade)
        elif action == "SELL":
            if not open_buys.get(symbol):
                continue  # unmatched sell — already flagged by validate_trades
            buy = open_buys[symbol].pop(0)
            pnl = (trade.get("price", 0) - buy.get("price", 0)) * trade.get("shares", 0)
            cumulative_pnl += pnl
            trade_pnl.append({
                "buy_date": buy.get("date"),
                "sell_date": trade.get("date"),
                "symbol": symbol,
                "shares": trade.get("shares"),
                "buy_price": buy.get("price"),
                "sell_price": trade.get("price"),
                "pnl": round(pnl, 4),
                "cumulative_pnl": round(cumulative_pnl, 4),
            })

    # Equity curve: cumulative P&L at each sell event (chronological order)
    equity_curve = [
        {"date": t["sell_date"], "cumulative_pnl": t["cumulative_pnl"]}
        for t in trade_pnl
    ]

    # Total return as a percentage of total capital deployed (sum of all buy costs)
    total_buy_cost = sum(
        t["buy_price"] * t["shares"] for t in trade_pnl
    )
    total_return_pct = (
        round((cumulative_pnl / total_buy_cost) * 100, 4)
        if total_buy_cost > 0
        else 0.0
    )

    # Helper to safely compute holding period in days
    def _holding_days(t):
        try:
            buy = t["buy_date"]
            sell = t["sell_date"]
            if not (buy and sell):
                return None
            days = (datetime.strptime(sell, "%Y-%m-%d") - datetime.strptime(buy, "%Y-%m-%d")).days
            return days if days >= 0 else None
        except Exception:
            return None

    # Only count trades with pnl > 0 (exclude breakeven and losses)
    # This is intentional: see test coverage and docstring
    winner_days = [
        d for t in trade_pnl if t["pnl"] > 0
        for d in [_holding_days(t)] if d is not None
    ]
    avg_holding_days_winners = round(float(statistics.mean(winner_days)), 2) if winner_days else None

    # Mean days held for trades that closed at a loss (pnl < 0, excluding breakeven)
    loser_days = [
        d for t in trade_pnl if t["pnl"] < 0
        for d in [_holding_days(t)] if d is not None
    ]
    avg_holding_days_losers = round(float(statistics.mean(loser_days)), 2) if loser_days else None

    return {
        "trade_pnl": trade_pnl,
        "equity_curve": equity_curve,
        "total_pnl": round(cumulative_pnl, 4),
        "total_return_pct": total_return_pct,
        "avg_holding_days_winners": avg_holding_days_winners,
        "avg_holding_days_losers": avg_holding_days_losers,
    }



# Minimum winners and losers required before flagging the disposition effect
MIN_TRADES_FOR_DISPOSITION_CHECK = 5
# Losers must be held at least 50% longer than winners to trigger the warning
DISPOSITION_EFFECT_THRESHOLD = 1.5

def check_disposition_effect(pnl_data: dict) -> dict | None:
    """Return a warning dict if losing trades are held significantly longer than winners.

    Requires at least MIN_TRADES_FOR_DISPOSITION_CHECK winners and losers to avoid noise from tiny samples.
    Returns None when there is insufficient data or no meaningful difference.
    """
    avg_winner_days = pnl_data.get("avg_holding_days_winners")
    avg_loser_days = pnl_data.get("avg_holding_days_losers")

    if avg_winner_days is None or avg_loser_days is None or avg_winner_days <= 0:
        return None

    trade_pnl = pnl_data.get("trade_pnl", [])
    num_winners = sum(1 for t in trade_pnl if t.get("pnl", 0) > 0)
    num_losers = sum(1 for t in trade_pnl if t.get("pnl", 0) < 0)

    if num_winners < MIN_TRADES_FOR_DISPOSITION_CHECK or num_losers < MIN_TRADES_FOR_DISPOSITION_CHECK:
        return None

    if avg_loser_days / avg_winner_days < DISPOSITION_EFFECT_THRESHOLD:
        return None

    return {
        "type": "disposition_effect",
        "level": "warning",
        "message": (
            f"You held losing trades an average of {avg_loser_days} days, "
            f"but winning trades only {avg_winner_days} days. "
            "Holding losers much longer than winners is called the 'disposition effect' — "
            "a common bias where traders wait and hope a loss will turn around. "
            "Consider using stop-losses to cut losing trades earlier."
        ),
    }



# Costs must eat this fraction of gross profit before the overtrading flag fires
OVERTRADING_COST_DRAG_THRESHOLD = 0.20
# More than one round-trip per trading day is considered high frequency
OVERTRADING_FREQUENCY_THRESHOLD = 252
# Minimum trades required for frequency/cost drag to be meaningful
MIN_TRADES_FOR_FREQUENCY_SIGNAL = 20


def check_overtrading(
    pnl_data: dict,
    commissions: dict,
    slippage: dict,
    bid_ask_spread: dict,
) -> dict | None:
    """Return a warning dict if trading costs materially drag on returns.

    Only fires when there are enough closed trades, gross profit is positive,
    and total costs exceed OVERTRADING_COST_DRAG_THRESHOLD of that profit.
    """
    trade_pnl = pnl_data.get("trade_pnl", [])
    num_closed = len(trade_pnl)

    # Input guards: all cost dicts must be present and numeric
    def _safe_cost(d, key):
        try:
            return float(d.get(key, 0.0))
        except Exception:
            return 0.0

    if not isinstance(commissions, dict) or not isinstance(slippage, dict) or not isinstance(bid_ask_spread, dict):
        return None

    if num_closed < MIN_TRADES_FOR_FREQUENCY_SIGNAL:
        return None

    gross_pnl = pnl_data.get("total_pnl", 0.0)
    if not isinstance(gross_pnl, (int, float)) or gross_pnl <= 0:
        return None

    total_costs = (
        _safe_cost(commissions, "total_commission_usd")
        + _safe_cost(slippage, "total_slippage_usd")
        + _safe_cost(bid_ask_spread, "total_spread_usd")
    )

    cost_drag_pct = total_costs / gross_pnl if gross_pnl else 0.0
    if cost_drag_pct < OVERTRADING_COST_DRAG_THRESHOLD:
        return None

    # Annualise trade count using trading days (252/year)
    trades_per_year = None
    try:
        buy_dates = [t["buy_date"] for t in trade_pnl if t.get("buy_date")]
        sell_dates = [t["sell_date"] for t in trade_pnl if t.get("sell_date")]
        if buy_dates and sell_dates:
            first_date = min(buy_dates)
            last_date = max(sell_dates)
            total_days = (
                datetime.strptime(last_date, "%Y-%m-%d")
                - datetime.strptime(first_date, "%Y-%m-%d")
            ).days
            if total_days > 0:
                # Use 252 trading days per year
                trades_per_year = round(num_closed * 252 / total_days, 1)
    except Exception:
        pass

    drag_pct_display = round(cost_drag_pct * 100, 1)
    freq_part = (
        f" at a rate of {trades_per_year:.0f} trades/year"
        if trades_per_year is not None
        else ""
    )

    return {
        "type": "overtrading",
        "level": "warning",
        "message": (
            f"Costs (commissions + slippage + spread) total ${total_costs:.2f}, "
            f"which is {drag_pct_display}% of gross profit. "
            f"You made {num_closed} closed trades{freq_part}. "
            "High trade frequency may be causing costs to materially drag on returns. "
            "Consider reducing trade frequency or reviewing position sizing."
        ),
        "cost_drag_pct": round(cost_drag_pct, 4),
        "total_costs_usd": round(total_costs, 2),
        "num_closed_trades": num_closed,
        "trades_per_year": trades_per_year,
    }


# Fraction of total trades in one symbol that triggers the concentration risk warning
CONCENTRATION_RISK_THRESHOLD = 0.50
# Minimum trades before the check is meaningful
MIN_TRADES_FOR_CONCENTRATION_CHECK = 2


def check_concentration_risk(trades: list[dict]) -> dict | None:
    """Return a warning dict if more than 50% of trades are in a single symbol.

    Concentration is measured by trade count, not position size or capital deployed.
    Trades with a missing or empty symbol field are skipped and logged.
    Returns None when there are too few trades or no symbol exceeds the threshold.
    """
    if len(trades) < MIN_TRADES_FOR_CONCENTRATION_CHECK:
        return None

    symbol_counts: dict[str, int] = {}
    for trade in trades:
        symbol = str(trade.get("symbol") or "").strip().upper()
        if not symbol:
            logger.warning("check_concentration_risk: trade skipped due to missing symbol: %r", trade)
            continue
        symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1

    total = sum(symbol_counts.values())
    if total == 0:
        return None

    most_traded = max(symbol_counts, key=lambda s: symbol_counts[s])
    pct = symbol_counts[most_traded] / total

    if pct <= CONCENTRATION_RISK_THRESHOLD:
        return None

    pct_display = round(pct * 100, 1)
    return {
        "type": "concentration_risk",
        "level": "warning",
        "message": (
            f"{pct_display}% of your trades are in {most_traded} "
            f"({symbol_counts[most_traded]} of {total}). "
            "Having more than half your trades in a single symbol increases exposure to that asset. "
            "Consider diversifying across more symbols to reduce concentration risk."
        ),
        "symbol": most_traded,
        "trade_count": symbol_counts[most_traded],
        "total_trades": total,
        "concentration_pct": round(pct, 4),
    }


def analyze_uploaded_trades(csv_data: str, commission_per_trade: float = DEFAULT_COMMISSION_PER_TRADE, slippage_pct: float = DEFAULT_SLIPPAGE_PCT, spread_pct: float = DEFAULT_SPREAD_PCT) -> dict:
    """Main entry point: sanitize, detect format, parse, validate, and return analysis results."""
    try:
        clean = sanitize_csv(csv_data)
        clean = normalize_broker_format(clean)
        fmt = detect_format(clean)
    except ValueError as e:
        return {
            "error": str(e),
            "format": "detailed",
            "trades": [],
            "warnings": [],
            "notices": [],
            "pnl": {},
            "significance": None,
        }

    warnings = []
    if fmt == "summary":
        try:
            summary = parse_summary(clean)
        except ValueError as e:
            return {
                "error": str(e),
                "format": fmt,
                "trades": [],
                "warnings": [],
                "notices": [],
                "pnl": {},
                "significance": None,
            }
        sufficiency_warning = check_trade_count_sufficiency(summary.get("num_trades", 0))
        if sufficiency_warning:
            warnings.append(sufficiency_warning)
        return {
            "format": fmt,
            "format_description": FORMAT_DESCRIPTIONS.get(fmt, ""),
            "summary": summary,
            "warnings": warnings,
        }

    trades = parse_detailed(clean, is_free_tier=False) or []  # TODO: re-enable for production
    all_issues = validate_trades(trades) or []
    WARNING_LEVELS = {"warning", "error"}
    INFO_LEVELS = {"info"}
    warnings.extend(i for i in all_issues if i.get("level", "warning") in WARNING_LEVELS)
    notices = [i for i in all_issues if i.get("level") in INFO_LEVELS]
    pnl = calculate_pnl(trades) if trades else {}
    num_closed = len(pnl.get("trade_pnl", []))
    sufficiency_warning = check_trade_count_sufficiency(num_closed)
    if sufficiency_warning:
        warnings.append(sufficiency_warning)
    commissions = calculate_commissions(trades, commission_per_trade=commission_per_trade) if trades else {}
    slippage = calculate_slippage(trades, slippage_pct=slippage_pct) if trades else {}
    bid_ask_spread = calculate_bid_ask_spread(trades, spread_pct=spread_pct) if trades else {}
    pnl_values = [t["pnl"] for t in pnl.get("trade_pnl", [])]
    significance = run_significance_tests(pnl_values) if pnl_values else None
    disposition_warning = check_disposition_effect(pnl)
    if disposition_warning:
        warnings.append(disposition_warning)
    overtrading_warning = check_overtrading(pnl, commissions, slippage, bid_ask_spread)
    if overtrading_warning:
        warnings.append(overtrading_warning)
    concentration_warning = check_concentration_risk(trades)
    if concentration_warning:
        warnings.append(concentration_warning)
    try:
        spy_benchmark = fetch_benchmark(trades, SPY_TICKER)
    except Exception:
        spy_benchmark = None
    try:
        qqq_benchmark = fetch_benchmark(trades, QQQ_TICKER)
    except Exception:
        qqq_benchmark = None
    return {
        "format": fmt,
        "format_description": FORMAT_DESCRIPTIONS.get(fmt, ""),
        "trades": trades,
        "warnings": warnings,
        "notices": notices,
        "pnl": pnl,
        "commissions": commissions,
        "slippage": slippage,
        "bid_ask_spread": bid_ask_spread,
        "significance": significance,
        "spy_benchmark": spy_benchmark,
        "qqq_benchmark": qqq_benchmark,
    }
