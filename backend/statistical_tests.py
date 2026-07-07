"""
statistical_tests.py
--------------------
Statistical significance layer that answers the key question:

  "Are these trading results genuinely better than random chance?"

Tests performed
---------------
1. One-sample t-test       – mean P&L vs zero (null: strategy ≈ random)
2. Bootstrapped CI         – 95 % confidence interval on mean return
3. Sharpe significance     – whether Sharpe ratio differs from 0
4. Win-rate binomial test  – whether win rate is above 50 % by chance
5. Minimum trade count     – guard against underpowered conclusions

Public API
----------
run_significance_tests(pnl_list, ...)  →  dict      ← main entry-point
plain_english_verdict(pnl_list, ...)   →  str       ← simple human-readable verdict
"""

from __future__ import annotations

import logging
import math
import random
from typing import Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------

DEFAULT_ALPHA: float = 0.05  # significance level (two-tailed)
DEFAULT_MIN_TRADES: int = 30  # minimum trade count for reliable inference
DEFAULT_BOOTSTRAP_ITERS: int = 10_000
DEFAULT_CI_LEVEL: float = 0.95


# ---------------------------------------------------------------------------
# Verdict constants (for import by tests and UI)
# ---------------------------------------------------------------------------

VERDICT_NOT_ENOUGH = "not enough trades to know yet"
VERDICT_REAL_EDGE = "your win rate looks like a real edge"

VERDICT_DESCRIPTIONS: dict[str, str] = {
    "SIGNIFICANT": (
        "Both the t-test and bootstrap confidence interval agree that your results "
        "are unlikely to be explained by luck alone. This is a positive signal, "
        "but keep validating on new data before trading live."
    ),
    "NOT_SIGNIFICANT": (
        "The tests could not confirm a genuine edge. Your results may still be "
        "real, but we cannot rule out random chance with the current data. "
        "More trades or a stronger strategy are needed."
    ),
    "INSUFFICIENT_DATA": (
        f"At least {DEFAULT_MIN_TRADES} trades are recommended for these tests to be "
        "reliable. Add more trade history and re-run the analysis."
    ),
}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _mean(data: list[float]) -> float:
    return sum(data) / len(data)


def _variance(data: list[float], ddof: int = 1) -> float:
    """Sample variance (ddof=1) or population variance (ddof=0)."""
    m = _mean(data)
    ss = sum((x - m) ** 2 for x in data)
    return ss / (len(data) - ddof)


def _std(data: list[float], ddof: int = 1) -> float:
    return math.sqrt(_variance(data, ddof))


def _t_cdf_approx(t: float, df: int) -> float:
    """
    Approximate CDF of the Student-t distribution using the regularised
    incomplete beta function identity.  Accuracy is sufficient for
    financial significance testing (error < 1e-6 for df >= 2).

    Returns P(T <= t) for t in (-inf, +inf).
    """
    x = df / (df + t * t)
    # regularised incomplete beta  I_x(df/2, 1/2)
    rib = _regularised_incomplete_beta(x, df / 2.0, 0.5)
    p_one_tail = rib / 2.0
    return p_one_tail if t < 0 else 1.0 - p_one_tail


def _regularised_incomplete_beta(x: float, a: float, b: float) -> float:
    """
    Regularised incomplete beta function I_x(a, b) via continued-fraction
    expansion (Lentz algorithm).  Used only for the t-distribution CDF.
    """
    if x < 0.0 or x > 1.0:
        raise ValueError(f"x={x} out of [0, 1]")
    if x == 0.0:
        return 0.0
    if x == 1.0:
        return 1.0

    # Use symmetry relation when x > (a+1)/(a+b+2) for faster convergence
    if x > (a + 1.0) / (a + b + 2.0):
        return 1.0 - _regularised_incomplete_beta(1.0 - x, b, a)

    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1.0 - x) * b - lbeta) / a

    # Lentz continued-fraction
    TINY = 1e-30
    MAX_ITER = 200
    EPS = 3e-7

    f = TINY
    C = f
    D = 0.0

    for m in range(MAX_ITER):
        for step in range(2):
            if step == 0:
                if m == 0:
                    numerator = 1.0
                else:
                    numerator = m * (b - m) * x / ((a + 2 * m - 1) * (a + 2 * m))
            else:
                numerator = -(a + m) * (a + b + m) * x / ((a + 2 * m) * (a + 2 * m + 1))

            D = 1.0 + numerator * D
            if abs(D) < TINY:
                D = TINY
            D = 1.0 / D

            C = 1.0 + numerator / C
            if abs(C) < TINY:
                C = TINY

            delta = C * D
            f *= delta

        if abs(delta - 1.0) < EPS:
            break

    return front * f


