"""
overfitting_detector.py
-----------------------
Detects signs of curve-fitting / data-snooping in backtested trading
strategies by scoring four independent evidence sources:

  1. Equity-curve smoothness   – suspiciously linear / uninterrupted curves
  2. Win-rate plausibility     – implausibly high win rates
  3. Sharpe-ratio plausibility – unrealistically high risk-adjusted returns
  4. Trade-frequency clustering – trades bunched into specific time windows

Each factor produces a sub-score in [0, 100] where:
  0   = no overfitting signal detected
  100 = strong evidence of overfitting / curve-fitting

The final ``overfitting_score`` is a weighted average across all four
factors.  A breakdown dict exposes each factor's contribution so callers
can pinpoint which dimension is driving the concern.

Statistical backbone
--------------------
``sharpe_significance`` and ``winrate_binomial_test`` are imported from
``statistical_tests`` so that scoring decisions are anchored to
established significance results rather than raw heuristics alone.

Public API
----------
score_equity_smoothness(equity_curve)              →  dict
score_win_rate(pnl_list)                           →  dict
score_sharpe(pnl_list, trades_per_year)            →  dict
score_trade_clustering(trade_dates)                →  dict
detect_overfitting(pnl_list, ...)                  →  dict   ← main entry
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Sequence

from statistical_tests import sharpe_significance, winrate_binomial_test

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scoring thresholds (all overridable via OverfittingConfig)
# ---------------------------------------------------------------------------

# Equity smoothness – R² of equity curve against a linear trend
_R2_LOW: float = 0.80  # below → minimal smoothness concern
_R2_HIGH: float = 0.98  # above → near-perfect smoothness → suspicious

# Win rate plausibility
_WR_LOW: float = 0.60  # below → normal trading win rate
_WR_HIGH: float = 0.90  # above → highly implausible for a discretionary eq strategy

# Annualised Sharpe plausibility
_SHARPE_LOW: float = 1.5  # below → reasonable
_SHARPE_HIGH: float = 4.0  # above → implausible without insider edge

# Trade-clustering Gini coefficient
_GINI_LOW: float = 0.20  # below → evenly distributed trades
_GINI_HIGH: float = 0.70  # above → severe clustering

# Default factor weights (sum = 1.0)
_WEIGHT_SMOOTHNESS: float = 0.30
_WEIGHT_WIN_RATE: float = 0.25
_WEIGHT_SHARPE: float = 0.25
_WEIGHT_CLUSTERING: float = 0.20

# Risk tier labels
_TIERS = [
    (80, "CRITICAL  – strong overfitting signal"),
    (60, "HIGH      – notable overfitting risk"),
    (40, "MODERATE  – some suspicious characteristics"),
    (20, "LOW       – minor concerns, monitor closely"),
    (0, "MINIMAL   – no significant overfitting signal"),
]

# Plain-English descriptions for each config key.
# Keyed to match config_used exactly so config_descriptions stays in sync automatically.
_CONFIG_DESCRIPTIONS: dict[str, str] = {
    "r2_low": (
        "Equity curve smoothness lower bound. "
        "An R² below this value means the curve is too erratic to look like a real strategy."
    ),
    "r2_high": (
        "Equity curve smoothness upper bound. "
        "A curve smoother than this is suspiciously perfect — "
        "real markets don't produce perfectly smooth equity lines."
    ),
    "win_rate_low": (
        "Win rate lower plausibility bound. "
        "Win rates below this are too low to suggest any edge."
    ),
    "win_rate_high": (
        "Win rate upper plausibility bound. "
        "Win rates above this are unusually high and may indicate the strategy "
        "was over-fitted to historical data."
    ),
    "sharpe_low": (
        "Sharpe ratio lower plausibility bound. "
        "Strategies with a Sharpe below this offer poor risk-adjusted returns."
    ),
    "sharpe_high": (
        "Sharpe ratio upper plausibility bound. "
        "Real strategies rarely sustain a Sharpe above this — higher values "
        "are a strong signal of curve-fitting."
    ),
    "gini_low": (
        "Trade clustering lower bound (Gini coefficient). "
        "A very low value means trades are evenly spread across time — "
        "which can indicate the strategy never sat out bad periods."
    ),
    "gini_high": (
        "Trade clustering upper bound (Gini coefficient). "
        "A very high value means almost all trades cluster in a tiny window — "
        "which can mean the strategy was only profitable in one lucky period."
    ),
    "trades_per_year": (
        "Assumed trading days per year used to annualise the Sharpe ratio. "
        "Set to None to skip annualisation and use the raw per-trade Sharpe directly."
    ),
    "alpha": (
        "Statistical significance level. "
        "A result is flagged as significant only when the chance of seeing it by luck "
        "is below this threshold."
    ),
    "clustering_buckets": (
        "Number of time buckets used to measure how evenly trades are spread across the "
        "backtest period. More buckets give a finer-grained picture of clustering."
    ),
}


# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------


@dataclass
class OverfittingConfig:
    """
    Tunable thresholds and weights for the overfitting detector.
    The defaults reflect published academic and practitioner norms for
    equity long/short strategies; adjust for options or HFT strategies.
    """

    # Factor weights (normalised internally if they don't sum to 1.0)
    weight_smoothness: float = _WEIGHT_SMOOTHNESS
    weight_win_rate: float = _WEIGHT_WIN_RATE
    weight_sharpe: float = _WEIGHT_SHARPE
    weight_clustering: float = _WEIGHT_CLUSTERING

    # Equity-curve smoothness (R²)
    r2_low: float = _R2_LOW
    r2_high: float = _R2_HIGH

    # Win rate boundaries
    win_rate_low: float = _WR_LOW
    win_rate_high: float = _WR_HIGH

    # Annualised Sharpe boundaries
    sharpe_low: float = _SHARPE_LOW
    sharpe_high: float = _SHARPE_HIGH

    # Trade-clustering Gini boundaries
    gini_low: float = _GINI_LOW
    gini_high: float = _GINI_HIGH

    # Number of time buckets used when evaluating clustering
    clustering_buckets: int = 10

    # trades_per_year – used to annualise per-trade Sharpe
    # Set to None to skip annualisation and use per-trade Sharpe directly
    trades_per_year: float = 252.0

    # Statistical significance level (passed to imported tests)
    alpha: float = 0.05


# ---------------------------------------------------------------------------
# Internal maths helpers
# ---------------------------------------------------------------------------


def _linear_r_squared(y: list[float]) -> float:
    """
    Coefficient of determination (R²) of a simple OLS fit
    y ~ a + b*t  where t = 0, 1, 2, …, n-1.

    Returns 1.0 if all y values are identical (degenerate case).
    """
    n = len(y)
    if n < 2:
        return 1.0

    x_mean = (n - 1) / 2.0
    y_mean = sum(y) / n

    ss_xx = sum((i - x_mean) ** 2 for i in range(n))
    ss_yy = sum((yi - y_mean) ** 2 for yi in y)
    ss_xy = sum((i - x_mean) * (yi - y_mean) for i, yi in enumerate(y))

    if ss_yy == 0.0:
        return 1.0  # flat curve – perfectly "linear"
    if ss_xx == 0.0:
        return 0.0  # single point

    slope = ss_xy / ss_xx
    intercept = y_mean - slope * x_mean
    y_pred = [slope * i + intercept for i in range(n)]
    ss_res = sum((yi - yp) ** 2 for yi, yp in zip(y, y_pred))

    return max(0.0, min(1.0, 1.0 - ss_res / ss_yy))


def _gini_coefficient(values: list[float]) -> float:
    """
    Gini coefficient of a distribution of non-negative values.

    0.0 → perfectly uniform  |  1.0 → fully concentrated in one bucket.
    Uses the standard sorted-cumsum formula; always returns [0, 1].
    """
    n = len(values)
    if n == 0 or sum(values) == 0:
        return 0.0

    sorted_v = sorted(values)
    total = sum(sorted_v)
    cumsum = 0.0
    weighted_sum = 0.0
    for i, v in enumerate(sorted_v, start=1):
        cumsum += v
        weighted_sum += cumsum

    gini = (2.0 * weighted_sum) / (n * total) - (n + 1) / n
    return max(0.0, min(1.0, gini))


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _linear_interpolate(value: float, low: float, high: float) -> float:
    """
    Map `value` linearly onto [0, 100]:
      value <= low   →  0
      value >= high  →  100
    """
    if value <= low:
        return 0.0
    if value >= high:
        return 100.0
    return _clamp((value - low) / (high - low) * 100.0)


def _risk_tier(score: float) -> str:
    for threshold, label in _TIERS:
        if score >= threshold:
            return label
    return _TIERS[-1][1]


def _cumulative_equity(pnl_list: list[float], start: float = 0.0) -> list[float]:
    """Convert per-trade P&L to a cumulative equity series starting at `start`."""
    equity = []
    running = start
    for p in pnl_list:
        running += p
        equity.append(running)
    return equity


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
    logger.warning("Could not parse date: %s", val)
    return None


# ---------------------------------------------------------------------------
# Factor 1 – Equity-curve smoothness
# ---------------------------------------------------------------------------


def score_equity_smoothness(
    equity_curve: Sequence[float],
    config: OverfittingConfig | None = None,
) -> dict:
    """
    Score how suspiciously smooth the equity curve is.

    A perfectly linear equity curve (R² ≈ 1.0) means the strategy
    generated nearly identical returns every period — a red flag for
    curve-fitting, since real strategies experience variance and
    drawdowns.

    Also computes a *drawdown-absence penalty*: if the curve never
    retraces more than 1 % of its peak, that adds up to 20 extra
    suspicion points.

    Parameters
    ----------
    equity_curve : sequence of cumulative equity values
                   (e.g. [100, 102, 105, 103, …])

    Returns
    -------
    dict with keys:
        score           float [0–100]
        r_squared       float
        max_drawdown_pct float
        interpretation  str
        warnings        list[str]
    """
    cfg = config or OverfittingConfig()
    curve = list(equity_curve)
    warnings: list[str] = []

    if len(curve) < 3:
        warnings.append(
            "Equity curve has fewer than 3 points — smoothness score defaulted to 0."
        )
        return {
            "score": 0.0,
            "r_squared": None,
            "max_drawdown_pct": None,
            "drawdown_penalty": 0.0,
            "interpretation": "Insufficient equity curve data.",
            "warnings": warnings,
        }

    r2 = _linear_r_squared(curve)

    # Max drawdown (peak-to-trough)
    peak = curve[0]
    max_dd = 0.0
    for v in curve:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak != 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    # Primary score from R²
    r2_score = _linear_interpolate(r2, cfg.r2_low, cfg.r2_high)

    # Drawdown-absence penalty: a curve with < 1% drawdown is suspicious
    # Scale: 0% drawdown → +20 penalty, 10%+ drawdown → 0 penalty
    dd_threshold = 0.01  # 1 %
    dd_penalty = 0.0
    if max_dd < dd_threshold:
        dd_penalty = _linear_interpolate(1.0 - max_dd / dd_threshold, 0.0, 1.0) * 0.20

    raw_score = _clamp(r2_score + dd_penalty)

    lines = [
        f"R²={r2:.4f} (threshold: low={cfg.r2_low}, high={cfg.r2_high}).",
        f"Max drawdown={max_dd:.2%}.",
        f"Smoothness sub-score={r2_score:.1f}/100; drawdown-absence penalty=+{dd_penalty:.1f}.",
    ]
    if r2 > 0.95:
        lines.append(
            "Near-perfect linearity detected — characteristic of overfit equity curves."
        )
        warnings.append("R² > 0.95: equity curve is suspiciously smooth.")
    if max_dd < 0.01:
        lines.append(
            "Max drawdown < 1% — virtually no losing periods, highly unrealistic."
        )
        warnings.append(
            "Max drawdown < 1%: absence of drawdowns is a curve-fitting signal."
        )

    return {
        "score": round(raw_score, 2),
        "r_squared": round(r2, 6),
        "max_drawdown_pct": round(max_dd * 100, 4),
        "drawdown_penalty": round(dd_penalty, 2),
        "interpretation": " ".join(lines),
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Factor 2 – Win-rate plausibility
# ---------------------------------------------------------------------------


def score_win_rate(
    pnl_list: Sequence[float],
    config: OverfittingConfig | None = None,
) -> dict:
    """
    Score the plausibility of the observed win rate.

    Genuine equity strategies rarely sustain win rates above 65–70 %
    over hundreds of trades.  Very high win rates (> 80–90 %) are
    hallmarks of overfitted mean-reversion or martingale-like systems.

    Uses ``winrate_binomial_test`` from statistical_tests to measure
    statistical significance of the observed win rate.

    Returns
    -------
    dict with keys:
        score           float [0–100]
        win_rate        float
        wins            int
        losses          int
        binomial_test   dict   (full result from statistical_tests)
        interpretation  str
        warnings        list[str]
    """
    cfg = config or OverfittingConfig()
    data = list(pnl_list)
    warnings: list[str] = []

    if not data:
        return {
            "score": 0.0,
            "win_rate": None,
            "wins": 0,
            "losses": 0,
            "binomial_test": {},
            "interpretation": "No P&L data provided.",
            "warnings": warnings,
        }

    binom = winrate_binomial_test(data, alpha=cfg.alpha)
    win_rate = binom.get("win_rate") or 0.0
    wins = binom.get("wins", 0)
    losses = binom.get("losses", 0)

    wr_score = _linear_interpolate(win_rate, cfg.win_rate_low, cfg.win_rate_high)

    # Bonus suspicion if stat-significant AND win rate is already high:
    # a believable strategy can be significant at 60 %; a 90 % significant win
    # rate is far harder to explain legitimately.
    significance_multiplier = (
        1.15 if binom.get("significant") and win_rate > 0.70 else 1.0
    )
    raw_score = _clamp(wr_score * significance_multiplier)

    lines = [
        f"Win rate={win_rate:.2%} ({wins}W / {losses}L).",
        f"Binomial test p-value={binom.get('p_value', 'N/A')}.",
        f"Win-rate sub-score={wr_score:.1f}/100.",
    ]
    if win_rate > cfg.win_rate_high:
        lines.append(
            f"Win rate exceeds {cfg.win_rate_high:.0%} — implausible for most equity strategies."
        )
        warnings.append(
            f"Win rate {win_rate:.2%} exceeds plausibility ceiling of {cfg.win_rate_high:.0%}."
        )
    if binom.get("significant") and win_rate > 0.70:
        lines.append(
            "High win rate is statistically significant — could indicate data snooping."
        )
        warnings.append(
            "Statistically significant high win rate may reflect look-ahead bias or over-optimisation."
        )

    return {
        "score": round(raw_score, 2),
        "win_rate": round(win_rate, 6),
        "wins": wins,
        "losses": losses,
        "binomial_test": binom,
        "interpretation": " ".join(lines),
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Factor 3 – Sharpe-ratio plausibility
# ---------------------------------------------------------------------------


def score_sharpe(
    pnl_list: Sequence[float],
    config: OverfittingConfig | None = None,
) -> dict:
    """
    Score the plausibility of the strategy's Sharpe ratio.

    Annualised Sharpe ratios above ~3 are very rare outside HFT or
    insider trading.  Values above 4 are almost always a sign of
    look-ahead bias, overfitting, or survivorship bias.

    The per-trade Sharpe from ``sharpe_significance`` is annualised as:

        annualised_sharpe = per_trade_sharpe × √(trades_per_year)

    Set ``config.trades_per_year = None`` to skip annualisation.

    Returns
    -------
    dict with keys:
        score              float [0–100]
        per_trade_sharpe   float | None
        annualised_sharpe  float | None
        sharpe_test        dict   (full result from statistical_tests)
        interpretation     str
        warnings           list[str]
    """
    cfg = config or OverfittingConfig()
    data = list(pnl_list)
    warnings: list[str] = []

    if not data:
        return {
            "score": 0.0,
            "per_trade_sharpe": None,
            "annualised_sharpe": None,
            "sharpe_test": {},
            "interpretation": "No P&L data provided.",
            "warnings": warnings,
        }

    sharpe_result = sharpe_significance(data, alpha=cfg.alpha)
    per_trade_sr = sharpe_result.get("sharpe_ratio")

    annualised_sr: float | None = None
    scored_sr: float = 0.0

    if per_trade_sr is not None:
        if cfg.trades_per_year and cfg.trades_per_year > 0:
            annualised_sr = per_trade_sr * math.sqrt(cfg.trades_per_year)
            scored_sr = abs(annualised_sr)  # use absolute value for one-sided scoring
        else:
            scored_sr = abs(per_trade_sr)

        used_high = (
            cfg.sharpe_high if cfg.trades_per_year else cfg.sharpe_high / math.sqrt(252)
        )
        used_low = (
            cfg.sharpe_low if cfg.trades_per_year else cfg.sharpe_low / math.sqrt(252)
        )
        sharpe_score = _linear_interpolate(scored_sr, used_low, used_high)
    else:
        sharpe_score = 0.0

    # Amplify if the Sharpe is also statistically significant
    sig_mult = (
        1.10 if sharpe_result.get("significant") and scored_sr > cfg.sharpe_low else 1.0
    )
    raw_score = _clamp(sharpe_score * sig_mult)

    ann_label = (
        f"{annualised_sr:.3f}" if annualised_sr is not None else "N/A (not annualised)"
    )
    pt_label = f"{per_trade_sr:.4f}" if per_trade_sr is not None else "N/A"
    lines = [
        f"Per-trade Sharpe={pt_label}.",
        f"Annualised Sharpe (×√{cfg.trades_per_year:.0f})={ann_label}.",
        f"Sharpe sub-score={sharpe_score:.1f}/100.",
    ]
    if annualised_sr is not None and abs(annualised_sr) > cfg.sharpe_high:
        lines.append(
            f"Annualised Sharpe {abs(annualised_sr):.2f} exceeds plausibility ceiling of {cfg.sharpe_high}."
        )
        warnings.append(
            f"Annualised Sharpe {abs(annualised_sr):.2f} > {cfg.sharpe_high}: "
            "implausible without curve-fitting or structural bias."
        )

    return {
        "score": round(raw_score, 2),
        "per_trade_sharpe": (
            round(per_trade_sr, 6) if per_trade_sr is not None else None
        ),
        "annualised_sharpe": (
            round(annualised_sr, 4) if annualised_sr is not None else None
        ),
        "sharpe_test": sharpe_result,
        "interpretation": " ".join(lines),
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Factor 4 – Trade-frequency clustering
# ---------------------------------------------------------------------------


def score_trade_clustering(
    trade_dates: Sequence[Any],
    config: OverfittingConfig | None = None,
) -> dict:
    """
    Score how unevenly trades are distributed across time.

    A strategy that made most of its trades in a narrow time window
    (e.g. a single volatile quarter) may simply have been curve-fitted
    to that regime.  We divide the full date range into equal-width
    buckets and compute the Gini coefficient of the trade counts.

    Additionally, the *coefficient of variation* (CV) of inter-trade
    intervals is reported: very low CV means evenly-spaced mechanical
    trades (can indicate a grid / martingale system).

    Parameters
    ----------
    trade_dates : sequence of date-like objects or ISO strings

    Returns
    -------
    dict with keys:
        score           float [0–100]
        gini            float
        cv_intervals    float | None
        num_trades      int
        num_buckets     int
        bucket_counts   list[int]
        interpretation  str
        warnings        list[str]
    """
    cfg = config or OverfittingConfig()
    warnings: list[str] = []

    parsed: list[date] = []
    for d in trade_dates:
        pd = _parse_date(d)
        if pd is not None:
            parsed.append(pd)

    if len(parsed) < 3:
        warnings.append(
            f"Only {len(parsed)} parseable trade dates — clustering score defaulted to 0."
        )
        return {
            "score": 0.0,
            "gini": None,
            "cv_intervals": None,
            "num_trades": len(parsed),
            "num_buckets": cfg.clustering_buckets,
            "bucket_counts": [],
            "interpretation": "Insufficient date data for clustering analysis.",
            "warnings": warnings,
        }

    parsed.sort()
    start_ord = parsed[0].toordinal()
    end_ord = parsed[-1].toordinal()
    span = end_ord - start_ord

    if span == 0:
        # All trades on one day
        warnings.append(
            "All trades occur on the same date — extreme clustering detected."
        )
        return {
            "score": 100.0,
            "gini": 1.0,
            "cv_intervals": 0.0,
            "num_trades": len(parsed),
            "num_buckets": cfg.clustering_buckets,
            "bucket_counts": [len(parsed)],
            "interpretation": "All trades on identical date — maximum clustering.",
            "warnings": warnings,
        }

    # Bucket trade counts
    nb = cfg.clustering_buckets
    bucket_size = span / nb
    bucket_counts = [0] * nb
    for d in parsed:
        idx = min(int((d.toordinal() - start_ord) / bucket_size), nb - 1)
        bucket_counts[idx] += 1

    gini = _gini_coefficient([float(c) for c in bucket_counts])

    # CV of inter-trade intervals
    intervals = [
        (parsed[i + 1].toordinal() - parsed[i].toordinal())
        for i in range(len(parsed) - 1)
    ]
    cv_intervals: float | None = None
    if intervals:
        mean_iv = sum(intervals) / len(intervals)
        if mean_iv > 0:
            std_iv = math.sqrt(
                sum((x - mean_iv) ** 2 for x in intervals) / len(intervals)
            )
            cv_intervals = std_iv / mean_iv

    gini_score = _linear_interpolate(gini, cfg.gini_low, cfg.gini_high)

    # Low CV (regular spacing) penalty — max +15 points on top of gini_score
    cv_penalty = 0.0
    if cv_intervals is not None and cv_intervals < 0.3:
        cv_penalty = _linear_interpolate(0.3 - cv_intervals, 0.0, 0.3) * 0.15

    raw_score = _clamp(gini_score + cv_penalty)

    lines = [
        f"Gini coefficient={gini:.4f} (threshold: low={cfg.gini_low}, high={cfg.gini_high}).",
        f"{len(parsed)} trades across {nb} time buckets: {bucket_counts}.",
        f"CV of inter-trade intervals={f'{cv_intervals:.3f}' if cv_intervals is not None else 'N/A'}.",
        f"Clustering sub-score={gini_score:.1f}/100; spacing penalty=+{cv_penalty:.1f}.",
    ]
    if gini > cfg.gini_high:
        lines.append("High Gini — trades heavily concentrated in a few time windows.")
        warnings.append(
            f"Gini {gini:.3f} > {cfg.gini_high}: trades clustered in narrow market regimes."
        )
    if cv_intervals is not None and cv_intervals < 0.2:
        lines.append(
            "Very low CV — trades are suspiciously evenly spaced (grid/mechanical system?)."
        )
        warnings.append(
            f"CV of intervals={cv_intervals:.3f}: near-mechanical trade spacing detected."
        )

    return {
        "score": round(raw_score, 2),
        "gini": round(gini, 6),
        "cv_intervals": round(cv_intervals, 6) if cv_intervals is not None else None,
        "num_trades": len(parsed),
        "num_buckets": nb,
        "bucket_counts": bucket_counts,
        "interpretation": " ".join(lines),
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Main entry-point
# ---------------------------------------------------------------------------


def detect_overfitting(
    pnl_list: Sequence[float],
    equity_curve: Sequence[float] | None = None,
    trade_dates: Sequence[Any] | None = None,
    config: OverfittingConfig | None = None,
) -> dict:
    """
    Run all four overfitting checks and return a unified risk report.

    Parameters
    ----------
    pnl_list     : per-trade P&L list (required).
    equity_curve : cumulative equity values.  If omitted, reconstructed
                   from ``pnl_list`` starting at 0.
    trade_dates  : dates for each trade (required for clustering).
                   Accepts ISO strings, ``datetime.date``, or ``datetime``.
    config       : OverfittingConfig (defaults used if None).

    Returns
    -------
    dict
    ├── overfitting_score   float [0–100]  weighted composite risk score
    ├── risk_tier           str            human-readable risk label
    ├── factor_scores
    │   ├── equity_smoothness  dict        (score_equity_smoothness result)
    │   ├── win_rate           dict        (score_win_rate result)
    │   ├── sharpe             dict        (score_sharpe result)
    │   └── trade_clustering   dict        (score_trade_clustering result)
    ├── breakdown_pct
    │   └── {factor: weighted_contribution}
    ├── all_warnings        list[str]      de-duplicated across all factors
    └── metadata
        ├── num_trades      int
        ├── weights_used    dict
        └── config_used     dict
    """
    cfg = config or OverfittingConfig()
    data = list(pnl_list)

    # Reconstruct equity curve if not provided
    if equity_curve is None:
        curve: list[float] = _cumulative_equity(data, start=0.0)
    else:
        curve = list(equity_curve)

    # Normalise weights to sum exactly to 1.0
    raw_weights = {
        "equity_smoothness": cfg.weight_smoothness,
        "win_rate": cfg.weight_win_rate,
        "sharpe": cfg.weight_sharpe,
        "trade_clustering": cfg.weight_clustering,
    }
    total_w = sum(raw_weights.values())
    if total_w == 0:
        total_w = 1.0
    weights = {k: v / total_w for k, v in raw_weights.items()}

    # ------------------------------------------------------------------
    # Run individual factor scorers
    # ------------------------------------------------------------------
    smoothness_result = score_equity_smoothness(curve, cfg)
    win_rate_result = score_win_rate(data, cfg)
    sharpe_result = score_sharpe(data, cfg)

    dates_input = trade_dates if trade_dates is not None else []
    clustering_result = score_trade_clustering(dates_input, cfg)

    factor_scores = {
        "equity_smoothness": smoothness_result,
        "win_rate": win_rate_result,
        "sharpe": sharpe_result,
        "trade_clustering": clustering_result,
    }

    # ------------------------------------------------------------------
    # Composite score
    # ------------------------------------------------------------------
    raw_factor_scores = {
        "equity_smoothness": smoothness_result["score"],
        "win_rate": win_rate_result["score"],
        "sharpe": sharpe_result["score"],
        "trade_clustering": clustering_result["score"],
    }

    composite = sum(weights[k] * raw_factor_scores[k] for k in weights)
    composite = _clamp(composite)

    breakdown_pct = {k: round(weights[k] * raw_factor_scores[k], 4) for k in weights}

    # ------------------------------------------------------------------
    # Deduplicate warnings
    # ------------------------------------------------------------------
    seen: set[str] = set()
    all_warnings: list[str] = []
    for key in ("equity_smoothness", "win_rate", "sharpe", "trade_clustering"):
        for w in factor_scores[key].get("warnings", []):
            if w not in seen:
                seen.add(w)
                all_warnings.append(w)

    # High-level composite warnings
    if composite >= 80:
        all_warnings.insert(
            0,
            "CRITICAL: Multiple strong overfitting signals detected. "
            "Do not deploy this strategy without extensive out-of-sample validation.",
        )
    elif composite >= 60:
        all_warnings.insert(
            0,
            "HIGH RISK: Significant overfitting indicators present. "
            "Walk-forward or out-of-sample testing strongly recommended.",
        )
    elif composite >= 40:
        all_warnings.insert(
            0,
            "MODERATE RISK: Some suspicious characteristics. "
            "Consider reducing parameter count and running robustness tests.",
        )

    # Interpret missing clustering data
    if not dates_input:
        all_warnings.append(
            "trade_dates not provided — trade-clustering factor defaulted to 0 "
            "(pass trade_dates for a complete assessment)."
        )

    return {
        "overfitting_score": round(composite, 2),
        "risk_tier": _risk_tier(composite),
        "factor_scores": factor_scores,
        "breakdown_pct": {k: round(v, 4) for k, v in breakdown_pct.items()},
        "all_warnings": all_warnings,
        "metadata": {
            "num_trades": len(data),
            "weights_used": {k: round(v, 6) for k, v in weights.items()},
            "config_used": {
                "r2_low": cfg.r2_low,
                "r2_high": cfg.r2_high,
                "win_rate_low": cfg.win_rate_low,
                "win_rate_high": cfg.win_rate_high,
                "sharpe_low": cfg.sharpe_low,
                "sharpe_high": cfg.sharpe_high,
                "gini_low": cfg.gini_low,
                "gini_high": cfg.gini_high,
                "trades_per_year": cfg.trades_per_year,
                "alpha": cfg.alpha,
                "clustering_buckets": cfg.clustering_buckets,
            },
            "config_descriptions": {
                k: _CONFIG_DESCRIPTIONS.get(k, "")
                for k in (
                    "r2_low",
                    "r2_high",
                    "win_rate_low",
                    "win_rate_high",
                    "sharpe_low",
                    "sharpe_high",
                    "gini_low",
                    "gini_high",
                    "trades_per_year",
                    "alpha",
                    "clustering_buckets",
                )
            },
        },
    }
