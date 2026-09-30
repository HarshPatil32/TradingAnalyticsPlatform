from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Default cost assumptions (all overridable via OptionsCostConfig)

# Per-contract commission (USD), charged on each trade leg (BTO, STC, etc.).
# Default 0.00 matches mainstream commission-free retail (Robinhood, Webull).
# Common paid-broker reference rates (override via commission_per_contract):
#   tastytrade ~$0.50/contract (caps may apply on sell-to-close)
#   Schwab / TD Ameritrade ~$0.65/contract
DEFAULT_OPTIONS_COMMISSION_PER_CONTRACT: float = 0.00
DEFAULT_OPTIONS_SLIPPAGE_PCT: float = 0.03  # 3% of premium per contract
DEFAULT_OPTIONS_SPREAD_PCT: float = 0.05  # 5% round-trip of premium

# Regulatory fee defaults — approximate placeholders pending EPIC 9.2 verification.
# Reconcile against current schedules before shipping real logic:
#   OCC clearing: https://www.theocc.com/Company-Information/Fees
#   ORF:          https://www.opradata.com/fees/
#   SEC fee:      https://www.sec.gov/rules-regulations/fee-rate-advisories
#   FINRA TAF:    https://www.finra.org/rules-guidance/key-topics/trading-activity-fee
DEFAULT_OCC_CLEARING_FEE_PER_CONTRACT: float = 0.02
DEFAULT_ORF_FEE_PER_CONTRACT: float = 0.01
DEFAULT_SEC_FEE_RATE: float = 0.0000278  # sell-side only, per $ notional
DEFAULT_FINRA_TAF_PER_CONTRACT: float = 0.00279  # sell-side only

# Upper bounds for request-body overrides (trust boundary; normal brokers stay well below).
_MAX_COMMISSION_OR_FEE_PER_CONTRACT: float = 1000.0
_MAX_SEC_FEE_RATE: float = 1.0

_SELL_SIDE_OPTION_ACTIONS = frozenset({"STO", "STC", "SELL"})