def _two_tail_p_value(t_stat: float, df: int) -> float:
    """Two-tailed p-value for a one-sample t-test."""
    cdf = _t_cdf_approx(abs(t_stat), df)
    return 2.0 * (1.0 - cdf)


def _normal_cdf(z: float) -> float:
    """Standard-normal CDF via math.erfc."""
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def _binomial_p_value(k: int, n: int, p0: float = 0.5) -> float:
    """
    Exact two-tailed p-value for the binomial test H0: win_rate == p0.
    Uses normal approximation with continuity correction for n > 50,
    exact sum for n <= 50.
    """
    if n <= 50:
        # Exact: sum P(X=i) for all i where P(X=i) <= P(X=k)
        prob_k = _binom_pmf(k, n, p0)
        p_val = sum(
            _binom_pmf(i, n, p0)
            for i in range(n + 1)
            if _binom_pmf(i, n, p0) <= prob_k + 1e-10
        )
        return min(p_val, 1.0)
    else:
        # Normal approximation with continuity correction
        mu = n * p0
        sigma = math.sqrt(n * p0 * (1 - p0))
        z = (abs(k - mu) - 0.5) / sigma
        return 2.0 * (1.0 - _normal_cdf(z))


def _binom_pmf(k: int, n: int, p: float) -> float:
    """Binomial probability mass function."""
    log_coeff = math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)
    if p == 0.0:
        return 1.0 if k == 0 else 0.0
    if p == 1.0:
        return 1.0 if k == n else 0.0
    log_prob = log_coeff + k * math.log(p) + (n - k) * math.log(1.0 - p)
    return math.exp(log_prob)


def _percentile(data: list[float], pct: float) -> float:
    """Linear-interpolation percentile (matches numpy default)."""
    if not data:
        raise ValueError("Empty data")
    sorted_data = sorted(data)
    n = len(sorted_data)
    idx = pct / 100.0 * (n - 1)
    lo = int(idx)
    hi = lo + 1
    if hi >= n:
        return sorted_data[-1]
    frac = idx - lo
    return sorted_data[lo] * (1 - frac) + sorted_data[hi] * frac


# ---------------------------------------------------------------------------
# Individual tests
# ---------------------------------------------------------------------------


def check_min_trade_count(
    n: int,
    min_trades: int = DEFAULT_MIN_TRADES,
) -> dict:
    """
    Guard check: is the sample large enough for reliable inference?
    """
    met = n >= min_trades
    warning: str | None = None
    if not met:
        warning = (
            f"Only {n} trades recorded; at least {min_trades} are recommended "
            f"for reliable statistical inference.  Results may be spurious."
        )
    return {
        "n": n,
        "min_required": min_trades,
        "met": met,
        "warning": warning,
    }


def ttest_vs_zero(
    pnl_list: list[float],
    alpha: float = DEFAULT_ALPHA,
) -> dict:
    """
    One-sample t-test: H0: mean(P&L) == 0.

    A significant result means the strategy's mean P&L is
    statistically distinguishable from zero (i.e. from random coin-flip
    trading with zero expected value).
    """
    n = len(pnl_list)
    if n < 2:
        return {
            "t_statistic": None,
            "p_value": None,
            "significant": False,
            "interpretation": "Insufficient data for t-test (need at least 2 trades).",
        }

    mean_pnl = _mean(pnl_list)
    se = _std(pnl_list, ddof=1) / math.sqrt(n)

    if se == 0.0:
        return {
            "t_statistic": None,
            "p_value": None,
            "significant": False,
            "interpretation": "All P&L values are identical — t-test undefined.",
        }

    t_stat = mean_pnl / se
    p_val = _two_tail_p_value(t_stat, df=n - 1)
    significant = p_val < alpha

    direction = "positive" if mean_pnl > 0 else "negative"
    interp = f"Mean P&L={mean_pnl:.4f}, t={t_stat:.3f}, p={p_val:.4f}. " + (
        f"Result IS significant (p < {alpha}): strategy has a {direction} edge vs random."
        if significant
        else f"Result is NOT significant (p >= {alpha}): cannot rule out random chance."
    )

    return {
        "t_statistic": round(t_stat, 6),
        "p_value": round(p_val, 6),
        "significant": significant,
        "interpretation": interp,
    }


