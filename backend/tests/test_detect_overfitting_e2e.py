"""
End-to-end tests for detect_overfitting() using real CSV trade data.

Two input formats are exercised:
  - Detailed list CSV  (one row per trade: date, symbol, pnl)
  - Summary dict CSV   (one row of aggregate stats; pnl synthesized from metrics)
"""

import csv
import io
import textwrap
from datetime import datetime, timedelta

from overfitting_detector import OverfittingConfig, detect_overfitting

# ---------------------------------------------------------------------------
# CSV fixtures
# ---------------------------------------------------------------------------

# 50 trades across 2023 — ~58 % win rate, realistic drawdowns, distributed dates
_HEALTHY_CSV = textwrap.dedent(
    """\
    date,symbol,pnl
    2023-01-03,AAPL,2.10
    2023-01-06,AAPL,-1.40
    2023-01-10,MSFT,1.85
    2023-01-13,MSFT,-1.20
    2023-01-18,GOOG,3.10
    2023-01-23,AAPL,-2.00
    2023-01-27,MSFT,1.50
    2023-02-02,GOOG,2.75
    2023-02-08,AAPL,-1.60
    2023-02-14,MSFT,1.95
    2023-02-17,GOOG,-0.80
    2023-02-22,AAPL,2.20
    2023-03-01,MSFT,-1.30
    2023-03-07,GOOG,1.70
    2023-03-14,AAPL,2.50
    2023-03-21,MSFT,-1.80
    2023-03-28,GOOG,1.40
    2023-04-04,AAPL,-1.10
    2023-04-11,MSFT,2.60
    2023-04-18,GOOG,-0.90
    2023-04-25,AAPL,1.85
    2023-05-02,MSFT,2.30
    2023-05-09,GOOG,-1.50
    2023-05-16,AAPL,1.65
    2023-05-23,MSFT,-2.10
    2023-05-30,GOOG,2.80
    2023-06-06,AAPL,-0.70
    2023-06-13,MSFT,1.75
    2023-06-20,GOOG,2.40
    2023-06-27,AAPL,-1.60
    2023-07-05,MSFT,2.00
    2023-07-12,GOOG,-1.40
    2023-07-19,AAPL,1.90
    2023-07-26,MSFT,-1.20
    2023-08-02,GOOG,2.15
    2023-08-09,AAPL,-0.95
    2023-08-16,MSFT,1.80
    2023-08-23,GOOG,2.35
    2023-08-30,AAPL,-1.70
    2023-09-06,MSFT,2.50
    2023-09-13,GOOG,-1.30
    2023-09-20,AAPL,1.60
    2023-09-27,MSFT,2.25
    2023-10-04,GOOG,-0.85
    2023-10-11,AAPL,1.95
    2023-10-18,MSFT,-1.55
    2023-10-25,GOOG,2.70
    2023-11-01,AAPL,1.35
    2023-11-08,MSFT,-1.00
    2023-11-15,GOOG,2.05
"""
)

# 50 trades — 90 % win rate, near-uniform gains, very smooth equity curve
_OVERFIT_CSV = textwrap.dedent(
    """\
    date,symbol,pnl
    2023-01-03,AAPL,1.00
    2023-01-04,AAPL,1.01
    2023-01-05,AAPL,1.00
    2023-01-06,AAPL,1.02
    2023-01-09,AAPL,1.00
    2023-01-10,AAPL,1.01
    2023-01-11,AAPL,1.00
    2023-01-12,AAPL,1.00
    2023-01-13,AAPL,-0.10
    2023-01-17,AAPL,1.00
    2023-01-18,AAPL,1.01
    2023-01-19,AAPL,1.00
    2023-01-20,AAPL,1.00
    2023-01-23,AAPL,1.01
    2023-01-24,AAPL,1.00
    2023-01-25,AAPL,1.00
    2023-01-26,AAPL,1.00
    2023-01-27,AAPL,-0.10
    2023-01-30,AAPL,1.00
    2023-01-31,AAPL,1.00
    2023-02-01,AAPL,1.00
    2023-02-02,AAPL,1.01
    2023-02-03,AAPL,1.00
    2023-02-06,AAPL,1.00
    2023-02-07,AAPL,1.01
    2023-02-08,AAPL,1.00
    2023-02-09,AAPL,1.00
    2023-02-10,AAPL,-0.10
    2023-02-13,AAPL,1.00
    2023-02-14,AAPL,1.00
    2023-02-15,AAPL,1.01
    2023-02-16,AAPL,1.00
    2023-02-17,AAPL,1.00
    2023-02-21,AAPL,1.00
    2023-02-22,AAPL,1.01
    2023-02-23,AAPL,1.00
    2023-02-24,AAPL,1.00
    2023-02-27,AAPL,-0.10
    2023-02-28,AAPL,1.00
    2023-03-01,AAPL,1.00
    2023-03-02,AAPL,1.01
    2023-03-03,AAPL,1.00
    2023-03-06,AAPL,1.00
    2023-03-07,AAPL,1.00
    2023-03-08,AAPL,1.01
    2023-03-09,AAPL,-0.10
    2023-03-10,AAPL,1.00
    2023-03-13,AAPL,1.00
    2023-03-14,AAPL,1.01
    2023-03-15,AAPL,1.00
"""
)