def _validate_non_negative_rate(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError(f"{name} must be >= 0, got {value}")


def _float_from_trade_field(value: object | None, default: float = 0.0) -> float:
    """Parse numeric trade fields; invalid or non-numeric values become ``default``."""
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            return float(text)
        except ValueError:
            return default
    return default


# Configuration dataclass


@dataclass
class OptionsCostConfig:
    """Holds tunable options cost parameters (defaults or request-body overrides)."""

    commission_per_contract: float = DEFAULT_OPTIONS_COMMISSION_PER_CONTRACT
    slippage_pct: float = DEFAULT_OPTIONS_SLIPPAGE_PCT
    spread_pct: float = DEFAULT_OPTIONS_SPREAD_PCT
    apply_regulatory_fees: bool = True
    occ_fee_per_contract: float = DEFAULT_OCC_CLEARING_FEE_PER_CONTRACT
    orf_fee_per_contract: float = DEFAULT_ORF_FEE_PER_CONTRACT
    sec_fee_rate: float = DEFAULT_SEC_FEE_RATE
    finra_taf_per_contract: float = DEFAULT_FINRA_TAF_PER_CONTRACT


def _parse_request_non_negative_float(
    raw: Mapping[str, object],
    key: str,
    default: float,
    *,
    max_value: float | None = None,
    max_one: bool = False,
) -> float:
    if key not in raw:
        return default
    value = raw[key]
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValueError(f"{key} must be a number.")
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{key} must be a number.") from None
    if not math.isfinite(parsed):
        raise ValueError(f"{key} must be a number.")
    if parsed < 0:
        raise ValueError(f"{key} must be a non-negative number.")
    if max_one and parsed > 1:
        raise ValueError(f"{key} must be <= 1.")
    if max_value is not None and parsed > max_value:
        raise ValueError(f"{key} must be at most {max_value}.")
    return parsed


def _parse_request_bool(
    raw: Mapping[str, object],
    key: str,
    default: bool,
) -> bool:
    if key not in raw:
        return default
    value = raw[key]
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean.")
    return value


def options_cost_config_from_request(
    raw: Mapping[str, object] | None,
) -> OptionsCostConfig:
    """Build ``OptionsCostConfig`` from JSON or multipart form fields."""
    if raw is None:
        return OptionsCostConfig()
    if not isinstance(raw, Mapping):
        raise ValueError("cost configuration must be an object.")
    if not raw:
        return OptionsCostConfig()

    return OptionsCostConfig(
        commission_per_contract=_parse_request_non_negative_float(
            raw,
            "commission_per_contract",
            DEFAULT_OPTIONS_COMMISSION_PER_CONTRACT,
            max_value=_MAX_COMMISSION_OR_FEE_PER_CONTRACT,
        ),
        slippage_pct=_parse_request_non_negative_float(
            raw,
            "slippage_pct",
            DEFAULT_OPTIONS_SLIPPAGE_PCT,
            max_one=True,
        ),
        spread_pct=_parse_request_non_negative_float(
            raw,
            "spread_pct",
            DEFAULT_OPTIONS_SPREAD_PCT,
            max_one=True,
        ),
        apply_regulatory_fees=_parse_request_bool(
            raw, "apply_regulatory_fees", True
        ),
        occ_fee_per_contract=_parse_request_non_negative_float(
            raw,
            "occ_fee_per_contract",
            DEFAULT_OCC_CLEARING_FEE_PER_CONTRACT,
            max_value=_MAX_COMMISSION_OR_FEE_PER_CONTRACT,
        ),
        orf_fee_per_contract=_parse_request_non_negative_float(
            raw,
            "orf_fee_per_contract",
            DEFAULT_ORF_FEE_PER_CONTRACT,
            max_value=_MAX_COMMISSION_OR_FEE_PER_CONTRACT,
        ),
        sec_fee_rate=_parse_request_non_negative_float(
            raw,
            "sec_fee_rate",
            DEFAULT_SEC_FEE_RATE,
            max_value=_MAX_SEC_FEE_RATE,
        ),
        finra_taf_per_contract=_parse_request_non_negative_float(
            raw,
            "finra_taf_per_contract",
            DEFAULT_FINRA_TAF_PER_CONTRACT,
            max_value=_MAX_COMMISSION_OR_FEE_PER_CONTRACT,
        ),
    )


def calculate_options_commissions(
    trades: list[dict],
    commission_per_contract: float = DEFAULT_OPTIONS_COMMISSION_PER_CONTRACT,
) -> dict:
    """Calculate total per-contract commission costs."""
    _validate_non_negative_rate("commission_per_contract", commission_per_contract)

    if not trades:
        return {
            "total_commission_usd": 0.0,
            "per_leg_avg_usd": 0.0,
            "num_legs": 0,
            "commission_rate": commission_per_contract,
        }

    total = 0.0
    for raw in trades:
        contracts = _float_from_trade_field(raw.get("contracts", 0) or 0)
        total += commission_per_contract * contracts

    num_legs = len(trades)
    return {
        "total_commission_usd": round(total, 4),
        "per_leg_avg_usd": round(total / num_legs, 4),
        "num_legs": num_legs,
        "commission_rate": commission_per_contract,
    }


def calculate_options_regulatory_fees(
    trades: list[dict],
    occ_fee_per_contract: float = DEFAULT_OCC_CLEARING_FEE_PER_CONTRACT,
    orf_fee_per_contract: float = DEFAULT_ORF_FEE_PER_CONTRACT,
    sec_fee_rate: float = DEFAULT_SEC_FEE_RATE,
    finra_taf_per_contract: float = DEFAULT_FINRA_TAF_PER_CONTRACT,
) -> dict:
    """Calculate OCC clearing, ORF, SEC, and FINRA TAF fees.

    SEC and FINRA TAF apply on sell-side legs only; each trade's ``action``
    field determines whether sell-side fees are charged. Default rates are
    approximate placeholders; reconcile against current schedules before production use.
    """
    _validate_non_negative_rate("occ_fee_per_contract", occ_fee_per_contract)
    _validate_non_negative_rate("orf_fee_per_contract", orf_fee_per_contract)
    _validate_non_negative_rate("sec_fee_rate", sec_fee_rate)
    _validate_non_negative_rate("finra_taf_per_contract", finra_taf_per_contract)

    rates_used = {
        "occ_fee_per_contract": occ_fee_per_contract,
        "orf_fee_per_contract": orf_fee_per_contract,
        "sec_fee_rate": sec_fee_rate,
        "finra_taf_per_contract": finra_taf_per_contract,
    }

    if not trades:
        return {
            "total_regulatory_fees_usd": 0.0,
            "occ_clearing_usd": 0.0,
            "orf_usd": 0.0,
            "sec_fee_usd": 0.0,
            "finra_taf_usd": 0.0,
            "num_legs": 0,
            "num_sell_legs": 0,
            "rates_used": rates_used,
        }

    occ_total = 0.0
    orf_total = 0.0
    sec_total = 0.0
    finra_total = 0.0
    num_sell_legs = 0

    for raw in trades:
        contracts = _float_from_trade_field(raw.get("contracts", 0) or 0)
        occ_total += occ_fee_per_contract * contracts
        orf_total += orf_fee_per_contract * contracts

        action = str(raw.get("action", "")).upper().strip()
        if action in _SELL_SIDE_OPTION_ACTIONS:
            num_sell_legs += 1
            finra_total += finra_taf_per_contract * contracts
            premium_raw = raw.get("premium")
            if premium_raw is None or premium_raw == "":
                premium_raw = raw.get("price")
            premium = _float_from_trade_field(premium_raw, 0.0)
            notional = abs(premium * contracts * 100)
            sec_total += sec_fee_rate * notional

    occ_clearing_usd = round(occ_total, 4)
    orf_usd = round(orf_total, 4)
    sec_fee_usd = round(sec_total, 4)
    finra_taf_usd = round(finra_total, 4)
    total = round(occ_total + orf_total + sec_total + finra_total, 4)

    return {
        "total_regulatory_fees_usd": total,
        "occ_clearing_usd": occ_clearing_usd,
        "orf_usd": orf_usd,
        "sec_fee_usd": sec_fee_usd,
        "finra_taf_usd": finra_taf_usd,
        "num_legs": len(trades),
        "num_sell_legs": num_sell_legs,
        "rates_used": rates_used,
    }


def calculate_options_slippage(
    trades: list[dict],
    slippage_pct: float = DEFAULT_OPTIONS_SLIPPAGE_PCT,
) -> dict:
    """Calculate market-impact / slippage costs per contract.

    Slippage is modelled as slippage_pct × (premium × contracts × 100).
    Legs with missing or zero premium contribute zero slippage.
    """
    _validate_non_negative_rate("slippage_pct", slippage_pct)
    if slippage_pct > 1:
        raise ValueError(f"slippage_pct must be <= 1, got {slippage_pct}")

    if not trades:
        return {
            "total_slippage_usd": 0.0,
            "per_leg_avg_usd": 0.0,
            "num_legs": 0,
            "slippage_pct_used": slippage_pct,
            "per_leg_breakdown": [],
        }

    per_leg_breakdown = []
    for raw in trades:
        contracts = _float_from_trade_field(raw.get("contracts", 0) or 0)
        premium_raw = raw.get("premium")
        if premium_raw is None or premium_raw == "":
            premium_raw = raw.get("price")
        premium = _float_from_trade_field(premium_raw, 0.0)
        notional = abs(premium * contracts * 100)
        slippage_usd = round(notional * slippage_pct, 4) if notional > 0 else 0.0
        per_leg_breakdown.append(
            {
                "action": str(raw.get("action", "")).upper().strip(),
                "contracts": contracts,
                "premium": premium,
                "notional_usd": round(notional, 4),
                "slippage_usd": slippage_usd,
            }
        )

    total = round(sum(e["slippage_usd"] for e in per_leg_breakdown), 4)
    num_legs = len(trades)
    return {
        "total_slippage_usd": total,
        "per_leg_avg_usd": round(total / num_legs, 4),
        "num_legs": num_legs,
        "slippage_pct_used": slippage_pct,
        "per_leg_breakdown": per_leg_breakdown,
    }


def calculate_options_bid_ask_spread(
    trades: list[dict],
    spread_pct: float = DEFAULT_OPTIONS_SPREAD_PCT,
) -> dict:
    """Calculate round-trip bid-ask spread costs per contract.

    Spread is modelled as spread_pct × (premium × contracts × 100).
    Legs with missing or zero premium contribute zero spread cost.
    """
    _validate_non_negative_rate("spread_pct", spread_pct)
    if spread_pct > 1:
        raise ValueError(f"spread_pct must be <= 1, got {spread_pct}")

    if not trades:
        return {
            "total_spread_usd": 0.0,
            "per_leg_avg_usd": 0.0,
            "num_legs": 0,
            "spread_pct_used": spread_pct,
            "per_leg_breakdown": [],
        }

    per_leg_breakdown = []
    for raw in trades:
        contracts = _float_from_trade_field(raw.get("contracts", 0) or 0)
        premium_raw = raw.get("premium")
        if premium_raw is None or premium_raw == "":
            premium_raw = raw.get("price")
        premium = _float_from_trade_field(premium_raw, 0.0)
        notional = abs(premium * contracts * 100)
        spread_usd = round(notional * spread_pct, 4) if notional > 0 else 0.0
        per_leg_breakdown.append(
            {
                "action": str(raw.get("action", "")).upper().strip(),
                "contracts": contracts,
                "premium": premium,
                "notional_usd": round(notional, 4),
                "spread_usd": spread_usd,
            }
        )

    total = round(sum(e["spread_usd"] for e in per_leg_breakdown), 4)
    num_legs = len(trades)
    return {
        "total_spread_usd": total,
        "per_leg_avg_usd": round(total / num_legs, 4),
        "num_legs": num_legs,
        "spread_pct_used": spread_pct,
        "per_leg_breakdown": per_leg_breakdown,
    }


def _finite_usd_from_value(value: object, default: float = 0.0) -> float:
    """Parse a numeric USD field; bool/invalid/non-finite values become 0.0."""
    parsed = _float_from_trade_field(value, default)
    if not math.isfinite(parsed):
        return 0.0
    return parsed


def _safe_cost_usd(d: object, key: str) -> float:
    """Read a USD total from a cost component dict; invalid values become 0.0."""
    if not isinstance(d, dict):
        return 0.0
    return _finite_usd_from_value(d.get(key, 0.0))


def _safe_gross_profit_usd(pnl_data: object) -> float:
    if not isinstance(pnl_data, dict):
        return 0.0
    return _finite_usd_from_value(pnl_data.get("total_pnl", 0.0))


def _validate_positive_account_size(account_size: float) -> None:
    if isinstance(account_size, bool) or not isinstance(account_size, (int, float)):
        raise ValueError("account_size must be a positive number.")
    if not math.isfinite(account_size) or account_size <= 0:
        raise ValueError("account_size must be a positive number.")


def calculate_options_after_cost_return(
    gross_profit_usd: float,
    total_costs_usd: float,
    account_size: float,
) -> dict[str, float]:
    """Gross P&L and return pct minus trading costs only (no tax)."""
    _validate_positive_account_size(account_size)
    gross = _finite_usd_from_value(gross_profit_usd)
    costs = _finite_usd_from_value(total_costs_usd)
    after_costs_profit_usd = gross - costs
    gross_return_pct = gross / account_size * 100
    total_cost_pct = costs / account_size * 100
    after_costs_pct = gross_return_pct - total_cost_pct
    return {
        "gross_return_pct": round(gross_return_pct, 4),
        "total_costs_pct": round(total_cost_pct, 4),
        "after_costs_profit_usd": round(after_costs_profit_usd, 4),
        "after_costs_pct": round(after_costs_pct, 4),
    }


def aggregate_options_total_costs(
    pnl_data: dict,
    commissions: dict,
    slippage: dict,
    bid_ask_spread: dict,
    *,
    regulatory_fees: dict | None = None,
    account_size: float | None = None,
) -> dict:
    commission_usd = _safe_cost_usd(commissions, "total_commission_usd")
    slippage_usd = _safe_cost_usd(slippage, "total_slippage_usd")
    spread_usd = _safe_cost_usd(bid_ask_spread, "total_spread_usd")
    regulatory_usd = (
        _safe_cost_usd(regulatory_fees, "total_regulatory_fees_usd")
        if regulatory_fees is not None
        else 0.0
    )

    gross_profit_usd = _safe_gross_profit_usd(pnl_data)
    total_costs_usd = round(
        commission_usd + slippage_usd + spread_usd + regulatory_usd, 4
    )

    if gross_profit_usd > 0:
        cost_drag_pct = round(total_costs_usd / gross_profit_usd, 4)
    else:
        cost_drag_pct = None

    trade_pnl = pnl_data.get("trade_pnl") if isinstance(pnl_data, dict) else None
    if not isinstance(trade_pnl, list):
        trade_pnl = []
    num_closed_trades = len(trade_pnl)

    result: dict = {
        "total_costs_usd": total_costs_usd,
        "cost_drag_pct": cost_drag_pct,
        "gross_profit_usd": gross_profit_usd,
        "num_closed_trades": num_closed_trades,
        "components_usd": {
            "commission": round(commission_usd, 4),
            "slippage": round(slippage_usd, 4),
            "spread": round(spread_usd, 4),
            "regulatory_fees": round(regulatory_usd, 4),
        },
    }
    if account_size is not None:
        result.update(
            calculate_options_after_cost_return(
                gross_profit_usd, total_costs_usd, account_size
            )
        )
    return result


def calculate_options_real_costs(
    trades: list[dict],
    account_size: float,
    config: OptionsCostConfig | None = None,
) -> dict:
    """Master function — run all cost components and return a unified breakdown."""
    raise NotImplementedError