def bootstrap_confidence_interval(
    pnl_list: list[float],
    ci_level: float = DEFAULT_CI_LEVEL,
    n_iterations: int = DEFAULT_BOOTSTRAP_ITERS,
    seed: int = 42,
) -> dict:
    """
    Non-parametric bootstrap confidence interval on mean P&L.

    Does not assume normality — robust for fat-tailed return distributions.
    """
    n = len(pnl_list)
    if n < 2:
        return {
            "mean": None,
            "ci_lower": None,
            "ci_upper": None,
            "ci_excludes_zero": False,
            "interpretation": "Insufficient data for bootstrap CI (need at least 2 trades).",
        }

    rng = random.Random(seed)
    boot_means: list[float] = []
    for _ in range(n_iterations):
        sample = [rng.choice(pnl_list) for _ in range(n)]
        boot_means.append(_mean(sample))

    alpha = 1.0 - ci_level
    lower_pct = (alpha / 2.0) * 100.0
    upper_pct = (1.0 - alpha / 2.0) * 100.0

    ci_lower = _percentile(boot_means, lower_pct)
    ci_upper = _percentile(boot_means, upper_pct)
    mean_pnl = _mean(pnl_list)
    excludes_zero = ci_lower > 0.0 or ci_upper < 0.0

    pct_label = int(ci_level * 100)
    interp = (
        f"{pct_label}% bootstrap CI: [{ci_lower:.4f}, {ci_upper:.4f}] "
        f"around mean={mean_pnl:.4f}. "
        + (
            "CI excludes zero — consistent with a real edge."
            if excludes_zero
            else "CI includes zero — edge is not reliably distinguished from chance."
        )
    )

    return {
        "mean": round(mean_pnl, 6),
        "ci_lower": round(ci_lower, 6),
        "ci_upper": round(ci_upper, 6),
        "ci_excludes_zero": excludes_zero,
        "interpretation": interp,
    }


def sharpe_significance(
    pnl_list: list[float],
    risk_free_per_trade: float = 0.0,
    alpha: float = DEFAULT_ALPHA,
) -> dict:
    """
    Test whether the annualised Sharpe ratio is significantly > 0.

    Uses the asymptotic t-statistic:  t = SR * sqrt(n)
    (Lo, 2002 — valid for i.i.d. returns).
    """
    n = len(pnl_list)
    if n < 2:
        return {
            "sharpe_ratio": None,
            "t_statistic": None,
            "p_value": None,
            "significant": False,
            "interpretation": "Insufficient data for Sharpe significance test.",
        }

    excess = [p - risk_free_per_trade for p in pnl_list]
    mean_excess = _mean(excess)
    std_excess = _std(excess, ddof=1)

    if std_excess == 0.0:
        return {
            "sharpe_ratio": None,
            "t_statistic": None,
            "p_value": None,
            "significant": False,
            "interpretation": "Zero standard deviation — Sharpe ratio undefined.",
        }

    sharpe = mean_excess / std_excess  # per-trade Sharpe
    t_stat = sharpe * math.sqrt(n)  # significance statistic
    p_val = _two_tail_p_value(t_stat, df=n - 1)
    significant = p_val < alpha

    interp = f"Per-trade Sharpe={sharpe:.4f}, t={t_stat:.3f}, p={p_val:.4f}. " + (
        f"Sharpe IS significantly different from zero (p < {alpha})."
        if significant
        else f"Sharpe is NOT significantly different from zero (p >= {alpha})."
    )

    return {
        "sharpe_ratio": round(sharpe, 6),
        "t_statistic": round(t_stat, 6),
        "p_value": round(p_val, 6),
        "significant": significant,
        "interpretation": interp,
    }


