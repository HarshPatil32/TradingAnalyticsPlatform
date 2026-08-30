"""
options_analyzer.py
-------------------
Parses, validates, and normalises uploaded options trade history CSV files
before handing the cleaned data off to the options analysis modules.

Options row schema

Required columns (see REQUIRED_OPTIONS_COLUMNS):
    date          Trade date, YYYY-MM-DD.
    underlying    Ticker symbol of the underlying asset.
    option_type   One of VALID_OPTION_TYPES (CALL or PUT).
    action        One of VALID_OPTION_ACTIONS (BTO, STO, BTC, STC, OEXP, OASGN).
    strike        Positive float, strike price in USD per share.
    expiration    Option expiration date, YYYY-MM-DD (distinct from date;
                  must be on or after date).
    contracts     Positive integer, number of contracts.
    premium       Non-negative float, quoted per share; total cash is
                  premium * contracts * multiplier. OEXP/OASGN rows use 0.

Optional columns (see OPTIONAL_OPTIONS_COLUMNS):
    multiplier    Positive integer; defaults to DEFAULT_CONTRACT_MULTIPLIER
                  (100) when absent or blank.
    fees          Non-negative float (0.0 is valid), user-reported broker fees
                  for the leg; defaults to 0.0 when absent or blank. May include
                  '$' or ',' like premium. Use a non-negative check when parsing,
                  not a positive-only parser. Distinct from estimated costs
                  computed by options_costs when this column is missing.

Action vocabulary uses open/close semantics (BTO/STO/BTC/STC) rather than
plain BUY/SELL so P&L pairing and risk checks can distinguish opening from
closing legs. OEXP and OASGN are passive-close events (expired worthless,
assigned) with premium 0; side resolution for P&L pairing is handled later.
Broker-specific exports are normalised to this set by
normalize_options_broker_format.
"""

from __future__ import annotations

import csv
import io
import logging
import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import NamedTuple, cast

from csv_analyzer import (
    _SYMBOL_RE,
    _detect_broker_format,
    _is_blank_csv_row,
    _map_required_columns,
    _parse_iso_date,
    _parse_mdy_date,
    _parse_positive_float,
    _require_field,
    _strip_row,
    normalize_headers,
    sanitize_csv,
)
from csv_analyzer import (
    parse_summary as _parse_stock_summary,
)

logger = logging.getLogger(__name__)

# from options_costs import (
#     DEFAULT_OPTIONS_COMMISSION_PER_CONTRACT,
#     calculate_options_commissions,
# )
# from options_greeks import calculate_greeks

# Constants and Exceptions


REQUIRED_OPTIONS_COLUMNS: frozenset[str] = frozenset(
    {
        "date",
        "underlying",
        "option_type",
        "action",
        "strike",
        "expiration",
        "contracts",
        "premium",
    }
)

OPTIONAL_OPTIONS_COLUMNS: frozenset[str] = frozenset({"multiplier", "fees"})

# Same keys as stock summary uploads until parse_options_summary defines otherwise.
REQUIRED_OPTIONS_SUMMARY_COLUMNS: frozenset[str] = frozenset(
    {
        "initial_capital",
        "final_balance",
        "num_trades",
        "win_rate",
        "start_date",
        "end_date",
    }
)

VALID_OPTION_TYPES: frozenset[str] = frozenset({"CALL", "PUT"})

# Open/close semantics required for P&L pairing and risk detection.
VALID_OPTION_ACTIONS: frozenset[str] = frozenset(
    {"BTO", "STO", "BTC", "STC", "OEXP", "OASGN"}
)

DEFAULT_CONTRACT_MULTIPLIER: int = 100


class ContractKey(NamedTuple):
    underlying: str
    option_type: str
    strike: float
    expiration: str


@dataclass
class MatchResult:
    matched: list[tuple[dict, dict]] = field(default_factory=list)
    unmatched_closes: list[dict] = field(default_factory=list)
    unclosed_opens: list[dict] = field(default_factory=list)


class OptionsFreeTierLimitExceeded(ValueError):
    """Raised when the free tier options row/contract limit is exceeded."""

    pass


