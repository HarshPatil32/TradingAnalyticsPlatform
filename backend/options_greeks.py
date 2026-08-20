from __future__ import annotations

import logging
import math
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


def _validate_positive(value: float, name: str) -> None:
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be positive, got {value!r}")


def _validate_non_negative(value: float, name: str) -> None:
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be non-negative, got {value!r}")


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
    _validate_positive(spot, "spot")
    _validate_positive(strike, "strike")
    _validate_positive(time_to_expiry, "time_to_expiry")
    _validate_positive(volatility, "volatility")
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
    _validate_non_negative(market_price, "market_price")
    _validate_positive(spot, "spot")
    _validate_positive(strike, "strike")
    _validate_positive(time_to_expiry, "time_to_expiry")
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
    _validate_positive(spot, "spot")
    _validate_positive(strike, "strike")
    _validate_positive(time_to_expiry, "time_to_expiry")
    _validate_positive(volatility, "volatility")
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
    _validate_positive(spot, "spot")
    _validate_positive(strike, "strike")
    _validate_positive(time_to_expiry, "time_to_expiry")
    _validate_positive(volatility, "volatility")
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
    _validate_positive(spot, "spot")
    _validate_positive(strike, "strike")
    _validate_positive(time_to_expiry, "time_to_expiry")
    _validate_positive(volatility, "volatility")
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
    _validate_positive(spot, "spot")
    _validate_positive(strike, "strike")
    _validate_positive(time_to_expiry, "time_to_expiry")
    _validate_positive(volatility, "volatility")
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
    _validate_positive(spot, "spot")
    _validate_positive(strike, "strike")
    _validate_positive(time_to_expiry, "time_to_expiry")
    _validate_positive(volatility, "volatility")
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
    _validate_positive(spot, "spot")
    _validate_positive(strike, "strike")
    _validate_positive(time_to_expiry, "time_to_expiry")
    _validate_positive(volatility, "volatility")
    raise NotImplementedError
