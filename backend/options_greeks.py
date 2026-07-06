from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Default pricing assumptions (all overridable via GreeksConfig)

DEFAULT_RISK_FREE_RATE: float = 0.05  # Annualized risk-free rate assumption
DEFAULT_DIVIDEND_YIELD: float = (
    0.00  # Continuous dividend/carry yield on the underlying
)
DEFAULT_IMPLIED_VOL_GUESS: float = (
    0.30  # Initial volatility guess for the IV solver (30%)
)
DEFAULT_IMPLIED_VOL_MAX_ITERATIONS: int = 100
DEFAULT_IMPLIED_VOL_TOLERANCE: float = (
    1e-6  # Price convergence tolerance in absolute dollars
)
MIN_IMPLIED_VOL: float = 0.001  # Solver lower bound (0.1%)
MAX_IMPLIED_VOL: float = 5.0  # Solver upper bound (500%)
TRADING_DAYS_PER_YEAR: int = 252  # For converting annualized theta to per-day theta


# Configuration dataclass


@dataclass
class GreeksConfig:
    """Holds tunable Black-Scholes pricing/Greeks parameters."""

    risk_free_rate: float = DEFAULT_RISK_FREE_RATE
    dividend_yield: float = DEFAULT_DIVIDEND_YIELD
    implied_vol_guess: float = DEFAULT_IMPLIED_VOL_GUESS
    implied_vol_max_iterations: int = DEFAULT_IMPLIED_VOL_MAX_ITERATIONS
    implied_vol_tolerance: float = DEFAULT_IMPLIED_VOL_TOLERANCE


def black_scholes_price(
    option_type: str,
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    dividend_yield: float = DEFAULT_DIVIDEND_YIELD,
) -> float:
    """Calculate the Black-Scholes-Merton theoretical price for a call or put option."""
    raise NotImplementedError


def calculate_implied_volatility(
    option_type: str,
    market_price: float,
    spot: float,
    strike: float,
    time_to_expiry: float,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    dividend_yield: float = DEFAULT_DIVIDEND_YIELD,
    config: GreeksConfig | None = None,
) -> float:
    """Solve for the implied volatility that reprices an option to its observed market price."""
    raise NotImplementedError


def calculate_delta(
    option_type: str,
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    dividend_yield: float = DEFAULT_DIVIDEND_YIELD,
) -> float:
    """Calculate delta: sensitivity of option price to a $1 change in the underlying."""
    raise NotImplementedError


def calculate_gamma(
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    dividend_yield: float = DEFAULT_DIVIDEND_YIELD,
) -> float:
    """Calculate gamma: sensitivity of delta to a $1 change in the underlying (same for calls and puts)."""
    raise NotImplementedError


def calculate_theta(
    option_type: str,
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    dividend_yield: float = DEFAULT_DIVIDEND_YIELD,
) -> float:
    """Calculate theta: sensitivity of option price to one day of time decay."""
    raise NotImplementedError


def calculate_vega(
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    dividend_yield: float = DEFAULT_DIVIDEND_YIELD,
) -> float:
    """Calculate vega: sensitivity of option price to a 1 percentage-point change in volatility (same for calls and puts)."""
    raise NotImplementedError


def calculate_rho(
    option_type: str,
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    dividend_yield: float = DEFAULT_DIVIDEND_YIELD,
) -> float:
    """Calculate rho: sensitivity of option price to a 1 percentage-point change in the risk-free rate."""
    raise NotImplementedError


def calculate_greeks(
    option_type: str,
    spot: float,
    strike: float,
    time_to_expiry: float,
    volatility: float,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    dividend_yield: float = DEFAULT_DIVIDEND_YIELD,
) -> dict:
    """Master function — compute price and all five standard Greeks in a single dict."""
    raise NotImplementedError