FREE_TIER_OPTIONS_ROW_LIMIT = 100


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _parse_positive_int(value: str, field: str, row_num: int) -> int:
    """Parse a string as a positive integer, raising ValueError with a clear message."""
    try:
        result = float(value)
    except ValueError:
        raise ValueError(f"Row {row_num}: {field} '{value}' is not a number")
    if math.isnan(result) or math.isinf(result) or result <= 0 or result % 1 != 0:
        raise ValueError(
            f"Row {row_num}: {field} must be a positive integer, got '{value}'"
        )
    return int(result)


def _parse_multiplier(value: str | None, row_num: int) -> int:
    """Parse optional multiplier; default to DEFAULT_CONTRACT_MULTIPLIER when blank."""
    if value is None:
        return DEFAULT_CONTRACT_MULTIPLIER
    stripped = value.strip()
    if not stripped:
        return DEFAULT_CONTRACT_MULTIPLIER
    return _parse_positive_int(stripped, "multiplier", row_num)


def _parse_premium(value: str | None, row_num: int) -> float:
    """Parse premium, stripping '$' and ',' before validating as a non-negative float."""
    cleaned = (
        _require_field(value, row_num, "premium").replace("$", "").replace(",", "")
    )
    try:
        result = float(cleaned)
    except ValueError:
        raise ValueError(f"Row {row_num}: premium '{value}' is not a number")
    if math.isnan(result) or math.isinf(result) or result < 0:
        raise ValueError(f"Row {row_num}: premium must be non-negative, got '{value}'")
    return result


def _parse_fees(value: str | None, row_num: int) -> float:
    """Parse optional fees; default to 0.0 when absent or blank."""
    if value is None or not value.strip():
        return 0.0
    cleaned = value.strip().replace("$", "").replace(",", "")
    try:
        result = float(cleaned)
    except ValueError:
        raise ValueError(f"Row {row_num}: fees '{value}' is not a number")
    if math.isnan(result) or math.isinf(result) or result < 0:
        raise ValueError(f"Row {row_num}: fees must be non-negative, got '{value}'")
    return result


