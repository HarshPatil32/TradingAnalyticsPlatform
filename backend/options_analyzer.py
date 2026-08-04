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
    expiration    Option expiration date, YYYY-MM-DD (distinct from date).
    contracts     Positive integer, number of contracts.
    premium       Non-negative float, quoted per share; total cash is
                  premium * contracts * multiplier. OEXP/OASGN rows use 0.

Optional columns (see OPTIONAL_OPTIONS_COLUMNS):
    multiplier    Positive integer; defaults to DEFAULT_CONTRACT_MULTIPLIER
                  (100) when absent or blank.
    fees          Non-negative float (0.0 is valid), user-reported broker fees
                  for the leg; defaults to 0.0 when absent or blank. Use a
                  non-negative check when parsing, not a positive-only parser.
                  Distinct from estimated costs computed by options_costs when
                  this column is missing.

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
from datetime import datetime

from csv_analyzer import (
    _detect_broker_format,
    _is_blank_csv_row,
    normalize_headers,
    sanitize_csv,
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
    """Parse a detailed options trade-list CSV into a list of typed trade dicts.

    If is_free_tier is True, enforce the free tier options row limit.
    """
    reader = csv.DictReader(io.StringIO(csv_data))

    if reader.fieldnames is None:
        raise ValueError("CSV is empty or has no header row")

    row_count = 0
    for raw_row in reader:
        if _is_blank_csv_row(raw_row):
            continue

        if is_free_tier and row_count >= FREE_TIER_OPTIONS_ROW_LIMIT:
            raise OptionsFreeTierLimitExceeded(
                f"Options row count exceeds the free tier limit of {FREE_TIER_OPTIONS_ROW_LIMIT}"
            )

        row_count += 1

    # Full field parsing lands in EPIC 7.1.
    raise NotImplementedError


def parse_options_summary(csv_data: str) -> dict:
    """Parse a summary-format options CSV into a single dict of aggregate metrics.

    Expects headers matching REQUIRED_OPTIONS_SUMMARY_COLUMNS (currently the same
    keys as stock summary uploads; revisit if the options summary schema changes).
    """
    # TODO:
    raise NotImplementedError


def validate_options(trades: list[dict]) -> list[dict]:
    """Check options trades for pairing errors and data quality issues."""
    # TODO:
    raise NotImplementedError


def calculate_options_pnl(trades: list[dict]) -> dict:
    """Compute per-position P&L, equity curve, and total return from an options trade list."""
    # TODO:
    raise NotImplementedError


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
# ---------------------------------------------------------------------------


def _detect_options_broker_format(csv_data: str) -> str | None:
    """Return a broker name string if a known brokerage export is detected, else None."""
    return _detect_broker_format(csv_data)


_ROBINHOOD_OPTIONS_TRADE_CODES: frozenset[str] = frozenset(
    {"BTO", "STO", "BTC", "STC", "OEXP", "OASGN"}
)

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
    try:
        expiration = datetime.strptime(match["expiration"], "%m/%d/%Y").strftime(
            "%Y-%m-%d"
        )
    except ValueError:
        return None
    return {
        "underlying": match["underlying"].upper(),
        "option_type": match["option_type"].upper(),
        "strike": match["strike"].replace(",", ""),
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
        try:
            date_val = datetime.strptime(raw_date, "%m/%d/%Y").strftime("%Y-%m-%d")
        except ValueError:
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