def winrate_binomial_test(
    pnl_list: list[float],
    null_win_rate: float = 0.5,
    alpha: float = DEFAULT_ALPHA,
) -> dict:
    """
    Binomial test: H0: win_rate == null_win_rate (default 0.50).

    Tests whether the observed win rate could arise by chance from a
    coin-flip process (50/50 random trades).
    """
    # Only count trades with nonzero P&L
    nonzero_pnl = [p for p in pnl_list if p != 0]
    n = len(nonzero_pnl)
    if n < 1:
        return {
            "win_rate": None,
            "wins": 0,
            "losses": 0,
            "p_value": None,
            "significant": False,
            "interpretation": "No nonzero-P&L trades provided (all breakeven or empty).",
        }

    wins = sum(1 for p in nonzero_pnl if p > 0)
    losses = n - wins
    win_rate = wins / n
    p_val = _binomial_p_value(wins, n, null_win_rate)
    significant = p_val < alpha

    direction = "above" if win_rate > null_win_rate else "below"
    interp = (
        f"Win rate={win_rate:.2%} ({wins}W / {losses}L), "
        f"p={p_val:.4f} vs H0={null_win_rate:.0%}. "
        + (
            f"Result IS significant: win rate is {direction} chance level."
            if significant
            else "Win rate is NOT significantly different from chance."
        )
    )

    return {
        "win_rate": round(win_rate, 6),
        "wins": wins,
        "losses": losses,
        "p_value": round(p_val, 6),
        "significant": significant,
        "interpretation": interp,
    }


# ---------------------------------------------------------------------------
# Main entry-point
# ---------------------------------------------------------------------------


def run_significance_tests(
    pnl_list: Sequence[float],
    alpha: float = DEFAULT_ALPHA,
    min_trades: int = DEFAULT_MIN_TRADES,
    ci_level: float = DEFAULT_CI_LEVEL,
    bootstrap_iters: int = DEFAULT_BOOTSTRAP_ITERS,
    bootstrap_seed: int = 42,
    risk_free_per_trade: float = 0.0,
) -> dict:
    """
    Run the full statistical significance battery on a trade P&L list.

    Parameters
    ----------
    pnl_list            : list[float]  – per-trade P&L (required)
    alpha               : float        – significance level (default 0.05)
    min_trades          : int          – minimum recommended trade count
    ci_level            : float        – bootstrap CI confidence level
    bootstrap_iters     : int          – bootstrap resampling iterations
    bootstrap_seed      : int          – RNG seed for reproducibility
    risk_free_per_trade : float        – per-trade risk-free return

    Returns
    -------
    dict — see module docstring for full structure.
    """
    pnl: list[float] = [float(x) for x in pnl_list]
    n = len(pnl)
    warnings: list[str] = []

    # --- 0. minimum trade count check ---
    count_check = check_min_trade_count(n, min_trades)
    if count_check["warning"]:
        warnings.append(count_check["warning"])

    if n < 2:
        return {
            "verdict": "INSUFFICIENT_DATA",
            "verdict_description": VERDICT_DESCRIPTIONS["INSUFFICIENT_DATA"],
            "confidence_level": ci_level,
            "summary": "Not enough trades to run any significance test (minimum 2 required).",
            "trade_count": n,
            "min_trade_count_met": False,
            "min_trade_count_description": (
                f"At least {min_trades} trades are needed so that statistical patterns "
                "are likely to hold up — smaller samples are too easily distorted by a "
                "few lucky or unlucky trades."
            ),
            "ttest": ttest_vs_zero(pnl, alpha),
            "bootstrap_ci": bootstrap_confidence_interval(
                pnl, ci_level, bootstrap_iters, bootstrap_seed
            ),
            "sharpe": sharpe_significance(pnl, risk_free_per_trade, alpha),
            "winrate": winrate_binomial_test(pnl, 0.5, alpha),
            "warnings": warnings,
        }

    # --- 1. individual tests ---
    tt = ttest_vs_zero(pnl, alpha)
    bci = bootstrap_confidence_interval(pnl, ci_level, bootstrap_iters, bootstrap_seed)
    sr = sharpe_significance(pnl, risk_free_per_trade, alpha)
    wr = winrate_binomial_test(pnl, 0.5, alpha)

    # --- 2. overall verdict ---
    # "SIGNIFICANT" requires BOTH the t-test AND the bootstrap CI to agree.
    # The Sharpe and win-rate tests are corroborating evidence.
    ttest_sig = tt.get("significant", False)
    ci_sig = bci.get("ci_excludes_zero", False)
    sharpe_sig = sr.get("significant", False)
    winrate_sig = wr.get("significant", False)

    tests_passed = sum([ttest_sig, ci_sig, sharpe_sig, winrate_sig])

    if not count_check["met"]:
        verdict = "INSUFFICIENT_DATA"
        summary = (
            f"Only {n} trades — below the {min_trades}-trade threshold. "
            f"Passed {tests_passed}/4 tests, but results are unreliable."
        )
    elif ttest_sig and ci_sig:
        verdict = "SIGNIFICANT"
        summary = (
            f"SIGNIFICANT edge detected at {int(ci_level * 100)}% confidence. "
            f"Passed {tests_passed}/4 tests (t-test + bootstrap CI both confirm). "
            f"Strategy mean P&L is unlikely due to chance (α={alpha})."
        )
    elif tests_passed >= 2:
        verdict = "NOT_SIGNIFICANT"
        summary = (
            f"Borderline result: passed {tests_passed}/4 tests, but t-test and "
            f"bootstrap CI do not both confirm significance. "
            f"More data or a stronger edge is needed."
        )
    else:
        verdict = "NOT_SIGNIFICANT"
        summary = (
            f"No significant edge detected. Passed {tests_passed}/4 tests. "
            f"Results are consistent with random chance at α={alpha}."
        )

    # --- 3. extra warnings ---
    mean_pnl = _mean(pnl)
    if mean_pnl < 0:
        warnings.append("Mean P&L is negative — strategy is losing money on average.")

    try:
        sk = _skewness(pnl)
        if abs(sk) > 2.0:
            warnings.append(
                f"High skewness ({sk:.2f}): return distribution is heavily skewed. "
                f"T-test normality assumption may be violated; bootstrap CI is more reliable."
            )
    except Exception:
        pass

    return {
        "verdict": verdict,
        "verdict_description": VERDICT_DESCRIPTIONS.get(verdict, ""),
        "confidence_level": ci_level,
        "summary": summary,
        "trade_count": n,
        "min_trade_count_met": count_check["met"],
        "min_trade_count_description": (
            f"At least {min_trades} trades are needed so that statistical patterns "
            "are likely to hold up — smaller samples are too easily distorted by a "
            "few lucky or unlucky trades."
        ),
        "ttest": tt,
        "bootstrap_ci": bci,
        "sharpe": sr,
        "winrate": wr,
        "warnings": warnings,
    }