def _is_invalid_positive(val: object) -> bool:
    try:
        result = float(val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return True
    return math.isnan(result) or math.isinf(result) or result <= 0


def _is_invalid_positive_int(val: object) -> bool:
    try:
        result = float(val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return True
    return math.isnan(result) or math.isinf(result) or result <= 0 or result % 1 != 0


def _is_invalid_non_negative(val: object) -> bool:
    try:
        result = float(val)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return True
    return math.isnan(result) or math.isinf(result) or result < 0


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


def sanitize_options_csv(csv_data: str) -> str:
    """Strip BOM, normalise line endings, and guard against unsafe CSV content."""
    return sanitize_csv(csv_data)


def detect_options_format(csv_data: str) -> str:
    """Return 'detailed' or 'summary' based on the CSV header columns."""
    reader = csv.reader(io.StringIO(csv_data))
    try:
        header_row = next(reader)
    except StopIteration:
        raise ValueError("CSV is empty or has no header row")

    actual_cols = normalize_headers(header_row)

    if not actual_cols:
        raise ValueError("CSV is empty or has no header row")

    if REQUIRED_OPTIONS_COLUMNS <= actual_cols:
        return "detailed"

    if REQUIRED_OPTIONS_SUMMARY_COLUMNS <= actual_cols:
        return "summary"

    missing_detailed = REQUIRED_OPTIONS_COLUMNS - actual_cols
    missing_summary = REQUIRED_OPTIONS_SUMMARY_COLUMNS - actual_cols
    if len(missing_detailed) <= len(missing_summary):
        raise ValueError(
            f"Your options CSV looks like a trade-by-trade upload but is missing these columns: {sorted(missing_detailed)}. "
            "Please check your file headers."
        )
    raise ValueError(
        f"Your options CSV looks like a summary upload but is missing these columns: {sorted(missing_summary)}. "
        "Please check your file headers."
    )


def parse_options_detailed(csv_data: str, is_free_tier: bool = True) -> list[dict]:
    """Parse a detailed options trade-list CSV into a list of typed trade dicts."""
    reader = csv.DictReader(io.StringIO(csv_data))

    if reader.fieldnames is None:
        raise ValueError("CSV is empty or has no header row")

    col = _map_required_columns(
        reader.fieldnames,
        REQUIRED_OPTIONS_COLUMNS,
        "Your options CSV is missing required columns:",
        ". Please check your file headers.",
    )
    norm_to_original = {f.strip().lower(): f for f in reader.fieldnames}
    multiplier_key = norm_to_original.get("multiplier")
    fees_key = norm_to_original.get("fees")

    trades: list[dict] = []
    for row_num, raw_row in enumerate(reader, start=2):
        if _is_blank_csv_row(raw_row):
            continue

        if is_free_tier and len(trades) >= FREE_TIER_OPTIONS_ROW_LIMIT:
            raise OptionsFreeTierLimitExceeded(
                f"Options row count exceeds the free tier limit of {FREE_TIER_OPTIONS_ROW_LIMIT}"
            )

        raw_row = _strip_row(raw_row)

        date_val = _require_field(raw_row[col["date"]], row_num, "date")
        parsed_date = _parse_iso_date(date_val, "date", row_num)

        underlying_val = _require_field(
            raw_row[col["underlying"]], row_num, "underlying"
        ).upper()
        # Disallow all-digit, trailing dot/hyphen, or any space
        if (
            not _SYMBOL_RE.match(underlying_val)
            or underlying_val.isdigit()
            or underlying_val.endswith((".", "-"))
            or " " in underlying_val
        ):
            raise ValueError(
                f"Row {row_num}: underlying '{underlying_val}' contains invalid characters"
            )

        option_type_val = _require_field(
            raw_row[col["option_type"]], row_num, "option_type"
        ).upper()
        if option_type_val not in VALID_OPTION_TYPES:
            raise ValueError(
                f"Row {row_num}: option_type '{option_type_val}' is not CALL or PUT"
            )

        action_val = _require_field(raw_row[col["action"]], row_num, "action").upper()
        if action_val not in VALID_OPTION_ACTIONS:
            raise ValueError(
                f"Row {row_num}: action '{action_val}' is not one of "
                f"{', '.join(sorted(VALID_OPTION_ACTIONS))}"
            )

        strike_val = _parse_positive_float(raw_row[col["strike"]], "strike", row_num)

        expiration_val = _require_field(
            raw_row[col["expiration"]], row_num, "expiration"
        )
        parsed_expiration = _parse_iso_date(expiration_val, "expiration", row_num)

        if parsed_expiration < parsed_date:
            raise ValueError(
                f"Row {row_num}: expiration '{expiration_val}' must not be before date '{date_val}'"
            )

        contracts_val = _parse_positive_int(
            _require_field(raw_row[col["contracts"]], row_num, "contracts"),
            "contracts",
            row_num,
        )

        premium_val = _parse_premium(raw_row[col["premium"]], row_num)

        multiplier_val = _parse_multiplier(
            raw_row.get(multiplier_key) if multiplier_key else None, row_num
        )
        fees_val = _parse_fees(raw_row.get(fees_key) if fees_key else None, row_num)

        trades.append(
            {
                "date": date_val,
                "underlying": underlying_val,
                "option_type": option_type_val,
                "action": action_val,
                "strike": strike_val,
                "expiration": expiration_val,
                "contracts": contracts_val,
                "premium": premium_val,
                "multiplier": multiplier_val,
                "fees": fees_val,
            }
        )

    return trades


def parse_options_summary(csv_data: str) -> dict:
    """Parse a summary-format options CSV into a single dict of aggregate metrics."""
    return _parse_stock_summary(csv_data)


def _normalize_option_action(action: object) -> str:
    return str(action).strip().upper() if action is not None else ""


def _position_key(trade: dict) -> ContractKey:
    underlying = str(trade.get("underlying") or "").strip().upper()
    option_type = str(trade.get("option_type") or "").strip().upper()
    strike = cast(float, trade.get("strike"))
    expiration = str(trade.get("expiration") or "").strip()
    return ContractKey(underlying, option_type, strike, expiration)


def _position_label(trade: dict) -> str:
    underlying = str(trade.get("underlying") or "").strip().upper()
    option_type = str(trade.get("option_type") or "").strip().upper()
    strike = trade.get("strike")
    expiration = str(trade.get("expiration") or "").strip()
    return f"{underlying} {option_type} strike {strike} exp {expiration}"


_OPEN_OPTION_ACTIONS = frozenset({"BTO", "STO"})
_CLOSE_OPTION_ACTIONS = frozenset({"BTC", "STC", "OEXP", "OASGN"})


def match_options_fifo(trades: list[dict]) -> MatchResult:
    """Pair open and close legs per contract using FIFO matching."""
    open_legs: dict[ContractKey, list[dict]] = {}
    result = MatchResult()
    for trade in trades:
        action = _normalize_option_action(trade.get("action"))
        key = _position_key(trade)
        if action in _OPEN_OPTION_ACTIONS:
            open_legs.setdefault(key, []).append(trade)
        elif action in _CLOSE_OPTION_ACTIONS:
            queue = open_legs.get(key)
            if not queue:
                result.unmatched_closes.append(trade)
            else:
                result.matched.append((queue.pop(0), trade))
    for queue in open_legs.values():
        result.unclosed_opens.extend(queue)
    return result


def validate_options(trades: list[dict]) -> list[dict]:
    """Check options trades for pairing errors and data quality issues."""
    warnings: list[dict] = []

    seen: dict[tuple, int] = {}
    for trade in trades:
        action = _normalize_option_action(trade.get("action"))
        underlying = str(trade.get("underlying") or "").strip().upper()
        option_type = str(trade.get("option_type") or "").strip().upper()
        date = str(trade.get("date") or "").strip()
        strike = trade.get("strike")
        expiration = str(trade.get("expiration") or "").strip()
        key = (date, underlying, option_type, action, strike, expiration)
        seen[key] = seen.get(key, 0) + 1

    for key, count in seen.items():
        if count > 1:
            date, underlying, option_type, action, strike, expiration = key
            warnings.append(
                {
                    "type": "duplicate",
                    "level": "warning",
                    "message": (
                        f"Duplicate trade: {action} {underlying} {option_type} "
                        f"{strike} exp {expiration} on {date} appears {count} times"
                    ),
                }
            )

    match_result = match_options_fifo(trades)

    for trade in match_result.unmatched_closes:
        action = _normalize_option_action(trade.get("action"))
        date = trade.get("date") or "unknown date"
        label = _position_label(trade)
        warnings.append(
            {
                "type": "unmatched_close",
                "level": "warning",
                "message": (f"{action} for {label} on {date} has no preceding open"),
            }
        )

    for matched_open, close_trade in match_result.matched:
        action = _normalize_option_action(close_trade.get("action"))
        if action in {"OEXP", "OASGN"}:
            open_date = matched_open.get("date") or "unknown date"
            close_date = close_trade.get("date") or "unknown date"
            label = _position_label(close_trade)
            pos_key = _position_key(close_trade)
            warnings.append(
                {
                    "type": "expired_position",
                    "level": "info",
                    "message": (
                        f"Expired: {label} (opened {open_date}, expired {close_date})"
                    ),
                    "underlying": pos_key.underlying,
                    "option_type": pos_key.option_type,
                    "strike": pos_key.strike,
                    "expiration": pos_key.expiration,
                    "open_date": open_date,
                    "date": close_date,
                    "action": action,
                }
            )

    for leg in match_result.unclosed_opens:
        date = leg.get("date") or "unknown date"
        label = _position_label(leg)
        pos_key = _position_key(leg)
        warnings.append(
            {
                "type": "unclosed_position",
                "level": "info",
                "message": (
                    f"Open position: {label} opened on {date} (no matching close yet)"
                ),
                "underlying": pos_key.underlying,
                "option_type": pos_key.option_type,
                "strike": pos_key.strike,
                "expiration": pos_key.expiration,
                "date": date,
            }
        )

    bto_keys: set[ContractKey] = {
        _position_key(t)
        for t in trades
        if _normalize_option_action(t.get("action")) == "BTO"
    }
    for leg in match_result.unclosed_opens:
        if _normalize_option_action(leg.get("action")) != "STO":
            continue
        pos_key = _position_key(leg)
        if pos_key not in bto_keys:
            date = leg.get("date") or "unknown date"
            label = _position_label(leg)
            warnings.append(
                {
                    "type": "naked_short",
                    "level": "warning",
                    "message": (
                        f"Naked short: STO {label} on {date} has no offsetting long position"
                    ),
                }
            )

    for idx, trade in enumerate(trades):
        label = _position_label(trade)
        row_num = idx + 1
        action = _normalize_option_action(trade.get("action"))

        if _is_invalid_positive_int(trade.get("contracts")):
            warnings.append(
                {
                    "type": "invalid_contracts",
                    "level": "warning",
                    "message": (
                        f"Row {row_num}: {label} has invalid contracts: "
                        f"{trade.get('contracts')}"
                    ),
                }
            )

        premium = trade.get("premium")
        if _is_invalid_non_negative(premium):
            warnings.append(
                {
                    "type": "invalid_premium",
                    "level": "warning",
                    "message": (
                        f"Row {row_num}: {label} has invalid premium: {premium}"
                    ),
                }
            )
        elif (
            action in {"OEXP", "OASGN"}
            and isinstance(premium, (int, float))
            and premium != 0
        ):
            warnings.append(
                {
                    "type": "invalid_premium",
                    "level": "warning",
                    "message": (
                        f"Row {row_num}: {label} {action} should have premium 0, "
                        f"got {premium}"
                    ),
                }
            )

        if _is_invalid_positive(trade.get("strike")):
            warnings.append(
                {
                    "type": "invalid_strike",
                    "level": "warning",
                    "message": (
                        f"Row {row_num}: {label} has invalid strike: "
                        f"{trade.get('strike')}"
                    ),
                }
            )

        if _is_invalid_positive_int(trade.get("multiplier")):
            warnings.append(
                {
                    "type": "invalid_multiplier",
                    "level": "warning",
                    "message": (
                        f"Row {row_num}: {label} has invalid multiplier: "
                        f"{trade.get('multiplier')}"
                    ),
                }
            )

        if _is_invalid_non_negative(trade.get("fees")):
            warnings.append(
                {
                    "type": "invalid_fees",
                    "level": "warning",
                    "message": (
                        f"Row {row_num}: {label} has invalid fees: {trade.get('fees')}"
                    ),
                }
            )

    return warnings


def calculate_options_pnl(trades: list[dict]) -> dict:
    """Compute realized P&L for closed long positions using FIFO matching."""
    match_result = match_options_fifo(trades)
    positions = []
    total_pnl = 0.0
    for open_leg, close_leg in match_result.matched:
        if _normalize_option_action(open_leg.get("action")) != "BTO":
            continue
        open_premium = float(open_leg["premium"])
        close_premium = float(close_leg["premium"])
        contracts = int(open_leg["contracts"])
        # multiplier is optional in the CSV schema; parse_options_detailed always fills it.
        multiplier = int(open_leg["multiplier"])
        pnl = (close_premium - open_premium) * contracts * multiplier
        rounded_pnl = round(pnl, 2)
        total_pnl += rounded_pnl
        positions.append(
            {
                "underlying": open_leg["underlying"],
                "option_type": open_leg["option_type"],
                "strike": open_leg["strike"],
                "expiration": open_leg["expiration"],
                "open_date": open_leg["date"],
                "close_date": close_leg["date"],
                "open_premium": open_premium,
                "close_premium": close_premium,
                "contracts": contracts,
                "multiplier": multiplier,
                "pnl": rounded_pnl,
            }
        )
    return {"positions": positions, "total_pnl": round(total_pnl, 2)}


def check_theta_decay_risk(trades: list[dict]) -> dict | None:
    """Return a warning dict if long options are held into rapid theta decay near expiration."""
    # TODO:
    raise NotImplementedError


def check_expired_worthless_pattern(pnl_data: dict) -> dict | None:
    """Return a warning dict if long options repeatedly expire worthless."""
    # TODO:
    raise NotImplementedError


def check_naked_selling_habit(trades: list[dict]) -> dict | None:
    """Return a warning dict if naked/undefined-risk selling is a recurring habit."""
    # TODO:
    raise NotImplementedError


def analyze_uploaded_options(csv_data: str) -> dict:
    """Main entry point: sanitize, detect format, parse, validate, and return analysis results."""
    # TODO:
    raise NotImplementedError


# ---------------------------------------------------------------------------
# Broker format normalisation
# Shared symbol decoders (_parse_robinhood_option_description, _parse_occ_option_symbol)
# are broker-agnostic; future broker normalizers should reuse them instead of re-parsing.
# ---------------------------------------------------------------------------


def _detect_options_broker_format(csv_data: str) -> str | None:
    """Return a broker name string if a known brokerage export is detected, else None."""
    return _detect_broker_format(csv_data)


# Trans Code values that represent actual options trades (not dividends, transfers, etc.)
_ROBINHOOD_OPTIONS_TRADE_CODES = VALID_OPTION_ACTIONS

_ROBINHOOD_OPTION_DESC_RE = re.compile(
    r"^(?P<underlying>[A-Za-z0-9.\-]+)\s+"
    r"(?P<expiration>\d{1,2}/\d{1,2}/\d{4})\s+"
    r"(?P<option_type>Call|Put)\s+"
    r"\$(?P<strike>[\d,]+(?:\.\d+)?)$",
    re.IGNORECASE,
)


def _parse_robinhood_option_description(description: str) -> dict | None:
    """Parse 'AAPL 1/19/2024 Call $185.00' into underlying/expiration/option_type/strike."""
    match = _ROBINHOOD_OPTION_DESC_RE.match(description.strip())
    if not match:
        return None
    expiration = _parse_mdy_date(match["expiration"])
    if expiration is None:
        return None
    return {
        "underlying": match["underlying"].upper(),
        "option_type": match["option_type"].upper(),
        "strike": match["strike"].replace(",", ""),
        "expiration": expiration,
    }


_OCC_SUFFIX_LEN = 15  # 6 date + 1 type + 8 strike; must match _OCC_SUFFIX_RE
_OCC_SUFFIX_RE = re.compile(
    r"^(?P<date>\d{6})(?P<type>[CP])(?P<strike>\d{8})$",
    re.IGNORECASE,
)


def _parse_occ_option_symbol(symbol: str) -> dict | None:
    """Parse an OCC symbol (root + YYMMDD + C/P + 8-digit strike*1000)."""
    stripped = symbol.strip()
    if len(stripped) <= _OCC_SUFFIX_LEN:
        return None
    root = stripped[:-_OCC_SUFFIX_LEN].strip()
    if not root:
        return None
    match = _OCC_SUFFIX_RE.match(stripped[-_OCC_SUFFIX_LEN:])
    if not match:
        return None
    try:
        # %y pivot: Python maps 00-68 -> 2000-2068, 69-99 -> 1969-1999
        expiration = datetime.strptime(match["date"], "%y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return None
    strike_int = int(match["strike"])
    strike_value = strike_int / 1000
    strike_str = (
        f"{strike_value:.2f}" if strike_int % 10 == 0 else f"{strike_value:.3f}"
    )
    return {
        "underlying": root.upper(),
        "option_type": "CALL" if match["type"].upper() == "C" else "PUT",
        "strike": strike_str,
        "expiration": expiration,
    }


def _normalize_robinhood_options(csv_data: str) -> str:
    """Convert a Robinhood options CSV export to the canonical detailed options format."""
    reader = csv.DictReader(io.StringIO(csv_data))
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(
        [
            "date",
            "underlying",
            "option_type",
            "action",
            "strike",
            "expiration",
            "contracts",
            "premium",
        ]
    )
    for row in reader:
        trans_code = (row.get("Trans Code") or "").strip().upper()
        if trans_code not in _ROBINHOOD_OPTIONS_TRADE_CODES:
            continue
        raw_date = (row.get("Activity Date") or "").strip()
        date_val = _parse_mdy_date(raw_date)
        if date_val is None:
            continue
        parsed_desc = _parse_robinhood_option_description(row.get("Description") or "")
        if parsed_desc is None:
            continue
        # Quantity is passed through as-is; positive-integer validation is in parse_options_detailed.
        contracts = (row.get("Quantity") or "").strip()
        raw_premium = (row.get("Price") or "").strip().lstrip("$").replace(",", "")
        premium = raw_premium if raw_premium else "0"
        writer.writerow(
            [
                date_val,
                parsed_desc["underlying"],
                parsed_desc["option_type"],
                trans_code,
                parsed_desc["strike"],
                parsed_desc["expiration"],
                contracts,
                premium,
            ]
        )
    return out.getvalue()


def normalize_options_broker_format(csv_data: str) -> str:
    """Detect and convert known broker export formats to the canonical options schema.

    Returns the data unchanged if no known broker format is detected.
    Currently supports: Robinhood.
    """
    broker = _detect_options_broker_format(csv_data)
    if broker == "robinhood":
        logger.info(
            "Detected Robinhood options export; normalizing to canonical format"
        )
        return _normalize_robinhood_options(csv_data)
    return csv_data
