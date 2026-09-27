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
    if not isinstance(commission_per_contract, (int, float)) or commission_per_contract < 0:
        raise ValueError(
            f"commission_per_contract must be >= 0, got {commission_per_contract}"
        )

    if not trades:
        return {
            "total_commission_usd": 0.0,
            "per_leg_avg_usd": 0.0,
            "num_legs": 0,
            "commission_rate": commission_per_contract,
        }

    total = 0.0
    for raw in trades:
        contracts = float(raw.get("contracts", 0) or 0)
        total += commission_per_contract * contracts

    num_legs = len(trades)
    return {
        "total_commission_usd": round(total, 4),
        "per_leg_avg_usd": round(total / num_legs, 4),
        "num_legs": num_legs,
        "commission_rate": commission_per_contract,
    }


def calculate_options_regulatory_fees(trades: list[dict]) -> dict:
    """Calculate OCC clearing, ORF, SEC, and FINRA TAF fees.

    SEC and FINRA TAF apply on sell-side legs only; each trade's ``action``
    field determines whether sell-side fees are charged.
    """
    raise NotImplementedError


def calculate_options_slippage(
    trades: list[dict],
    slippage_pct: float = DEFAULT_OPTIONS_SLIPPAGE_PCT,
) -> dict:
    """Calculate market-impact / slippage costs per contract."""
    raise NotImplementedError


def calculate_options_bid_ask_spread(
    trades: list[dict],
    spread_pct: float = DEFAULT_OPTIONS_SPREAD_PCT,
) -> dict:
    """Calculate round-trip bid-ask spread costs per contract."""
    raise NotImplementedError


def calculate_options_real_costs(
    trades: list[dict],
    account_size: float,
    config: OptionsCostConfig | None = None,
) -> dict:
    """Master function — run all cost components and return a unified breakdown."""
    raise NotImplementedError