def plain_english_verdict(
    pnl_list: Sequence[float],
    alpha: float = DEFAULT_ALPHA,
    min_trades: int = DEFAULT_MIN_TRADES,
    **kwargs,
) -> str:
    """
    Returns a plain-English verdict on whether the strategy shows a real edge.

    "not enough trades to know yet"        — too few trades, or no significant edge
    "your win rate looks like a real edge" — t-test and bootstrap CI both confirm significance
    """
    result = run_significance_tests(
        pnl_list, alpha=alpha, min_trades=min_trades, **kwargs
    )
    if result["verdict"] == "SIGNIFICANT":
        return VERDICT_REAL_EDGE
    return VERDICT_NOT_ENOUGH


def _skewness(data: list[float]) -> float:
    """Sample skewness (Fisher-Pearson standardised coefficient)."""
    n = len(data)
    if n < 3:
        return 0.0
    m = _mean(data)
    s = _std(data, ddof=1)
    if s == 0:
        return 0.0
    return (sum((x - m) ** 3 for x in data) / n) / (s**3)


# ---------------------------------------------------------------------------
# CLI smoke-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    # --- Example 1: clearly profitable strategy ---
    winning_trades = [
        12.5,
        8.3,
        -3.1,
        15.2,
        9.8,
        -2.4,
        11.0,
        7.6,
        -1.8,
        14.3,
        10.5,
        6.2,
        -4.0,
        13.1,
        8.9,
        -2.9,
        12.0,
        9.3,
        -3.5,
        11.7,
        7.8,
        -1.5,
        14.9,
        10.2,
        8.1,
        -2.2,
        13.5,
        9.7,
        -3.8,
        12.3,
        11.1,
        6.9,
        -2.6,
        15.0,
        8.5,
    ]

    print("=" * 60)
    print("EXAMPLE 1 — Consistently profitable strategy")
    print("=" * 60)
    result = run_significance_tests(winning_trades)
    print(json.dumps(result, indent=2))

    # --- Example 2: random noise ---
    rng = random.Random(99)
    noise_trades = [rng.gauss(0, 10) for _ in range(35)]

    print("\n" + "=" * 60)
    print("EXAMPLE 2 — Random noise (should NOT be significant)")
    print("=" * 60)
    result2 = run_significance_tests(noise_trades)
    print(json.dumps(result2, indent=2))

    # --- Example 3: too few trades ---
    tiny = [5.0, -2.0, 8.0, 3.0, -1.0]
    print("\n" + "=" * 60)
    print("EXAMPLE 3 — Insufficient trade count (5 trades)")
    print("=" * 60)
    result3 = run_significance_tests(tiny)
    print(json.dumps(result3, indent=2))
