from __future__ import annotations

import logging
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
    """Holds tunable options cost parameters.

    Individual regulatory fee rates are not yet configurable here; EPIC 9.6
    will add per-fee overrides when request-body config is implemented.
    """

    commission_per_contract: float = DEFAULT_OPTIONS_COMMISSION_PER_CONTRACT
    slippage_pct: float = DEFAULT_OPTIONS_SLIPPAGE_PCT
    spread_pct: float = DEFAULT_OPTIONS_SPREAD_PCT
    apply_regulatory_fees: bool = True


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


def calculate_options_real_costs(
    trades: list[dict],
    account_size: float,
    config: OptionsCostConfig | None = None,
) -> dict:
    """Master function — run all cost components and return a unified breakdown."""
    raise NotImplementedError