# 6 trades with an explicit cumulative equity column for override testing.
# The pnl series is jagged but the equity column is perfectly linear.
_EXPLICIT_EQUITY_CSV = textwrap.dedent(
    """\
    date,pnl,equity
    2023-01-03,1.5,10.0
    2023-01-05,-0.5,20.0
    2023-01-10,1.5,30.0
    2023-01-15,-0.5,40.0
    2023-01-20,1.5,50.0
    2023-01-25,-0.5,60.0
"""
)

# Summary-format CSVs (aggregate stats, one data row each)
_HEALTHY_SUMMARY_CSV = textwrap.dedent(
    """\
    initial_capital,final_balance,num_trades,win_rate,start_date,end_date
    10000,11820,50,0.58,2023-01-03,2023-11-15
"""
)

_SUSPICIOUS_SUMMARY_CSV = textwrap.dedent(
    """\
    initial_capital,final_balance,num_trades,win_rate,start_date,end_date
    10000,14750,50,0.94,2023-01-03,2023-03-15
"""
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_trade_csv(csv_str: str) -> tuple[list[float], list[str]]:
    """Parse a per-trade CSV with 'date' and 'pnl' columns."""
    reader = csv.DictReader(io.StringIO(csv_str.strip()))
    pnl_list, trade_dates = [], []
    for row in reader:
        pnl_list.append(float(row["pnl"]))
        trade_dates.append(row["date"].strip())
    return pnl_list, trade_dates


def _parse_summary_csv(csv_str: str) -> dict:
    """Parse a one-row summary CSV into a typed dict."""
    reader = csv.DictReader(io.StringIO(csv_str.strip()))
    rows = list(reader)
    assert len(rows) == 1, "Summary CSV must have exactly one data row"
    row = rows[0]
    return {
        "initial_capital": float(row["initial_capital"]),
        "final_balance": float(row["final_balance"]),
        "num_trades": int(row["num_trades"]),
        "win_rate": float(row["win_rate"]),
        "start_date": row["start_date"].strip(),
        "end_date": row["end_date"].strip(),
    }


def _synthetic_pnl_from_summary(summary: dict) -> tuple[list[float], list[str]]:
    """
    Build a per-trade pnl_list and evenly-spaced date list from a summary dict
    so that detect_overfitting() can be called with results that reflect the
    summary's aggregate metrics (win_rate, total_return, date range).
    """
    n = summary["num_trades"]
    win_rate = summary["win_rate"]
    total_return = summary["final_balance"] - summary["initial_capital"]
    wins = round(n * win_rate)
    losses = n - wins

    if wins > 0 and losses > 0:
        per_win = total_return / wins * 1.5
        per_loss = -(total_return / losses * 0.5)
    elif wins > 0:
        per_win, per_loss = total_return / wins, 0.0
    else:
        per_win, per_loss = 0.0, total_return / losses

    pnl_list = [per_win] * wins + [per_loss] * losses

    start = datetime.strptime(summary["start_date"], "%Y-%m-%d").date()
    end = datetime.strptime(summary["end_date"], "%Y-%m-%d").date()
    span = (end - start).days
    step = max(1, span // n)
    trade_dates = [(start + timedelta(days=i * step)).isoformat() for i in range(n)]

    return pnl_list, trade_dates


# ---------------------------------------------------------------------------
# Tests — detailed list CSV format (one row per trade)
# ---------------------------------------------------------------------------


class TestDetectOverfittingDetailedCsv:
    """detect_overfitting() fed from a per-trade CSV (detailed list format)."""

    def test_healthy_strategy_returns_complete_result(self):
        pnl, dates = _parse_trade_csv(_HEALTHY_CSV)
        result = detect_overfitting(pnl_list=pnl, trade_dates=dates)

        assert "overfitting_score" in result
        assert "risk_tier" in result
        assert "factor_scores" in result
        assert "breakdown_pct" in result
        assert "all_warnings" in result
        assert "metadata" in result

    def test_healthy_strategy_score_is_float_in_valid_range(self):
        pnl, dates = _parse_trade_csv(_HEALTHY_CSV)
        score = detect_overfitting(pnl_list=pnl, trade_dates=dates)["overfitting_score"]

        assert isinstance(score, float)
        assert 0.0 <= score <= 100.0

    def test_healthy_strategy_all_four_factor_scores_present(self):
        pnl, dates = _parse_trade_csv(_HEALTHY_CSV)
        factors = detect_overfitting(pnl_list=pnl, trade_dates=dates)["factor_scores"]

        assert set(factors.keys()) == {
            "equity_smoothness",
            "win_rate",
            "sharpe",
            "trade_clustering",
        }
        for factor_result in factors.values():
            assert "score" in factor_result
            assert 0.0 <= factor_result["score"] <= 100.0

    def test_healthy_strategy_risk_tier_is_not_critical(self):
        # A realistic 58 % win-rate strategy should not reach the HIGH/CRITICAL band.
        pnl, dates = _parse_trade_csv(_HEALTHY_CSV)
        tier = detect_overfitting(pnl_list=pnl, trade_dates=dates)["risk_tier"]

        assert "CRITICAL" not in tier and "HIGH" not in tier

    def test_healthy_strategy_metadata_trade_count_matches_csv(self):
        pnl, dates = _parse_trade_csv(_HEALTHY_CSV)
        result = detect_overfitting(pnl_list=pnl, trade_dates=dates)

        assert result["metadata"]["num_trades"] == len(pnl)

    def test_healthy_strategy_factor_scores_have_non_empty_interpretation(self):
        pnl, dates = _parse_trade_csv(_HEALTHY_CSV)
        factors = detect_overfitting(pnl_list=pnl, trade_dates=dates)["factor_scores"]

        for factor_result in factors.values():
            assert "interpretation" in factor_result
            assert isinstance(factor_result["interpretation"], str)
            assert len(factor_result["interpretation"]) > 0

    def test_overfit_strategy_scores_higher_than_healthy(self):
        healthy_pnl, healthy_dates = _parse_trade_csv(_HEALTHY_CSV)
        overfit_pnl, overfit_dates = _parse_trade_csv(_OVERFIT_CSV)

        healthy_score = detect_overfitting(
            pnl_list=healthy_pnl, trade_dates=healthy_dates
        )["overfitting_score"]
        overfit_score = detect_overfitting(
            pnl_list=overfit_pnl, trade_dates=overfit_dates
        )["overfitting_score"]

        assert overfit_score > healthy_score

    def test_overfit_strategy_win_rate_factor_is_elevated(self):
        pnl, dates = _parse_trade_csv(_OVERFIT_CSV)
        win_rate_score = detect_overfitting(pnl_list=pnl, trade_dates=dates)[
            "factor_scores"
        ]["win_rate"]["score"]

        assert win_rate_score > 0

    def test_overfit_strategy_equity_smoothness_is_flagged(self):
        pnl, dates = _parse_trade_csv(_OVERFIT_CSV)
        smoothness_score = detect_overfitting(pnl_list=pnl, trade_dates=dates)[
            "factor_scores"
        ]["equity_smoothness"]["score"]

        assert smoothness_score > 0

    def test_overfit_strategy_produces_warnings(self):
        pnl, dates = _parse_trade_csv(_OVERFIT_CSV)
        all_warnings = detect_overfitting(pnl_list=pnl, trade_dates=dates)[
            "all_warnings"
        ]

        assert len(all_warnings) > 0

    def test_clustering_factor_populated_only_when_dates_provided(self):
        pnl, dates = _parse_trade_csv(_HEALTHY_CSV)

        result_with = detect_overfitting(pnl_list=pnl, trade_dates=dates)
        result_without = detect_overfitting(pnl_list=pnl)

        assert result_with["factor_scores"]["trade_clustering"]["num_trades"] == len(
            dates
        )
        assert result_without["factor_scores"]["trade_clustering"]["num_trades"] == 0

    def test_breakdown_pct_components_sum_to_overfitting_score(self):
        pnl, dates = _parse_trade_csv(_HEALTHY_CSV)
        result = detect_overfitting(pnl_list=pnl, trade_dates=dates)

        breakdown_sum = sum(result["breakdown_pct"].values())
        assert abs(breakdown_sum - result["overfitting_score"]) < 0.1

    def test_weights_in_metadata_sum_to_one(self):
        pnl, dates = _parse_trade_csv(_HEALTHY_CSV)
        weights = detect_overfitting(pnl_list=pnl, trade_dates=dates)["metadata"][
            "weights_used"
        ]

        assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_win_rate_factor_wins_match_csv_positive_pnl_count(self):
        pnl, dates = _parse_trade_csv(_HEALTHY_CSV)
        expected_wins = sum(1 for p in pnl if p > 0)
        wins_reported = detect_overfitting(pnl_list=pnl, trade_dates=dates)[
            "factor_scores"
        ]["win_rate"]["wins"]

        assert wins_reported == expected_wins

    def test_sharpe_factor_exposes_annualised_and_per_trade_values(self):
        pnl, dates = _parse_trade_csv(_HEALTHY_CSV)
        sharpe_factor = detect_overfitting(pnl_list=pnl, trade_dates=dates)[
            "factor_scores"
        ]["sharpe"]

        assert "annualised_sharpe" in sharpe_factor
        assert "per_trade_sharpe" in sharpe_factor

    def test_explicit_equity_curve_overrides_pnl_reconstruction(self):
        """Passing equity_curve from the CSV takes precedence over reconstruction from pnl."""
        rows = list(csv.DictReader(io.StringIO(_EXPLICIT_EQUITY_CSV.strip())))
        pnl = [float(r["pnl"]) for r in rows]
        equity = [float(r["equity"]) for r in rows]

        # [10,20,30,40,50,60] is perfectly linear → R² = 1.0 → full smoothness score
        result_explicit = detect_overfitting(pnl_list=pnl, equity_curve=equity)
        # Reconstructed equity [1.5,1.0,2.5,2.0,3.5,3.0] is jagged → low R²
        result_implicit = detect_overfitting(pnl_list=pnl)

        explicit_r2 = result_explicit["factor_scores"]["equity_smoothness"]["r_squared"]
        implicit_r2 = result_implicit["factor_scores"]["equity_smoothness"]["r_squared"]

        assert explicit_r2 > implicit_r2


# ---------------------------------------------------------------------------
# Tests — summary dict CSV format (aggregate stats → synthetic pnl)
# ---------------------------------------------------------------------------


class TestDetectOverfittingSummaryDict:
    """
    detect_overfitting() fed from a summary-format CSV.
    pnl_list is synthesized via _synthetic_pnl_from_summary so that the
    aggregate metrics (num_trades, win_rate) are honoured exactly.
    """

    def test_healthy_summary_returns_complete_result(self):
        summary = _parse_summary_csv(_HEALTHY_SUMMARY_CSV)
        pnl, dates = _synthetic_pnl_from_summary(summary)
        result = detect_overfitting(pnl_list=pnl, trade_dates=dates)

        assert "overfitting_score" in result
        assert "risk_tier" in result
        assert "factor_scores" in result

    def test_healthy_summary_trade_count_matches_summary_field(self):
        summary = _parse_summary_csv(_HEALTHY_SUMMARY_CSV)
        pnl, dates = _synthetic_pnl_from_summary(summary)
        result = detect_overfitting(pnl_list=pnl, trade_dates=dates)

        assert result["metadata"]["num_trades"] == summary["num_trades"]

    def test_healthy_summary_score_is_in_valid_range(self):
        summary = _parse_summary_csv(_HEALTHY_SUMMARY_CSV)
        pnl, dates = _synthetic_pnl_from_summary(summary)
        score = detect_overfitting(pnl_list=pnl, trade_dates=dates)["overfitting_score"]

        assert 0.0 <= score <= 100.0

    def test_suspicious_summary_scores_higher_than_healthy(self):
        healthy_summary = _parse_summary_csv(_HEALTHY_SUMMARY_CSV)
        suspicious_summary = _parse_summary_csv(_SUSPICIOUS_SUMMARY_CSV)

        healthy_pnl, healthy_dates = _synthetic_pnl_from_summary(healthy_summary)
        suspicious_pnl, suspicious_dates = _synthetic_pnl_from_summary(
            suspicious_summary
        )

        healthy_score = detect_overfitting(
            pnl_list=healthy_pnl, trade_dates=healthy_dates
        )["overfitting_score"]
        suspicious_score = detect_overfitting(
            pnl_list=suspicious_pnl, trade_dates=suspicious_dates
        )["overfitting_score"]

        assert suspicious_score > healthy_score

    def test_suspicious_summary_win_rate_factor_reflects_summary_stat(self):
        """The win-rate factor must report the same win count as the synthesized pnl."""
        summary = _parse_summary_csv(_SUSPICIOUS_SUMMARY_CSV)
        pnl, dates = _synthetic_pnl_from_summary(summary)
        result = detect_overfitting(pnl_list=pnl, trade_dates=dates)

        expected_wins = round(summary["num_trades"] * summary["win_rate"])
        reported_wins = result["factor_scores"]["win_rate"]["wins"]

        assert reported_wins == expected_wins

    def test_suspicious_summary_win_rate_factor_has_warnings(self):
        summary = _parse_summary_csv(_SUSPICIOUS_SUMMARY_CSV)
        pnl, dates = _synthetic_pnl_from_summary(summary)
        wr_warnings = detect_overfitting(pnl_list=pnl, trade_dates=dates)[
            "factor_scores"
        ]["win_rate"]["warnings"]

        assert len(wr_warnings) > 0

    def test_summary_date_range_drives_clustering_trade_count(self):
        summary = _parse_summary_csv(_HEALTHY_SUMMARY_CSV)
        pnl, dates = _synthetic_pnl_from_summary(summary)
        clustering = detect_overfitting(pnl_list=pnl, trade_dates=dates)[
            "factor_scores"
        ]["trade_clustering"]

        assert clustering["num_trades"] == summary["num_trades"]
        assert clustering["num_buckets"] == 10  # default bucket count

    def test_all_warnings_is_a_list(self):
        summary = _parse_summary_csv(_HEALTHY_SUMMARY_CSV)
        pnl, dates = _synthetic_pnl_from_summary(summary)
        all_warnings = detect_overfitting(pnl_list=pnl, trade_dates=dates)[
            "all_warnings"
        ]

        assert isinstance(all_warnings, list)

    def test_all_factor_scores_expose_warnings_key(self):
        summary = _parse_summary_csv(_HEALTHY_SUMMARY_CSV)
        pnl, dates = _synthetic_pnl_from_summary(summary)
        factors = detect_overfitting(pnl_list=pnl, trade_dates=dates)["factor_scores"]

        for factor in factors.values():
            assert "warnings" in factor
            assert isinstance(factor["warnings"], list)

    def test_config_used_exposed_in_metadata(self):
        summary = _parse_summary_csv(_HEALTHY_SUMMARY_CSV)
        pnl, dates = _synthetic_pnl_from_summary(summary)
        cfg_used = detect_overfitting(pnl_list=pnl, trade_dates=dates)["metadata"][
            "config_used"
        ]

        for key in (
            "r2_low",
            "r2_high",
            "win_rate_low",
            "win_rate_high",
            "sharpe_low",
            "sharpe_high",
        ):
            assert key in cfg_used

    def test_stricter_win_rate_config_raises_score_for_moderate_win_rate(self):
        """
        Lowering win_rate_low catches a 58 % win rate that the default config ignores,
        producing a higher composite score.
        """
        summary = _parse_summary_csv(_HEALTHY_SUMMARY_CSV)
        pnl, dates = _synthetic_pnl_from_summary(summary)  # ~58 % win rate

        default_result = detect_overfitting(pnl_list=pnl, trade_dates=dates)
        # Default win_rate_low=0.60 → 58 % is below threshold → win-rate score = 0

        stricter_config = OverfittingConfig(win_rate_low=0.40, win_rate_high=0.65)
        stricter_result = detect_overfitting(
            pnl_list=pnl, trade_dates=dates, config=stricter_config
        )
        # Stricter win_rate_low=0.40 → 58 % is inside the suspicious band → win-rate score > 0

        assert (
            stricter_result["overfitting_score"] > default_result["overfitting_score"]
        )
